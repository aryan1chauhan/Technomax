from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Case, User
from app.schemas.dispatch import CaseOut
from app.core.security import get_current_user

router = APIRouter(prefix="/api/cases")

@router.get("/", response_model=list[CaseOut])
def get_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cases = db.query(Case)\
        .filter(Case.user_id == current_user.id)\
        .order_by(Case.created_at.desc())\
        .all()
        
    return cases

@router.get("/hospital")
def get_hospital_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "hospital":
        raise HTTPException(status_code=403, detail="Not a hospital account")
    
    # Get cases assigned to this user's hospital
    cases = db.query(Case)\
        .filter(Case.assigned_hospital_id == current_user.hospital_id)\
        .order_by(Case.created_at.desc())\
        .all()
    
    return cases
