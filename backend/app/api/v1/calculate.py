"""Deterministic calculation endpoints (Constitution §18)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import CalculationRequest, CalculationResponse
from app.services.calculation import CALCULATORS, run_calculation

router = APIRouter(prefix="/v1/calculate", tags=["calculation"])


@router.get("/types")
def calculation_types(user: User = Depends(get_current_user)):
    return {"available": sorted(CALCULATORS.keys())}


@router.post("/{calc_type}", response_model=CalculationResponse)
def calculate(
    calc_type: str,
    payload: CalculationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if calc_type not in CALCULATORS:
        raise HTTPException(status_code=404, detail=f"Unknown calculation type: {calc_type}")
    try:
        result = run_calculation(calc_type, payload.params)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid parameters: {exc}")
    return CalculationResponse(calc_type=calc_type, result=result)
