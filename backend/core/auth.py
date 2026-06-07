"""
VYAS v2.0 — Auth Dependency
==============================
FastAPI dependency that validates the access token and returns the current User.

Usage:
    @router.get("/protected")
    def my_endpoint(current_user: User = Depends(get_current_user)):
        ...

Token source: Authorization: Bearer <access_token> header.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from core.security import verify_access_token
from database import get_db
from models.user import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate access token and return the authenticated user.
    Raises HTTP 401 on any authentication failure.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_access_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.query(User).filter_by(id=int(user_id_str)).first()
    if user is None or not user.is_active:
        raise credentials_exc

    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Like get_current_user but returns None instead of raising on auth failure.
    Used for endpoints that work both authenticated and unauthenticated.
    """
    if not token:
        return None
    try:
        return get_current_user(token, db)
    except HTTPException:
        return None
