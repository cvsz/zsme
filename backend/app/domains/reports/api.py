from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.exceptions import HTTPException

from app.api.dependencies import ReportsReadDep, SessionDep
from app.domains.reports.schemas import (
    AgedReport,
    BalanceSheetReport,
    GeneralLedgerReport,
    ProfitLossReport,
    TrialBalanceReport,
)
from app.domains.reports.service import (
    ReportDomainError,
    aged_report,
    balance_sheet,
    general_ledger,
    profit_loss,
    trial_balance,
)

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


@router.get("/profit-loss", response_model=ProfitLossReport)
def get_profit_loss(
    principal: ReportsReadDep,
    db: SessionDep,
    from_date: date,
    to_date: date,
) -> ProfitLossReport:
    try:
        return profit_loss(db, principal, from_date, to_date)
    except ReportDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/balance-sheet", response_model=BalanceSheetReport)
def get_balance_sheet(
    principal: ReportsReadDep,
    db: SessionDep,
    as_of: date,
) -> BalanceSheetReport:
    try:
        return balance_sheet(db, principal, as_of)
    except ReportDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/general-ledger", response_model=GeneralLedgerReport)
def get_general_ledger(
    principal: ReportsReadDep,
    db: SessionDep,
    from_date: date,
    to_date: date,
) -> GeneralLedgerReport:
    try:
        return general_ledger(db, principal, from_date, to_date)
    except ReportDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/aged-receivable", response_model=AgedReport)
def get_aged_receivable(
    principal: ReportsReadDep,
    db: SessionDep,
    as_of: date,
) -> AgedReport:
    try:
        return aged_report(db, principal, as_of, "sales_invoice")
    except ReportDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/aged-payable", response_model=AgedReport)
def get_aged_payable(
    principal: ReportsReadDep,
    db: SessionDep,
    as_of: date,
) -> AgedReport:
    try:
        return aged_report(db, principal, as_of, "vendor_bill")
    except ReportDomainError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


__all__ = ["router"]
