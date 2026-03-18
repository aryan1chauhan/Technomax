from fastapi import APIRouter, Depends
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
