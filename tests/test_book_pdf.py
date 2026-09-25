import unittest

from pdf_fakes import FakePdfDocument, FakePdfPage, span
from book_pdf import CONTEXT_CHARS, BookPdf, context_snippets

LINE_BOX = (72, 60, 120, 72)
PAGE_COUNT = 3
FIRST_PAGE, MIDDLE_PAGE, LAST_PAGE = 1, 2, 3
OVERFLOW = 5
IMAGE_DIR = "images"


def _page(text, number=FIRST_PAGE):
    return FakePdfPage(lines=[(span(text, LINE_BOX),)], number=number)


def _document(page_count):
    return FakePdfDocument([_page(f"Sayfa {number}", number) for number in range(FIRST_PAGE, page_count + 1)])


class ContextSnippetsTest(unittest.TestCase):
    def test_middle_page_sees_both_neighbours(self):
        self.assertEqual(context_snippets(_document(PAGE_COUNT), MIDDLE_PAGE),
                         {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_first_page_has_no_previous_text(self):
        self.assertEqual(context_snippets(_document(PAGE_COUNT), FIRST_PAGE)["prev_tail"], "")

    def test_last_page_has_no_following_text(self):
        self.assertEqual(context_snippets(_document(PAGE_COUNT), LAST_PAGE)["next_head"], "")

    def test_single_page_document_has_no_context(self):
        self.assertEqual(context_snippets(_document(FIRST_PAGE), FIRST_PAGE), {"prev_tail": "", "next_head": ""})

    def test_neighbour_text_is_cut_to_the_context_size(self):
        long_page = _page("x" * (CONTEXT_CHARS + OVERFLOW))
        document = FakePdfDocument([long_page, FakePdfPage(), long_page])
        self.assertEqual({key: len(text) for key, text in context_snippets(document, MIDDLE_PAGE).items()},
                         {"prev_tail": CONTEXT_CHARS, "next_head": CONTEXT_CHARS})


class _RecordingExtractor:
    """Hangi sayfanın çıkarıldığını kaydeder."""

    def __init__(self):
        self.pages = []

    def extract(self, page, image_dir):
        self.pages.append((page.number, image_dir))
        return {"blocks": [], "math": [], "running_header": None}

    def hyphen_fixes(self, page):
        return {"McGrawHill": f"McGraw-Hill@{page.number}"}


class BookPdfTest(unittest.TestCase):
    def setUp(self):
        self.opened = 0
        self.extractor = _RecordingExtractor()
        self.book = BookPdf(self._open, self.extractor)

    def _open(self):
        self.opened += 1
        return _document(PAGE_COUNT)

    def test_extraction_and_context_share_one_opening(self):
        extracted = self.book.extract(MIDDLE_PAGE, IMAGE_DIR)
        self.assertEqual((self.opened, self.extractor.pages), (1, [(MIDDLE_PAGE, IMAGE_DIR)]))
        self.assertEqual(extracted["context"], {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_hyphen_fixes_come_from_the_asked_page(self):
        self.assertEqual(self.book.hyphen_fixes(LAST_PAGE), {"McGrawHill": "McGraw-Hill@3"})


if __name__ == "__main__":
    unittest.main()
