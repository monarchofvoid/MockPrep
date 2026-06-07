"""
VYAS v2.1.2 — Structured Logging Configuration
===============================================
v2.1.2 FIX — BUG-SILENT-LOGS:

  ROOT CAUSE (precisely):
    configure_logging() is called at module import time in main.py (line ~67).
    At that point, uvicorn has NOT yet called its own dictConfig.
    Our StreamHandler(stdout) is added successfully (handlers=1 in startup log).

    Then uvicorn starts the worker and calls:
      logging.config.dictConfig({'root': {'handlers': ['default'], 'level': 'INFO'}, ...})
    The 'root' key in dictConfig REPLACES root.handlers entirely (this is standard
    Python logging.config.dictConfig behavior — specifying 'root' is destructive).
    Our stdout handler is removed. All application logs now go to uvicorn's stderr.

    The lifespan() function runs after dictConfig but:
      - "ASGI lifespan protocol appears unsupported" means lifespan IS being skipped.
      - Even if lifespan runs, our second configure_logging() call in lifespan is needed.

  FIX:
    1. This function is now called TWICE:
       - Once at module import time (same as before — some logs still appear)
       - Once inside lifespan() AFTER uvicorn's dictConfig (re-adds our handler)
    2. The marker check (_vyas_handler attribute) prevents duplicate handlers.
    3. Every call re-applies our formatter to ALL existing handlers, so even
       uvicorn's stderr handler uses our format for consistency.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Settings

_DEV_FORMAT  = "%(asctime)s.%(msecs)03d  %(levelname)-8s  %(name)-35s  %(message)s"
_DEV_DATE    = "%H:%M:%S"
_PROD_FORMAT = "%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"
_PROD_DATE   = "%Y-%m-%dT%H:%M:%S"
_MARKER      = "_vyas_handler"


def configure_logging(settings: "Settings | None" = None) -> None:
    """
    Configure application-wide logging.

    Safe to call multiple times — uses a marker attribute to detect our
    own StreamHandler(stdout) and avoids adding duplicate handlers.

    Must be called from lifespan() as well as at module import time,
    because uvicorn's dictConfig (called during worker init) wipes handlers
    that were added before uvicorn started. The lifespan call re-adds ours.
    """
    if settings is not None:
        log_level_name = settings.LOG_LEVEL.upper()
        is_production  = settings.is_production
        log_file       = getattr(settings, "LOG_FILE", "") or ""
    else:
        import os
        log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        is_production  = os.getenv("ENVIRONMENT", "development") == "production"
        log_file       = os.getenv("LOG_FILE", "")

    log_level: int = getattr(logging, log_level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt=_PROD_FORMAT if is_production else _DEV_FORMAT,
        datefmt=_PROD_DATE if is_production else _DEV_DATE,
    )

    root = logging.getLogger()

    # Check if our tagged stdout handler is already present
    already_has_vyas_handler = any(
        getattr(h, _MARKER, False) for h in root.handlers
    )

    if not already_has_vyas_handler:
        # Add StreamHandler(stdout) — Render/terminals capture stdout.
        # This is the handler that makes application logs visible.
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        setattr(console_handler, _MARKER, True)  # tag so we detect it on re-call
        root.addHandler(console_handler)

        if log_file:
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                fh = RotatingFileHandler(
                    log_path, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
                )
                fh.setFormatter(formatter)
                fh.setLevel(logging.INFO)
                root.addHandler(fh)
            except (OSError, PermissionError) as exc:
                # Read-only filesystem — stdout only
                logging.getLogger("vyas.logging").warning(
                    "Cannot write log file %s: %s — stdout only", log_file, exc
                )

    # Always update level and reformat ALL existing handlers (including uvicorn's stderr)
    root.setLevel(log_level)
    for handler in root.handlers:
        if not isinstance(handler, RotatingFileHandler):
            handler.setFormatter(formatter)

    # Quieten noisy libraries
    for name, level in {
        "httpx":             logging.WARNING,
        "httpcore":          logging.WARNING,
        "sqlalchemy.engine": logging.WARNING,
        "sqlalchemy.pool":   logging.WARNING,
        "passlib":           logging.WARNING,
        "celery":            logging.INFO,
        "razorpay":          logging.WARNING,
        "google":            logging.WARNING,
        "urllib3":           logging.WARNING,
        "asyncio":           logging.WARNING,
    }.items():
        logging.getLogger(name).setLevel(level)

    # Sanity check — this line MUST appear in terminal after every (re)start.
    # If it appears before requests but not after, the lifespan call is not running.
    logging.getLogger("vyas.logging").info(
        "Logging configured: level=%s production=%s file=%s handlers=%d vyas_handler_was_present=%s",
        log_level_name,
        is_production,
        log_file or "none",
        len(root.handlers),
        already_has_vyas_handler,
    )