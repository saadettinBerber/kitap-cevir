import json
import os
import tempfile
import unittest

from pdf_fakes import FakePdfDocument, FakePdfPage, span
from book_pdf import BookPdf
from page_input import PageInputBuilder
from prepare_page import PagePreparer
from progress import Progress
from project import Project

PARA = {"type": "para", "sentences": [{"en": "Text."}]}
IMAGE = {"type": "image", "src": "img-1.png"}
PROGRESS = {"book_pdf": "book.pdf", "pdf_offset": 1, "book_total_pages": 4, "last_translated_page": 0,
            "chapters": [{"num": 1, "en": "One", "tr": "Bir", "start": 1}],
            "pages": {}, "pages_per_run": 2}


def _fake_document(page_count):
    pages = [FakePdfPage(lines=[(span(f"Sayfa {number}", (72, 60, 120, 72)),)], number=number)
             for number in range(1, page_count + 1)]
    return FakePdfDocument(pages)


class _FakeExtractor:
    """PDF sayfası -> bloklar; PDF taramadan girdi kurulumunu sınar."""

    def __init__(self, blocks_by_pdf_page):
        self.blocks_by_pdf_page = blocks_by_pdf_page

    def extract(self, page, image_dir):
        return {"blocks": self.blocks_by_pdf_page[page.number], "math": [],
                "running_header": {"is_chapter": False, "text": "Styles"}}


class PagePreparationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project(self.tmp.name)
        self.progress = Progress(json.loads(json.dumps(PROGRESS)))
        with open(os.path.join(self.tmp.name, "progress.json"), "w", encoding="utf-8") as handle:
            json.dump(self.progress.data, handle)
        extractor = _FakeExtractor({2: [PARA], 3: [IMAGE], 4: [PARA], 5: [PARA]})
        book_pdf = BookPdf(lambda: _fake_document(5), extractor)
        self.builder = PageInputBuilder(self.project, self.progress, book_pdf)
        self.preparer = PagePreparer(self.project, self.progress, self.builder)

    def tearDown(self):
        self.tmp.cleanup()

    def test_input_carries_chapter_section_and_context(self):
        document = self.builder.build(1)
        self.assertEqual((document["pdf_page"], document["chapter"]["en"], document["section"]["en"]),
                         (2, "One", "Styles"))
        self.assertEqual(document["context"], {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_next_pages_skip_and_mark_blank_ones(self):
        prepared, blanks = self.preparer.prepare_next(None)
        self.assertEqual(([entry["page"] for entry in prepared], blanks), ([1, 3], [2]))
        self.assertTrue(self.project.load_progress().data["pages"]["2"]["blank"])

    def test_next_pages_stop_at_the_asked_count(self):
        prepared, blanks = self.preparer.prepare_next(1)
        self.assertEqual(([entry["page"] for entry in prepared], blanks), ([1], []))

    def test_requested_blank_page_is_not_marked(self):
        self.assertEqual(self.preparer.prepare_page(2), [])
        self.assertNotIn("2", self.project.load_progress().data["pages"])


if __name__ == "__main__":
    unittest.main()
