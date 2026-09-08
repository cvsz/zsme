from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.exceptions import HTTPException

from app.api.dependencies import ReportsReadDep, SessionDep
from app.domains.reports.schemas import TrialBalanceReport
from app.domains.reports.service import ReportDomainError, trial_balance

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("/trial-balance", response_model=TrialBalanceReport)
def get_trial_balance(
    principal: ReportsReadDep,
    db: SessionDep,
    from_date: date,
    to_date: date,
) -> TrialBalanceReport:
    try:
        return trial_balance(db, principal, from_date, to_date)
    except ReportDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


__all__ = ["router"]
