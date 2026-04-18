"""Replay API route for debugging and decision introspection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.replay_service import replay_case


router = APIRouter()


@router.get("/replay/{case_id}")
async def replay(case_id: str) -> dict:
    result = await replay_case(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return result

