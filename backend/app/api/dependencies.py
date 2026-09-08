from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.auth import Principal, get_current_principal
from app.db.session import get_session

SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]

__all__ = ["PrincipalDep", "SessionDep"]
