"""
Centralized logging system for Nugget.

This module provides a unified logging interface that can be used throughout
the application. It supports different log levels and can optionally integrate
with Qt's debugging system.

Usage:
    from utils.logger import logger

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.exception("Exception with traceback")
"""

import logging
import sys
import os
import platform
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Mapping, Optional


# Create a custom formatter
class NuggetFormatter(logging.Formatter):
    """Custom formatter with colored output for console."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        # Format: [LEVEL] module: message
        if self.use_colors:
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            reset = self.COLORS["RESET"]
            formatted = f"{color}[{record.levelname}]{reset} {record.name}: {record.getMessage()}"
        else:
            formatted = f"[{record.levelname}] {record.name}: {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def setup_logger(
    name: str = "Nugget", level: int = logging.DEBUG, log_file: Optional[str] = None
) -> logging.Logger:
    """
    Set up and configure the logger.

    Args:
        name: Logger name
        level: Logging level (default: DEBUG)
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    logger.setLevel(level)

    # Console handler (avoid duplicates)
    has_console = any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout
        for h in logger.handlers
    )
    if not has_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(NuggetFormatter(use_colors=True))
        logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        abs_log_file = os.path.abspath(log_file)
        has_file = any(
            isinstance(h, logging.FileHandler)
            and os.path.abspath(getattr(h, "baseFilename", "")) == abs_log_file
            for h in logger.handlers
        )
        if not has_file:
            file_handler = logging.FileHandler(abs_log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(NuggetFormatter(use_colors=False))
            logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        module_name: Name of the module requesting the logger

    Returns:
        Logger instance for the module
    """
    return logging.getLogger(f"Nugget.{module_name}")


# Default logger instance
logger = setup_logger()

# Track the active log file path (if enabled)
_active_log_file: Optional[str] = None


def get_default_log_dir(app_name: str = "Nugget") -> str:
    """
    Return a platform-appropriate log directory and ensure it exists.
    """
    if sys.platform == "darwin":
        base_dir = os.path.join(os.path.expanduser("~"), "Library", "Logs", app_name)
    elif os.name == "nt":
        base_dir = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), app_name, "logs")
    else:
        state_home = os.getenv("XDG_STATE_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "state"
        )
        base_dir = os.path.join(state_home, app_name.lower(), "logs")

    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def get_default_log_file(app_name: str = "Nugget", filename: str = "nugget.log") -> str:
    """
    Return the default log file path for Nugget.
    """
    return os.path.join(get_default_log_dir(app_name=app_name), filename)


def enable_file_logging(log_file: Optional[str] = None, level: int = logging.DEBUG) -> str:
    """
    Enable file logging for Nugget (idempotent). Returns the log file path.
    """
    global _active_log_file
    if log_file is None:
        log_file = get_default_log_file()
    _active_log_file = os.path.abspath(log_file)
    setup_logger(name="Nugget", level=level, log_file=_active_log_file)
    return _active_log_file


def get_active_log_file() -> Optional[str]:
    return _active_log_file


def _safe_pkg_version(dist_name: str) -> str:
    try:
        return metadata.version(dist_name)
    except Exception:
        return "unknown"


def collect_diagnostics(
    *,
    app_version: Optional[str] = None,
    app_build: Optional[int] = None,
    alert_text: Optional[str] = None,
    traceback_text: Optional[str] = None,
    device_info: Optional[Mapping[str, Any]] = None,
    extra: Optional[Mapping[str, Any]] = None,
    log_file: Optional[str] = None,
) -> str:
    """
    Build a diagnostics text blob suitable for copying into bug reports.
    """
    now = datetime.now(timezone.utc).isoformat()
    if log_file is None:
        log_file = _active_log_file

    lines: list[str] = []
    lines.append("=== Nugget Diagnostics ===")
    lines.append(f"timestamp_utc: {now}")
    if app_version is not None:
        lines.append(f"nugget_version: {app_version}")
    if app_build is not None:
        lines.append(f"nugget_build: {app_build}")
    lines.append(f"os: {platform.platform()}")
    lines.append(f"python: {sys.version.replace(os.linesep, ' ')}")
    lines.append(f"pymobiledevice3: {_safe_pkg_version('pymobiledevice3')}")
    lines.append(f"PySide6: {_safe_pkg_version('PySide6')}")
    if log_file:
        lines.append(f"log_file: {log_file}")

    if device_info:
        lines.append("")
        lines.append("--- device ---")
        for k, v in device_info.items():
            if k == "udid" and v is not None:
                s = str(v)
                v = s if len(s) <= 6 else ("*" * (len(s) - 6) + s[-6:])
            lines.append(f"{k}: {v}")

    if extra:
        lines.append("")
        lines.append("--- extra ---")
        for k, v in extra.items():
            lines.append(f"{k}: {v}")

    if alert_text:
        lines.append("")
        lines.append("--- alert ---")
        lines.append(alert_text)

    if traceback_text:
        lines.append("")
        lines.append("--- traceback/details ---")
        lines.append(traceback_text)

    lines.append("")
    return "\n".join(lines)


# Module-specific loggers
def get_posterboard_logger() -> logging.Logger:
    """Get logger for PosterBoard module."""
    return get_logger("posterboard")


def get_templates_logger() -> logging.Logger:
    """Get logger for Templates module."""
    return get_logger("templates")


def get_device_logger() -> logging.Logger:
    """Get logger for Device Management module."""
    return get_logger("device")


def get_restore_logger() -> logging.Logger:
    """Get logger for Restore module."""
    return get_logger("restore")
