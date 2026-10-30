"""Behavioral checks for coverage, evidence integrity and offline packaging."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_site import build
from validate_lesson import validate_data


class CourseContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.prepared = self.root / "prepared"
        (self.prepared / "pages").mkdir(parents=True)
        source = {"filename": "fixture.pdf", "sha256": "a" * 64, "page_count": 2, "format": "pdf", "title": "Fixture"}
        self.manifest = {"schema_version": 1, "source": source, "warnings": [], "pages": []}
        for n in (1, 2):
            rel = f"pages/page-{n:04}.png"
            Image.new("RGB", (160, 90), (n * 50, 100, 180)).save(self.prepared / rel)
            self.manifest["pages"].append({"page": n, "printed_page": str(n + 10), "text": "Source", "notes": "", "image": rel, "width": 160, "height": 90, "warnings": []})
        block = {"kind": "source", "text": "One explanatory statement."}
        self.lesson = {
            "schema_version": 1, "title": "Fixture", "subtitle": "Small valid course",
            "source": {key: source[key] for key in ("filename", "sha256", "page_count")},
            "overview": {"summary": "Learn a rule then apply it.", "objectives": ["Explain the rule"], "prerequisites": [], "storyline": [{"title": "Main", "pages": [1, 2], "summary": "Rule and use"}]},
            "pages": [{"page": n, "title": f"Page {n}", "section": "Main", "blocks": [copy.deepcopy(block)], "role": copy.deepcopy(block), "bridge_prev": copy.deepcopy(block), "bridge_next": copy.deepcopy(block), "takeaway": copy.deepcopy(block), "concept_ids": [f"c{n}"]} for n in (1, 2)],
            "concepts": [{"id": f"c{n}", "label": f"Concept {n}", "description": "Definition", "group": "Main", "pages": [n], "kind": "source"} for n in (1, 2)],
            "relations": [{"id": "r1", "from": "c1", "to": "c2", "type": "application", "label": "Use", "explanation": "Page 2 applies the rule stated on page 1.", "pages": [1, 2], "kind": "inference"}],
        }

    def tearDown(self):
        self.temp.cleanup()

    def errors(self):
        return validate_data(self.lesson, self.manifest, self.prepared)

    def write_inputs(self):
        source = self.prepared / "source.json"
        lesson = self.root / "lesson.json"
        source.write_text(json.dumps(self.manifest))
        lesson.write_text(json.dumps(self.lesson))
        return source, lesson

    def test_complete_course_and_packaged_assets(self):
        self.assertEqual(self.errors(), [])
        result = build(*self.write_inputs(), self.root / "site")
        with zipfile.ZipFile(result["archive"]) as archive:
            names = set(archive.namelist())
            for rel in ("index.html", "lesson.json", "source.json", "pages/page-0002.png", "assets/vendor/katex/katex.min.js", "assets/vendor/katex/fonts/KaTeX_Main-Regular.woff2"):
                self.assertIn("site/" + rel, names)

    def test_missing_and_reordered_pages_are_rejected(self):
        self.lesson["pages"].reverse()
        self.assertTrue(any("physical page" in e for e in self.errors()))
        self.lesson["pages"].pop()
        with self.assertRaises(ValueError):
            build(*self.write_inputs(), self.root / "site")
        self.assertFalse((self.root / "site").exists())

    def test_mismatched_source_is_rejected(self):
        self.lesson["source"]["sha256"] = "b" * 64
        self.assertTrue(any("sha256" in e for e in self.errors()))

    def test_corrupted_formula_control_character_is_rejected(self):
        self.lesson["pages"][0]["bridge_prev"]["text"] = "$\x08ar v_3$"
        self.assertTrue(any("control character" in e for e in self.errors()))

    def test_unrenderable_formula_is_not_packaged(self):
        self.lesson["pages"][0]["blocks"][0]["text"] = r"$$\notarealcommand{x}$$"
        with self.assertRaisesRegex(ValueError, "Formula validation failed"):
            build(*self.write_inputs(), self.root / "site")
        self.assertFalse((self.root / "site").exists())

    def test_graph_references_and_evidence_are_checked(self):
        self.lesson["concepts"][0]["pages"] = [2]
        self.lesson["relations"][0]["pages"] = [1]
        self.lesson["relations"][0]["to"] = "missing"
        errors = self.errors()
        self.assertTrue(any("disagree" in e for e in errors))
        self.assertTrue(any("evidence" in e for e in errors))
        self.assertTrue(any("unknown concept" in e for e in errors))

    def test_corrupt_and_escaping_images_are_rejected(self):
        (self.prepared / self.manifest["pages"][0]["image"]).write_text("broken image")
        self.assertTrue(any("unreadable image" in e for e in self.errors()))
        self.manifest["pages"][0]["image"] = "../outside.png"
        self.assertTrue(any("must stay" in e for e in self.errors()))

    def test_course_text_cannot_close_embedded_script(self):
        payload = '</script><script>alert("x")</script>'
        self.lesson["pages"][0]["blocks"][0]["text"] = payload
        result = build(*self.write_inputs(), self.root / "site")
        content = Path(result["index"]).read_text()
        self.assertNotIn(payload, content)
        class Embedded(HTMLParser):
            def __init__(self):
                super().__init__()
                self.active = False
                self.parts = []
            def handle_starttag(self, tag, attrs):
                self.active = tag == "script" and dict(attrs).get("id") == "lesson-data"
            def handle_endtag(self, tag):
                if tag == "script": self.active = False
            def handle_data(self, data):
                if self.active: self.parts.append(data)
        parser = Embedded()
        parser.feed(content)
        restored = json.loads("".join(parser.parts))
        self.assertEqual(restored["pages"][0]["blocks"][0]["text"], payload)

    def test_rebuild_preserves_unrelated_user_files(self):
        inputs = self.write_inputs()
        out = self.root / "site"
        build(*inputs, out)
        (out / "personal-notes.txt").write_text("keep")
        self.lesson["title"] = "Updated"
        build(*self.write_inputs(), out)
        self.assertEqual((out / "personal-notes.txt").read_text(), "keep")
        self.assertEqual(json.loads((out / "lesson.json").read_text())["title"], "Updated")


if __name__ == "__main__":
    unittest.main()
