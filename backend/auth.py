"""
VYAS v2.0 — auth.py (backward-compatibility shim)
====================================================
All existing routers import from this module (auth.get_current_user,
auth.hash_password, etc.). This shim re-exports everything from the
new core/ modules so existing code continues to work without changes.

DO NOT add new logic here. Use core/security.py and core/auth.py.
"""

from core.security import (  # noqa: F401 — re-export
    hash_password,
    verify_password,
    create_access_token,
)
from core.auth import get_current_user  # noqa: F401 — re-export

# Legacy alias kept for any code that imports create_access_token from here
__all__ = ["hash_password", "verify_password", "create_access_token", "get_current_user"]
