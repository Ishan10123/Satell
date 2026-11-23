"""Bounded, non-executing extractors for structured text formats."""
from __future__ import annotations

import configparser
import csv
import io
import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

from .extractors import DocumentParseError, DocumentSegment, normalize_text


DEFAULT_LIMITS = {
    "max_file_bytes": 10 * 1024 * 1024,
    "max_depth": 64,
    "max_nodes": 100_000,
    "max_records": 50_000,
    "max_columns": 512,
    "max_cell_chars": 100_000,
}


def _check_depth(text: str, maximum: int) -> None:
    depth = 0
    quote: str | None = None
    escaped = False
    for char in text:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
            if depth > maximum:
                raise DocumentParseError(f"Structured document exceeds nesting depth limit ({maximum}).")
        elif char in "]}":
            depth = max(0, depth - 1)


def _walk(value: Any, path: str, output: list[tuple[str, str]], limits: dict[str, int], depth: int = 0) -> None:
    if depth > limits["max_depth"]:
        raise DocumentParseError("Structured document exceeds maximum nesting depth.")
    if len(output) >= limits["max_nodes"]:
        raise DocumentParseError("Structured document exceeds maximum node count.")
    if isinstance(value, dict):
        for key, child in value.items():
            _walk(child, f"{path}.{key}" if path else str(key), output, limits, depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", output, limits, depth + 1)
    else:
        rendered = "null" if value is None else ("true" if value is True else "false" if value is False else str(value))
        if rendered:
            output.append((path or "$", rendered))


def _segments(fields: list[tuple[str, str]], max_cell_chars: int) -> tuple[DocumentSegment, ...]:
    out = []
    for path, value in fields:
        if len(value) > max_cell_chars:
            raise DocumentParseError("Structured field exceeds maximum cell/value size.")
        text = normalize_text(f"{path}: {value}")
        if text:
            out.append(DocumentSegment(text, "text", (path,)))
    if not out:
        raise DocumentParseError("Document contains no extractable structured values.")
    return tuple(out)


def parse_json(text: str, limits: dict[str, int]) -> tuple[str, tuple[DocumentSegment, ...]]:
    _check_depth(text, limits["max_depth"])
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"duplicate object key: {key}")
            value[key] = item
        return value
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"invalid constant {token}")))
    except (ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise DocumentParseError(f"Malformed JSON: {exc}") from exc
    fields: list[tuple[str, str]] = []
    _walk(value, "$", fields, limits)
    return "", _segments(fields, limits["max_cell_chars"])


def parse_jsonl(text: str, limits: dict[str, int]) -> tuple[str, tuple[DocumentSegment, ...]]:
    fields: list[tuple[str, str]] = []
    rows = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        rows += 1
        if rows > limits["max_records"]:
            raise DocumentParseError("JSONL exceeds maximum record count.")
        try:
            value = json.loads(line, object_pairs_hook=lambda pairs: _unique_pairs(pairs), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        except (ValueError, json.JSONDecodeError, RecursionError) as exc:
            raise DocumentParseError(f"Malformed JSONL at line {line_no}: {exc}") from exc
        _check_depth(line, limits["max_depth"])
        row_fields: list[tuple[str, str]] = []
        _walk(value, "$", row_fields, limits)
        fields.extend((f"record[{line_no}].{path.removeprefix('$.')}", val) for path, val in row_fields)
        if len(fields) > limits["max_nodes"]:
            raise DocumentParseError("JSONL exceeds maximum node count.")
    return "", _segments(fields, limits["max_cell_chars"])


def _unique_pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError(f"duplicate object key: {key}")
        value[key] = item
    return value


def parse_yaml(text: str, limits: dict[str, int]) -> tuple[str, tuple[DocumentSegment, ...]]:
    _check_depth(text, limits["max_depth"])
    try:
        # Reject alias/anchor constructs to avoid expansion and ensure predictable resource use.
        for token in yaml.scan(text):
            if token.__class__.__name__ in {"AliasToken", "AnchorToken"}:
                raise DocumentParseError("YAML anchors and aliases are not supported.")
        class UniqueSafeLoader(yaml.SafeLoader):
            pass

        def construct_mapping(loader, node, deep=False):
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise yaml.constructor.ConstructorError("while constructing a mapping", node.start_mark,
                                                            f"duplicate key {key!r}", key_node.start_mark)
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
        value = yaml.load(text, Loader=UniqueSafeLoader)
    except DocumentParseError:
        raise
    except (yaml.YAMLError, RecursionError) as exc:
        raise DocumentParseError(f"Malformed or unsafe YAML: {exc}") from exc
    fields: list[tuple[str, str]] = []
    _walk(value, "$", fields, limits)
    return "", _segments(fields, limits["max_cell_chars"])


def parse_toml(text: str, limits: dict[str, int]) -> tuple[str, tuple[DocumentSegment, ...]]:
    _check_depth(text, limits["max_depth"])
    try:
        value = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        raise DocumentParseError(f"Malformed TOML: {exc}") from exc
    fields: list[tuple[str, str]] = []
    _walk(value, "$", fields, limits)
    return "", _segments(fields, limits["max_cell_chars"])


def parse_ini(text: str, limits: dict[str, int]) -> tuple[str, tuple[DocumentSegment, ...]]:
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise DocumentParseError(f"Malformed INI: {exc}") from exc
    if len(parser.sections()) > limits["max_records"]:
        raise DocumentParseError("INI exceeds maximum section count.")
    fields = []
    for section in parser.sections():
        for key, value in parser.items(section, raw=True):
            fields.append((f"[{section}].{key}", value))
            if len(fields) > limits["max_nodes"]:
                raise DocumentParseError("INI exceeds maximum key count.")
    return "", _segments(fields, limits["max_cell_chars"])


def parse_csv(text: str, limits: dict[str, int]) -> tuple[str, tuple[DocumentSegment, ...]]:
    try:
        rows = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = next(rows, None)
        if not headers:
            raise DocumentParseError("CSV has no header row.")
        if len(headers) > limits["max_columns"] or any(not h.strip() for h in headers) or len(set(headers)) != len(headers):
            raise DocumentParseError("CSV headers are empty, duplicated, or exceed column limit.")
        fields = []
        for row_no, row in enumerate(rows, start=2):
            if row_no - 1 > limits["max_records"]:
                raise DocumentParseError("CSV exceeds maximum record count.")
            if len(row) != len(headers):
                raise DocumentParseError(f"CSV row {row_no} has {len(row)} fields; expected {len(headers)}.")
            for header, cell in zip(headers, row):
                fields.append((f"row[{row_no}].{header}", cell))
                if len(fields) > limits["max_nodes"]:
                    raise DocumentParseError("CSV exceeds maximum cell count.")
        return "", _segments(fields, limits["max_cell_chars"])
    except csv.Error as exc:
        raise DocumentParseError(f"Malformed CSV: {exc}") from exc


def parse_xml(text: str, limits: dict[str, int]) -> tuple[str, tuple[DocumentSegment, ...]]:
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, flags=re.IGNORECASE):
        raise DocumentParseError("XML DTD and entity declarations are not supported.")
    fields: list[tuple[str, str]] = []
    nodes = 0
    stack: list[tuple[str, dict[str, int], str]] = []
    try:
        for event, element in ET.iterparse(io.StringIO(text), events=("start", "end")):
            if event == "start":
                nodes += 1
                depth = len(stack) + 1
                if nodes > limits["max_nodes"] or depth > limits["max_depth"]:
                    raise DocumentParseError("XML exceeds maximum node count or nesting depth.")
                tag = str(element.tag)
                if stack:
                    parent_path, child_counts, _ = stack[-1]
                    child_counts[tag] = child_counts.get(tag, 0) + 1
                    path = f"{parent_path}/{tag}[{child_counts[tag]}]"
                else:
                    path = f"/{tag}[1]"
                stack.append((path, {}, tag))
                for key, value in element.attrib.items():
                    fields.append((f"{path}/@{key}", value))
            else:
                path, _, _ = stack[-1]
                if element.text and element.text.strip():
                    fields.append((path, element.text.strip()))
                if element.tail and element.tail.strip():
                    fields.append((f"{path}/tail", element.tail.strip()))
                stack.pop()
                element.clear()
    except DocumentParseError:
        raise
    except ET.ParseError as exc:
        raise DocumentParseError(f"Malformed XML: {exc}") from exc
    return "", _segments(fields, limits["max_cell_chars"])


PARSERS = {".json": parse_json, ".jsonl": parse_jsonl, ".yaml": parse_yaml, ".yml": parse_yaml,
           ".csv": parse_csv, ".xml": parse_xml, ".toml": parse_toml, ".ini": parse_ini}
