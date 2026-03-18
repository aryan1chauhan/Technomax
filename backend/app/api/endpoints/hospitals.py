from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.db.database import get_db
from app.db.models import Hospital, Availability, User
from app.schemas.hospital import HospitalOut, AvailabilityUpdate
from app.core.security import get_current_user

router = APIRouter(prefix="/api/hospitals")

@router.get("/", response_model=list[HospitalOut])
def get_hospitals(db: Session = Depends(get_db)):
    hospitals = db.query(Hospital).all()
    result = []
    
    for hospital in hospitals:
        availability = db.query(Availability)\
            .filter(Availability.hospital_id == hospital.id)\
            .order_by(Availability.updated_at.desc())\
            .first()
            
        hospital_dict = {
            "id": hospital.id,
            "name": hospital.name,
            "address": hospital.address,
            "lat": hospital.lat,
            "lng": hospital.lng,
            "availability": availability
        }
        result.append(hospital_dict)
        
    return result

@router.put("/{hospital_id}/availability")
def update_availability(
    hospital_id: int, 
    availability_in: AvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "hospital":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hospital accounts can update availability"
        )
        
    availability = db.query(Availability).filter(Availability.hospital_id == hospital_id).first()
    
    if availability:
        availability.beds = availability_in.beds
        availability.icu = availability_in.icu
        availability.doctors = availability_in.doctors
        availability.equipment = availability_in.equipment
        availability.accepting = availability_in.accepting
        availability.updated_at = datetime.now(timezone.utc)
    else:
        new_availability = Availability(
            hospital_id=hospital_id,
            beds=availability_in.beds,
            icu=availability_in.icu,
            doctors=availability_in.doctors,
            equipment=availability_in.equipment,
            accepting=availability_in.accepting,
            updated_at=datetime.now(timezone.utc)
        )
        db.add(new_availability)
        
    db.commit()
    
    return {"message": "Availability updated successfully"}
