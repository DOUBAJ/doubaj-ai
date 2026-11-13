"""Global paths and constants. Portable: all user data lives next to the executable."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "DOUBAJ AI"
APP_VERSION = "1.0.0"
AUTHOR_AR = "دباج أحمد"
AUTHOR_FR = "DOUBAJ AHMED"


def _base_dir() -> Path:
    """Folder that contains the EXE (frozen) or the project root (source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Bundled read-only resources (assets)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "doubaj" / "assets"
    return Path(__file__).resolve().parent / "assets"


BASE_DIR = _base_dir()
# Portable data folder. Can be overridden with DOUBAJ_DATA_DIR (useful for tests).
DATA_DIR = Path(os.environ.get("DOUBAJ_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "doubaj.sqlite3"
FILES_DIR = DATA_DIR / "files"          # uploaded files copies
OUTPUT_DIR = DATA_DIR / "outputs"       # generated documents
MODELS_DIR = DATA_DIR / "models"        # optional local GGUF models
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"


def ensure_dirs() -> None:
    for d in (DATA_DIR, FILES_DIR, OUTPUT_DIR, MODELS_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
