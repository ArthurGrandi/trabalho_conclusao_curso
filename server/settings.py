"""Portable filesystem defaults for local runs and GitHub Codespaces."""
import os
from pathlib import Path

PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]


def data_directory() -> Path:
    configured = os.getenv("TCC_DATA_DIR")
    return Path(configured).expanduser() if configured else PROJECT_DIRECTORY / ".tcc-data"
