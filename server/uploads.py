"""Bounded, local-only parsing of user supplied curriculum and vacancy files."""
from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from pathlib import PurePath

import fitz
import pandas as pd
from fastapi import HTTPException, UploadFile
from .areas import canonical_area, infer_area

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_ROWS = 2000


def clean_filename(name: str | None) -> str:
    return PurePath((name or "arquivo").replace("\\", "/")).name[:160]


async def read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if not data:
        raise HTTPException(422, "O arquivo está vazio.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "O arquivo excede o limite de 20 MB.")
    return data


def normalized(value) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(value).lower().strip()) if not unicodedata.combining(c))


def segment_ppc(data: bytes, filename: str) -> dict:
    if not data.startswith(b"%PDF-"):
        raise HTTPException(422, "Envie um PDF válido com texto extraível.")
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise HTTPException(422, "Não foi possível abrir o PDF. O arquivo pode estar corrompido.")
    with document:
        if document.needs_pass:
            raise HTTPException(422, "PDF protegido por senha. Envie uma versão sem proteção e com texto extraível.")
        if len(document) > 500:
            raise HTTPException(422, "O PDF excede o limite de 500 páginas.")
        texts = [page.get_text("text", sort=True) for page in document]
        if sum(len(re.sub(r"\W", "", text)) for text in texts) < 80:
            raise HTTPException(422, "PDF escaneado ou sem texto extraível. O MVP não faz OCR; exporte o PPC como PDF textual.")
        if sum(map(len, texts)) > 3_000_000:
            raise HTTPException(422, "O texto do PDF é muito extenso para este MVP.")
        disciplines = []
        heading = re.compile(r"(?im)^\s*(?:disciplina|componente\s+curricular|unidade\s+curricular)\s*[:–—-]\s*(.{3,180})\s*$")
        current = None
        for page_number, text in enumerate(texts, 1):
            matches = list(heading.finditer(text))
            if not matches:
                if current:
                    current["raw"] += "\n" + text
                continue
            if current:
                current["raw"] += "\n" + text[:matches[0].start()]
            for index, match in enumerate(matches):
                current = {"name": match.group(1).strip(), "page": page_number,
                           "raw": text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]}
                disciplines.append(current)
        if not disciplines:
            # Real curricula vary greatly. Never pretend an unrecognized layout is a reliable segmentation.
            disciplines = [{"name": f"Trecho da página {i}", "page": i, "raw": text,
                            "alert": "Formato não reconhecido. Revise o nome, divida ou una as disciplinas antes de confirmar."}
                           for i, text in enumerate(texts, 1) if text.strip()]
        if len(disciplines) > 400:
            raise HTTPException(422, "Foram encontrados mais de 400 trechos. Envie apenas a seção curricular do PPC.")
        parsed = []
        for index, item in enumerate(disciplines, 1):
            raw = item["raw"].strip()
            bibliography = re.search(r"(?im)^\s*(?:bibliografia|refer[eê]ncias)(?:\s+(?:b[aá]sica|complementar|bibliogr[aá]ficas))?\s*[:–—-]?", raw)
            counting = raw[:bibliography.start()] if bibliography else raw
            period = re.search(r"(?:per[ií]odo|semestre)\s*[:–—-]?\s*(\d{1,2})|\b(\d{1,2})[º°o]?\s*(?:per[ií]odo|semestre)", raw, re.I)
            hours = re.search(r"(?:carga\s+hor[aá]ria|c\.?\s*h\.?)\s*[:–—-]?\s*(\d{1,4})", raw, re.I)
            syllabus = re.search(r"(?is)ementa\s*[:–—-]?\s*(.*?)(?=\n\s*objetivos?\b|\Z)", counting)
            objectives = re.search(r"(?is)objetivos?(?:\s+gerais?|\s+espec[ií]ficos?)?\s*[:–—-]?\s*(.*)", counting)
            parsed.append({"id": f"d{index}", "name": item["name"], "period": int(next(x for x in period.groups() if x)) if period else 1,
                           "hours": int(hours.group(1)) if hours else 0, "page": item["page"],
                           "syllabus": (syllabus.group(1) if syllabus else counting).strip(),
                           "objectives": objectives.group(1).strip() if objectives else "",
                           "bibliography": raw[bibliography.start():].strip() if bibliography else "",
                           "alert": item.get("alert") or ("Carga horária não identificada; confira a segmentação." if not hours else None)})
        return {"filename": filename, "size": len(data), "pages": len(texts), "disciplines": parsed,
                "text_extractable": True, "warnings": ["A segmentação é assistida: confira os trechos antes de confirmar."]}


def read_tables(data: bytes, filename: str, max_rows: int = MAX_ROWS) -> dict[str, pd.DataFrame]:
    suffix = filename.lower().rsplit(".", 1)[-1]
    try:
        if suffix == "xlsx":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 60 * 1024 * 1024:
                    raise HTTPException(413, "O conteúdo descompactado do XLSX excede 60 MB.")
            return pd.read_excel(io.BytesIO(data), sheet_name=None, nrows=max_rows + 1, dtype=str, keep_default_na=False)
        if suffix != "csv":
            raise HTTPException(422, "Use um arquivo CSV ou XLSX.")
        text = None
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise HTTPException(422, "Codificação inválida. Salve o CSV em UTF-8.")
        delimiter = ";" if text.partition("\n")[0].count(";") > text.partition("\n")[0].count(",") else ","
        return {"data": pd.read_csv(io.StringIO(text), sep=delimiter, nrows=max_rows + 1, dtype=str, keep_default_na=False)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Não foi possível ler a planilha. Confira o formato e os cabeçalhos.")


def deduplicate_jobs(jobs: list[dict]) -> tuple[list[dict], int]:
    unique, seen = [], set()
    for item in jobs:
        job = {key: str(item.get(key, "") or "").strip() for key in ("title", "company", "city", "area", "date", "url", "description", "source")}
        external_id = str(item.get("external_id") or item.get("job_id") or "").strip()
        supplied_id = str(item.get("id") or "").strip()
        if not external_id and supplied_id and not re.fullmatch(r"j\d+", supplied_id):
            external_id = supplied_id
        # Internal jN identifiers must not collide across collection queries.
        keys = {("content", normalized(job["title"]), normalized(job["company"]), normalized(job["city"]))}
        if job["url"]:
            keys.add(("url", job["url"].rstrip("/")))
        if external_id:
            keys.add(("id", normalized(job["source"]), external_id))
        if keys & seen:
            seen.update(keys)
            continue
        seen.update(keys)
        if external_id:
            job["external_id"] = external_id
        job["id"] = f"j{len(unique) + 1}"
        job["area"] = canonical_area(job["area"], job["title"], job["description"])
        unique.append(job)
    return unique, len(jobs) - len(unique)


def parse_jobs(data: bytes, filename: str) -> dict:
    table = next(iter(read_tables(data, filename).values()))
    if len(table) > MAX_ROWS:
        raise HTTPException(422, f"Importe no máximo {MAX_ROWS} vagas por lote.")
    aliases = {"titulo": "title", "cargo": "title", "empresa": "company", "cidade": "city", "localizacao": "city", "location": "city",
               "area": "area", "data": "date", "date_posted": "date", "link": "url", "job_url": "url", "descricao": "description", "fonte": "source"}
    table.columns = [aliases.get(normalized(column), normalized(column)) for column in table.columns]
    if table.columns.duplicated().any():
        raise HTTPException(422, "Há colunas duplicadas no arquivo de vagas.")
    if not {"title", "description"}.issubset(table.columns):
        raise HTTPException(422, "O arquivo precisa das colunas título (title/cargo) e descrição (description/descricao). Opcionais: empresa, cidade, área, data e URL.")
    jobs, skipped = [], 0
    for row in table.to_dict(orient="records"):
        if not str(row.get("title", "")).strip() or not str(row.get("description", "")).strip():
            skipped += 1
            continue
        if any(len(str(value)) > 100_000 for value in row.values()):
            raise HTTPException(422, "Uma célula excede o limite de 100 mil caracteres.")
        jobs.append({**row, "source": row.get("source") or "CSV importado"})
    if not jobs:
        raise HTTPException(422, "Nenhuma vaga válida encontrada. Título e descrição são obrigatórios.")
    jobs, duplicates = deduplicate_jobs(jobs)
    return {"jobs": jobs, "count": len(jobs), "duplicates": duplicates,
            "warnings": ([f"{skipped} linha(s) sem título ou descrição ignorada(s)."] if skipped else [])}
