"""Deterministic extractors for source, diagram, template, config, and office files."""
from __future__ import annotations

import ast
import io
import json
import re
import zipfile
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any
import xml.etree.ElementTree as ET

from .extractors import DocumentParseError, DocumentSegment

LIMITS = {"max_records": 50_000, "max_nodes": 100_000, "max_columns": 512,
          "max_cell_chars": 100_000, "max_output_chars": 5_000_000,
          "max_archive_entries": 20_000, "max_archive_uncompressed_bytes": 100 * 1024 * 1024,
          "max_archive_ratio": 200}

LANGUAGES = {".py": "python", ".js": "javascript", ".mjs": "javascript", ".ts": "typescript",
             ".java": "java", ".cs": "csharp", ".go": "go", ".rs": "rust", ".sh": "shell"}
DECLS = {
 "javascript": re.compile(r"^\s*(?:(?:export|default|async|declare|abstract)\s+)*(?:class|function)\s+([\w$]+)|^\s*(?:export\s+)?(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*=>"),
 "typescript": re.compile(r"^\s*(?:(?:export|default|async|declare|abstract)\s+)*(?:class|interface|enum|function)\s+([\w$]+)|^\s*(?:export\s+)?(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*=>"),
 "java": re.compile(r"^\s*(?:(?:public|protected|private|static|final|abstract|synchronized|native|default)\s+)*(?:class|interface|enum|record)\s+([\w$]+)|^\s*(?:(?:public|protected|private|static|final|abstract|synchronized|native)\s+)+[\w<>?,.\[\]]+\s+([\w$]+)\s*\([^;]*\)\s*(?:throws [^{]+)?\{"),
 "csharp": re.compile(r"^\s*(?:(?:public|internal|protected|private|static|sealed|abstract|partial)\s+)*(?:class|interface|struct|record|enum)\s+([\w]+)|^\s*(?:(?:public|internal|protected|private|static|async|virtual|override|sealed|abstract)\s+)+[\w<>?,.\[\]]+\s+([\w]+)\s*\([^;]*\)\s*(?:=>|\{)"),
 "go": re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([\w]+)\s*\(|^\s*type\s+([\w]+)\s+(?:struct|interface)\b"),
 "rust": re.compile(r"^\s*(?:(?:pub(?:\([^)]*\))?|async|unsafe|const)\s+)*(?:fn|struct|enum|trait|type)\s+([\w]+)"),
 "shell": re.compile(r"^\s*(?:function\s+([\w.-]+)\s*|([\w.-]+)\s*\(\s*\)\s*\{)")}


def _symbol_ranges(text: str, language: str):
    lines = text.splitlines()
    if language == "python":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError) as exc:
            raise DocumentParseError(f"Malformed Python source: {exc}") from exc
        output = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
                output.append((start, getattr(node, "end_lineno", node.lineno), node.name,
                               "class" if isinstance(node, ast.ClassDef) else "function"))
        return lines, output
    matcher = DECLS.get(language)
    found = []
    if matcher:
        for no, line in enumerate(lines, 1):
            match = matcher.match(line)
            if match:
                name = next((g for g in match.groups() if g), None)
                if name:
                    kind = "class" if re.search(r"\b(class|interface|enum|record|struct|trait|type)\b", line) else "function"
                    found.append((no, len(lines), name, kind))
    # Source-only brace accounting to estimate boundaries; no compiler/eval is used.
    bounded = []
    for index, row in enumerate(found):
        start, _, name, kind = row
        indent = len(lines[start-1]) - len(lines[start-1].lstrip())
        end = len(lines)
        for next_start, _, _, _ in found[index+1:]:
            next_indent = len(lines[next_start-1]) - len(lines[next_start-1].lstrip())
            if next_indent <= indent:
                end = next_start - 1
                break
        bounded.append((start, max(start, end), name, kind))
    return lines, bounded


def parse_source(text: str, limits: dict[str, int], extension: str, module_name: str | None = None):
    if len(text) > limits.get("max_output_chars", LIMITS["max_output_chars"]):
        raise DocumentParseError("Source exceeds output limit.")
    language = LANGUAGES[extension]
    lines, symbols = _symbol_ranges(text, language)
    if not lines:
        raise DocumentParseError("Source file is empty.")
    if len(lines) > limits.get("max_records", LIMITS["max_records"]):
        raise DocumentParseError("Source exceeds line limit.")
    module = module_name or Path("source" + extension).stem
    segments = []
    if not symbols:
        value = text.strip("\r\n")
        if value:
            segments.append(DocumentSegment(value, "code", (f"{module} module",), None, 1, len(lines), language, module))
    else:
        start = symbols[0][0]
        if start > 1 and any(line.strip() for line in lines[:start-1]):
            segments.append(DocumentSegment("\n".join(lines[:start-1]), "code", (f"{module} module", "module declarations"), None, 1, start-1, language, module))
        for first, last, name, kind in symbols:
            value = "\n".join(lines[first-1:last]).rstrip()
            if value:
                segments.append(DocumentSegment(value, "code", (f"{module} module", f"{kind} {name}"), None, first, last, language, name))
    if not segments:
        raise DocumentParseError("Source contains no extractable text.")
    return module, tuple(segments)


def parse_dot(text: str, limits: dict[str, int]):
    labels = re.findall(r"\blabel\s*=\s*\"((?:\\.|[^\"\\])*)\"", text)
    edges = re.findall(r"([A-Za-z_][\w.-]*)\s*(?:->|--)\s*([A-Za-z_][\w.-]*)", text)
    graph = re.search(r"\b(?:di)?graph\s+([A-Za-z_][\w.-]*)", text)
    fields = []
    if graph:
        fields.append(("graph", graph.group(1)))
    fields += [(f"label[{i}]", x) for i, x in enumerate(labels, 1)]
    fields += [(f"edge[{i}]", f"{a} -> {b}") for i, (a, b) in enumerate(edges, 1)]
    if not fields:
        raise DocumentParseError("DOT has no graph labels or edges.")
    return graph.group(1) if graph else "Graph", tuple(DocumentSegment(f"{k}: {v}", "text", (k,)) for k,v in fields)


def parse_excalidraw(text: str, limits: dict[str, int]):
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise DocumentParseError(f"Malformed Excalidraw JSON: {exc}") from exc
    elements = data.get("elements") if isinstance(data, dict) else None
    if not isinstance(elements, list) or len(elements) > limits.get("max_nodes", LIMITS["max_nodes"]):
        raise DocumentParseError("Excalidraw elements are invalid or exceed limits.")
    segments = []
    for i, item in enumerate(elements):
        if isinstance(item, dict) and item.get("isDeleted") is not True:
            value = next((item.get(k) for k in ("text", "originalText", "label") if isinstance(item.get(k), str) and item[k].strip()), None)
            if value:
                segments.append(DocumentSegment(value, "text", (f"diagram element {i+1}",), None, None, None, "excalidraw", None))
    return str(data.get("name") or "Excalidraw diagram"), tuple(segments)


def parse_gliffy(text: str, limits: dict[str, int]):
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise DocumentParseError(f"Malformed Gliffy JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("contentType") != "application/gliffy+json":
        raise DocumentParseError("Unsupported Gliffy format; expected Gliffy JSON.")
    values = []
    def walk(node, path="diagram", depth=0):
        if depth > limits.get("max_depth", 64) or len(values) > limits.get("max_nodes", LIMITS["max_nodes"]):
            raise DocumentParseError("Gliffy structure exceeds limits.")
        if isinstance(node, dict):
            for key, value in node.items():
                if key.casefold() in {"text", "label", "title", "description"} and isinstance(value, str) and value.strip():
                    values.append((f"{path}.{key}", value))
                elif isinstance(value, (dict, list)):
                    walk(value, f"{path}.{key}", depth+1)
        elif isinstance(node, list):
            for i, value in enumerate(node): walk(value, f"{path}[{i}]", depth+1)
    walk(data)
    segments = tuple(DocumentSegment(f"{p}: {v}", "text", (p,), None, None, None, "gliffy", None) for p,v in values)
    return "Gliffy diagram", segments


def parse_svg(text: str, limits: dict[str, int]):
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise DocumentParseError("SVG DTD and entity declarations are unsupported.")
    fields=[]; count=0; title=""
    try:
        for event, elem in ET.iterparse(io.StringIO(text), events=("start","end")):
            tag=str(elem.tag).split("}")[-1].lower()
            if event == "start":
                count+=1
                if count > limits.get("max_nodes", LIMITS["max_nodes"]): raise DocumentParseError("SVG exceeds element limit.")
                for key,value in elem.attrib.items():
                    name=key.split("}")[-1].lower()
                    if name in {"aria-label","alt"} and value.strip(): fields.append((f"{tag} {name}",value.strip()))
            else:
                if tag in {"title","desc","text","tspan"}:
                    value=" ".join("".join(elem.itertext()).split())
                    if value:
                        fields.append((tag,value))
                        if tag=="title" and not title: title=value
                elem.clear()
    except DocumentParseError: raise
    except ET.ParseError as exc: raise DocumentParseError(f"Malformed SVG: {exc}") from exc
    segments=tuple(DocumentSegment(f"{p}: {v}","text",(p,),None,None,None,"svg",None) for p,v in fields)
    return title or "SVG diagram", segments


def parse_gotmpl(text: str, limits: dict[str,int]):
    if text.count("{{") != text.count("}}"):
        raise DocumentParseError("Malformed Go template delimiters.")
    segs=[]; cursor=0
    for match in re.finditer(r"{{-?.*?-?}}",text,re.S):
        for a,b in ((cursor,match.start()),(match.start(),match.end())):
            value=text[a:b].strip()
            if value:
                segs.append(DocumentSegment(value,"code",("Go template",),None,text.count("\n",0,a)+1,text.count("\n",0,b)+1,"gotmpl","template"))
        cursor=match.end()
    tail=text[cursor:].strip()
    if tail: segs.append(DocumentSegment(tail,"code",("Go template",),None,text.count("\n",0,cursor)+1,len(text.splitlines()),"gotmpl","template"))
    return "Go template",tuple(segs)


def parse_conf(text: str, limits: dict[str,int]):
    segs=[]; section="global"
    for no, raw in enumerate(text.splitlines(),1):
        val=raw.strip()
        if not val or val.startswith(("#",";")): continue
        if val.startswith("[") and val.endswith("]"): section=val[1:-1].strip()
        else: segs.append(DocumentSegment(f"{section} line {no}: {val}","text",(section,),None,no,no,"conf",None))
    return "Configuration",tuple(segs)


def parse_notebook(text: str, limits: dict[str, int]):
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise DocumentParseError(f"Malformed notebook JSON: {exc}") from exc
    cells = data.get("cells") if isinstance(data, dict) else None
    if not isinstance(cells, list) or len(cells) > limits.get("max_records", LIMITS["max_records"]):
        raise DocumentParseError("Notebook has invalid or excessive cell count.")
    kernel = data.get("metadata", {}).get("kernelspec", {}).get("language") if isinstance(data.get("metadata"), dict) else None
    language = kernel if isinstance(kernel, str) and len(kernel) < 40 else "python"
    segments = []
    for index, cell in enumerate(cells, 1):
        if not isinstance(cell, dict):
            raise DocumentParseError(f"Notebook cell {index} is not an object.")
        kind = cell.get("cell_type")
        source = cell.get("source", "")
        value = "".join(source) if isinstance(source, list) and all(isinstance(x, str) for x in source) else source
        if kind not in {"code", "markdown", "raw"} or not isinstance(value, str):
            raise DocumentParseError(f"Notebook cell {index} has invalid source metadata.")
        if value.strip():
            lines = len(value.splitlines())
            segments.append(DocumentSegment(value.strip("\n"), "code" if kind == "code" else "text",
                                            (f"Cell {index}", kind), None, 1, max(1, lines),
                                            language if kind == "code" else "notebook-markdown", f"cell-{index}"))
    if not segments:
        raise DocumentParseError("Notebook contains no extractable cell source.")
    return "Notebook", tuple(segments)


def parse_sql(text: str, limits: dict[str, int]):
    if len(text) > limits.get("max_output_chars", LIMITS["max_output_chars"]):
        raise DocumentParseError("SQL source exceeds output limit.")
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"^\s*(?:(?:--|/\*).*?\*/\s*)*(?:CREATE|ALTER|DROP|SELECT|INSERT|UPDATE|DELETE|WITH|GRANT|REVOKE|BEGIN|COMMIT)\b", line, re.I)]
    if not starts:
        starts = [0] if any(line.strip() for line in lines) else []
    segments = []
    for index, start in enumerate(starts):
        end = starts[index + 1] - 1 if index + 1 < len(starts) else len(lines) - 1
        value = "\n".join(lines[start:end+1]).strip()
        if value:
            segments.append(DocumentSegment(value, "code", (f"SQL statement {index+1}",), None, start+1, end+1, "sql", f"statement-{index+1}"))
    if not segments:
        raise DocumentParseError("SQL source is empty.")
    return "SQL", tuple(segments)


def _guard_zip(path: Path, limits):
    try:
        with zipfile.ZipFile(path) as z:
            entries=z.infolist()
            if not entries or len(entries)>limits.get("max_archive_entries",LIMITS["max_archive_entries"]): raise DocumentParseError("Office archive entry limit exceeded.")
            total=0
            for e in entries:
                if e.flag_bits & 1: raise DocumentParseError("Encrypted Office archives are unsupported.")
                normalized_name = e.filename.replace("\\", "/")
                if (PurePosixPath(normalized_name).is_absolute() or PureWindowsPath(e.filename).is_absolute()
                        or PureWindowsPath(e.filename).drive or ".." in PurePosixPath(normalized_name).parts):
                    raise DocumentParseError("Unsafe Office archive member path.")
                total+=e.file_size
                if e.file_size/max(e.compress_size,1)>limits.get("max_archive_ratio",LIMITS["max_archive_ratio"]): raise DocumentParseError("Office compression ratio limit exceeded.")
                if total>limits.get("max_archive_uncompressed_bytes",LIMITS["max_archive_uncompressed_bytes"]): raise DocumentParseError("Office expanded-size limit exceeded.")
    except DocumentParseError: raise
    except (OSError,zipfile.BadZipFile,RuntimeError) as exc: raise DocumentParseError(f"Malformed Office package: {exc}") from exc


def parse_office(path: Path, ext: str, limits: dict[str,int]):
    _guard_zip(path,limits); segments=[]; metadata={"office_format":ext[1:]}
    try:
        if ext==".docx":
            from docx import Document
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
            from docx.text.paragraph import Paragraph
            from docx.table import Table
            doc=Document(str(path)); props=doc.core_properties
            metadata.update({"document_title":props.title or None,"author":props.author or None,"subject":props.subject or None,"created":str(props.created) if props.created else None})
            paragraph_no=table_no=0
            for child in doc.element.body.iterchildren():
                if isinstance(child,CT_P):
                    paragraph_no+=1; para=Paragraph(child,doc)
                    value=para.text.strip()
                    if value:
                        style=para.style.name if para.style else "paragraph"
                        segments.append(DocumentSegment(value,"text",(style,),None,None,None,"docx",style))
                elif isinstance(child,CT_Tbl):
                    table_no+=1; table=Table(child,doc)
                    header=[c.text.strip() for c in table.rows[0].cells] if table.rows else []
                    for row_no,row in enumerate(table.rows[1:],2):
                        for col,cell in enumerate(row.cells):
                            if cell.text.strip():
                                label=header[col] if col<len(header) and header[col] else f"column_{col+1}"
                                segments.append(DocumentSegment(f"table[{table_no}].row[{row_no}].{label}: {cell.text.strip()}","text",(f"Table {table_no}",label),None,None,None,"docx",label))
        elif ext==".xlsx":
            from openpyxl import load_workbook
            book=load_workbook(path,read_only=True,data_only=False,keep_links=False)
            sheet_names=[s.title for s in book.worksheets]
            try:
                for sheet in book.worksheets:
                    if sheet.max_row>limits.get("max_records",LIMITS["max_records"]) or sheet.max_column>limits.get("max_columns",LIMITS["max_columns"]): raise DocumentParseError("XLSX sheet dimensions exceed limit.")
                    rows=sheet.iter_rows(values_only=True); headers=next(rows,None)
                    if headers is None: continue
                    for row_no,row in enumerate(rows,2):
                        for col,value in enumerate(row):
                            if value is None: continue
                            label=str(headers[col]).strip() if col<len(headers) and headers[col] is not None else f"column_{col+1}"
                            cell=str(value)
                            if len(cell)>limits.get("max_cell_chars",LIMITS["max_cell_chars"]): raise DocumentParseError("XLSX cell length limit exceeded.")
                            segments.append(DocumentSegment(f"{sheet.title}.row[{row_no}].{label}: {cell}","text",(sheet.title,label),None,row_no,row_no,"xlsx",label))
                            if len(segments)>limits.get("max_nodes",LIMITS["max_nodes"]): raise DocumentParseError("XLSX cell count limit exceeded.")
            finally: book.close()
            metadata["sheet_names"]=sheet_names
        else:
            from pptx import Presentation
            deck=Presentation(str(path))
            if len(deck.slides)>limits.get("max_records",LIMITS["max_records"]): raise DocumentParseError("PPTX slide count limit exceeded.")
            for slide_no,slide in enumerate(deck.slides,1):
                for shape_no,shape in enumerate(slide.shapes,1):
                    heading=f"Slide {slide_no}"
                    if getattr(shape,"has_text_frame",False):
                        value="\n".join(p.text for p in shape.text_frame.paragraphs).strip()
                        if value: segments.append(DocumentSegment(value,"text",(heading,),slide_no,None,None,"pptx",getattr(shape,"name",None)))
                    if getattr(shape,"has_table",False):
                        table=shape.table; header=[c.text.strip() for c in table.rows[0].cells] if table.rows else []
                        for row_no,row in enumerate(table.rows[1:],2):
                            for col,cell in enumerate(row.cells):
                                if cell.text.strip():
                                    label=header[col] if col<len(header) and header[col] else f"column_{col+1}"
                                    segments.append(DocumentSegment(f"slide[{slide_no}].table[{shape_no}].row[{row_no}].{label}: {cell.text.strip()}","text",(heading,f"Table {shape_no}",label),slide_no,row_no,row_no,"pptx",label))
                try: notes=slide.notes_slide.notes_text_frame.text.strip()
                except (AttributeError,KeyError): notes=""
                if notes: segments.append(DocumentSegment(notes,"text",(f"Slide {slide_no}","Speaker notes"),slide_no,None,None,"pptx","speaker notes"))
        if sum(len(s.text) for s in segments)>limits.get("max_output_chars",LIMITS["max_output_chars"]): raise DocumentParseError("Office extracted text limit exceeded.")
    except DocumentParseError: raise
    except Exception as exc: raise DocumentParseError(f"Office extraction failed: {exc}") from exc
    if not segments: raise DocumentParseError("Office document contains no extractable text.")
    return metadata.get("document_title") or path.stem,tuple(segments),metadata
