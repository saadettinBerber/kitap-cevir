import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from page_document import PageDocument
from project import Project
from translated_pages import TranslatedPages
from regen_concepts import CardInputs, CardOutputs, select_pages

PAGE = 4
PROGRESS = {"book": {"slug": "demo"}, "book_pdf": "book.pdf", "pdf_offset": 0,
            "extraction": {"default_code_language": "python"},
            "concepts": {"kinds": ["explain", "tradeoff"]}, "pages": {}}
SPEC = {"kinds": ["explain", "tradeoff"], "code_langs": ["python"], "code_comment_lang": "en"}
PAGE_DATA = {"id": "page-4", "page": PAGE, "pdf_page": 4, "title": {"en": "T", "tr": "B"},
             "chapter": {"num": 1, "en": "One", "tr": "Bir"}, "section": {"en": "S", "tr": "K"},
             "blocks": [{"type": "heading", "level": 1, "en": "Styles", "tr": "Tarzlar"},
                        {"type": "para", "sentences": [{"en": "A.", "tr": "A."}, {"en": "B.", "tr": "B."}]},
                        {"type": "image", "src": "x.png"}],
             "concepts": [{"id": "eski", "bad": {"code": "x"}}]}


def _pair(text="x"):
    return {"en": text, "tr": text}


def _explain(card_id):
    return {"id": card_id, "kind": "explain", "title": _pair(), "summary": _pair(), "tip": _pair()}


class SelectPagesTest(unittest.TestCase):
    def test_ranges_are_expanded(self):
        self.assertEqual(select_pages(["1-5", "9"], [4, 7, 9])[0], [4, 9])

    def test_untranslated_pages_are_skipped_in_order(self):
        self.assertEqual(select_pages(["9", "1-3"], [4, 7])[1], [1, 2, 3, 9])

    def test_all_selects_every_translated_page(self):
        self.assertEqual(select_pages(["all"], [4, 7]), ([4, 7], []))


class _BookTestCase(unittest.TestCase):
    """Tek çevrilmiş sayfalı (PAGE) bir kitap projesi; testi yoktur."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self.tmp.name, "progress.json"), "w", encoding="utf-8") as handle:
            json.dump(PROGRESS, handle)
        self.project = Project(self.tmp.name)
        self.pages = TranslatedPages(self.project)
        self.pages.save(PageDocument(PAGE_DATA))

    def tearDown(self):
        self.tmp.cleanup()


class CardInputsTest(_BookTestCase):
    def setUp(self):
        super().setUp()
        self.inputs = CardInputs.for_project(self.project)

    def test_card_input_carries_the_page_heading_fields(self):
        document = self.inputs.card_input(PageDocument(PAGE_DATA))
        self.assertEqual({key: document[key] for key in ("id", "page", "chapter", "section", "title")},
                         {key: PAGE_DATA[key] for key in ("id", "page", "chapter", "section", "title")})

    def test_heading_fields_missing_on_the_page_are_empty(self):
        heading_fields = ("chapter", "section", "title")
        bare_page = {key: value for key, value in PAGE_DATA.items() if key not in heading_fields}
        document = self.inputs.card_input(PageDocument(bare_page))
        self.assertEqual([document[key] for key in heading_fields], [{}, {}, {}])

    def test_card_input_flattens_text_blocks(self):
        document = self.inputs.card_input(PageDocument(PAGE_DATA))
        self.assertEqual(document["content"], [
            {"type": "heading", "en": "Styles", "tr": "Tarzlar"},
            {"type": "para", "en": "A. B.", "tr": "A. B."}])

    def test_card_input_asks_for_new_cards_by_the_book_spec(self):
        document = self.inputs.card_input(PageDocument(PAGE_DATA))
        self.assertEqual((document["concepts_spec"], document["concepts"]), (SPEC, []))

    def test_prepare_writes_the_input_file(self):
        self.inputs.prepare([PAGE])
        with open(self.project.work_cards_file("in", PAGE), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["id"], "page-4")

    def test_prepare_lists_the_written_files_relative_to_the_project(self):
        self.assertEqual(self.inputs.prepare([PAGE]), ["_work/cards/in/page-4.json"])


class CardOutputsTest(_BookTestCase):
    def setUp(self):
        super().setUp()
        self.outputs = CardOutputs.for_project(self.project)

    def _write_output(self, cards):
        path = self.project.work_cards_file("out", PAGE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"concepts": cards}, handle)

    def _saved_page(self):
        return self.pages.get(PAGE)

    def test_valid_cards_have_no_problems(self):
        self._write_output([_explain("a"), _explain("b")])
        self.assertEqual(self.outputs.apply([PAGE]), {PAGE: []})

    def test_valid_cards_replace_only_the_old_cards(self):
        self._write_output([_explain("a"), _explain("b")])
        self.outputs.apply([PAGE])
        self.assertEqual(self._saved_page(), PageDocument({**PAGE_DATA, "concepts": [_explain("a"), _explain("b")]}))

    def test_invalid_cards_are_reported(self):
        self._write_output([_explain("a")])
        self.assertEqual(self.outputs.apply([PAGE]), {PAGE: ["kart sayısı 1 (2-4 olmalı)"]})

    def test_invalid_cards_leave_the_page(self):
        self._write_output([_explain("a")])
        self.outputs.apply([PAGE])
        self.assertEqual(self._saved_page(), PageDocument(PAGE_DATA))

    def test_apply_reports_missing_output(self):
        self.assertEqual(self.outputs.apply([PAGE]), {PAGE: ["çıktı yok: _work/cards/out/page-4.json"]})

    def test_missing_page_is_not_reported_as_missing_output(self):
        self._write_output([_explain("a"), _explain("b")])
        os.remove(self.project.page_js(PAGE))
        with self.assertRaises(FileNotFoundError):
            self.outputs.apply([PAGE])


if __name__ == "__main__":
    unittest.main()
