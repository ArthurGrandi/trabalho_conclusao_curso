"""Local FastAPI service for the curriculum–market research workflow."""
from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import re
import time
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .dictionary import DICTIONARY, build_dictionary
from .areas import canonical_area
from .engine import analyze
from .reporting import csv_archive, export_tables, import_annotations, make_sample, now, validation_result, workbook
from .storage import Store
from .settings import data_directory
from .uploads import clean_filename, deduplicate_jobs, parse_jobs, read_upload, segment_ppc


@asynccontextmanager
async def lifespan(application):
    recover_interrupted_batches()
    yield


app = FastAPI(title="Alinhamento Currículo–Mercado de TI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])
_store: Store | None = None


def store() -> Store:
    global _store
    directory = data_directory()
    if _store is None or _store.directory != directory:
        _store = Store(directory)
    return _store


def batch_or_404(batch_id: int) -> dict:
    batch = store().get(batch_id)
    if batch is None:
        raise HTTPException(404, "Lote não encontrado.")
    return batch


def public_batch(batch: dict) -> dict:
    # Annotation labels and frozen dictionary requirements are server-side data.
    return {key: value for key, value in batch.items() if key not in ("annotations", "dictionary_snapshot", "sample")}


def log(batch: dict, message: str, level: str = "info"):
    batch.setdefault("logs", []).append({"time": now(), "level": level, "message": message})


def recover_interrupted_batches():
    """Record interrupted work on startup without restarting network requests."""
    for batch in store().all():
        interrupted_process = batch["status"] == "processing"
        interrupted_collection = batch["status"] == "review" and batch.get("collection", {}).get("running")
        if not interrupted_process and not interrupted_collection:
            continue
        def recover(current):
            if current["status"] == "processing":
                current.update(status="failed", error="A execução foi interrompida pelo reinício do servidor. Crie um novo lote para executar novamente; nenhuma chamada ao LLM foi retomada automaticamente.")
                for item in current["stages"]:
                    if item["status"] == "running":
                        item.update(status="failed", detail="Processamento interrompido pelo reinício do servidor.")
                log(current, current["error"], "warning")
            elif current["status"] == "review" and current.get("collection", {}).get("running"):
                current["collection"].update(running=False, partial=True, interrupted=True, count=len(current["jobs"]))
                stage(current, "collection", "warning", f"Coleta interrompida pelo reinício do servidor. {len(current['jobs'])} vagas preservadas; nenhuma requisição foi retomada.")
                log(current, "Coleta interrompida pelo reinício. Revise as vagas preservadas ou crie um novo lote.", "warning")
        store().update(batch["id"], recover)


def stage(batch: dict, key: str, status: str, detail: str, duration: float | None = None):
    item = next(row for row in batch["stages"] if row["key"] == key)
    item.update(status=status, detail=detail)
    if duration is not None:
        item["duration"] = round(duration, 3)


def llm_capabilities() -> dict:
    try:
        from .llm import llm_status
        return llm_status()
    except ImportError:
        return {"enabled": False, "message": "Integração de modelo indisponível."}


@app.get("/api/health")
def health():
    llm = llm_capabilities()
    return {"status": "ok", "capabilities": {"pdf": True, "jobspy": importlib.util.find_spec("jobspy") is not None, "llm": llm.get("enabled", False), "llm_detail": llm},
            "dictionary_count": len(build_dictionary(store().dictionary_edits()))}


@app.get("/api/dictionary")
def get_dictionary():
    return {"entries": build_dictionary(store().dictionary_edits()), "edits": store().dictionary_edits(), "applies_to": "next_batch"}


class DictionaryEdit(BaseModel):
    competency_id: str = Field(min_length=1, max_length=100)
    alias: str | None = Field(default=None, max_length=120)
    context: str | None = Field(default=None, max_length=500)


@app.post("/api/dictionary")
def edit_dictionary(body: DictionaryEdit):
    if body.competency_id not in {str(row["id"]) for row in DICTIONARY}:
        raise HTTPException(422, "Selecione uma competência existente do dicionário.")
    if not (body.alias and body.alias.strip()) and not (body.context and body.context.strip()):
        raise HTTPException(422, "Informe um sinônimo ou uma regra de contexto.")
    edit = {"id": body.competency_id, "competency_id": body.competency_id, "alias": (body.alias or "").strip(), "synonym": (body.alias or "").strip(), "created_at": now()}
    if body.context and body.context.strip():
        edit["context"] = [part.strip() for part in re.split(r"[,;\n]", body.context) if part.strip()]
    store().add_dictionary_edit(edit)
    return {"saved": True, "applies_to": "next_batch", "edit": edit}


@app.post("/api/ppc")
async def upload_ppc(file: UploadFile = File(...)):
    filename = clean_filename(file.filename)
    return segment_ppc(await read_upload(file), filename)


@app.post("/api/jobs/preview")
async def preview_jobs(file: UploadFile = File(...)):
    filename = clean_filename(file.filename)
    return parse_jobs(await read_upload(file), filename)


class NewBatch(BaseModel):
    config: dict
    ppc: dict
    jobs: list[dict] = Field(default_factory=list, max_length=2000)


class DisciplineEdit(BaseModel):
    disciplines: list[dict] = Field(min_length=1, max_length=400)
    corrections: int = Field(default=0, ge=0, le=10000)


class Decision(BaseModel):
    association_id: str
    decision: Literal["accepted", "rejected"] | None


DEFAULT_CONFIG = {"course": "Bacharelado em Sistemas de Informação", "city": "Itajaí, SC", "radius": 40, "platform": "indeed", "target": 500,
                  "terms": ["desenvolvedor", "programador", "analista de sistemas", "analista de dados", "suporte de TI", "infraestrutura de TI", "engenheiro de software", "tecnologia da informação"],
                  "tags": "", "threshold": 5, "llm_limit": 3000, "methods": ["M2", "A1", "A2"], "source": "csv"}


def validate_config(raw: dict) -> dict:
    config = {**DEFAULT_CONFIG, **raw}
    if config["source"] not in ("csv", "jobspy", "demo"):
        raise HTTPException(422, "Fonte de vagas inválida.")
    for key, minimum, maximum in (("radius", 0, 500), ("target", 1, 2000), ("threshold", 0, 100), ("llm_limit", 0, 10000)):
        try:
            value = float(config[key])
        except (ValueError, TypeError):
            raise HTTPException(422, f"Valor inválido para {key}.")
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise HTTPException(422, f"{key} deve estar entre {minimum} e {maximum}.")
        config[key] = value if key == "threshold" else int(value)
    if not isinstance(config["terms"], list) or not (0 if config["source"] == "demo" else 1) <= len(config["terms"]) <= 20 or any(not isinstance(term, str) or not 1 <= len(term.strip()) <= 120 for term in config["terms"]):
        raise HTTPException(422, "Informe de 1 a 20 termos de busca, com até 120 caracteres cada.")
    methods = config.get("methods")
    if not isinstance(methods, list) or not methods or any(item not in ("M1", "M2", "M3", "A1", "A2") for item in methods):
        raise HTTPException(422, "Selecione métodos válidos de extração e associação.")
    if not any(item.startswith("M") for item in methods):
        raise HTTPException(422, "Selecione ao menos um método de extração (M1, M2 ou M3).")
    if str(config["platform"]).lower() not in ("indeed", "linkedin", "glassdoor", "google", "google vagas"):
        raise HTTPException(422, "Plataforma de vagas inválida.")
    for key in ("course", "city", "tags"):
        if not isinstance(config.get(key), str) or len(config[key]) > 500:
            raise HTTPException(422, f"Campo {key} inválido.")
    return config


def validate_disciplines(rows: list[dict]) -> list[dict]:
    if not rows or len(rows) > 400:
        raise HTTPException(422, "O PPC deve conter entre 1 e 400 disciplinas revisáveis.")
    result, ids = [], set()
    for index, row in enumerate(rows, 1):
        discipline = {"id": str(row.get("id") or f"d{index}"), "name": str(row.get("name", "")).strip(),
                      "syllabus": str(row.get("syllabus", "")), "objectives": str(row.get("objectives", "")), "bibliography": str(row.get("bibliography", "")), "alert": row.get("alert")}
        if not discipline["name"] or len(discipline["name"]) > 250 or not (discipline["syllabus"].strip() or discipline["objectives"].strip()):
            raise HTTPException(422, "Cada disciplina precisa de nome e ementa ou objetivos.")
        if any(len(discipline[key]) > 100_000 for key in ("syllabus", "objectives", "bibliography")):
            raise HTTPException(422, "Um trecho de disciplina excede 100 mil caracteres.")
        if discipline["id"] in ids or len(discipline["id"]) > 100:
            raise HTTPException(422, "Os identificadores de disciplinas devem ser únicos.")
        ids.add(discipline["id"])
        for key, default, maximum in (("period", 1, 30), ("hours", 0, 5000), ("page", 1, 500)):
            try:
                value = int(row.get(key, default) or default)
            except (ValueError, TypeError):
                raise HTTPException(422, f"Confira o campo {key} da disciplina.")
            if not 0 <= value <= maximum:
                raise HTTPException(422, f"Confira o campo {key} da disciplina.")
            discipline[key] = value
        result.append(discipline)
    return result


def new_batch(config: dict, ppc: dict, jobs: list[dict], demo: bool = False) -> dict:
    disciplines = validate_disciplines(ppc.get("disciplines", []))
    if len(jobs) > 2000 or any(not str(job.get("title", "")).strip() or not str(job.get("description", "")).strip() for job in jobs):
        raise HTTPException(422, "Cada vaga precisa de título e descrição; limite de 2000 vagas.")
    if any(len(str(value)) > 100_000 for job in jobs for value in job.values()):
        raise HTTPException(422, "Uma vaga excede o limite de tamanho.")
    jobs, duplicates = deduplicate_jobs(jobs)
    collecting = config["source"] == "jobspy"
    body = {"created_at": now(), "status": "review", "demo": demo, "config": config,
            "ppc": {"filename": clean_filename(ppc.get("filename")), "size": ppc.get("size", 0), "pages": ppc.get("pages", 1)},
            "disciplines": disciplines, "jobs": jobs, "results": None, "corrections": 0, "llm_calls": 0, "logs": [], "annotations": {},
            "dictionary_snapshot": store().dictionary_edits(), "collection": {"running": collecting, "count": len(jobs), "duplicates": duplicates, "target": config["target"], "partial": False},
            "stages": [{"key": "collection", "label": "Coleta de vagas", "status": "running" if collecting else "completed", "detail": "Preparando coleta JobSpy." if collecting else f"{len(jobs)} vagas importadas; {duplicates} duplicadas removidas.", "duration": 0},
                       {"key": "segmentation", "label": "Segmentação do PPC", "status": "completed", "detail": f"{len(disciplines)} disciplinas aguardando revisão humana.", "duration": 0},
                       {"key": "extraction", "label": "Extração de competências", "status": "waiting", "detail": "Aguardando confirmação do PPC.", "duration": 0},
                       {"key": "association", "label": "Associação vaga–disciplina", "status": "waiting", "detail": "Aguardando extração.", "duration": 0},
                       {"key": "classification", "label": "Classificação por área", "status": "waiting", "detail": "Regra por título e descrição da vaga.", "duration": 0},
                       {"key": "indicators", "label": "Cálculo dos indicadores", "status": "waiting", "detail": "Aguardando associações.", "duration": 0}]}
    body["validation"] = validation_result(body)
    log(body, "Lote criado. Dicionário congelado nesta execução; alterações de curadoria valerão para o próximo lote.")
    return store().create(body)


@app.get("/api/batches")
def list_batches():
    return [{"id": batch["id"], "created_at": batch["created_at"], "status": batch["status"], "demo": batch["demo"], "config": batch["config"],
             "jobs_count": len(batch["jobs"]), "disciplines_count": len(batch["disciplines"]), "collection": batch.get("collection"),
             "course": batch["config"]["course"], "city": batch["config"]["city"], "jobs": len(batch["jobs"])} for batch in store().all()]


@app.post("/api/batches", status_code=201)
def create_batch(body: NewBatch, background: BackgroundTasks):
    config = validate_config(body.config)
    if config["source"] == "csv" and not body.jobs:
        raise HTTPException(422, "Importe um CSV ou XLSX de vagas antes de rodar.")
    if config["source"] == "demo":
        raise HTTPException(422, "Use o endpoint de demonstração para dados ilustrativos.")
    if config["source"] == "jobspy" and importlib.util.find_spec("jobspy") is None:
        raise HTTPException(422, "JobSpy não está instalado neste ambiente. Importe CSV/XLSX ou instale server/requirements-jobspy.txt.")
    batch = new_batch(config, body.ppc, body.jobs)
    if config["source"] == "jobspy":
        background.add_task(collect_jobs, batch["id"])
    return public_batch(batch)


@app.post("/api/demo", status_code=201)
def create_demo():
    from .demo import demo_data
    data = demo_data()
    config = validate_config({**data["config"], "source": "demo"})
    batch = new_batch(config, {**data["ppc"], "disciplines": data["disciplines"]}, data["jobs"], demo=True)
    store().update(batch["id"], lambda current: current.update(status="processing"))
    process_batch(batch["id"])
    return public_batch(batch_or_404(batch["id"]))


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: int):
    return public_batch(batch_or_404(batch_id))


@app.patch("/api/batches/{batch_id}/disciplines")
def edit_disciplines(batch_id: int, body: DisciplineEdit):
    batch_or_404(batch_id)
    disciplines = validate_disciplines(body.disciplines)
    def change(batch):
        if batch["status"] != "review":
            raise HTTPException(409, "Só é possível editar o PPC durante a revisão. Reexecute em um novo lote para preservar o histórico.")
        batch.update(disciplines=disciplines, corrections=body.corrections)
        batch.pop("sample", None)
        stage(batch, "segmentation", "completed", f"{len(disciplines)} disciplinas revisadas; bibliografia fora da cobertura.")
        log(batch, f"Revisão salva: {len(disciplines)} disciplinas.")
    return public_batch(store().update(batch_id, change))


@app.post("/api/batches/{batch_id}/confirm")
def confirm_batch(batch_id: int, background: BackgroundTasks):
    batch_or_404(batch_id)
    def change(batch):
        if batch["status"] != "review":
            raise HTTPException(409, "Este lote já foi confirmado ou encerrado.")
        if batch.get("collection", {}).get("running"):
            raise HTTPException(409, "A coleta ainda está em andamento. Aguarde a conclusão para confirmar.")
        if not batch["jobs"]:
            raise HTTPException(422, "Nenhuma vaga disponível. Crie um novo lote com um CSV ou uma coleta válida.")
        batch["status"] = "processing"
        log(batch, "PPC confirmado. Iniciando análise com as disciplinas revisadas.")
    batch = store().update(batch_id, change)
    background.add_task(process_batch, batch_id)
    return public_batch(batch)


@app.post("/api/batches/{batch_id}/cancel")
def cancel_batch(batch_id: int):
    batch_or_404(batch_id)
    def change(batch):
        if batch["status"] in ("completed", "failed"):
            raise HTTPException(409, "Este lote já foi encerrado.")
        batch["status"] = "cancelled"
        batch["collection"]["running"] = False
        for item in batch["stages"]:
            if item["status"] == "running":
                item.update(status="warning", detail="Cancelado pelo usuário; resultados incompletos não foram publicados.")
        log(batch, "Execução cancelada pelo usuário.", "warning")
    return public_batch(store().update(batch_id, change))


@app.post("/api/batches/{batch_id}/decisions")
def save_decision(batch_id: int, body: Decision):
    batch_or_404(batch_id)
    def change(batch):
        if batch["status"] != "completed":
            raise HTTPException(409, "Aguarde os resultados para revisar as evidências.")
        association = next((row for row in batch["results"].get("associations", []) if str(row.get("id")) == body.association_id), None)
        if association is None:
            raise HTTPException(404, "Associação não encontrada.")
        association.update(decision=body.decision, human_decision=body.decision)
        log(batch, f"Decisão humana registrada na associação {body.association_id}: {body.decision or 'removida'}. Indicadores automáticos preservados.")
    return public_batch(store().update(batch_id, change))


def collect_jobs(batch_id: int):
    """Bounded retries, cancellation between requests, and honest partial collection."""
    started = time.monotonic()
    try:
        from jobspy import scrape_jobs
        batch = batch_or_404(batch_id)
        config, collected, raw_count = batch["config"], [], 0
        platform = {"google vagas": "google"}.get(config["platform"].lower(), config["platform"].lower())
        for index, term in enumerate(config["terms"], 1):
            if batch_or_404(batch_id)["status"] == "cancelled" or len(collected) >= config["target"]:
                break
            store().update(batch_id, lambda current: stage(current, "collection", "running", f"Termo {index} de {len(config['terms'])}: {term}; {len(collected)} vagas únicas."))
            frame = None
            for attempt in range(1, 4):
                if batch_or_404(batch_id)["status"] == "cancelled":
                    return
                try:
                    frame = scrape_jobs(site_name=[platform], search_term=term, google_search_term=f"{term} {config['city']}" if platform == "google" else None,
                                        location=config["city"], distance=round(config["radius"] / 1.609344), results_wanted=min(config["target"] - len(collected), 500),
                                        country_indeed="Brazil", description_format="plain", fetch_description=True, verbose=0)
                    break
                except Exception as exc:
                    # Never persist exception contents: remote libraries may include credentials or request URLs.
                    store().update(batch_id, lambda current: log(current, f"Coleta falhou para '{term}' (tentativa {attempt}/3; {type(exc).__name__}).", "warning"))
                    if attempt < 3:
                        time.sleep(min(attempt * 2, 4))
            if frame is not None and not frame.empty:
                rows = []
                for item in frame.fillna("").to_dict(orient="records"):
                    description = str(item.get("description", ""))
                    title = str(item.get("title", ""))
                    if not description.strip() or not title.strip():
                        continue
                    rows.append({"title": title, "description": description[:100000], "company": str(item.get("company", "")), "city": str(item.get("location", config["city"])), "external_id": str(item.get("id", "")),
                                 "date": str(item.get("date_posted", "")), "url": str(item.get("job_url", "")), "source": f"{platform} via JobSpy"})
                raw_count += len(rows)
                collected, _ = deduplicate_jobs(collected + rows)
                collected = collected[:config["target"]]
                def progress(current):
                    if current["status"] == "cancelled":
                        return
                    current["jobs"] = collected
                    current["collection"].update(count=len(collected), duplicates=max(0, raw_count-len(collected)))
                store().update(batch_id, progress)
            if index < len(config["terms"]) and len(collected) < config["target"]:
                time.sleep(1)
        def finish(current):
            if current["status"] == "cancelled":
                return
            partial = len(current["jobs"]) < config["target"]
            current["collection"].update(running=False, partial=partial, count=len(current["jobs"]), raw_count=raw_count)
            detail = f"{len(current['jobs'])} vagas únicas de {raw_count} registros; meta {config['target']}." + (" Coleta parcial: a fonte não entregou a meta." if partial else "")
            stage(current, "collection", "warning" if partial else "completed", detail, time.monotonic() - started)
            log(current, detail, "warning" if partial else "info")
        store().update(batch_id, finish)
    except Exception as exc:
        def failure(current):
            if current["status"] == "cancelled":
                return
            current["collection"].update(running=False, partial=True)
            stage(current, "collection", "warning", f"Coleta indisponível ({type(exc).__name__}). Importe CSV em um novo lote.", time.monotonic()-started)
            log(current, "A coleta não pôde ser concluída; nenhuma vaga foi inventada.", "warning")
        store().update(batch_id, failure)


def process_batch(batch_id: int):
    started = time.monotonic()
    batch = batch_or_404(batch_id)
    if batch["status"] != "processing":
        return
    store().update(batch_id, lambda current: stage(current, "extraction", "running", "Analisando ementas, objetivos e descrições das vagas; bibliografia excluída."))
    try:
        classified_at = time.monotonic()
        classified_jobs = [{**job, "area": canonical_area(job.get("area"), job["title"], job["description"])} for job in batch["jobs"]]
        classification_counts = Counter(job["area"] for job in classified_jobs)
        classification_detail = "Áreas informadas normalizadas; áreas ausentes inferidas pelo título e depois pela descrição: " + ", ".join(f"{area}: {count}" for area, count in sorted(classification_counts.items())) + "."
        def save_classification(current):
            if current["status"] == "processing":
                current["jobs"] = classified_jobs
                if any(item["key"] == "classification" for item in current["stages"]):
                    stage(current, "classification", "completed", classification_detail, time.monotonic()-classified_at)
                log(current, classification_detail)
        store().update(batch_id, save_classification)
        batch["jobs"] = classified_jobs
        results = analyze(batch["disciplines"], batch["jobs"], batch["config"], dictionary_overrides=batch["dictionary_snapshot"],
                          should_cancel=lambda: batch_or_404(batch_id)["status"] == "cancelled")
        def complete(current):
            if current["status"] != "processing":
                return
            current.update(status="completed", results=results, completed_at=now(), llm_calls=results.get("summary", {}).get("llm_calls", 0))
            elapsed = time.monotonic() - started
            methods = results.get("method_status", {})
            missing_extract = [name for name in ("M1", "M2", "M3") if methods.get(name, {}).get("requested") and not methods[name].get("executed")]
            missing_association = [name for name in ("A1", "A2") if methods.get(name, {}).get("requested") and not methods[name].get("executed")]
            stage(current, "extraction", "warning" if missing_extract else "completed", "Competências extraídas com os métodos disponíveis." + (f" Não executados: {', '.join(missing_extract)}. Veja o log." if missing_extract else ""), elapsed)
            stage(current, "association", "warning" if missing_association else "completed", f"{len(results.get('associations', []))} associações com evidência verificável." + (f" Não executados: {', '.join(missing_association)}. Veja o log." if missing_association else ""))
            stage(current, "indicators", "completed", "Indicadores calculados. Validação depende de anotações humanas.")
            current["validation"] = validation_result(current)
            log(current, "Análise concluída. Cada indicador usa exclusivamente os dados deste lote.")
            for method, status in results.get("method_status", {}).items():
                log(current, f"Método {method}: {json.dumps(status, ensure_ascii=False) if isinstance(status, dict) else status}")
        store().update(batch_id, complete)
    except Exception as exc:
        def failure(current):
            if current["status"] == "cancelled":
                return
            current.update(status="failed", error=f"A análise falhou ({type(exc).__name__}). Revise os arquivos e os métodos; veja o log do servidor para diagnóstico.")
            stage(current, "extraction", "failed", current["error"], time.monotonic() - started)
            log(current, current["error"], "error")
        store().update(batch_id, failure)
        import logging
        logging.getLogger("tcc").exception("Batch %s failed", batch_id)


def completed_batch(batch_id: int) -> dict:
    batch = batch_or_404(batch_id)
    if batch["status"] != "completed":
        raise HTTPException(409, "Os resultados deste lote ainda não estão disponíveis.")
    return batch


def attachment(data: bytes, filename: str, media_type: str) -> Response:
    return Response(data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@app.get("/api/batches/{batch_id}/export")
def export_batch(batch_id: int, format: Literal["xlsx", "csv"] = "xlsx", tables: str = "indicators,gaps,disciplines,jobs,associations,validation"):
    batch = completed_batch(batch_id)
    all_tables = export_tables(batch)
    selected = [item.strip() for item in tables.split(",") if item.strip()]
    if not selected or any(item not in all_tables for item in selected):
        raise HTTPException(422, "Selecione tabelas de exportação válidas.")
    chosen = {name: all_tables[name] for name in selected}
    if format == "csv":
        return attachment(csv_archive(chosen), f"lote-{batch_id}-resultados.zip", "application/zip")
    return attachment(workbook(chosen), f"lote-{batch_id}-resultados.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/batches/{batch_id}/sample")
def sample_batch(batch_id: int):
    batch = batch_or_404(batch_id)
    if batch["status"] not in ("review", "completed") or not batch["jobs"] or batch.get("collection", {}).get("running"):
        raise HTTPException(409, "A amostra fica disponível após a coleta de vagas, durante a revisão e após os resultados.")
    tables = make_sample(batch, build_dictionary(batch.get("dictionary_snapshot", [])))
    # Persist the unit IDs so future imports are checked against exactly this frozen sample.
    snapshot = {"extraction": [{key: row[key] for key in ("source", "document_id", "competency_id")} for row in tables["extraction"]],
                "associations": [{key: row[key] for key in ("job_id", "discipline_id")} for row in tables["associations"]]}
    store().update(batch_id, lambda current: current.update(sample=snapshot))
    return attachment(workbook(tables), f"lote-{batch_id}-amostra-cega.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/batches/{batch_id}/annotations")
async def annotations_batch(batch_id: int, file: UploadFile = File(...), annotator: Literal["primary", "secondary"] = Form("primary")):
    batch = completed_batch(batch_id)
    if not batch.get("sample"):
        raise HTTPException(409, "Baixe a amostra deste lote antes de importar as anotações.")
    filename = clean_filename(file.filename)
    annotation = import_annotations(await read_upload(file), filename, batch["sample"])
    def change(current):
        current.setdefault("annotations", {})[annotator] = annotation
        current["validation"] = validation_result(current)
        log(current, f"Anotação {annotator} importada: {annotation['counts']['labels']} rótulos humanos.")
    return public_batch(store().update(batch_id, change))


@app.get("/api/batches/{batch_id}/log")
def batch_log(batch_id: int):
    batch = batch_or_404(batch_id)
    lines = [f"Lote {batch_id} | DEMONSTRAÇÃO" if batch["demo"] else f"Lote {batch_id}", f"Criado em {batch['created_at']} | status {batch['status']}"]
    lines += [f"{row['time']} [{row['level'].upper()}] {row['message']}" for row in batch["logs"]]
    return attachment("\n".join(lines).encode("utf-8"), f"lote-{batch_id}.log", "text/plain; charset=utf-8")


# In production a single API process can serve the built React app and public files.
DIST_DIRECTORY = Path(__file__).resolve().parents[1] / "dist"
if DIST_DIRECTORY.is_dir():
    app.mount("/", StaticFiles(directory=DIST_DIRECTORY, html=True), name="frontend")
