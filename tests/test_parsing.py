import tempfile
import unittest
from pathlib import Path

from src.rag_pipeline.parsing import DocumentParseError, load_parser_registry, parse_file, parse_many


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_html_preserves_title_headings_and_code_while_dropping_navigation(self):
        path = self.write("guide.html", """
            <html><head><title>Guide &amp; Setup</title></head><body>
            <nav>irrelevant navigation</nav><h1>Install</h1>
            <p>Use the local tool.</p><pre><code>run --safe</code></pre>
            <script>steal_secrets()</script><h2>Verify</h2><p>Check the result.</p>
            </body></html>
        """)
        parsed = parse_file(path)
        self.assertEqual(parsed.title, "Guide & Setup")
        self.assertEqual([segment.segment_type for segment in parsed.segments], ["text", "code", "text"])
        self.assertEqual(parsed.segments[0].headings, ("Install",))
        self.assertEqual(parsed.segments[1].text, "run --safe")
        self.assertEqual(parsed.segments[2].headings, ("Install", "Verify"))
        combined = " ".join(segment.text for segment in parsed.segments)
        self.assertNotIn("irrelevant navigation", combined)
        self.assertNotIn("steal_secrets", combined)

    def test_markdown_preserves_hierarchy_and_separate_code_segments(self):
        parsed = parse_file(self.write("guide.md", """# Handbook

Intro text.

## Install

Use these steps.

```python
    print('not executed')
```
"""))
        self.assertEqual(parsed.title, "Handbook")
        self.assertEqual(parsed.segments[0].headings, ("Handbook",))
        self.assertEqual(parsed.segments[2].segment_type, "code")
        self.assertEqual(parsed.segments[2].headings, ("Handbook", "Install"))
        self.assertIn("    print('not executed')", parsed.segments[2].text)

    def test_unclosed_markdown_code_block_runs_to_end_of_file(self):
        parsed = parse_file(self.write("unclosed.md", "# Title\n```python\ncode"))
        self.assertEqual(parsed.segments[-1].segment_type, "code")
        self.assertEqual(parsed.segments[-1].text, "code")

    def test_inline_backtick_example_does_not_open_a_fence(self):
        parsed = parse_file(self.write(
            "inline-fence.md",
            "# Title\n\nRun ```astro dev start``` to launch the example.\n\n## Next\n\nMore text.",
        ))
        combined = "\n".join(segment.text for segment in parsed.segments)
        self.assertIn("astro dev start", combined)
        self.assertIn("More text.", combined)
        self.assertTrue(any(segment.headings == ("Title", "Next") for segment in parsed.segments))

    def test_mismatched_fence_marker_is_kept_inside_code(self):
        parsed = parse_file(self.write(
            "mismatched-fence.md",
            "```python\nline one\n~~~\nline two\n```\n",
        ))
        self.assertEqual(len(parsed.segments), 1)
        self.assertEqual(parsed.segments[0].segment_type, "code")
        self.assertIn("~~~", parsed.segments[0].text)
        self.assertIn("line two", parsed.segments[0].text)

    def test_rst_preserves_sections_and_literal_code(self):
        parsed = parse_file(self.write("manual.rst", """Manual
======

Overview text.

Usage
-----

Run this::

    safe_command()
"""))
        self.assertEqual(parsed.title, "Manual")
        self.assertEqual(parsed.segments[-1].segment_type, "code")
        self.assertEqual(parsed.segments[-1].headings, ("Manual", "Usage"))
        self.assertEqual(parsed.segments[-1].text, "safe_command()")

    def test_plain_text_normalizes_unicode_and_whitespace(self):
        parsed = parse_file(self.write("notes.txt", "A\u00a0  useful\u200b\n\n\nline."))
        self.assertEqual(len(parsed.segments), 1)
        self.assertEqual(parsed.segments[0].text, "A useful\n\nline.")

    def test_empty_and_unsupported_documents_fail_explicitly(self):
        with self.assertRaisesRegex(DocumentParseError, "no extractable text"):
            parse_file(self.write("empty.txt", " \n\t"))
        parsed = parse_file(self.write("source.py", "print('not run')"))
        self.assertEqual(parsed.segments[0].language, "python")

    def test_file_size_limit_is_enforced(self):
        with self.assertRaisesRegex(DocumentParseError, "size limit"):
            parse_file(self.write("large.txt", "12345"), max_file_bytes=4)

    def test_batch_results_keep_parse_failures_visible(self):
        good = self.write("good.txt", "useful content")
        bad = self.write("bad.pdf", "not a PDF")
        outcomes = parse_many([good, bad])
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(outcomes[0].succeeded)
        self.assertFalse(outcomes[1].succeeded)
        self.assertIn("PDF extraction failed", outcomes[1].error)

    def test_malformed_pdf_is_reported(self):
        with self.assertRaisesRegex(DocumentParseError, "PDF extraction failed"):
            parse_file(self.write("broken.pdf", "not a pdf"))

    def test_structured_parsers_preserve_paths_headers_and_rows(self):
        examples = {
            "data.json": '{"service":{"name":"api","ports":[80,443]}}',
            "data.jsonl": '{"id":1,"name":"one"}\n{"id":2,"name":"two"}\n',
            "data.yaml": "service:\n  name: api\n  ports:\n    - 80\n",
            "data.yml": "enabled: true\n",
            "data.csv": "name,version\napi,1\nworker,2\n",
            "data.xml": '<services><service id="api">public</service></services>',
            "data.toml": '[service]\nname = "api"\n',
            "data.ini": '[service]\nname = api\n',
        }
        for name, body in examples.items():
            with self.subTest(name=name):
                parsed = parse_file(self.write(name, body))
                self.assertTrue(parsed.segments)
                self.assertTrue(any(segment.headings for segment in parsed.segments))
        csv_text = "\n".join(s.text for s in parse_file(self.root / "data.csv").segments)
        self.assertIn("row[2].name: api", csv_text)
        self.assertIn("row[3].name: worker", csv_text)

    def test_structured_malformed_or_unsafe_inputs_fail_closed(self):
        for name, body in (
            ("bad.json", '{"a":1,"a":2}'),
            ("bad.jsonl", '{"a":1}\nnot json\n'),
            ("bad.yaml", "!!python/object/apply:os.system ['echo unsafe']"),
            ("duplicate.yaml", "key: first\nkey: second\n"),
            ("bad.csv", "a,b\n1\n"),
            ("bad.xml", '<!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'),
            ("bad.toml", "x = [1\n"),
            ("bad.ini", "[broken\nvalue=x"),
        ):
            with self.subTest(name=name), self.assertRaises(DocumentParseError):
                parse_file(self.write(name, body))

    def test_structured_depth_size_and_registry_controls(self):
        deep = "{" + '"x":{' * 8 + '"leaf":1' + "}" * 8 + "}"
        path = self.write("deep.json", deep)
        with self.assertRaisesRegex(DocumentParseError, "nesting depth"):
            parse_file(path, parser_registry={"parsers": {".json": {"enabled": True, "limits": {"max_depth": 4}}}})
        with self.assertRaisesRegex(DocumentParseError, "size limit"):
            parse_file(self.write("huge.yaml", "x: " + "a" * 100), parser_registry={"parsers": {".yaml": {"enabled": True, "limits": {"max_file_bytes": 20}}}})
        with self.assertRaisesRegex(DocumentParseError, "nesting depth"):
            parse_file(self.write("deep.xml", "<a><b><c><d><e>value</e></d></c></b></a>"),
                       parser_registry={"parsers": {".xml": {"enabled": True, "limits": {"max_depth": 3}}}})
        registry = load_parser_registry(Path(__file__).resolve().parents[1] / "configs" / "parser_registry.json")
        self.assertTrue(parse_file(self.write("source.py", "print(1)"), parser_registry=registry).segments)
        with self.assertRaisesRegex(DocumentParseError, "Unsupported"):
            parse_file(self.write("source.py", "print(1)"), parser_registry={"parsers": {}})


if __name__ == "__main__":
    unittest.main()
