"""Single canonical area vocabulary used by collection, import and analysis.

Classification is an explicit heuristic, not an LLM finding. A provided category
is normalized through known aliases; an unsupported provided category becomes
Outra. With no category, the job title is considered before its description, so
a programmer who uses a database is not automatically classified as a data job.
"""
import re
import unicodedata

CANONICAL_AREAS = ("Programação", "Análise", "Dados", "Suporte", "Infraestrutura", "Outra")


def _normalize(text):
    return "".join(char for char in unicodedata.normalize("NFKD", str(text or "").lower().strip()) if not unicodedata.combining(char))


_ALIASES = {
    "Programação": ("programacao", "desenvolvimento", "backend", "back-end", "back end", "frontend", "front-end", "front end", "full stack", "full-stack", "fullstack", "mobile", "desenvolvimento web", "engenharia de software", "qualidade", "quality assurance", "qa", "testes", "software development"),
    "Análise": ("analise", "analise de sistemas", "analista de sistemas", "negocios", "analise de negocios", "business analysis", "requisitos", "gestao", "gestao e produto", "produto", "product", "projetos", "gestao de projetos"),
    "Dados": ("dados", "data", "data science", "data engineering", "data analysis", "ciencia de dados", "engenharia de dados", "analise de dados", "analytics", "business intelligence", "bi", "inteligencia artificial", "machine learning", "ia", "ml", "banco de dados", "dba"),
    "Suporte": ("suporte", "suporte tecnico", "suporte de ti", "help desk", "helpdesk", "service desk", "atendimento tecnico"),
    "Infraestrutura": ("infraestrutura", "devops", "devsecops", "sre", "cloud", "nuvem", "redes", "seguranca", "seguranca da informacao", "ciberseguranca", "cybersecurity", "plataforma", "operacoes", "infrastructure"),
    "Outra": ("outra", "outras", "outro", "outros", "other", "nao classificada", "nao informada"),
}
AREA_ALIASES = {alias: canonical for canonical, aliases in _ALIASES.items() for alias in aliases}

_RULES = (
    ("Suporte", r"\b(?:suporte|help\s?desk|service\s?desk|atendimento tecnico)\b"),
    ("Dados", r"\b(?:dados|data\s+(?:science|engineering|analysis|scientist|engineer)|business intelligence|analytics|bi|machine learning|inteligencia artificial|dba)\b"),
    ("Infraestrutura", r"\b(?:infraestrutura|devops|devsecops|sre|redes|cloud|nuvem|plataforma|seguranca|cybersecurity|ciberseguranca)\b"),
    ("Programação", r"\b(?:desenvolv\w*|program\w*|software|front[ -]?end|back[ -]?end|full[ -]?stack|mobile|qa|qualidade|testes?)\b"),
    ("Análise", r"\b(?:analist\w*|analis\w*|requisit\w*|negocio\w*|produto|projet\w*|product owner|scrum master)\b"),
)


def infer_area(text):
    """Classify a title or description with stable ordered lexical rules."""
    text = _normalize(text)
    if text in AREA_ALIASES:
        return AREA_ALIASES[text]
    return next((area for area, pattern in _RULES if re.search(pattern, text)), "Outra")


def canonical_area(value, title="", description=""):
    """Normalize a label or infer a missing label from title, then description."""
    value = _normalize(value)
    if value:
        return AREA_ALIASES.get(value, "Outra")
    inferred = infer_area(title)
    return inferred if inferred != "Outra" else infer_area(description)
