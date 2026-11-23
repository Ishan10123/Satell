from dataclasses import dataclass
from html.parser import HTMLParser
import json
import re
import unicodedata
from pathlib import Path
import textwrap
from typing import Any, Iterable



SUPPORTED_EXTENSIONS = {".html", ".htm", ".md", ".markdown", ".rst", ".pdf", ".txt"}
IGNORED_HTML_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "svg", "template"}
BLOCK_TAGS = {"article", "section", "div", "p", "li", "dt", "dd", "blockquote", "tr", "br", "hr"}
HEADING_TAGS = {f"h{level}": level for level in range(1, 7)}


class DocumentParseError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentSegment:
    text: str
    segment_type: str = "text"
    headings: tuple[str, ...] = ()
    page_number: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    language: str | None = None
    symbol_name: str | None = None


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    segments: tuple[DocumentSegment, ...]
    source_path: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _RawSegment:
    text: str
    segment_type: str
    headings: tuple[str, ...]
    line_start: int | None = None
    line_end: int | None = None
    language: str | None = None
    symbol_name: str | None = None


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\u00a0", " ").replace("\u200b", "")
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_code(value: str) -> str:
    value = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    lines = value.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(line.rstrip() for line in lines)


def _segments_from_blocks(blocks: Iterable[_RawSegment]) -> tuple[DocumentSegment, ...]:
    segments = []
    for block in blocks:
        text = normalize_code(block.text) if block.segment_type == "code" else normalize_text(block.text)
        if text:
            segments.append(DocumentSegment(text, block.segment_type, block.headings,
                                            None, block.line_start, block.line_end,
                                            block.language, block.symbol_name))
    return tuple(segments)


class _HtmlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.headings: list[str] = []
        self.blocks: list[_RawSegment] = []
        self.block_parts: list[str] = []
        self.code_parts: list[str] = []
        self.title_depth = 0
        self.heading_level: int | None = None
        self.code_depth = 0
        self.pre_depth = 0
        self.ignore_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if self.ignore_stack:
            if tag in IGNORED_HTML_TAGS:
                self.ignore_stack.append(tag)
            return
        if tag in IGNORED_HTML_TAGS:
            self.flush_block()
            self.ignore_stack.append(tag)
        elif tag == "title":
            self.title_depth += 1
        elif tag in HEADING_TAGS:
            self.flush_block()
            self.heading_level = HEADING_TAGS[tag]
            self.heading_parts = []
        elif tag == "pre":
            self.flush_block()
            self.pre_depth += 1
            self.code_parts = []
        elif tag == "code":
            self.code_depth += 1
            if self.code_depth == 1 and self.pre_depth == 0:
                self.flush_block()
                self.code_parts = []
        elif tag in BLOCK_TAGS:
            self.flush_block()

    def handle_endtag(self, tag: str) -> None:
        if self.ignore_stack:
            if tag == self.ignore_stack[-1]:
                self.ignore_stack.pop()
            return
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        elif tag in HEADING_TAGS and self.heading_level is not None:
            text = normalize_text("".join(self.heading_parts))
            if text:
                level = self.heading_level
                self.headings = self.headings[: level - 1]
                self.headings.extend([""] * max(0, level - len(self.headings)))
                self.headings[level - 1] = text
                self.headings = self.headings[:level]
            self.heading_level = None
            self.heading_parts = []
        elif tag == "pre" and self.pre_depth:
            self.pre_depth -= 1
            self.emit_code()
        elif tag == "code" and self.code_depth:
            self.code_depth -= 1
            if self.code_depth == 0 and self.pre_depth == 0:
                self.emit_code()
        elif tag in BLOCK_TAGS:
            self.flush_block()

    def handle_data(self, data: str) -> None:
        if self.ignore_stack:
            return
        if self.title_depth:
            self.title_parts.append(data)
        elif self.heading_level is not None:
            self.heading_parts.append(data)
        elif self.pre_depth or self.code_depth:
            self.code_parts.append(data)
        else:
            self.block_parts.append(data)

    def flush_block(self) -> None:
        text = normalize_text(" ".join(self.block_parts))
        if text:
            self.blocks.append(_RawSegment(text, "text", tuple(item for item in self.headings if item)))
        self.block_parts = []

    def emit_code(self) -> None:
        text = "".join(self.code_parts)
        if text:
            self.blocks.append(_RawSegment(text, "code", tuple(item for item in self.headings if item)))
        self.code_parts = []


def parse_html(text: str) -> tuple[str, tuple[DocumentSegment, ...]]:
    parser = _HtmlExtractor()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise DocumentParseError(f"HTML extraction failed: {exc}") from exc
    parser.flush_block()
    parser.emit_code()
    title = normalize_text(" ".join(parser.title_parts))
    segments = _segments_from_blocks(parser.blocks)
    return title, segments


def parse_markdown(text: str) -> tuple[str, tuple[DocumentSegment, ...]]:
    lines = text.splitlines()
    title = ""
    headings: list[str] = []
    blocks: list[_RawSegment] = []
    paragraph: list[str] = []
    code: list[str] | None = None
    code_fence_char: str | None = None
    code_fence_length = 0

    def flush_paragraph() -> None:
        content = normalize_text(" ".join(paragraph))
        if content:
            blocks.append(_RawSegment(content, "text", tuple(headings)))
        paragraph.clear()

    for line in lines:
        if code is not None:
            closing_fence = re.match(r"^ {0,3}(`{3,}|~{3,})[ \t]*$", line)
            if (
                closing_fence
                and closing_fence.group(1)[0] == code_fence_char
                and len(closing_fence.group(1)) >= code_fence_length
            ):
                content = "\n".join(code)
                if content:
                    blocks.append(_RawSegment(content, "code", tuple(headings)))
                code = None
                code_fence_char = None
                code_fence_length = 0
            else:
                code.append(line)
            continue

        opening_fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opening_fence:
            fence_marker = opening_fence.group(1)
            info_string = opening_fence.group(2)
            # Backticks are forbidden in a backtick fence's info string. This
            # keeps inline examples such as `````command``` from opening a
            # block that consumes the rest of the document.
            if fence_marker[0] == "~" or "`" not in info_string:
                flush_paragraph()
                code = []
                code_fence_char = fence_marker[0]
                code_fence_length = len(fence_marker)
                continue
        if opening_fence and (opening_fence.group(1)[0] == "`" and "`" in opening_fence.group(2)):
            paragraph.append(line.strip())
            continue
        if opening_fence:
            flush_paragraph()
            # An invalid backtick opener is ordinary Markdown text.
            paragraph.append(line.strip())
            continue
        heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            value = normalize_text(heading.group(2))
            headings = headings[:level - 1]
            headings.extend([""] * max(0, level - len(headings)))
            headings[level - 1] = value
            headings = headings[:level]
            if not title and level == 1:
                title = value
            continue
        if not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line.strip())
    if code is not None:
        # CommonMark treats an unclosed fenced block as extending through EOF.
        content = "\n".join(code)
        if content:
            blocks.append(_RawSegment(content, "code", tuple(headings)))
    flush_paragraph()
    return title, _segments_from_blocks(blocks)


def parse_rst(text: str) -> tuple[str, tuple[DocumentSegment, ...]]:
    lines = text.splitlines()
    headings: list[str] = []
    blocks: list[_RawSegment] = []
    paragraph: list[str] = []
    code: list[str] | None = None
    title = ""
    adornment = re.compile(r"^\s*([=~`:#*+\-^\"'])\1{2,}\s*$")

    def flush_paragraph() -> None:
        content = normalize_text(" ".join(paragraph))
        if content:
            blocks.append(_RawSegment(content, "text", tuple(headings)))
        paragraph.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        if code is not None:
            if line.strip() and not line.startswith((" ", "\t")):
                content = textwrap.dedent("\n".join(code))
                if content:
                    blocks.append(_RawSegment(content, "code", tuple(headings)))
                code = None
            else:
                code.append(line)
                index += 1
                continue
        if line.strip().endswith("::"):
            flush_paragraph()
            code = []
            index += 1
            if index < len(lines) and not lines[index].strip():
                index += 1
            continue
        if index + 1 < len(lines) and line.strip() and adornment.match(lines[index + 1]):
            flush_paragraph()
            marker = lines[index + 1].strip()[0]
            level = {"=": 1, "-": 2, "~": 3, "^": 4}.get(marker, 5)
            value = normalize_text(line)
            headings = headings[:level - 1]
            headings.extend([""] * max(0, level - len(headings)))
            headings[level - 1] = value
            headings = headings[:level]
            if not title and level == 1:
                title = value
            index += 2
            continue
        if not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line.strip())
        index += 1
    if code is not None:
        content = textwrap.dedent("\n".join(code))
        if content:
            blocks.append(_RawSegment(content, "code", tuple(headings)))
    flush_paragraph()
    return title, _segments_from_blocks(blocks)


def parse_text(text: str) -> tuple[str, tuple[DocumentSegment, ...]]:
    content = normalize_text(text)
    segments = (DocumentSegment(content),) if content else ()
    return "", segments


def parse_pdf(path: Path) -> tuple[str, tuple[DocumentSegment, ...]]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path), strict=True)
        metadata = reader.metadata
        title = normalize_text(metadata.title) if metadata and metadata.title else ""
        segments = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = normalize_text(page.extract_text() or "")
            if page_text:
                segments.append(DocumentSegment(page_text, "text", (), page_number))
        return title, tuple(segments)
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError(f"PDF extraction failed for {path.name}: {exc}") from exc


def load_parser_registry(path: str | Path) -> dict:
    """Load an explicit extension-to-parser registry; configuration never broadens authorization."""
    with Path(path).open("r", encoding="utf-8-sig") as file:
        config = json.load(file)
    if not isinstance(config, dict) or config.get("config_version") != "1.0" or not isinstance(config.get("parsers"), dict):
        raise ValueError("Invalid parser registry configuration.")
    known = SUPPORTED_EXTENSIONS
    registered_names = {"html", "markdown", "rst", "pdf", "text", *STRUCTURED_PARSER_NAMES, *ADVANCED_PARSER_NAMES}
    for extension, definition in config["parsers"].items():
        if (extension not in known or not isinstance(definition, dict)
                or not isinstance(definition.get("enabled"), bool)
                or definition.get("parser") not in registered_names):
            raise ValueError(f"Invalid parser registry entry: {extension}")
        limits = definition.get("limits", {})
        if not isinstance(limits, dict) or any(type(v) is not int or v < 1 for v in limits.values()):
            raise ValueError(f"Invalid parser limits: {extension}")
    return config


def parse_file(path: str | Path, max_file_bytes: int = 50 * 1024 * 1024, parser_registry: dict | None = None) -> ParsedDocument:
    source_path = Path(path).resolve()
    try:
        size = source_path.stat().st_size
    except OSError as exc:
        raise DocumentParseError(f"Cannot access document: {source_path}") from exc
    if not source_path.is_file():
        raise DocumentParseError(f"Document is not a file: {source_path}")
    if size > max_file_bytes:
        raise DocumentParseError(f"Document exceeds the {max_file_bytes}-byte size limit.")
    extension = source_path.suffix.lower()
    definition = (parser_registry or {}).get("parsers", {}).get(extension) if parser_registry else None
    if parser_registry is not None and (definition is None or definition.get("enabled") is not True):
        raise DocumentParseError(f"Unsupported document extension: {extension or '[none]'}")
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError(f"Unsupported document extension: {extension or '[none]'}")
    parser_name = definition.get("parser", DEFAULT_PARSER_NAMES.get(extension)) if definition else DEFAULT_PARSER_NAMES.get(extension)
    parse_metadata: dict[str, Any] = {}
    if parser_name in STRUCTURED_PARSER_NAMES or parser_name in ADVANCED_PARSER_NAMES:
        configured_limit = (definition or {}).get("limits", {}).get("max_file_bytes", DEFAULT_LIMITS["max_file_bytes"])
        if size > configured_limit:
            raise DocumentParseError(f"Document exceeds the {configured_limit}-byte parser size limit.")
    if parser_name in STRUCTURED_PARSER_NAMES:
        try:
            text = source_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise DocumentParseError(f"Cannot decode document {source_path.name}: {exc}") from exc
        limits = dict(DEFAULT_LIMITS)
        if definition:
            limits.update(definition.get("limits", {}))
        limits["max_file_bytes"] = min(max_file_bytes, limits["max_file_bytes"])
        title, segments = STRUCTURED_PARSER_NAMES[parser_name](text, limits)
    elif parser_name == "source_code":
        try:
            text = source_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise DocumentParseError(f"Cannot decode source {source_path.name}: {exc}") from exc
        limits = dict(DEFAULT_LIMITS)
        if definition:
            limits.update(definition.get("limits", {}))
        title, segments = ADVANCED_PARSER_NAMES[parser_name](text, limits, extension, source_path.stem)
    elif parser_name in {"docx", "xlsx", "pptx"}:
        limits = dict(DEFAULT_LIMITS)
        limits.update(ADVANCED_LIMITS)
        if definition:
            limits.update(definition.get("limits", {}))
        title, segments, parse_metadata = ADVANCED_PARSER_NAMES[parser_name](source_path, extension, limits)
    elif parser_name in ADVANCED_PARSER_NAMES:
        try:
            text = source_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise DocumentParseError(f"Cannot decode document {source_path.name}: {exc}") from exc
        limits = dict(DEFAULT_LIMITS)
        limits.update(ADVANCED_LIMITS)
        if definition:
            limits.update(definition.get("limits", {}))
        if parser_name == "source_code":
            title, segments = ADVANCED_PARSER_NAMES[parser_name](text, limits, extension, source_path.stem)
        else:
            title, segments = ADVANCED_PARSER_NAMES[parser_name](text, limits)
    elif parser_name == "pdf":
        title, segments = parse_pdf(source_path)
    else:
        try:
            text = source_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise DocumentParseError(f"Cannot decode document {source_path.name}: {exc}") from exc
        if parser_name == "html":
            title, segments = parse_html(text)
        elif parser_name == "markdown":
            title, segments = parse_markdown(text)
        elif parser_name == "rst":
            title, segments = parse_rst(text)
        elif parser_name == "text":
            title, segments = parse_text(text)
        else:
            raise DocumentParseError(f"No parser is registered for {extension}.")
    if not segments:
        raise DocumentParseError(f"Document contains no extractable text: {source_path.name}")
    effective_limits = dict(DEFAULT_LIMITS)
    effective_limits.update(ADVANCED_LIMITS)
    if definition:
        effective_limits.update(definition.get("limits", {}))
    if len(segments) > effective_limits.get("max_nodes", 100_000):
        raise DocumentParseError("Document exceeds maximum extracted segment count.")
    if sum(len(segment.text) for segment in segments) > effective_limits.get("max_output_chars", 5_000_000):
        raise DocumentParseError("Document exceeds maximum extracted text size.")
    return ParsedDocument(
        title=title or source_path.stem,
        segments=segments,
        source_path=str(source_path),
        metadata={"file_name": source_path.name, "file_size_bytes": size, "extension": extension, **parse_metadata},
    )
@dataclass(frozen=True)
class ParseOutcome:
    source_path: str
    document: ParsedDocument | None
    error: str | None

    @property
    def succeeded(self) -> bool:
        return self.document is not None and self.error is None


def parse_many(paths: Iterable[str | Path], max_file_bytes: int = 50 * 1024 * 1024) -> tuple[ParseOutcome, ...]:
    outcomes = []
    for path in paths:
        source_path = str(Path(path).resolve())
        try:
            document = parse_file(path, max_file_bytes=max_file_bytes)
        except DocumentParseError as exc:
            outcomes.append(ParseOutcome(source_path, None, str(exc)))
        else:
            outcomes.append(ParseOutcome(source_path, document, None))
    return tuple(outcomes)


# Imported after the core data types are defined because structured extractors
# emit DocumentSegment instances from this module.
from .structured import DEFAULT_LIMITS, PARSERS as STRUCTURED_PARSERS  # noqa: E402
SUPPORTED_EXTENSIONS.update(STRUCTURED_PARSERS)
STRUCTURED_PARSER_NAMES = {
    extension[1:]: parser for extension, parser in STRUCTURED_PARSERS.items()
}
DEFAULT_PARSER_NAMES = {
    ".html": "html", ".htm": "html", ".md": "markdown", ".markdown": "markdown",
    ".rst": "rst", ".pdf": "pdf", ".txt": "text",
    **{f".{name}": name for name in STRUCTURED_PARSER_NAMES},
}
from .advanced import LANGUAGES as SOURCE_LANGUAGES, LIMITS as ADVANCED_LIMITS  # noqa: E402
from .advanced import parse_conf, parse_dot, parse_excalidraw, parse_gliffy, parse_gotmpl, parse_notebook, parse_office, parse_source, parse_sql, parse_svg  # noqa: E402
ADVANCED_PARSER_NAMES = {
    "source_code": parse_source, "dot": parse_dot, "excalidraw": parse_excalidraw,
    "gliffy": parse_gliffy, "gotmpl": parse_gotmpl, "conf": parse_conf,
    "svg": parse_svg, "docx": parse_office, "xlsx": parse_office, "pptx": parse_office,
    "notebook": parse_notebook, "sql": parse_sql,
}
DEFAULT_PARSER_NAMES.update({ext: "source_code" for ext in SOURCE_LANGUAGES})
DEFAULT_PARSER_NAMES.update({".dot": "dot", ".excalidraw": "excalidraw", ".gliffy": "gliffy",
                            ".gotmpl": "gotmpl", ".conf": "conf", ".svg": "svg",
                            ".docx": "docx", ".xlsx": "xlsx", ".pptx": "pptx"})
DEFAULT_PARSER_NAMES.update({".ipynb": "notebook", ".sql": "sql"})
SUPPORTED_EXTENSIONS.update(SOURCE_LANGUAGES)
SUPPORTED_EXTENSIONS.update({".dot", ".excalidraw", ".gliffy", ".gotmpl", ".conf", ".svg", ".docx", ".xlsx", ".pptx", ".ipynb", ".sql"})
