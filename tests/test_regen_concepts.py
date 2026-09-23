import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from page_document import PageDocument
from project import Project
from regen_concepts import CardRegenerator

PROGRESS = {"book": {"slug": "demo"}, "book_pdf": "book.pdf", "pdf_offset": 0,
            "extraction": {"default_code_language": "python"},
            "concepts": {"kinds": ["explain", "tradeoff"]}, "pages": {}}
PAGE = {"id": "page-4", "page": 4, "pdf_page": 4, "title": {"en": "T", "tr": "B"},
        "blocks": [{"type": "heading", "level": 1, "en": "Styles", "tr": "Tarzlar"},
                   {"type": "para", "sentences": [{"en": "A.", "tr": "A."}, {"en": "B.", "tr": "B."}]},
                   {"type": "image", "src": "x.png"}],
        "concepts": [{"id": "eski", "bad": {"code": "x"}}]}


def _pair(text="x"):
    return {"en": text, "tr": text}


def _explain(card_id):
    return {"id": card_id, "kind": "explain", "title": _pair(), "summary": _pair(), "tip": _pair()}


class RegenConceptsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self.tmp.name, "progress.json"), "w", encoding="utf-8") as handle:
            json.dump(PROGRESS, handle)
        self.project = Project(self.tmp.name)
        PageDocument(PAGE).write(self.project.pages_dir)
        self.regenerator = CardRegenerator(self.project)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_output(self, cards):
        path = self.regenerator.cards_path("out", 4)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"concepts": cards}, handle)

    def test_select_pages_expands_ranges_and_skips_untranslated(self):
        self.assertEqual(self.regenerator.select_pages(["1-5", "9"]), [4])
        self.assertEqual(self.regenerator.select_pages(["all"]), [4])

    def test_card_input_flattens_text_blocks(self):
        document = self.regenerator.card_input(PAGE)
        self.assertEqual(document["content"], [
            {"type": "heading", "en": "Styles", "tr": "Tarzlar"},
            {"type": "para", "en": "A. B.", "tr": "A. B."}])
        self.assertEqual(document["concepts"], [])

    def test_prepare_writes_input_with_spec(self):
        self.regenerator.prepare([4])
        with open(self.regenerator.cards_path("in", 4), encoding="utf-8") as handle:
            spec = json.load(handle)["concepts_spec"]
        self.assertEqual((spec["kinds"], spec["code_langs"]), (["explain", "tradeoff"], ["python"]))

    def test_apply_replaces_only_concepts(self):
        self._write_output([_explain("a"), _explain("b")])
        self.assertEqual(self.regenerator.apply([4]), {4: []})
        page = PageDocument.read(self.project.page_js(4)).data
        self.assertEqual([card["id"] for card in page["concepts"]], ["a", "b"])
        self.assertEqual(page["blocks"], PAGE["blocks"])

    def test_apply_keeps_page_when_cards_are_invalid(self):
        self._write_output([_explain("a")])
        self.assertEqual(self.regenerator.apply([4]), {4: ["kart sayısı 1 (2-4 olmalı)"]})
        self.assertEqual(PageDocument.read(self.project.page_js(4)).data["concepts"], PAGE["concepts"])

    def test_apply_reports_missing_output(self):
        self.assertIn("çıktı yok", self.regenerator.apply([4])[4][0])


if __name__ == "__main__":
    unittest.main()
