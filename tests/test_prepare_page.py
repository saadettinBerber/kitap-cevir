import json
import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from page_input import PageInputBuilder, context_snippets
from prepare_page import PagePreparer
from project import Project

PARA = {"type": "para", "sentences": [{"en": "Text."}]}
IMAGE = {"type": "image", "src": "img-1.png"}
PROGRESS = {"book_pdf": "book.pdf", "pdf_offset": 1, "book_total_pages": 4, "last_translated_page": 0,
            "chapters": [{"num": 1, "en": "One", "tr": "Bir", "start": 1}],
            "pages": {}, "pages_per_run": 2}


def _document(page_count):
    document = fitz.open()
    for number in range(1, page_count + 1):
        document.new_page().insert_text((72, 72), f"Sayfa {number}")
    return document


class ContextSnippetsTest(unittest.TestCase):
    def test_middle_page_sees_both_neighbours(self):
        with _document(3) as document:
            self.assertEqual(context_snippets(document, 2), {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_first_page_has_no_previous_text(self):
        with _document(3) as document:
            self.assertEqual(context_snippets(document, 1)["prev_tail"], "")

    def test_last_page_has_no_following_text(self):
        with _document(3) as document:
            self.assertEqual(context_snippets(document, 3)["next_head"], "")

    def test_single_page_document_has_no_context(self):
        with _document(1) as document:
            self.assertEqual(context_snippets(document, 1), {"prev_tail": "", "next_head": ""})


class _FakeExtractor:
    """PDF sayfası -> bloklar; PDF taramadan girdi kurulumunu sınar."""

    def __init__(self, blocks_by_pdf_page):
        self.blocks_by_pdf_page = blocks_by_pdf_page

    def extract(self, pdf_path, pdf_page, image_dir):
        return {"blocks": self.blocks_by_pdf_page[pdf_page], "math": [],
                "running_header": {"is_chapter": False, "text": "Styles"}}


class PagePreparationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with _document(5) as document:
            document.save(os.path.join(self.tmp.name, "book.pdf"))
        self.project = Project(self.tmp.name)
        self.progress = json.loads(json.dumps(PROGRESS))
        with open(os.path.join(self.tmp.name, "progress.json"), "w", encoding="utf-8") as handle:
            json.dump(self.progress, handle)
        extractor = _FakeExtractor({2: [PARA], 3: [IMAGE], 4: [PARA], 5: [PARA]})
        self.builder = PageInputBuilder(self.project, self.progress, extractor)
        self.preparer = PagePreparer(self.project, self.progress, self.builder)

    def tearDown(self):
        self.tmp.cleanup()

    def test_input_carries_chapter_section_and_context(self):
        document = self.builder.build(1)
        self.assertEqual((document["pdf_page"], document["chapter"]["en"], document["section"]["en"]),
                         (2, "One", "Styles"))
        self.assertEqual(document["context"], {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_next_pages_skip_and_mark_blank_ones(self):
        prepared = self.preparer.prepare_pages("next", None)
        self.assertEqual([entry["page"] for entry in prepared], [1, 3])
        self.assertTrue(self.project.load_progress()["pages"]["2"]["blank"])

    def test_requested_blank_page_is_not_marked(self):
        self.assertEqual(self.preparer.prepare_pages("2", None), [])
        self.assertNotIn("2", self.project.load_progress()["pages"])


if __name__ == "__main__":
    unittest.main()
