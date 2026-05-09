"""
VYAS v2.0 — Auth Dependencies
================================
FastAPI dependency functions for authentication.
Separated from auth.py to allow clean imports across routers.

v2.0:
  - get_current_user now uses core.security.verify_access_token
  - Returns proper 401 for expired/invalid tokens
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

import models
from database import get_db
from core.security import verify_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    FastAPI dependency: extracts and validates the current user from
    the Bearer access token.

    Returns the User ORM object.
    Raises HTTP 401 for invalid/expired tokens or inactive users.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter_by(id=int(user_id)).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user
