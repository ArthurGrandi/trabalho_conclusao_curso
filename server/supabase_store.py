"""Supabase persistence for the small, server-hosted research MVP.

This adapter uses the Management API and the already configured project-scoped
PAT. It deliberately does not send that credential to the browser or silently
fall back to a local database. The API is experimental and is not intended as a
high-throughput application database connection.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timezone
from email.utils import parsedate_to_datetime
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from typing import Callable
from uuid import uuid4

import httpx

from .settings import data_directory


class _RequestGate:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_request: float | None = None
        self.not_before = 0.0


_REQUEST_GATES: dict[str, _RequestGate] = {}
_REQUEST_GATES_LOCK = threading.Lock()


def _request_gate(project_ref: str) -> _RequestGate:
    # Multiple adapter instances in one API process share the same project quota.
    with _REQUEST_GATES_LOCK:
        return _REQUEST_GATES.setdefault(project_ref, _RequestGate())


class SupabaseStoreError(RuntimeError):
    """Safe application-facing error; never contains response bodies or tokens."""


class SupabaseConfigurationError(SupabaseStoreError):
    pass


class SupabaseUnavailableError(SupabaseStoreError):
    pass


class SupabaseMigrationError(SupabaseStoreError):
    pass


class SupabaseConflictError(SupabaseStoreError):
    pass


class SupabaseStore:
    source_name = "supabase"

    def __init__(
        self,
        directory: str | Path | None = None,
        *,
        project_ref: str | None = None,
        access_token: str | None = None,
        client: httpx.Client | None = None,
        cache_ttl: float = 0.4,
        retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        request_interval: float = 0.65,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ):
        self.directory = Path(directory) if directory is not None else data_directory()
        self.project_ref = project_ref if project_ref is not None else os.getenv("SUPABASE_PROJECT_REF", "")
        token = access_token if access_token is not None else os.getenv("SUPABASE_ACCESS_TOKEN", "")
        if not re.fullmatch(r"[a-z0-9]{20}", self.project_ref):
            raise SupabaseConfigurationError("Configure SUPABASE_PROJECT_REF com a referência válida do projeto Supabase (20 letras minúsculas ou números).")
        if not token or not token.strip():
            raise SupabaseConfigurationError("SUPABASE_ACCESS_TOKEN não está configurado no servidor. Configure a credencial existente no ambiente; não há fallback automático para SQLite.")
        if "\n" in token or "\r" in token:
            raise SupabaseConfigurationError("SUPABASE_ACCESS_TOKEN possui formato inválido.")
        self._token = token
        self._url = f"https://api.supabase.com/v1/projects/{self.project_ref}/database/query"
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(25.0, connect=10.0),
            trust_env=True,
            follow_redirects=False,
        )
        self._owns_client = client is None
        self._retries = min(3, max(0, int(retries)))
        self._sleep = sleep
        interval = float(request_interval)
        if not math.isfinite(interval) or interval < 0:
            raise SupabaseConfigurationError("O intervalo de requisições ao Supabase deve ser um número finito não negativo.")
        self._request_interval = min(60.0, interval)
        self._clock = clock
        self._wall_clock = wall_clock
        self._gate = _request_gate(self.project_ref)
        self._cache_ttl = min(0.5, max(0.0, float(cache_ttl)))
        self._cache: dict[int, tuple[float, dict | None]] = {}
        self._dictionary_cache: tuple[float, list[dict]] | None = None
        self._cache_lock = threading.RLock()
        self._ready = False
        self._counts: dict[str, int] | None = None

    def __repr__(self):
        return f"SupabaseStore(project_ref={self.project_ref!r}, source_name='supabase')"

    def close(self):
        if self._owns_client:
            self._client.close()

    def _wait_for_request_slot(self):
        while True:
            with self._gate.lock:
                deadline = self._gate.not_before
                if self._gate.last_request is not None:
                    deadline = max(deadline, self._gate.last_request + self._request_interval)
                remaining = deadline - self._clock()
                if remaining <= 0:
                    self._gate.last_request = self._clock()
                    return
            # Release the lock so a response can extend the shared cooldown.
            self._sleep(min(60.0, remaining))

    def _header_delay(self, value: str | None, *, reset: bool = False) -> float | None:
        if not value:
            return None
        try:
            delay = float(value)
            if not math.isfinite(delay) or delay < 0:
                return None
            if reset and delay >= 1_000_000_000:
                # Reset may be a delta in seconds or an absolute Unix timestamp.
                if delay >= 1_000_000_000_000:
                    delay /= 1000
                delay -= self._wall_clock()
        except (TypeError, ValueError):
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                delay = date.timestamp() - self._wall_clock()
            except (TypeError, ValueError, OverflowError):
                return None
        return min(60.0, max(0.0, delay))

    def _rate_limit_delay(self, response: httpx.Response) -> float:
        delays = []
        for header, reset in (("retry-after", False), ("x-ratelimit-reset", True), ("ratelimit-reset", True)):
            delay = self._header_delay(response.headers.get(header), reset=reset)
            if delay is not None:
                delays.append(delay)
        # If both headers exist, respect the later advertised retry time.
        return max(delays) if delays else 1.0

    def _record_rate_limit(self, response: httpx.Response):
        remaining = response.headers.get("x-ratelimit-remaining", response.headers.get("ratelimit-remaining"))
        exhausted = remaining is not None and remaining.strip() == "0"
        if response.status_code != 429 and not (response.is_success and exhausted):
            return
        delay = self._rate_limit_delay(response)
        with self._gate.lock:
            self._gate.not_before = max(self._gate.not_before, self._clock() + delay)

    def _clear_cache(self, batch_id: int | None = None):
        with self._cache_lock:
            if batch_id is None:
                self._cache.clear()
            else:
                self._cache.pop(batch_id, None)
            self._dictionary_cache = None

    @staticmethod
    def _json(value) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        except (ValueError, TypeError):
            raise SupabaseStoreError("Os dados do lote não podem ser convertidos em JSON válido.") from None

    def query(self, query: str, parameters: list | None = None, *, read_only: bool = True) -> list[dict]:
        """Execute trusted, fixed SQL from server modules, never an HTTP client.

        Import helpers use this method to call the migration's fixed functions.
        All user data belongs in ``parameters``, not in the SQL string.
        """
        if not read_only:
            self._clear_cache()
        return self._query(query, parameters, read_only=read_only)

    def _query(self, query: str, parameters: list | None = None, *, read_only: bool = True, attempt_state: dict | None = None) -> list[dict]:
        payload = {"query": query, "parameters": parameters or [], "read_only": bool(read_only)}
        for attempt in range(self._retries + 1):
            self._wait_for_request_slot()
            try:
                response = self._client.post(
                    self._url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                    follow_redirects=False,
                )
            except httpx.TransportError:
                if attempt_state is not None and not read_only:
                    attempt_state["ambiguous"] = True
                if attempt < self._retries:
                    self._sleep(min(0.2 * (2**attempt), 1.0))
                    continue
                self._ready = False
                raise SupabaseUnavailableError("Não foi possível acessar o Supabase. Verifique a conexão do servidor e tente novamente; os dados não foram movidos para SQLite.") from None
            self._record_rate_limit(response)
            if response.status_code in (401, 403):
                self._ready = False
                raise SupabaseConfigurationError("O Supabase recusou a credencial do servidor. Verifique a validade do PAT e as permissões DatabaseReadWrite para este projeto.")
            if response.status_code not in (200, 201):
                # SQL errors can use HTTP 500; identify missing migrations before retrying.
                text = response.text.lower()
                missing = any(code in text for code in ("42p01", "42883", "42703", "3f000")) or (
                    "does not exist" in text and any(word in text for word in ("alinhamento", "relation", "function", "schema"))
                )
                if missing:
                    self._ready = False
                    raise SupabaseMigrationError("A migração de persistência do schema alinhamento não está instalada ou está incompleta no projeto Supabase.")
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt_state is not None and not read_only and response.status_code != 429:
                    attempt_state["ambiguous"] = True
                if attempt < self._retries:
                    if response.status_code != 429:
                        self._sleep(min(0.2 * (2**attempt), 1.0))
                    continue
                self._ready = False
                raise SupabaseUnavailableError("O Supabase está temporariamente indisponível ou limitou as requisições. Aguarde e tente novamente.")
            if response.status_code not in (200, 201):
                self._ready = False
                raise SupabaseUnavailableError("O Supabase recusou a operação de persistência. Revise a migração e a configuração do servidor.")
            try:
                rows = response.json()
            except (ValueError, UnicodeError):
                self._ready = False
                raise SupabaseUnavailableError("O Supabase retornou uma resposta de persistência inválida.") from None
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                self._ready = False
                raise SupabaseUnavailableError("O Supabase retornou um formato de persistência inesperado.")
            return rows
        raise SupabaseUnavailableError("Não foi possível concluir a operação no Supabase.")

    @staticmethod
    def _batch_row(row: dict) -> dict:
        body = row.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except ValueError:
                body = None
        if not isinstance(body, dict) or not isinstance(row.get("id"), int):
            raise SupabaseUnavailableError("O Supabase retornou um lote com formato inválido.")
        return {**deepcopy(body), "id": row["id"]}

    @staticmethod
    def _batch_id(batch_id: int) -> int:
        if isinstance(batch_id, bool) or not isinstance(batch_id, int) or batch_id < 1:
            raise SupabaseStoreError("O identificador do lote deve ser um inteiro positivo.")
        return batch_id

    def _read(self, batch_id: int) -> dict | None:
        rows = self._query("SELECT id, body, revision FROM alinhamento.batches WHERE id = $1::bigint", [batch_id])
        return rows[0] if rows else None

    def _cache_body(self, batch_id: int, body: dict | None):
        with self._cache_lock:
            self._cache[batch_id] = (time.monotonic(), deepcopy(body))

    def create(self, body: dict) -> dict:
        request_id = str(uuid4())
        rows = self._query(
            "SELECT id, body, revision FROM alinhamento.create_batch($1::uuid, $2::jsonb)",
            [request_id, self._json(body)], read_only=False,
        )
        if not rows:
            raise SupabaseUnavailableError("O Supabase não confirmou a criação do lote.")
        created = self._batch_row(rows[0])
        self._cache_body(created["id"], created)
        return deepcopy(created)

    def get(self, batch_id: int) -> dict | None:
        batch_id = self._batch_id(batch_id)
        with self._cache_lock:
            cached = self._cache.get(batch_id)
            if cached is not None and time.monotonic() - cached[0] < self._cache_ttl:
                return deepcopy(cached[1])
        row = self._read(batch_id)
        body = self._batch_row(row) if row is not None else None
        self._cache_body(batch_id, body)
        return deepcopy(body)

    def all(self) -> list[dict]:
        rows = self._query("SELECT id, body, revision FROM alinhamento.batches ORDER BY id DESC")
        bodies = [self._batch_row(row) for row in rows]
        for body in bodies:
            self._cache_body(body["id"], body)
        return deepcopy(bodies)

    def update(self, batch_id: int, change: Callable[[dict], None]) -> dict | None:
        batch_id = self._batch_id(batch_id)
        self._clear_cache(batch_id)
        for _ in range(5):
            row = self._read(batch_id)  # Always fresh for cross-process compare-and-swap.
            if row is None:
                return None
            current = self._batch_row(row)
            revision = row.get("revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise SupabaseMigrationError("A revisão do lote no Supabase é inválida. Verifique a migração de persistência.")
            change(current)
            current["id"] = batch_id
            state = {}
            written = self._query(
                "UPDATE alinhamento.batches SET body = $1::jsonb, revision = revision + 1, updated_at = now() "
                "WHERE id = $2::bigint AND revision = $3::bigint RETURNING id, body, revision",
                [self._json(current), batch_id, revision], read_only=False, attempt_state=state,
            )
            if written:
                updated = self._batch_row(written[0])
                self._cache_body(batch_id, updated)
                return deepcopy(updated)
            if state.get("ambiguous"):
                # A lost response may follow a committed write. Do not apply the callback twice.
                confirmed = self._read(batch_id)
                if confirmed and self._batch_row(confirmed) == current and confirmed.get("revision", 0) > revision:
                    self._cache_body(batch_id, current)
                    return deepcopy(current)
                raise SupabaseUnavailableError("Não foi possível confirmar a gravação no Supabase após uma falha de conexão. Recarregue o lote antes de repetir a alteração.")
            # Another process wrote first. Reapply a pure callback to its fresh snapshot.
            self._clear_cache(batch_id)
        raise SupabaseConflictError("O lote foi alterado simultaneamente muitas vezes. Recarregue-o e tente novamente.")

    def dictionary_edits(self) -> list[dict]:
        with self._cache_lock:
            if self._dictionary_cache is not None and time.monotonic() - self._dictionary_cache[0] < self._cache_ttl:
                return deepcopy(self._dictionary_cache[1])
        rows = self._query("SELECT body FROM alinhamento.dictionary_edits ORDER BY id")
        edits = [deepcopy(row["body"]) for row in rows if isinstance(row.get("body"), dict)]
        if len(edits) != len(rows):
            raise SupabaseUnavailableError("O Supabase retornou uma edição de dicionário inválida.")
        with self._cache_lock:
            self._dictionary_cache = (time.monotonic(), deepcopy(edits))
        return edits

    def add_dictionary_edit(self, edit: dict) -> dict:
        self._clear_cache()
        rows = self._query(
            "SELECT id, body FROM alinhamento.create_dictionary_edit($1::uuid, $2::jsonb)",
            [str(uuid4()), self._json(edit)], read_only=False,
        )
        if not rows or not isinstance(rows[0].get("body"), dict):
            raise SupabaseUnavailableError("O Supabase não confirmou a edição do dicionário.")
        return deepcopy(rows[0]["body"])

    def check_ready(self) -> dict:
        rows = self._query(
            "SELECT to_regclass('alinhamento.batches') IS NOT NULL AS batches_ready, "
            "to_regclass('alinhamento.dictionary_edits') IS NOT NULL AS dictionary_ready, "
            "to_regprocedure('alinhamento.create_batch(uuid,jsonb)') IS NOT NULL AS create_batch_ready, "
            "to_regprocedure('alinhamento.create_dictionary_edit(uuid,jsonb)') IS NOT NULL AS create_dictionary_ready"
        )
        required = ("batches_ready", "dictionary_ready", "create_batch_ready", "create_dictionary_ready")
        if not rows or not all(rows[0].get(key) is True for key in required):
            self._ready = False
            raise SupabaseMigrationError("A migração de persistência do schema alinhamento não está instalada ou está incompleta no projeto Supabase.")
        counts = self._query(
            "SELECT (SELECT count(*) FROM alinhamento.batches)::bigint AS batches, "
            "(SELECT count(*) FROM alinhamento.dictionary_edits)::bigint AS dictionary_edits"
        )
        if not counts or not all(isinstance(counts[0].get(key), int) for key in ("batches", "dictionary_edits")):
            raise SupabaseUnavailableError("O Supabase não confirmou o estado da persistência.")
        self._counts = {key: counts[0][key] for key in ("batches", "dictionary_edits")}
        self._ready = True
        return self.health_description()

    def health_description(self) -> dict:
        return {"backend": self.source_name, "project_ref": self.project_ref, "ready": self._ready,
                "counts": deepcopy(self._counts), "transport": "management_api"}


SupabaseManagementStore = SupabaseStore
