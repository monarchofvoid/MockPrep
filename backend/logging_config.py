"""
VYAS v0.6 — Centralised Logging Configuration
================================================
Import and call configure_logging() once at the top of main.py.
All modules should use:
    import logging
    logger = logging.getLogger(__name__)
instead of print().
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def configure_logging() -> None:
    """
    Set up root logger with:
      - StreamHandler to stdout (always)
      - RotatingFileHandler to logs/vyas.log (if LOG_FILE env is set or default)

    Log level is controlled by LOG_LEVEL env var (default: INFO).
    Sensitive data must never be passed to logger — caller's responsibility.
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(log_level)

    # ── stdout handler (always present) ──────────────────────────────────────
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    # ── optional rotating file handler ────────────────────────────────────────
    log_file = os.getenv("LOG_FILE", "")
    if log_file:
        try:
            fh = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,   # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except OSError as exc:
            logging.warning("Could not open log file %r: %s", log_file, exc)

    # Quieten noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)
