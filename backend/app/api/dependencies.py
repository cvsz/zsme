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

__all__ = [
    "OrganizationReadDep",
    "OrganizationWriteDep",
    "ApReadDep",
    "ApWriteDep",
    "ArReadDep",
    "ArWriteDep",
    "PartnerReadDep",
    "PartnerWriteDep",
    "PrincipalDep",
    "SessionDep",
]
