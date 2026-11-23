import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.rag_pipeline.parsing import DocumentParseError, parse_file
from src.rag_pipeline.chunking import ChunkConfig, chunk_document


class AdvancedParsingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_python_ast_extracts_named_symbols_and_line_provenance(self):
        parsed = parse_file(self.write("sample.py", "import math\n\ndef area(r):\n    return math.pi * r * r\n"))
        self.assertEqual(parsed.metadata["extension"], ".py")
        function = next(segment for segment in parsed.segments if segment.symbol_name == "area")
        self.assertEqual(function.language, "python")
        self.assertEqual((function.line_start, function.line_end), (3, 4))

    def test_code_chunks_keep_line_and_symbol_provenance_at_boundaries(self):
        class CharacterTokenizer:
            def encode(self, text):
                return list(text)

            def decode(self, tokens):
                return "".join(tokens)

        content = {"content_id": "content", "segments": [{
            "text": "def run():\n    first()\n    second()\n    third()",
            "segment_type": "code", "headings": ["module", "function run"],
            "line_start": 10, "line_end": 13, "language": "python", "symbol_name": "run",
        }]}
        chunks = chunk_document(content, {"document_id": "doc", "segment_page_numbers": [None]},
                                CharacterTokenizer(), "token_based",
                                ChunkConfig(max_tokens=25, overlap_tokens=0))
        parts = [part for chunk in chunks for part in chunk.segments]
        self.assertTrue(all(part["language"] == "python" and part["symbol_name"] == "run" for part in parts))
        self.assertTrue(all(part["line_start"] <= part["line_end"] for part in parts))
        self.assertEqual(parts[0]["line_start"], 10)

    def test_non_python_source_keeps_structural_symbol_and_path_provenance(self):
        path = self.write("widget.go", "package demo\n\nfunc Build() string {\n return \"safe\"\n}\n")
        parsed = parse_file(path)
        self.assertEqual(parsed.segments[0].language, "go")
        function = next(segment for segment in parsed.segments if segment.symbol_name == "Build")
        self.assertGreaterEqual(function.line_start, 1)
        self.assertEqual(parsed.source_path, str(path.resolve()))

    def test_structured_formats_preserve_paths_headers_and_rows(self):
        cases = [
            ("data.json", '{"service":{"port":8080}}', "service.port"),
            ("data.jsonl", '{"id":1,"name":"Ada"}\n', "record[1].name"),
            ("data.yaml", "service:\n  port: 8080\n", "service.port"),
            ("data.yml", "service:\n  port: 8080\n", "service.port"),
            ("data.csv", "name,role\nAda,admin\n", "row[2].role"),
            ("data.xml", "<service><port>8080</port></service>", "/service[1]/port[1]"),
            ("data.toml", "[service]\nport=8080\n", "service.port"),
            ("data.ini", "[service]\nport=8080\n", "[service].port"),
        ]
        for name, text, expected in cases:
            with self.subTest(extension=name):
                parsed = parse_file(self.write(name, text))
                self.assertTrue(any(expected in (s.text + " " + " ".join(s.headings)) for s in parsed.segments))

    def test_structured_parsers_fail_closed_on_malformed_and_unsafe_input(self):
        for name, text in [
            ("bad.json", '{"x":'),
            ("bad.csv", "name,role\nAda\n"),
            ("bad.yaml", "base: &x [1]\ncopy: *x\n"),
            ("bad.xml", '<!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'),
            ("deep.json", "[" * 80 + "0" + "]" * 80),
        ]:
            with self.subTest(name=name), self.assertRaises(DocumentParseError):
                parse_file(self.write(name, text))

    def test_diagram_extractors_keep_labels_and_do_not_execute_content(self):
        cases = [
            ("graph.dot", 'digraph Flow { A -> B; label="Checkout"; }', "Checkout"),
            ("board.excalidraw", json.dumps({"elements": [{"type": "text", "text": "Deploy"}]}), "Deploy"),
            ("board.gliffy", json.dumps({"contentType": "application/gliffy+json", "diagram": {"title": "Deploy"}}), "Deploy"),
            ("icon.svg", '<svg xmlns="http://www.w3.org/2000/svg"><title>Deploy</title><text>Release</text><path d="x"/></svg>', "Deploy"),
        ]
        for name, text, expected in cases:
            with self.subTest(name=name):
                parsed = parse_file(self.write(name, text))
                combined = " ".join(s.text for s in parsed.segments)
                self.assertIn(expected, combined)
                self.assertNotIn("path", combined)

    def test_svg_dtd_is_rejected_and_template_is_literal(self):
        with self.assertRaises(DocumentParseError):
            parse_file(self.write("bad.svg", '<!DOCTYPE svg [<!ENTITY x "bad">]><svg>&x;</svg>'))
        parsed = parse_file(self.write("template.gotmpl", "Hello {{ .Name }}"))
        self.assertIn("{{ .Name }}", " ".join(s.text for s in parsed.segments))

    def test_notebook_outputs_are_ignored_and_sql_keeps_statement_lines(self):
        notebook = {"cells": [{"cell_type": "code", "source": ["print('source')"], "outputs": [{"text": ["secret output"]}]}], "metadata": {}}
        parsed = parse_file(self.write("demo.ipynb", json.dumps(notebook)))
        self.assertIn("print('source')", parsed.segments[0].text)
        self.assertNotIn("secret output", " ".join(s.text for s in parsed.segments))
        sql = parse_file(self.write("query.sql", "-- schema\nCREATE TABLE users(id INT);\n"))
        self.assertEqual(sql.segments[0].line_start, 2)
        self.assertEqual(sql.segments[0].language, "sql")

    def test_docx_xlsx_pptx_extract_text_and_structured_metadata(self):
        from docx import Document
        from openpyxl import Workbook
        from pptx import Presentation
        from pptx.util import Inches

        docx = self.root / "guide.docx"
        doc = Document()
        doc.core_properties.title = "Guide title"
        doc.add_heading("Install", level=1)
        doc.add_paragraph("Run locally")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text, table.cell(0, 1).text = "Command", "Purpose"
        table.cell(1, 0).text, table.cell(1, 1).text = "ragctl", "Index"
        doc.save(docx)
        parsed_docx = parse_file(docx)
        self.assertEqual(parsed_docx.metadata["document_title"], "Guide title")
        self.assertTrue(any("table[1].row[2].Command: ragctl" == s.text for s in parsed_docx.segments))

        xlsx = self.root / "guide.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.title = "Commands"
        sheet.append(["Command", "Purpose"])
        sheet.append(["ragctl", "Index"])
        book.save(xlsx)
        parsed_xlsx = parse_file(xlsx)
        self.assertEqual(parsed_xlsx.metadata["sheet_names"], ["Commands"])
        self.assertTrue(any("Commands.row[2].Command: ragctl" == s.text for s in parsed_xlsx.segments))

        pptx = self.root / "guide.pptx"
        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
        shape.text = "Install locally"
        deck.save(pptx)
        parsed_pptx = parse_file(pptx)
        self.assertTrue(any("Install locally" in s.text and s.page_number == 1 for s in parsed_pptx.segments))

    def test_office_zip_bomb_and_size_limits_fail_closed(self):
        path = self.root / "bomb.docx"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("doc.xml", "A" * 1_000_000)
        with self.assertRaises(DocumentParseError):
            parse_file(path, parser_registry={"parsers": {".docx": {"enabled": True, "parser": "docx", "limits": {"max_archive_ratio": 2}}}})
        with self.assertRaises(DocumentParseError):
            parse_file(self.write("large.json", '{"x":"123456"}'), max_file_bytes=5)


if __name__ == "__main__":
    unittest.main()
