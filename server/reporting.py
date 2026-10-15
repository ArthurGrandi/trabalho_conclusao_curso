"""Reproducible exports and human evaluation. Empty labels never become negatives."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import zipfile
from collections import Counter
from datetime import datetime, timezone

import pandas as pd
from fastapi import HTTPException
from openpyxl import Workbook

from .uploads import read_tables, normalized


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_cell(value):
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        # Spreadsheet applications must never interpret user supplied descriptions as formulas.
        value = "".join(c for c in value if ord(c) >= 32 or c in "\n\r\t")
        if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
            value = "'" + value
        return value[:32760]
    return value


def workbook(tables: dict[str, list[dict]]) -> bytes:
    book = Workbook()
    book.remove(book.active)
    for name, rows in tables.items():
        sheet = book.create_sheet(name[:31])
        columns = list(dict.fromkeys(key for row in rows for key in row)) or ["informacao"]
        sheet.append(columns)
        for row in rows:
            sheet.append([safe_cell(row.get(column)) for column in columns])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(55, max(14, len(str(column[0].value)) + 2))
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def csv_archive(tables: dict[str, list[dict]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, rows in tables.items():
            stream = io.StringIO(newline="")
            columns = list(dict.fromkeys(key for row in rows for key in row)) or ["informacao"]
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows({key: safe_cell(value) for key, value in row.items()} for row in rows)
            archive.writestr(f"{name}.csv", "\ufeff" + stream.getvalue())
    return output.getvalue()


def export_tables(batch: dict) -> dict[str, list[dict]]:
    results = batch.get("results") or {}
    indicators = results.get("indicators", {})
    indicator_rows = []
    for key, value in indicators.items():
        values = value if isinstance(value, list) else [value]
        for index, item in enumerate(values):
            indicator_rows.append({"indicator": key, "index": index + 1, **(item if isinstance(item, dict) else {"value": item}),
                                   "batch_id": batch["id"], "demo": batch["demo"]})
    return {
        "indicators": indicator_rows,
        "gaps": [row for row in results.get("competencies", []) if row.get("status") in ("gap", "partial", "Lacuna", "Parcial", "lacuna", "parcial") and row.get("count", 0) > 0 and row.get("percent", 0) >= batch["config"].get("threshold", 5)],
        "disciplines": [dict(row, **next((item for item in results.get("discipline_contributions", []) if item.get("id", item.get("discipline_id")) == row["id"]), {})) for row in batch["disciplines"]],
        "jobs": batch["jobs"],
        "associations": results.get("associations", []),
        "validation": [dict(row, group="extraction") for row in batch.get("validation", {}).get("extraction", [])] + [dict(row, group="association") for row in batch.get("validation", {}).get("association", [])] or [{"status": "Sem anotações humanas; métricas de validação não calculadas."}],
    }


def make_sample(batch: dict, dictionary: list[dict]) -> dict[str, list[dict]]:
    rng = random.Random(f"curriculo-mercado:{batch['id']}")
    by_area = {}
    for job in batch["jobs"]:
        by_area.setdefault(job.get("area", "Outra"), []).append(job)
    jobs = []
    # Fixed stratified sample, independent of method predictions.
    for area in sorted(by_area):
        group = sorted(by_area[area], key=lambda row: str(row["id"]))
        jobs.extend(rng.sample(group, min(12, len(group))))
    jobs = jobs[:60]
    extraction = []
    for source, documents in (("jobs", jobs), ("ppc", batch["disciplines"])):
        for document in documents:
            text = document.get("title", "") + "\n" + document.get("description", "") if source == "jobs" else document.get("syllabus", "") + "\n" + document.get("objectives", "")
            for competency in dictionary:
                extraction.append({"source": source, "document_id": document["id"], "document_name": document.get("title", document.get("name", "")),
                                   "text": text, "competency_id": competency["id"], "competency": competency["name"], "present": ""})
    pairs = [(job, discipline) for job in jobs for discipline in batch["disciplines"]]
    selected = rng.sample(pairs, min(100, len(pairs)))
    associations = [{"job_id": job["id"], "title": job["title"], "description": job["description"], "discipline_id": discipline["id"],
                     "discipline_name": discipline["name"], "syllabus": discipline.get("syllabus", "") + "\n" + discipline.get("objectives", ""), "related": ""}
                    for job, discipline in selected]
    fingerprint = hashlib.sha256(json.dumps({"extraction": [(x["source"], x["document_id"], x["competency_id"]) for x in extraction], "pairs": [(x["job_id"], x["discipline_id"]) for x in associations]}, sort_keys=True).encode()).hexdigest()[:16]
    return {"extraction": extraction, "associations": associations, "guide": [
        {"item": "Lote", "instruction": str(batch["id"])},
        {"item": "Identificação da amostra", "instruction": fingerprint},
        {"item": "Extração", "instruction": "Na folha extraction, preencha present com 1 se a competência está explicitamente presente no texto; caso contrário 0. Não use a bibliografia como cobertura."},
        {"item": "Associação", "instruction": "Na folha associations, preencha related com 1 se a disciplina cobre competências exigidas na vaga; caso contrário 0."},
        {"item": "Anotação cega", "instruction": "Anote sem consultar saídas dos métodos. Não altere IDs, nomes de folhas nem cabeçalhos. Células em branco não são avaliadas."},
        {"item": "Amostra", "instruction": "Até 60 vagas, no máximo 12 por área, todas as disciplinas e até 100 pares sorteados. Seleção determinística independente de predições; mantenha a amostra de desenvolvimento à parte."},
    ]}


def _label(value):
    value = normalized(value)
    if value in ("", "nan", "none"):
        return None
    if value in ("1", "1.0", "sim", "true", "yes", "presente", "relacionado"):
        return True
    if value in ("0", "0.0", "nao", "false", "no", "ausente", "nao relacionado"):
        return False
    raise HTTPException(422, "Anotações devem ser 1 (sim), 0 (não) ou vazias.")


def import_annotations(data: bytes, filename: str, sample: dict) -> dict:
    tables = read_tables(data, filename, max_rows=100_000)
    allowed_extract = {(row["source"], row["document_id"], row["competency_id"]) for row in sample["extraction"]}
    allowed_pairs = {(row["job_id"], row["discipline_id"]) for row in sample["associations"]}
    labels = {"extraction": [], "associations": []}
    for name, frame in tables.items():
        name = normalized(name)
        if name not in ("extraction", "associations"):
            continue
        required = {"source", "document_id", "competency_id", "present"} if name == "extraction" else {"job_id", "discipline_id", "related"}
        if not required.issubset(frame.columns):
            raise HTTPException(422, f"A folha {name} deve preservar os cabeçalhos da amostra exportada.")
        seen = set()
        for row in frame.to_dict(orient="records"):
            value = _label(row["present" if name == "extraction" else "related"])
            if value is None:
                continue
            key = (row["source"], row["document_id"], row["competency_id"]) if name == "extraction" else (row["job_id"], row["discipline_id"])
            if key not in (allowed_extract if name == "extraction" else allowed_pairs):
                raise HTTPException(422, "Uma anotação possui IDs que não pertencem à amostra deste lote.")
            if key in seen:
                raise HTTPException(422, "Há anotações duplicadas para a mesma unidade.")
            seen.add(key)
            labels[name].append({**{column: row[column] for column in required if column not in ("present", "related")}, "label": value})
    if not any(labels.values()):
        raise HTTPException(422, "Nenhuma anotação válida encontrada. Preencha present ou related na amostra exportada.")
    return {"filename": filename, "imported_at": now(), "counts": {
        "jobs": len({row["document_id"] for row in labels["extraction"] if row["source"] == "jobs"}),
        "disciplines": len({row["document_id"] for row in labels["extraction"] if row["source"] == "ppc"}),
        "pairs": len(labels["associations"]), "labels": sum(map(len, labels.values()))}, "labels": labels}


def _metrics(gold: list[dict], predict, identify) -> tuple[dict, list[dict]]:
    counts = Counter()
    errors = []
    for row in gold:
        predicted = identify(row) in predict
        expected = bool(row["label"])
        counts["tp" if expected and predicted else "fp" if predicted else "fn" if expected else "tn"] += 1
        if expected != predicted:
            errors.append({**{key: value for key, value in row.items() if key != "label"}, "type": "fp" if predicted else "fn"})
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "tn": counts["tn"], "items": len(gold)}, errors


def validation_result(batch: dict) -> dict:
    annotations = batch.get("annotations", {})
    primary, secondary = annotations.get("primary"), annotations.get("secondary")
    result = {"status": "annotated" if primary else "pending", "primary": {k: v for k, v in primary.items() if k != "labels"} if primary else None,
              "secondary": {k: v for k, v in secondary.items() if k != "labels"} if secondary else None,
              "extraction": [], "association": [], "errors": [], "agreement": None,
              "scope_note": "Os métodos são comparados no mesmo suporte por fonte: somente documentos ou pares efetivamente processados por todos os métodos comparados. Saídas ausentes por limite, falha ou cancelamento não são rótulos negativos. Métodos sem saídas válidas na fonte não recebem métrica. Com A2, o recorte comum contém apenas pares candidatos efetivamente julgados; ele não representa todos os pares sorteados.",
              "supports": {"extraction": {}, "association": {}},
              "fingerprint": (batch.get("results") or {}).get("fingerprint")}
    if not primary:
        return result
    predictions = (batch.get("results") or {}).get("predicted_by_method", {})
    extraction_methods = {name: values for name, values in predictions.items() if name.startswith("M") and isinstance(values, dict)}
    for source in ("jobs", "ppc"):
        source_key = "job" if source == "jobs" else "ppc"
        full_gold = [row for row in primary["labels"]["extraction"] if row["source"] == source]
        full_documents = {str(row["document_id"]) for row in full_gold}
        supports = {}
        for method, values in extraction_methods.items():
            if method == "M3":
                processed = set(map(str, values.get("evaluated_documents", {}).get(source_key, [])))
                if not processed:
                    continue
                supports[method] = processed
            else:
                # M1/M2 run on every document, including documents with no positive match.
                supports[method] = full_documents
        common_documents = full_documents.copy()
        for processed in supports.values():
            common_documents &= processed
        gold = [row for row in full_gold if str(row["document_id"]) in common_documents]
        result["supports"]["extraction"][source] = {"documents": len(common_documents), "items": len(gold), "methods": list(supports), "excluded_items": len(full_gold) - len(gold)}
        scope_note = f"{len(common_documents)} documento(s), {len(gold)} rótulo(s), mesmo suporte para {', '.join(supports) or 'nenhum método'}; {len(full_gold) - len(gold)} rótulo(s) fora do suporte comum."
        if not gold:
            continue
        for method in supports:
            values = extraction_methods[method]
            predicted = {(str(row["document_id"]), str(row["competency_id"])) for row in values.get(source_key, [])}
            metrics, errors = _metrics(gold, predicted, lambda row: (str(row["document_id"]), str(row["competency_id"])))
            result["extraction"].append({**metrics, "documents": len(common_documents), "source": source, "method": method, "target": .8 if source == "jobs" else .75, "scope_note": scope_note})
            result["errors"].extend({**error, "source": source, "method": method} for error in errors)
    association_methods = {name: values for name, values in predictions.items() if name.startswith("A") and isinstance(values, list) and (name != "A2" or values)}
    full_gold = primary["labels"]["associations"]
    common_pairs = {(str(row["job_id"]), str(row["discipline_id"])) for row in full_gold}
    if "A2" in association_methods:
        common_pairs &= {(str(row["job_id"]), str(row["discipline_id"])) for row in association_methods["A2"]}
    gold = [row for row in full_gold if (str(row["job_id"]), str(row["discipline_id"])) in common_pairs]
    result["supports"]["association"] = {"pairs": len(common_pairs), "items": len(gold), "methods": list(association_methods), "excluded_items": len(full_gold) - len(gold), "candidate_only": "A2" in association_methods}
    scope_note = f"{len(gold)} par(es) no mesmo suporte para {', '.join(association_methods) or 'nenhum método'}. " + ("Recorte de candidatos efetivamente julgados por A2; não representa todos os pares sorteados." if "A2" in association_methods else "Pares com anotação humana da amostra sorteada.")
    if gold:
        for method, values in association_methods.items():
            predicted = {(str(row["job_id"]), str(row["discipline_id"])) for row in values if row.get("related", True)}
            metrics, errors = _metrics(gold, predicted, lambda row: (str(row["job_id"]), str(row["discipline_id"])))
            result["association"].append({**metrics, "method": method, "target": .70, "scope_note": scope_note})
            result["errors"].extend({**error, "method": method} for error in errors)
    if secondary:
        def combined(annotation):
            return {("extraction", row["source"], row["document_id"], row["competency_id"]): row["label"] for row in annotation["labels"]["extraction"]} | {
                ("associations", row["job_id"], row["discipline_id"]): row["label"] for row in annotation["labels"]["associations"]}
        left, right = combined(primary), combined(secondary)
        common = sorted(left.keys() & right.keys())
        if common:
            n = len(common)
            observed = sum(left[key] == right[key] for key in common) / n
            p_left = sum(left[key] for key in common) / n
            p_right = sum(right[key] for key in common) / n
            chance = p_left * p_right + (1 - p_left) * (1 - p_right)
            result["agreement"] = {"kappa": (observed - chance) / (1 - chance) if chance < 1 else None, "items": n,
                                   "observed_agreement": observed, "note": "Kappa indefinido quando todos os rótulos são iguais." if chance == 1 else None}
    return result
