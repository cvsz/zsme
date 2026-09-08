from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.auth import Principal, get_current_principal, require_permission
from app.db.session import get_session

SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
OrganizationReadDep = Annotated[Principal, Depends(require_permission("organization:read"))]
OrganizationWriteDep = Annotated[Principal, Depends(require_permission("organization:write"))]
PartnerReadDep = Annotated[Principal, Depends(require_permission("partner:read"))]
PartnerWriteDep = Annotated[Principal, Depends(require_permission("partner:write"))]
ArReadDep = Annotated[Principal, Depends(require_permission("ar:read"))]
ArWriteDep = Annotated[Principal, Depends(require_permission("ar:write"))]
ApReadDep = Annotated[Principal, Depends(require_permission("ap:read"))]
ApWriteDep = Annotated[Principal, Depends(require_permission("ap:write"))]
AccountingReadDep = Annotated[Principal, Depends(require_permission("accounting:read"))]
AccountingWriteDep = Annotated[Principal, Depends(require_permission("accounting:write"))]
ReportsReadDep = Annotated[Principal, Depends(require_permission("reports:read"))]
TaxReadDep = Annotated[Principal, Depends(require_permission("tax:read"))]
TaxWriteDep = Annotated[Principal, Depends(require_permission("tax:write"))]
BankingReadDep = Annotated[Principal, Depends(require_permission("banking:read"))]
BankingWriteDep = Annotated[Principal, Depends(require_permission("banking:write"))]
AuditReadDep = Annotated[Principal, Depends(require_permission("audit:read"))]

__all__ = [
    "OrganizationReadDep",
    "OrganizationWriteDep",
    "ApReadDep",
    "ApWriteDep",
    "AccountingReadDep",
    "AccountingWriteDep",
    "ReportsReadDep",
    "TaxReadDep",
    "TaxWriteDep",
    "BankingReadDep",
    "BankingWriteDep",
    "AuditReadDep",
    "ArReadDep",
    "ArWriteDep",
    "PartnerReadDep",
    "PartnerWriteDep",
    "PrincipalDep",
    "SessionDep",
]
