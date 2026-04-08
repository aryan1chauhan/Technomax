from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from app.db.database import get_db
from app.db.models import Hospital, Availability, User
from app.schemas.hospital import HospitalOut, AvailabilityUpdate
from app.core.security import get_current_user

router = APIRouter(prefix="/api/hospitals")

@router.get("/", response_model=list[HospitalOut])
def get_hospitals(db: Session = Depends(get_db)):
    # FIX: Single JOIN query instead of N+1 (was 189 queries, now 1)
    # Subquery: get the latest availability record per hospital
    latest_avail = db.query(
        Availability.hospital_id,
        func.max(Availability.updated_at).label("max_updated")
    ).group_by(Availability.hospital_id).subquery()
    
    rows = db.query(Hospital, Availability).outerjoin(
        latest_avail,
        Hospital.id == latest_avail.c.hospital_id
    ).outerjoin(
        Availability,
        (Availability.hospital_id == latest_avail.c.hospital_id) &
        (Availability.updated_at == latest_avail.c.max_updated)
    ).all()
    
    result = []
    for hospital, availability in rows:
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
    
    # SECURITY: Prevent IDOR — hospital can only update its own availability
    if hospital_id != current_user.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own hospital"
        )
        
    availability = db.query(Availability).filter(Availability.hospital_id == hospital_id).first()
    
    if availability:
        if availability_in.beds is not None:
            availability.beds = availability_in.beds
        if availability_in.icu is not None:
            availability.icu = availability_in.icu
        if availability_in.doctors is not None:
            availability.doctors = availability_in.doctors
        if availability_in.equipment is not None:
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
