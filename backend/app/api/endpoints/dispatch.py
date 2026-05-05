"""
dispatch.py — Core endpoint for the MediRoute Dispatch ML Pipeline.

Refactored to offload business logic to dispatch_service.py.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.dispatch import DispatchRequest, DispatchResponse
from app.services.dispatch_service import execute_dispatch

router = APIRouter(prefix="/api/dispatch")

# Keep runtime references patchable in tests via app.api.endpoints.dispatch.*
STABILIZATION_DELAY_MINUTES = 18.0


@router.post("/", response_model=DispatchResponse, tags=["Dispatch ML"])
async def dispatch_ambulance(
    dispatch_request: DispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DispatchResponse:
    """
    Finds the optimal destination(s) using the multi-stage ML/constraint dispatch engine.
    For critical cases, uses the stabilize-first decision model.
    Records the decision and deduplicates beds atomically.
    """
    return await execute_dispatch(dispatch_request=dispatch_request, db=db, current_user=current_user)
