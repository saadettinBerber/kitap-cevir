import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from page_document import PageDocument
from project import Project
from regen_concepts import CardInputs, CardOutputs, select_pages

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


class SelectPagesTest(unittest.TestCase):
    def test_ranges_are_expanded_and_untranslated_pages_skipped(self):
        self.assertEqual(select_pages(["1-5", "9"], [4, 7]), ([4], [1, 2, 3, 5, 9]))

    def test_all_selects_every_translated_page(self):
        self.assertEqual(select_pages(["all"], [4, 7]), ([4, 7], []))


class _BookTestCase(unittest.TestCase):
    """Tek çevrilmiş sayfalı (4) bir kitap projesi; testi yoktur."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self.tmp.name, "progress.json"), "w", encoding="utf-8") as handle:
            json.dump(PROGRESS, handle)
        self.project = Project(self.tmp.name)
        PageDocument(PAGE).write(self.project.page_js(PAGE["page"]))

    def tearDown(self):
        self.tmp.cleanup()


class CardInputsTest(_BookTestCase):
    def setUp(self):
        super().setUp()
        self.inputs = CardInputs.for_project(self.project)

    def test_card_input_flattens_text_blocks(self):
        document = self.inputs.card_input(PAGE)
        self.assertEqual(document["content"], [
            {"type": "heading", "en": "Styles", "tr": "Tarzlar"},
            {"type": "para", "en": "A. B.", "tr": "A. B."}])
        self.assertEqual(document["concepts"], [])

    def test_prepare_writes_input_with_spec(self):
        self.inputs.prepare([4])
        with open(self.project.work_cards_file("in", 4), encoding="utf-8") as handle:
            spec = json.load(handle)["concepts_spec"]
        self.assertEqual((spec["kinds"], spec["code_langs"]), (["explain", "tradeoff"], ["python"]))


class CardOutputsTest(_BookTestCase):
    def setUp(self):
        super().setUp()
        self.outputs = CardOutputs.for_project(self.project)

    def _write_output(self, cards):
        path = self.project.work_cards_file("out", 4)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"concepts": cards}, handle)

    def test_apply_replaces_only_concepts(self):
        self._write_output([_explain("a"), _explain("b")])
        self.assertEqual(self.outputs.apply([4]), {4: []})
        page = PageDocument.read(self.project.page_js(4)).data
        self.assertEqual([card["id"] for card in page["concepts"]], ["a", "b"])
        self.assertEqual(page["blocks"], PAGE["blocks"])

    def test_apply_keeps_page_when_cards_are_invalid(self):
        self._write_output([_explain("a")])
        self.assertEqual(self.outputs.apply([4]), {4: ["kart sayısı 1 (2-4 olmalı)"]})
        self.assertEqual(PageDocument.read(self.project.page_js(4)).data["concepts"], PAGE["concepts"])

    def test_apply_reports_missing_output(self):
        self.assertIn("çıktı yok", self.outputs.apply([4])[4][0])

    def test_missing_page_is_not_reported_as_missing_output(self):
        self._write_output([_explain("a"), _explain("b")])
        os.remove(self.project.page_js(4))
        with self.assertRaises(FileNotFoundError):
            self.outputs.apply([4])

if __name__ == "__main__":
    unittest.main()
