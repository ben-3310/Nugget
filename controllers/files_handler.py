"""
File handling utilities for Nugget.

Provides functions for accessing bundled files in both development
and PyInstaller-frozen environments.
"""

import sys
from os import path, getcwd


def get_bundle_files(name: str) -> str:
    """
    Get the path to bundled files, handling both development and frozen modes.

    When running from source, files are relative to current working directory.
    When running from PyInstaller bundle, files are in sys._MEIPASS.

    Args:
        name: Relative path to the file (using forward slashes)

    Returns:
        Absolute path to the file
    """
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    base_path = getattr(sys, "_MEIPASS", getcwd())

    return path.join(base_path, *name.split('/'))
