"""Choose a storage backend explicitly; never hide a remote failure locally."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .settings import PROJECT_DIRECTORY, data_directory
from .storage import Store


class PersistenceConfigurationError(RuntimeError):
    pass


def storage_options() -> tuple[str, Path, str]:
    backend = os.getenv("TCC_STORAGE_BACKEND", "auto").strip().lower()
    if backend not in {"auto", "sqlite", "supabase"}:
        raise PersistenceConfigurationError("TCC_STORAGE_BACKEND deve ser auto, sqlite ou supabase.")
    project_ref = os.getenv("SUPABASE_PROJECT_REF", "").strip()
    if not project_ref:
        project_file = PROJECT_DIRECTORY / "supabase" / "project.json"
        try:
            project_ref = json.loads(project_file.read_text()).get("project_ref", "")
        except (OSError, ValueError):
            project_ref = ""
    if backend == "auto":
        backend = "supabase" if os.getenv("SUPABASE_ACCESS_TOKEN") or os.getenv("SUPABASE_PROJECT_REF") else "sqlite"
    return backend, data_directory().resolve(), project_ref


def build_store(options: tuple[str, Path, str]):
    backend, directory, project_ref = options
    if backend == "sqlite":
        return Store(directory)
    from .supabase_store import SupabaseStore
    return SupabaseStore(project_ref=project_ref, directory=directory)


def storage_description(database) -> dict:
    backend = getattr(database, "source_name", "sqlite")
    return {"backend": backend, "label": "Supabase" if backend == "supabase" else "SQLite local", "cloud": backend == "supabase"}
