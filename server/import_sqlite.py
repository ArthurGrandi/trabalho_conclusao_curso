"""Copy an existing SQLite store into Supabase without removing its source.

Inspection is the default. Applying first creates a consistent SQLite backup;
remote import functions retain source identities and reject changed-source
conflicts instead of replacing existing data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import data_directory


class SQLiteImportError(RuntimeError):
    """A safe diagnostic that contains no uploaded or annotation content."""


def _json(body: dict) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(body: dict) -> str:
    return hashlib.sha256(_json(body).encode("utf-8")).hexdigest()


def _snapshot(source: Path) -> sqlite3.Connection:
    if not source.is_file():
        raise SQLiteImportError("Banco SQLite de origem não encontrado; nenhum banco vazio foi criado.")
    snapshot = sqlite3.connect(":memory:")
    try:
        # mode=ro includes committed WAL transactions; immutable=1 would omit
        # those transactions when a local application is still running.
        connection = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
        try:
            connection.backup(snapshot)
        finally:
            connection.close()
        if snapshot.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise SQLiteImportError("O banco SQLite não passou na verificação de integridade.")
        return snapshot
    except sqlite3.Error as error:
        snapshot.close()
        raise SQLiteImportError("Não foi possível ler uma cópia consistente do banco SQLite.") from error
    except Exception:
        snapshot.close()
        raise


def _rows(snapshot: sqlite3.Connection, table: str) -> list[dict]:
    # table is selected only from the two hard-coded calls below.
    if table not in ("batches", "dictionary_edits"):
        raise ValueError("Tabela inválida")
    try:
        records = snapshot.execute(f"SELECT id, body FROM {table} ORDER BY id").fetchall()
    except sqlite3.Error as error:
        raise SQLiteImportError("O banco SQLite não contém a estrutura esperada da plataforma.") from error
    result = []
    for row_id, serialized in records:
        try:
            body = json.loads(serialized)
            if not isinstance(body, dict) or not isinstance(row_id, int) or row_id < 1:
                raise ValueError("Documento inválido")
            if table == "batches" and body.get("id", row_id) != row_id:
                raise ValueError("Identificador inconsistente")
            fingerprint = _fingerprint(body)
        except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as error:
            raise SQLiteImportError(f"Documento inválido em {table}, registro {row_id}; a origem foi preservada.") from error
        result.append({"source_id": row_id, "body": body, "fingerprint": fingerprint})
    return result


def _identity(source: Path, groups: dict[str, list[dict]], state_directory: Path) -> tuple[str, Path, bool]:
    filename = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest() + ".json"
    manifest = state_directory / filename
    if manifest.exists():
        try:
            saved = json.loads(manifest.read_text(encoding="utf-8"))
            key = saved["source_key"]
            if saved["version"] != 1 or not isinstance(key, str) or not re.fullmatch(r"sqlite-v1:[0-9a-f]{64}", key):
                raise ValueError("Manifesto inválido")
            return key, manifest, False
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise SQLiteImportError("O manifesto local de importação está inválido; preserve-o para investigar a origem.") from error
    # created_at is immutable in the local store. This anchor also identifies a
    # standalone copy of the database, without depending on its absolute path.
    # The manifest freezes the key for older rows that lack creation timestamps.
    for table, rows in groups.items():
        if rows:
            row = rows[0]
            created = row["body"].get("created_at")
            anchor = {"table": table, "source_id": row["source_id"]}
            if isinstance(created, str) and created.strip():
                anchor["created_at"] = created
            else:
                anchor["fingerprint"] = row["fingerprint"]
            return "sqlite-v1:" + _fingerprint(anchor), manifest, True
    # Empty databases import no records. Do not persist this provisional key;
    # their first populated snapshot will supply an immutable anchor.
    return "sqlite-v1:" + hashlib.sha256(b"empty-sqlite-store").hexdigest(), manifest, False


def _save_manifest(path: Path, source_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".import-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump({"version": 1, "source_key": source_key}, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _backup(snapshot: sqlite3.Connection, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    handle, temporary = tempfile.mkstemp(prefix=".sqlite-backup-", dir=directory)
    os.close(handle)
    target = directory / f"platform-before-supabase-{timestamp}-{uuid.uuid4().hex[:8]}.sqlite3"
    try:
        destination = sqlite3.connect(temporary)
        try:
            snapshot.backup(destination)
        finally:
            destination.close()
        with open(temporary, "rb") as saved:
            os.fsync(saved.fileno())
        os.replace(temporary, target)
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


def import_sqlite_snapshot(
    source: str | Path | None = None,
    remote: Any = None,
    apply: bool = False,
    *,
    state_directory: str | Path | None = None,
    backup_directory: str | Path | None = None,
) -> dict:
    """Inspect or import one consistent snapshot; never delete the local file.

    ``remote.query`` must implement bound parameters and the private schema's
    idempotent ``import_batch`` / ``import_dictionary_edit`` SQL functions.
    Each source row keeps its own import receipt, so interrupted runs can resume.
    """
    source = Path(source) if source is not None else data_directory() / "platform.sqlite3"
    state = Path(state_directory) if state_directory is not None else data_directory() / "import-state"
    backups = Path(backup_directory) if backup_directory is not None else data_directory() / "backups"
    if apply and remote is None:
        raise SQLiteImportError("A importação precisa de um armazenamento Supabase configurado.")
    snapshot = _snapshot(source)
    try:
        groups = {"batches": _rows(snapshot, "batches"), "dictionary_edits": _rows(snapshot, "dictionary_edits")}
        source_key, manifest, save_manifest = _identity(source, groups, state)
        report = {
            "dry_run": not apply,
            "source_key": source_key,
            "counts": {table: len(rows) for table, rows in groups.items()},
            "imported": {table: 0 for table in groups},
            "skipped": {table: 0 for table in groups},
            "id_mapping": {table: {} for table in groups},
            "backup": None,
        }
        if not apply:
            return report
        # Complete backup and identity persistence before the first remote write.
        try:
            report["backup"] = str(_backup(snapshot, backups))
            if save_manifest:
                _save_manifest(manifest, source_key)
        except (OSError, sqlite3.Error) as error:
            raise SQLiteImportError("Não foi possível salvar o backup e o manifesto; a importação não foi iniciada.") from error
        for table, rows in groups.items():
            function = "import_batch" if table == "batches" else "import_dictionary_edit"
            sql = f"SELECT id, imported FROM alinhamento.{function}($1::text, $2::bigint, $3::text, $4::uuid, $5::jsonb)"
            for row in rows:
                request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_key}:{table}:{row['source_id']}:{row['fingerprint']}"))
                try:
                    result = remote.query(sql, [source_key, row["source_id"], row["fingerprint"], request_id, _json(row["body"])], read_only=False)
                    if not isinstance(result, list) or len(result) != 1:
                        raise ValueError("Resposta de importação inválida")
                    item = result[0]
                    remote_id = item["id"]
                    if isinstance(remote_id, bool) or not isinstance(remote_id, int) or remote_id < 1 or not isinstance(item["imported"], bool):
                        raise ValueError("Recibo de importação inválido")
                except Exception as error:
                    raise SQLiteImportError(
                        f"A importação parou em {table}, registro {row['source_id']}. "
                        "O SQLite e o backup foram preservados; registros remotos existentes não foram substituídos."
                    ) from error
                report["id_mapping"][table][str(row["source_id"])] = remote_id
                report["imported" if item["imported"] else "skipped"][table] += 1
        return report
    finally:
        snapshot.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspeciona ou importa o SQLite local para o Supabase, preservando sua origem.")
    parser.add_argument("--source", type=Path, default=data_directory() / "platform.sqlite3")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Salva backup e aplica a importação idempotente.")
    mode.add_argument("--dry-run", action="store_true", help="Mostra apenas contagens, sem gravar arquivos ou dados remotos (padrão).")
    arguments = parser.parse_args(argv)
    remote = None
    try:
        if arguments.apply:
            from .persistence import PersistenceConfigurationError, storage_options
            from .supabase_store import SupabaseStore, SupabaseStoreError
            try:
                _, directory, project_ref = storage_options()
                remote = SupabaseStore(directory=directory, project_ref=project_ref)
            except (SupabaseStoreError, PersistenceConfigurationError) as error:
                raise SQLiteImportError(str(error)) from None
        report = import_sqlite_snapshot(arguments.source, remote, apply=arguments.apply)
    except (SQLiteImportError, OSError) as error:
        print(f"Importação não concluída: {error}", file=sys.stderr)
        return 1
    finally:
        if remote is not None:
            remote.close()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
