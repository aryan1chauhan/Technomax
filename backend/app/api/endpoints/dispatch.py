from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Hospital, Availability, Case, User
from app.schemas.dispatch import DispatchRequest, DispatchResponse
from app.core.security import get_current_user
from app.engine.ml_scorer import predict_best_hospital

router = APIRouter(prefix="/api/dispatch")

@router.post("/", response_model=DispatchResponse)
def dispatch_ambulance(
    request: DispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ambulance":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance accounts can dispatch"
        )
        
    hospitals = db.query(Hospital).all()
    hospital_dicts = []
    
    for hospital in hospitals:
        availability = db.query(Availability)\
            .filter(Availability.hospital_id == hospital.id)\
            .order_by(Availability.updated_at.desc())\
            .first()
            
        if not availability:
            continue
            
        hospital_dict = {
            "id": hospital.id,
            "name": hospital.name,
            "address": hospital.address,
            "lat": hospital.lat,
            "lng": hospital.lng,
            "beds": availability.beds,
            "icu": availability.icu,
            "doctors": availability.doctors,
            "equipment": availability.equipment,
            "accepting": availability.accepting
        }
        hospital_dicts.append(hospital_dict)
        
    result = predict_best_hospital(
        hospitals=hospital_dicts,
        equipment_needed=request.equipment_needed,
        ambulance_lat=request.ambulance_lat,
        ambulance_lng=request.ambulance_lng,
        condition=request.condition
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No suitable hospital found"
        )
        
    new_case = Case(
        user_id=current_user.id,
        condition=request.condition,
        equipment_needed=request.equipment_needed,
        ambulance_lat=request.ambulance_lat,
        ambulance_lng=request.ambulance_lng,
        assigned_hospital_id=result["id"],
        final_score=result["final_score"],
        distance_km=result["distance_km"],
        eta_minutes=result["eta_minutes"]
    )
    
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    
    return DispatchResponse(
        case_id=new_case.id,
        hospital_id=result["id"],
        hospital_name=result["name"],
        address=result["address"],
        final_score=result["final_score"],
        confidence=result.get("confidence", 0.0),
        distance_km=result["distance_km"],
        eta_minutes=result["eta_minutes"],
        beds_available=result["beds"],
        equipment_matched=result["equipment_matched"],
        equipment_missing=result["equipment_missing"],
        lat=result["lat"],
        lng=result["lng"],
        ml_reasoning=result.get("ml_reasoning", [])
    )
