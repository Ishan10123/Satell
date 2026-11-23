import re


_SENSITIVE = re.compile(r"\b(password|passcode|secret|api[ -]?key|token|credential|private key|ssn|social security)\b", re.I)
_STOP_PREFIX = re.compile(r"^(?:(?:please\s+)?(?:explain|describe|tell me|show me)(?:\s+how)?\s+|(?:how|what|why|when|where)\s+(?:does|do|is|are|can|to)\s+|how\s+)+", re.I)
_CONTEXTUAL_QUESTION = re.compile(
    r"^in\s+([^,!?]+),?\s+(what|how|why|when|where)\s+(?:does|do|is|are|can|should)\s+(?:a|an|the)?\s*(.+)$",
    re.I,
)
_FOLLOWUP_INSTRUCTION = re.compile(
    r"\?\s*(?:give|provide|include|show|write|explain|describe|tell me|also|and then)\b.*$",
    re.I,
)
_TITLE_FILLERS = {"perform", "performs", "performing", "work", "works", "handle", "handles", "use", "uses", "using"}
_BRANDS = {"api": "API", "bm25": "BM25", "css": "CSS", "docker": "Docker", "fastapi": "FastAPI",
           "gpu": "GPU", "http": "HTTP", "json": "JSON", "llm": "LLM", "postgresql": "PostgreSQL",
           "python": "Python", "qdrant": "Qdrant", "rag": "RAG", "rrf": "RRF", "sql": "SQL",
           "sqlite": "SQLite", "xml": "XML", "yaml": "YAML"}


def title_from_first_question(value: str, *, maximum: int = 64) -> str:
    text = " ".join((value or "").split())
    if not text or _SENSITIVE.search(text) or re.search(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\b(?:sk|ghp|gho|xox[baprs])-[-A-Za-z0-9_]{12,}", text, re.I):
        return "New conversation"
    text = _FOLLOWUP_INSTRUCTION.sub("?", text)
    text = text.split("?", 1)[0]
    contextual = _CONTEXTUAL_QUESTION.match(text)
    if contextual:
        text = f"{contextual.group(1)} {contextual.group(3)}"
    else:
        text = _STOP_PREFIX.sub("", text)
    text = re.sub(r"[`*_#]+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n.,!?;:-–—_'\"`#*")
    if not text:
        return "New conversation"
    words = []
    for word in text.split():
        key = word.casefold().strip("()[]{}.,:;!?'“”\"")
        if key in _TITLE_FILLERS:
            continue
        words.append(_BRANDS.get(key, word[:1].upper() + word[1:]))
    result = " ".join(words)
    if len(result) > maximum:
        result = result[:maximum + 1].rsplit(" ", 1)[0].rstrip(" .,!?;:-")
    return result or "New conversation"
