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
from typing import Optional


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

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(NuggetFormatter(use_colors=True))
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
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
