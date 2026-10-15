"""Vocabulário inicial próprio do MVP (não é o dicionário ausente dos anexos).

As 73 entradas combinam tecnologias e conceitos; relações indicam candidatos
conceituais, nunca equivalência de conteúdo ou julgamento de um LLM. ``base``
seleciona um subconjunto transparente para a comparação M1 × M2. A curadoria
gera uma cópia para a próxima execução e não altera lotes existentes.
"""
from copy import deepcopy
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _entry(name, aliases, concept, area, base=False, kind="technology", context=None):
    identifier = re.sub(r"[^a-z0-9]+", "-", normalize(name)).strip("-")
    # Distinct IDs for the punctuation-bearing C family.
    identifier = {"C++": "cpp", "C#": "csharp", ".NET": "dotnet"}.get(name, identifier)
    result = {"id": identifier, "name": name, "synonyms": list(aliases),
              "concept": concept, "area": area, "type": kind, "base": base}
    if context:
        result["context"] = list(context)
    return result


D = "Programação"
DA = "Dados"
I = "Infraestrutura"
S = "Infraestrutura"
G = "Análise"
SU = "Suporte"

DICTIONARY = [
    _entry("Python", [], "Algoritmos e estruturas de dados", DA, True),
    _entry("Java", [], "Programação orientada a objetos", D, True),
    _entry("JavaScript", ["ECMAScript", "JS"], "Desenvolvimento web", D, True),
    _entry("TypeScript", [], "Desenvolvimento web", D, True),
    _entry("C", ["linguagem C"], "Algoritmos e estruturas de dados", D, context=["linguagem", "programacao", "programming", "embedded", "embarcado", "c++", "c/c++"]),
    _entry("C++", ["CPP"], "Programação orientada a objetos", D, True),
    _entry("C#", ["C Sharp", "CSharp"], "Programação orientada a objetos", D, True),
    _entry("PHP", [], "Desenvolvimento web", D, True),
    _entry("Ruby", [], "Desenvolvimento web", D),
    _entry("Go", ["Golang"], "Sistemas distribuídos", D, context=["golang", "linguagem", "backend", "back-end", "programacao", "microservicos", "desenvolvimento"]),
    _entry("Rust", [], "Algoritmos e estruturas de dados", D),
    _entry("R", ["linguagem R", "RStudio"], "Estatística", DA, context=["estatistica", "dados", "analise", "rstudio", "linguagem", "data science", "modelos"]),
    _entry("Swift", [], "Programação orientada a objetos", D),
    _entry("Kotlin", [], "Programação orientada a objetos", D),
    _entry("HTML", ["HTML5"], "Desenvolvimento web", D, True),
    _entry("CSS", ["CSS3"], "Desenvolvimento web", D, True),
    _entry("React", ["React.js", "ReactJS"], "Desenvolvimento web", D, True),
    _entry("Angular", ["AngularJS"], "Desenvolvimento web", D, True),
    _entry("Vue.js", ["Vue", "VueJS"], "Desenvolvimento web", D),
    _entry("Node.js", ["NodeJS", "Node"], "Desenvolvimento web", D, True),
    _entry("Django", [], "Desenvolvimento web", D),
    _entry("Flask", [], "Desenvolvimento web", D),
    _entry("Spring", ["Spring Boot", "SpringBoot"], "Programação orientada a objetos", D),
    _entry(".NET", ["Dotnet", "ASP.NET", "ASP NET"], "Programação orientada a objetos", D, True),
    _entry("Laravel", [], "Desenvolvimento web", D),
    _entry("SQL", ["Structured Query Language"], "Banco de dados", DA, True),
    _entry("PostgreSQL", ["Postgres"], "Banco de dados", DA, True),
    _entry("MySQL", [], "Banco de dados", DA, True),
    _entry("MongoDB", ["Mongo"], "Banco de dados", DA, True),
    _entry("Redis", [], "Banco de dados", DA),
    _entry("Oracle", ["Oracle Database"], "Banco de dados", DA),
    _entry("SQLite", [], "Banco de dados", DA),
    _entry("Git", [], "Controle de versão", D, True),
    _entry("Docker", [], "Contêineres", I, True),
    _entry("Kubernetes", ["K8s"], "Contêineres", I, True),
    _entry("Terraform", [], "Computação em nuvem", I),
    _entry("AWS", ["Amazon Web Services"], "Computação em nuvem", I, True),
    _entry("Azure", ["Microsoft Azure"], "Computação em nuvem", I, True),
    _entry("GCP", ["Google Cloud", "Google Cloud Platform"], "Computação em nuvem", I),
    _entry("Linux", ["GNU/Linux"], "Sistemas distribuídos", I, True),
    _entry("Windows Server", [], "Sistemas distribuídos", I),
    _entry("Power BI", ["PowerBI"], "Análise de dados", DA, True),
    _entry("Tableau", [], "Análise de dados", DA),
    _entry("Excel", ["Microsoft Excel"], "Análise de dados", DA),
    _entry("Pandas", [], "Análise de dados", DA),
    _entry("Apache Spark", ["PySpark", "Spark"], "Sistemas distribuídos", DA),
    _entry("TensorFlow", [], "Machine Learning", DA),
    _entry("PyTorch", [], "Machine Learning", DA),
    _entry("Scikit-learn", ["sklearn", "scikit learn"], "Machine Learning", DA),
    _entry("Machine Learning", ["aprendizado de máquina", "aprendizagem de máquina", "ML"], "Machine Learning", DA, True, "concept", ["dados", "modelo", "python", "treino", "treinamento", "machine learning", "aprendizado", "classificacao", "regressao"]),
    _entry("Inteligência Artificial", ["artificial intelligence", "IA", "AI"], "Inteligência Artificial", DA, True, "concept", ["inteligencia", "artificial", "modelo", "modelos", "dados", "machine", "algoritmo", "aprendizado", "generativa", "llm", "chatbot", "neural"]),
    _entry("Estatística", ["statistics", "inferência estatística", "regressão linear"], "Estatística", DA, False, "concept"),
    _entry("Análise de dados", ["data analysis", "análise exploratória", "analytics", "analise de dados"], "Análise de dados", DA, False, "concept"),
    _entry("Banco de dados", ["bancos de dados", "database", "databases", "modelagem de dados"], "Banco de dados", DA, True, "concept"),
    _entry("Programação orientada a objetos", ["orientação a objetos", "orientada a objetos", "POO", "OOP", "object oriented"], "Programação orientada a objetos", D, False, "concept"),
    _entry("Algoritmos e estruturas de dados", ["algoritmos", "estruturas de dados", "data structures"], "Algoritmos e estruturas de dados", D, False, "concept"),
    _entry("Desenvolvimento web", ["programação web", "desenvolvimento front-end", "desenvolvimento frontend", "desenvolvimento back-end", "desenvolvimento backend", "web development", "interfaces web", "frameworks web"], "Desenvolvimento web", D, True, "concept"),
    _entry("APIs e serviços", ["API", "APIs", "REST", "RESTful", "serviços web", "web services", "GraphQL"], "APIs e serviços", D, True, "concept"),
    _entry("Testes de software", ["testes automatizados", "teste de software", "testes unitários", "unit testing", "TDD", "quality assurance"], "Testes de software", D, False, "concept"),
    _entry("Engenharia de requisitos", ["elicitação de requisitos", "análise de requisitos", "levantamento de requisitos", "especificação de requisitos", "requisitos de software", "histórias de usuário", "casos de uso"], "Engenharia de requisitos", G, False, "concept"),
    _entry("Métodos ágeis", ["metodologias ágeis", "Scrum", "Kanban", "agile"], "Métodos ágeis", G, True, "concept"),
    _entry("UX/UI", ["UX", "UI", "user experience", "experiência do usuário", "design de interfaces", "usabilidade", "interação humano-computador"], "UX/UI", G, False, "concept"),
    _entry("Redes de computadores", ["redes de comunicação", "TCP/IP", "TCP", "DNS", "roteamento", "computer networks"], "Redes de computadores", I, True, "concept"),
    _entry("Segurança da informação", ["segurança cibernética", "cybersecurity", "cibersegurança", "criptografia", "segurança de redes"], "Segurança da informação", S, True, "concept"),
    _entry("Computação em nuvem", ["cloud computing", "cloud", "infraestrutura em nuvem"], "Computação em nuvem", I, False, "concept"),
    _entry("DevOps", ["DevSecOps"], "DevOps", I, True, "concept"),
    _entry("Integração contínua", ["CI/CD", "CI CD", "continuous integration", "entrega contínua", "continuous delivery", "pipelines de integração"], "Integração contínua", I, False, "concept"),
    _entry("Contêineres", ["container", "containers", "contêiner", "conteinerizacao", "containerization"], "Contêineres", I, False, "concept"),
    _entry("Sistemas distribuídos", ["distributed systems", "microserviços", "microsserviços", "microservices", "computação distribuída"], "Sistemas distribuídos", I, False, "concept"),
    _entry("Suporte técnico", ["help desk", "helpdesk", "service desk", "atendimento técnico", "suporte de TI", "suporte ao usuário"], "Suporte técnico", SU, True, "concept"),
    _entry("Gestão de projetos", ["gerenciamento de projetos", "project management", "PMBOK"], "Gestão de projetos", G, False, "concept"),
    _entry("Observabilidade", ["monitoramento de sistemas", "Prometheus", "Grafana", "observability"], "Observabilidade", I, False, "concept"),
    _entry("ETL", ["ELT", "engenharia de dados", "pipelines de dados", "extração transformação e carga"], "ETL", DA, False, "concept"),
]


def build_dictionary(overrides=None):
    """Return a fresh vocabulary, applying supported additive curation.

    Accepts a list of entries or an ``{entry_id: {synonyms, context, enabled}}``
    map. A full list from the API is accepted as well. Unknown entries need a
    name; arbitrary regex is intentionally not executed.
    """
    entries = deepcopy(DICTIONARY)
    if not overrides:
        return entries
    if isinstance(overrides, dict) and "entries" in overrides:
        overrides = overrides["entries"]
    changes = overrides if isinstance(overrides, list) else [dict(v, id=k) for k, v in overrides.items() if isinstance(v, dict)]
    by_id = {item["id"]: item for item in entries}
    for change in changes:
        key = change.get("id")
        current = by_id.get(key)
        if current:
            for field in ("name", "concept", "area", "type", "base", "enabled"):
                if field in change:
                    current[field] = change[field]
            for field in ("synonyms", "context"):
                if field in change and isinstance(change[field], list):
                    current[field] = list(dict.fromkeys(str(v) for v in change[field] if str(v).strip()))
            # UI can append a single alias without replacing existing aliases.
            if change.get("synonym"):
                current["synonyms"] = list(dict.fromkeys(current["synonyms"] + [str(change["synonym"])]))
        elif change.get("name"):
            item = _entry(change["name"], change.get("synonyms", []), change.get("concept", change["name"]), change.get("area", D), kind=change.get("type", "technology"))
            item["id"] = key or item["id"]
            entries.append(item)
            by_id[item["id"]] = item
    return [item for item in entries if item.get("enabled", True)]


assert len(DICTIONARY) == 73
