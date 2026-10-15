"""Deterministic, evidence-first lexical curriculum × labour-market analysis.

The annexes name I1–I8 but do not provide mathematical definitions. FORMULAS
records the explicit operational choices used here. Conceptual candidates are
shown separately; they never masquerade as an LLM judgment or literal coverage.
Bibliography is never part of the matching input.
"""
from collections import Counter
from hashlib import sha256
import json
import re
import unicodedata

from .dictionary import build_dictionary, normalize
from .llm import LLMClient, llm_status
from .areas import canonical_area


FORMULAS = {
    "i1": "100 × vagas distintas que citam a competência / vagas do recorte. Cada competência conta uma vez por vaga.",
    "i2": "100 × Σ frequência das competências com ocorrência literal no PPC / Σ frequências de todas as competências demandadas. Parcial por conceito recebe peso 0 em I2.",
    "i3": "Competências sem ocorrência literal no PPC com I1 ≥ limiar configurado. Inclui candidatas apenas por conceito, explicitamente marcadas como parciais.",
    "i4": "100 × Σ frequência das competências com ocorrência literal OU do conceito relacionado no PPC / Σ frequências. É um limite lexical conceitual, não prova de equivalência curricular.",
    "i5": "I2 recalculado nas vagas de cada área, usando o mesmo conjunto de disciplinas e sem ponderação subjetiva.",
    "i6": "100 × Σ frequências das competências literalmente presentes na disciplina / Σ frequências de todas as competências demandadas. A soma pode exceder I2 porque disciplinas se sobrepõem.",
    "i7": "Competências literalmente presentes em ementa/objetivos do PPC e ausentes em todas as vagas do recorte.",
    "i8": "Jaccard(A,B) = |vagas com A ∩ vagas com B| / |vagas com A ∪ vagas com B|. União vazia recebe 0.",
}

AMBIGUOUS_ALIASES = {"c", "r", "go", "ml", "ai", "ia"}
NEGATION_BEFORE = re.compile(
    r"(?:nao\s+(?:(?:e|eh|sera)\s+)?(?:necessari[oa]|obrigatori[oa]|exigid[oa])|"
    r"nao\s+(?:exigimos|exige|requer|precisa|necessita|precisamos)|"
    r"sem\s+(?:necessidade|exigencia|experiencia|conhecimento)|"
    r"dispens(?:a|avel|amos)(?:\s+(?:conhecimento|experiencia))?)\b[^.;!?:\n]{0,95}$"
)
NEGATION_AFTER = re.compile(r"^\s*(?:(?:,|\(|\[)\s*)?(?:nao\s+(?:(?:e|eh|sera)\s+)?(?:necessari[oa]|obrigatori[oa]|exigid[oa])|dispensavel)\b")
ADVERSATIVE = re.compile(r"\b(?:mas|porem|contudo|entretanto)\b")
BIBLIOGRAPHY_HEADING = re.compile(r"(?im)^\s*(?:bibliografia|refer[eê]ncias)(?:\s+(?:b[aá]sica|complementar|bibliogr[aá]ficas))?\s*[:–—-]?")


def _normalized_offsets(value):
    text = str(value or "")
    chars, offsets = [], []
    for index, char in enumerate(text):
        for transformed in unicodedata.normalize("NFKD", char).lower():
            if not unicodedata.combining(transformed):
                chars.append(transformed)
                offsets.append(index)
    return text, "".join(chars), offsets


def _pattern(alias):
    words = re.split(r"\s+", normalize(alias).strip())
    escaped = r"\s+".join(re.escape(word) for word in words)
    return re.compile(r"(?<![\w+#])" + escaped + r"(?![\w+#])")


def _is_negated(normalized, start, end):
    before = normalized[max(0, start - 130):start]
    # A contrast resets the scope: "não exige Java, mas Python é necessário".
    before = ADVERSATIVE.split(before)[-1]
    if re.search(r"\bnao\s+(?:so|apenas|somente)\b", before):
        return False
    return bool(NEGATION_BEFORE.search(before) or NEGATION_AFTER.search(normalized[end:end + 85]))


def _excerpt(text, start, end, radius=105):
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    # Retain an exact, contiguous substring, so verification is mechanical.
    return text[left:right].strip()


def find_matches(value, entry):
    """Return genuine positive occurrences, preserving source substrings.

    Escaped aliases use token boundaries (Java ≠ JavaScript, C ≠ C++/C#).
    Ambiguous short aliases require context within 90 characters. Negated
    requirements are suppressed; bibliography is excluded by the caller.
    """
    text, normalized, offsets = _normalized_offsets(value)
    if not normalized:
        return []
    matches, spans = [], []
    aliases = sorted(set([entry["name"]] + entry.get("synonyms", [])), key=len, reverse=True)
    for alias in aliases:
        for match in _pattern(alias).finditer(normalized):
            start, end = match.span()
            if any(start < previous_end and end > previous_start for previous_start, previous_end in spans):
                continue
            if normalize(alias) == "r" and normalized[end:end + 1] == "$":
                continue
            if normalize(alias) in AMBIGUOUS_ALIASES:
                vicinity = normalized[max(0, start - 90):min(len(normalized), end + 90)]
                contexts = entry.get("context", [])
                if not contexts or not any(_pattern(word).search(vicinity) for word in contexts):
                    continue
            if _is_negated(normalized, start, end):
                continue
            source_start, source_end = offsets[start], offsets[end - 1] + 1
            spans.append((start, end))
            matches.append({"alias": alias, "matched": text[source_start:source_end],
                            "start": source_start, "end": source_end,
                            "text": _excerpt(text, source_start, source_end)})
    return sorted(matches, key=lambda item: item["start"])


def _discipline_sections(discipline):
    # Names alone do not establish curricular coverage. Only teachable content.
    sections = []
    for section in ("syllabus", "objectives"):
        text = str(discipline.get(section) or "")
        bibliography = BIBLIOGRAPHY_HEADING.search(text)
        sections.append((section, text[:bibliography.start()] if bibliography else text))
    return sections


def _job_sections(job):
    return [("title", str(job.get("title") or "")),
            ("description", str(job.get("description") or ""))]


def _extract(entries, disciplines, jobs):
    result = {}
    for entry in entries:
        item = {"jobs": {}, "disciplines": {}}
        for source, documents, sections in (("job", jobs, _job_sections), ("ppc", disciplines, _discipline_sections)):
            destination = "jobs" if source == "job" else "disciplines"
            for document in documents:
                document_id = str(document["id"])
                evidence = []
                for section, text in sections(document):
                    matches = find_matches(text, entry)
                    for match in matches[:2]:
                        evidence.append({"source": source, "source_id": document_id,
                                         "text": match["text"], "page": document.get("page") if source == "ppc" else None,
                                         "section": section, "matched": match["matched"]})
                if evidence:
                    item[destination][document_id] = evidence
        result[entry["id"]] = item
    return result


def _predictions(extracted):
    return {source: [{"document_id": document_id, "competency_id": competency_id}
                     for competency_id, matches in extracted.items()
                     for document_id in matches["jobs" if source == "job" else "disciplines"]]
            for source in ("job", "ppc")}


def _percent(value, denominator):
    return round(100 * value / denominator, 2) if denominator else 0.0


def _tags(config):
    value = config.get("tags") or ""
    if isinstance(value, list):
        return [normalize(tag).strip() for tag in value if str(tag).strip()]
    return [normalize(tag).strip() for tag in re.split(r"[,;\n]", str(value)) if tag.strip()]


def _unknown_terms(jobs, entries):
    """Conservative suggestions, not extracted competencies or indicators."""
    known = {normalize(alias) for entry in entries for alias in [entry["name"]] + entry.get("synonyms", [])}
    known_tokens = {token for phrase in known for token in re.findall(r"\w+", phrase)}
    common = {"ti", "clt", "pj", "br", "sc", "sp", "pr", "rs", "rh", "pc", "sla", "sre", "brasil", "empresa", "vaga", "vagas", "requisitos", "diferenciais", "responsabilidades", "experiencia", "conhecimento", "desenvolvedor", "analista", "engenheiro", "especialista", "tecnico", "coordenador", "demonstracao", "sintetica", "sintetico", "remoto", "junior", "pleno", "senior", "trabalho", "conhecimentos", "pt", "br", "a1", "m2", "csv", "pdf", "api", "apis", "sql", "tcp", "dns"}
    candidates = {}
    for job in jobs:
        text = str(job.get("description") or "")
        terms = set()
        for match in re.finditer(r"\b(?:[A-Z][A-Za-z0-9]*[+#.]?[A-Za-z0-9]*|[a-z]+(?:[A-Z][a-z]+)+)\b", text):
            prefix = text[:match.start()].rstrip()
            if not prefix or prefix[-1] in ".!?:\n":
                continue  # Avoid ordinary capitalized verbs at sentence starts.
            terms.add(match.group())
        for term in terms:
            key = normalize(term)
            if len(key) < 3 or key in known or key in known_tokens or key in common or key.isdigit():
                continue
            bucket = candidates.setdefault(key, {"term": term, "job_ids": []})
            bucket["job_ids"].append(str(job["id"]))
    return [dict(item, count=len(item["job_ids"]), suggestion="Revisar antes de adicionar ao dicionário")
            for item in sorted(candidates.values(), key=lambda item: (-len(item["job_ids"]), item["term"]))[:20]]


def _run_llm(disciplines, jobs, dictionary, candidates, config, requested, should_cancel=None):
    """Optional model execution; incomplete documents never become negatives."""
    public_status = llm_status()
    response = {"status": public_status, "documents": [], "judgments": [], "competencies": [],
                "stats": {"calls": 0, "failed": 0, "cache_hits": 0, "discarded": 0,
                          "executed_methods": [], "unexecuted_methods": ["M3", "A2"]},
                "partial": False, "pending_documents": 0, "pending_judgments": 0, "cancelled": False}
    predictions, associations = {}, []
    if should_cancel and should_cancel():
        response["cancelled"] = True
        return response, predictions, associations
    if not requested & {"M3", "A2"} or not public_status["enabled"]:
        return response, predictions, associations
    client = LLMClient(max_calls=config.get("llm_limit", 3000))
    by_name = {entry["name"]: entry for entry in dictionary}
    consecutive_failures = 0
    stopped = False
    if "M3" in requested:
        documents = [("job", document, _job_sections) for document in jobs]
        documents += [("ppc", document, _discipline_sections) for document in disciplines]
        predicted = {"job": [], "ppc": [], "evaluated_documents": {"job": [], "ppc": []}}
        for source, document, sections in documents:
            if should_cancel and should_cancel():
                response["cancelled"] = stopped = True
                break
            text = "\n".join(value for _, value in sections(document))
            result = client.extract_competencies(text, source=source, competency_names=list(by_name))
            record = {"source": source, "document_id": document["id"], **result}
            response["documents"].append(record)
            if result["status"] == "completed":
                consecutive_failures = 0
                predicted["evaluated_documents"][source].append(document["id"])
                for found in result.get("competencies", []):
                    entry = by_name.get(found["name"])
                    if not entry:
                        continue
                    predicted[source].append({"document_id": document["id"], "competency_id": entry["id"]})
                    response["competencies"].append({"source": source, "source_id": document["id"],
                                                     "competency_id": entry["id"], "name": entry["name"],
                                                     "text": found["excerpt"], "page": document.get("page"),
                                                     "verified": True, "method": "M3"})
            elif result["status"] == "failed":
                consecutive_failures += 1
            if result["status"] == "budget_exhausted" or consecutive_failures >= 3:
                stopped = True
                break
        response["pending_documents"] = len(documents) - sum(item["status"] == "completed" for item in response["documents"])
        if any(predicted["evaluated_documents"].values()):
            predictions["M3"] = predicted
    if "A2" in requested:
        by_job = {item["id"]: item for item in jobs}
        by_discipline = {item["id"]: item for item in disciplines}
        by_entry = {item["id"]: item for item in dictionary}
        pair_totals = Counter((item["job_id"], item["discipline_id"]) for item in candidates)
        pair_done, pair_positive = Counter(), set()
        # Prioritize literal candidates. All ordering is stable across runs.
        candidates = sorted(candidates, key=lambda item: (item["verdict"] != "covers", item["id"]))
        for candidate in ([] if stopped else candidates):
            if should_cancel and should_cancel():
                response["cancelled"] = True
                break
            result = client.judge_pair(by_job[candidate["job_id"]], by_discipline[candidate["discipline_id"]], by_entry[candidate["competency_id"]])
            response["judgments"].append({"association_id": candidate["id"].replace("a1:", "a2:", 1), **result})
            if result["status"] == "completed":
                consecutive_failures = 0
                verdict = "none" if result["verdict"] == "does_not_cover" else result["verdict"]
                associations.append({**candidate, "id": candidate["id"].replace("a1:", "a2:", 1), "method": "A2",
                                     "verdict": verdict, "reason": result["reason"],
                                     "job_excerpt": result["job_excerpt"], "ppc_excerpt": result["ppc_excerpt"],
                                     "verified": True,
                                     "evidence": [{"source": "job", "source_id": candidate["job_id"], "text": result["job_excerpt"], "page": None, "section": "description"},
                                                  {"source": "ppc", "source_id": candidate["discipline_id"], "text": result["ppc_excerpt"], "page": candidate["page"], "section": "syllabus/objectives"}]})
                pair = candidate["job_id"], candidate["discipline_id"]
                pair_done[pair] += 1
                if verdict != "none":
                    pair_positive.add(pair)
            elif result["status"] == "failed":
                consecutive_failures += 1
            if result["status"] == "budget_exhausted" or consecutive_failures >= 3:
                break
        response["pending_judgments"] = len(candidates) - len(associations)
        pairs = [{"job_id": pair[0], "discipline_id": pair[1], "related": pair in pair_positive}
                 for pair in sorted(pair_done) if pair in pair_positive or pair_done[pair] == pair_totals[pair]]
        if pairs:
            predictions["A2"] = pairs
    response["stats"] = client.stats()
    response["partial"] = bool(response["pending_documents"] or response["pending_judgments"])
    return response, predictions, associations


def analyze(disciplines, jobs, config, dictionary_overrides=None, should_cancel=None):
    """Compute a reproducible snapshot without changing any input objects.

    A1 is a lexical candidate association, not pedagogical equivalence. Optional
    M3/A2 use the configured real model and verify quotes. They never replace the
    literal I2/I4 definitions. Human decisions are persisted separately by API.
    """
    disciplines = [dict(item, id=str(item["id"])) for item in disciplines]
    jobs = [dict(item, id=str(item["id"]), area=canonical_area(item.get("area"), item.get("title"), item.get("description"))) for item in jobs]
    config = dict(config)
    requested = set(config.get("methods") or ["M2", "A1"])
    dictionary = build_dictionary(dictionary_overrides)
    all_dictionary = dictionary
    tag_filters = _tags(config)
    if tag_filters:
        dictionary = [entry for entry in dictionary if any(tag in {normalize(entry["id"]), normalize(entry["name"]), normalize(entry["concept"]), normalize(entry["area"]), *(normalize(alias) for alias in entry.get("synonyms", []))} for tag in tag_filters)]
    # Always extract concept anchors even when a technology scope is chosen.
    # They supply partial candidates but are not independently added to demand.
    concept_names = {normalize(entry["concept"]) for entry in dictionary}
    anchor_entries = [entry for entry in all_dictionary if entry["type"] == "concept" and normalize(entry["name"]) in concept_names]
    anchored_names = {normalize(entry["name"]) for entry in anchor_entries}
    for entry in dictionary:
        if normalize(entry["concept"]) not in anchored_names:
            # A relation may name a concept outside the 73 counted entries.
            # It is eligible only as an anchor, never as extra demand.
            anchor_entries.append({"id": "concept-anchor-" + re.sub(r"[^a-z0-9]+", "-", normalize(entry["concept"])),
                                   "name": entry["concept"], "synonyms": [], "type": "concept",
                                   "concept": entry["concept"], "area": entry["area"]})
            anchored_names.add(normalize(entry["concept"]))
    extraction_entries = {entry["id"]: entry for entry in dictionary + anchor_entries}
    all_extracted = _extract(list(extraction_entries.values()), disciplines, jobs)
    active_name = "M2" if "M2" in requested else "M1" if "M1" in requested else None
    active_entries = [entry for entry in dictionary if active_name == "M2" or (active_name == "M1" and entry.get("base"))]
    concept_by_name = {normalize(entry["name"]): entry for entry in anchor_entries}
    competencies, associations, candidates = [], [], []
    for entry in active_entries:
        matches = all_extracted[entry["id"]]
        literal_ids = list(matches["disciplines"])
        anchor = concept_by_name.get(normalize(entry["concept"]))
        concept_matches = all_extracted.get(anchor["id"], {"disciplines": {}})["disciplines"] if anchor else {}
        conceptual_ids = [key for key in concept_matches if key not in literal_ids]
        job_ids = list(matches["jobs"])
        if not job_ids and not literal_ids:
            continue
        state = "covered" if literal_ids else "partial" if conceptual_ids else "gap"
        evidence = [ev for collection in (matches["jobs"], matches["disciplines"]) for values in collection.values() for ev in values]
        evidence += [dict(ev, conceptual=True) for values in concept_matches.values() for ev in values if ev["source_id"] not in literal_ids]
        competency = {**entry, "job_ids": job_ids, "discipline_ids": literal_ids,
                      "concept_discipline_ids": conceptual_ids, "count": len(job_ids),
                      "percent": _percent(len(job_ids), len(jobs)), "status": state,
                      "evidence": evidence, "method": active_name}
        competencies.append(competency)
        if not {"A1", "A2"} & requested:
            continue
        for job_id in job_ids:
            job_evidence = matches["jobs"][job_id][0]
            for discipline_id in literal_ids + conceptual_ids:
                literal = discipline_id in literal_ids
                ppc_evidence = (matches["disciplines"] if literal else concept_matches)[discipline_id][0]
                candidate = {
                    "id": f"a1:{job_id}:{discipline_id}:{entry['id']}",
                    "job_id": job_id, "discipline_id": discipline_id, "competency_id": entry["id"],
                    "method": "A1", "verdict": "covers" if literal else "partial",
                    "reason": (f"A1 encontrou {entry['name']} ou um sinônimo em ementa/objetivos. A ocorrência lexical não prova profundidade pedagógica."
                               if literal else f"A1 encontrou apenas o conceito {entry['concept']} no PPC; a tecnologia {entry['name']} não está explícita. Candidata parcial, fora de I2."),
                    "job_excerpt": job_evidence["text"], "ppc_excerpt": ppc_evidence["text"],
                    "page": ppc_evidence["page"], "verified": True, "decision": None,
                    "evidence": [job_evidence, ppc_evidence],
                }
                candidates.append(candidate)
                if "A1" in requested:
                    associations.append(candidate)
    competencies.sort(key=lambda item: (-item["count"], item["name"]))
    demanded = [item for item in competencies if item["count"]]
    total_demand = sum(item["count"] for item in demanded)
    literal_weight = sum(item["count"] for item in demanded if item["status"] == "covered")
    concept_weight = sum(item["count"] for item in demanded if item["status"] != "gap")
    threshold = float(config.get("threshold", 5))
    priority = [item for item in demanded if item["status"] != "covered" and item["percent"] >= threshold]
    i1 = [{"competency_id": item["id"], "name": item["name"], "count": item["count"], "percent": item["percent"], "status": item["status"]} for item in demanded]
    i2, i4 = _percent(literal_weight, total_demand), _percent(concept_weight, total_demand)
    area_indicators = []
    for area in sorted({str(job.get("area") or "Não classificada") for job in jobs}):
        area_job_ids = {job["id"] for job in jobs if str(job.get("area") or "Não classificada") == area}
        weights = [(item, len(set(item["job_ids"]) & area_job_ids)) for item in demanded]
        weight = sum(value for _, value in weights)
        area_indicators.append({"area": area, "jobs": len(area_job_ids), "demand_count": weight,
                                "coverage": _percent(sum(value for item, value in weights if item["status"] == "covered"), weight),
                                "conceptual_coverage": _percent(sum(value for item, value in weights if item["status"] != "gap"), weight)})
    contributions = []
    for discipline in disciplines:
        covered = [item for item in demanded if discipline["id"] in item["discipline_ids"]]
        value = sum(item["count"] for item in covered)
        contributions.append({"discipline_id": discipline["id"], "name": discipline.get("name", ""),
                              "percent": _percent(value, total_demand), "weight": value,
                              "competency_count": len(covered), "competency_ids": [item["id"] for item in covered]})
    contributions.sort(key=lambda item: (-item["percent"], item["name"]))
    top = demanded[:6]
    matrix = []
    for row in top:
        values = []
        for col in top:
            left, right = set(row["job_ids"]), set(col["job_ids"])
            union = len(left | right)
            values.append(round(len(left & right) / union, 4) if union else 0.0)
        matrix.append(values)
    cooccurrence = {"labels": [item["name"] for item in top], "ids": [item["id"] for item in top], "matrix": matrix}
    surplus = [{"competency_id": item["id"], "name": item["name"], "discipline_ids": item["discipline_ids"]} for item in competencies if item["count"] == 0 and item["discipline_ids"]]
    indicators = {"i1": i1, "i2": i2, "i3": [item["id"] for item in priority], "i4": i4,
                  "i5": area_indicators, "i6": contributions, "i7": surplus, "i8": cooccurrence,
                  "literal_coverage": i2, "conceptual_coverage": i4, "priority_gap_count": len(priority),
                  "literal_weight": literal_weight, "conceptual_weight": concept_weight, "total_demand": total_demand,
                  "job_count": len(jobs), "discipline_count": len(disciplines),
                  "demanded_competency_count": len(demanded), "ppc_competency_count": sum(bool(item["discipline_ids"]) for item in competencies)}
    predictions = {}
    for method in ("M1", "M2"):
        if method in requested:
            scoped = {entry["id"]: all_extracted[entry["id"]] for entry in dictionary if method == "M2" or entry.get("base")}
            predictions[method] = _predictions(scoped)
    if "A1" in requested:
        pairs = sorted({(item["job_id"], item["discipline_id"]) for item in associations})
        predictions["A1"] = [{"job_id": job_id, "discipline_id": discipline_id, "related": True} for job_id, discipline_id in pairs]
    llm, llm_predictions, llm_associations = _run_llm(disciplines, jobs, dictionary, candidates, config, requested, should_cancel)
    predictions.update(llm_predictions)
    associations.extend(llm_associations)
    method_status = {method: {"requested": method in requested, "available": method not in {"A2", "M3"} or llm["status"]["enabled"],
                              "executed": method in predictions,
                              "reason": (llm["status"]["message"] if not llm["status"]["enabled"] else "Resultados reais com citações verificadas; consulte execução parcial e falhas.") if method in {"A2", "M3"} else "Extração lexical com evidência verificável." if method != "A1" else "Associação lexical literal ou candidata por conceito."}
                     for method in ("M1", "M2", "M3", "A1", "A2")}
    fingerprint = sha256(json.dumps({"disciplines": disciplines, "jobs": jobs, "config": config, "dictionary": all_dictionary}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"competencies": competencies, "associations": associations, "indicators": indicators,
            "area_indicators": area_indicators, "discipline_contributions": contributions,
            "cooccurrence": cooccurrence, "priority_gaps": [item["id"] for item in priority],
            "ppc_without_demand": surplus, "unknown_terms": _unknown_terms(jobs, dictionary),
            "method_status": method_status, "predicted_by_method": predictions,
            "llm": llm, "formulas": FORMULAS, "fingerprint": fingerprint, "fingerprint_kind": "input",
            "summary": {"jobs": len(jobs), "disciplines": len(disciplines), "competencies": len(demanded),
                        "associations": len(associations), "bibliography_excluded": True,
                        "llm_calls": llm["stats"]["calls"], "extraction_method": active_name,
                        "source": config.get("source", "csv"), "demo": config.get("source") == "demo"},
            "warnings": (["Não há vagas no recorte; percentuais calculados como zero."] if not jobs else [])
                        + (["Selecione M1 ou M2 para calcular o painel lexical. A extração M3 é apresentada separadamente, quando configurada."] if not active_name else [])
                        + (["Execução LLM parcial: documentos ou julgamentos pendentes/falhos não entram como negativos na validação."] if llm["partial"] else [])
                        + (["O filtro de tags não encontrou entradas do dicionário."] if tag_filters and not dictionary else [])}
