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

__all__ = [
    "OrganizationReadDep",
    "OrganizationWriteDep",
    "PartnerReadDep",
    "PartnerWriteDep",
    "PrincipalDep",
    "SessionDep",
]
