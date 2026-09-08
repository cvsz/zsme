from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.exceptions import HTTPException

from app.api.dependencies import DashboardReadDep, SessionDep
from app.domains.dashboard.schemas import DashboardSummary
from app.domains.dashboard.service import DashboardDomainError, dashboard_summary

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    principal: DashboardReadDep,
    db: SessionDep,
    as_of: date | None = None,
) -> DashboardSummary:
    try:
        return dashboard_summary(db, principal, as_of)
    except DashboardDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


__all__ = ["router"]
