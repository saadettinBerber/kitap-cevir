import contextlib
import io
import json
import os
import tempfile
import unittest

from pdf_fakes import FakePdfDocument, FakePdfPage, span
from book_pdf import BookPdf
from book_settings import BookSettings
from page_input import PageInputBuilder
from prepare_page import PagePreparer, PreparationReport
from progress import Progress
from project import Project

PARA = {"type": "para", "sentences": [{"en": "Text."}]}
IMAGE = {"type": "image", "src": "img-1.png"}
MATH = {"type": "math", "src": "eq-1.png", "text": "x", "latex": ""}
BLANK_PAGE = 2
PAGE_COUNT = 5
LINE_BOX = (72, 60, 120, 72)
PROGRESS = {"book_pdf": "book.pdf", "pdf_offset": 1, "book_total_pages": 4, "last_translated_page": 0,
            "chapters": [{"num": 1, "en": "One", "tr": "Bir", "start": 1}],
            "pages": {}, "pages_per_run": 2}


def _fake_document():
    pages = [FakePdfPage(lines=[(span(f"Sayfa {number}", LINE_BOX),)], number=number)
             for number in range(1, PAGE_COUNT + 1)]
    return FakePdfDocument(pages)


class _FakeExtractor:
    """PDF sayfası -> bloklar; PDF taramadan girdi kurulumunu sınar."""

    def __init__(self, blocks_by_pdf_page):
        self._blocks_by_pdf_page = blocks_by_pdf_page

    def extract(self, page, image_dir):
        return {"blocks": self._blocks_by_pdf_page[page.number], "math": [],
                "running_header": {"is_chapter": False, "text": "Styles"}, "skipped_equations": []}


class _SkippingExtractor(_FakeExtractor):
    """Her sayfada bir satır içi denklemi yerleştiremeyen çıkarıcı."""

    def extract(self, page, image_dir):
        return {**super().extract(page, image_dir), "skipped_equations": [f"denklem {page.number} atlandı"]}


class PagePreparerTest(unittest.TestCase):
    """Kitap sayfası 2 (PDF 3) yalnız görsel taşır: boş sayfadır."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project(self.tmp.name)
        progress = Progress(json.loads(json.dumps(PROGRESS)))
        self.project.save_progress(progress)
        extractor = _FakeExtractor({2: [PARA, MATH], 3: [IMAGE], 4: [PARA], 5: [PARA]})
        builder = PageInputBuilder(progress, BookPdf(_fake_document, extractor))
        self.preparer = PagePreparer(self.project, builder)

    def tearDown(self):
        self.tmp.cleanup()

    def _saved_pages(self):
        with open(os.path.join(self.tmp.name, "progress.json"), encoding="utf-8") as handle:
            return json.load(handle)["pages"]

    def test_next_pages_skip_blank_ones(self):
        prepared, blanks = self.preparer.prepare_next(None)
        self.assertEqual(([entry["page"] for entry in prepared], blanks), ([1, 3], [BLANK_PAGE]))

    def test_skipped_blank_page_is_marked(self):
        self.preparer.prepare_next(None)
        self.assertTrue(self._saved_pages()[str(BLANK_PAGE)]["blank"])

    def test_next_pages_stop_at_the_asked_count(self):
        prepared, blanks = self.preparer.prepare_next(1)
        self.assertEqual(([entry["page"] for entry in prepared], blanks), ([1], []))

    def test_requested_blank_page_is_not_prepared(self):
        self.assertEqual(self.preparer.prepare_page(BLANK_PAGE), [])

    def test_requested_blank_page_is_not_marked(self):
        self.preparer.prepare_page(BLANK_PAGE)
        self.assertNotIn(str(BLANK_PAGE), self._saved_pages())

    def test_summary_tells_where_the_input_is_and_what_it_holds(self):
        self.assertEqual(self.preparer.prepare_page(1), [{"page": 1, "pdf_page": 2, "path": "_work/in/page-1.json",
                                                          "blocks": "para:1, math:1", "math": 1}])

    def test_skipped_equations_are_printed_while_preparing(self):
        book_pdf = BookPdf(_fake_document, _SkippingExtractor({2: [PARA]}))
        builder = PageInputBuilder(self.project.load_progress(), book_pdf)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            PagePreparer(self.project, builder).prepare_page(1)
        self.assertEqual(output.getvalue(), "  ! denklem 2 atlandı\n")

    def test_input_file_is_written_for_the_translator(self):
        self.preparer.prepare_page(1)
        with open(self.project.work_input(1), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["blocks"], [PARA, MATH])


class PreparationReportTest(unittest.TestCase):
    WITH_VISION = BookSettings({})
    WITHOUT_VISION = BookSettings({"translator": {"vision": False}})
    ENTRY = {"page": 1, "pdf_page": 2, "path": "_work/in/page-1.json", "blocks": "math:1", "math": 1}

    @staticmethod
    def _shown(report, prepared):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            report.show(prepared)
        return output.getvalue()

    def test_nothing_prepared_is_said(self):
        self.assertEqual(self._shown(PreparationReport(self.WITH_VISION), []), "Hazırlanacak sayfa yok.\n")

    def test_translator_with_vision_is_asked_for_latex(self):
        self.assertIn("latex` alanlarını doldursun", self._shown(PreparationReport(self.WITH_VISION), [self.ENTRY]))

    def test_translator_without_vision_leaves_latex_to_the_png(self):
        self.assertIn("okuyucu PNG gösterir", self._shown(PreparationReport(self.WITHOUT_VISION), [self.ENTRY]))


if __name__ == "__main__":
    unittest.main()
