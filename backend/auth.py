"""
VYAS v0.6 — Authentication Module
====================================
Changes vs v0.5:
  D4: SECRET_KEY validation now delegates to config.py
  D5: Comment added explaining missing refresh token system
  P3: Import from config instead of raw os.getenv
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import models
from database import get_db
from config import AppConfig

# ── Config ────────────────────────────────────────────────────────────────────
# D4: SECRET_KEY validation: raises RuntimeError in production if missing,
#     warns loudly in development (never silently uses an insecure default).
# D5 Note: This system uses long-lived access tokens (7 days by default).
#    There is no refresh token mechanism in v0.6. When a token expires, the user
#    must log in again. A refresh token system is planned for v0.7.
SECRET_KEY = AppConfig.SECRET_KEY
ALGORITHM  = AppConfig.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = AppConfig.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ── Dependency: extract current user from Bearer token ───────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter_by(id=int(user_id)).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user
