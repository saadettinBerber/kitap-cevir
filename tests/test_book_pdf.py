import unittest

from pdf_fakes import FakePdfDocument, FakePdfPage, span
from book_pdf import CONTEXT_CHARS, BookPdf, context_snippets


def _page(text, number=1):
    return FakePdfPage(lines=[(span(text, (72, 60, 120, 72)),)], number=number)


def _document(page_count):
    return FakePdfDocument([_page(f"Sayfa {number}", number) for number in range(1, page_count + 1)])


class ContextSnippetsTest(unittest.TestCase):
    def test_middle_page_sees_both_neighbours(self):
        self.assertEqual(context_snippets(_document(3), 2), {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_first_page_has_no_previous_text(self):
        self.assertEqual(context_snippets(_document(3), 1)["prev_tail"], "")

    def test_last_page_has_no_following_text(self):
        self.assertEqual(context_snippets(_document(3), 3)["next_head"], "")

    def test_single_page_document_has_no_context(self):
        self.assertEqual(context_snippets(_document(1), 1), {"prev_tail": "", "next_head": ""})

    def test_neighbour_text_is_cut_to_the_context_size(self):
        long_page = _page("x" * (CONTEXT_CHARS + 5))
        document = FakePdfDocument([long_page, FakePdfPage(), long_page])
        self.assertEqual({key: len(text) for key, text in context_snippets(document, 2).items()},
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
        return _document(3)

    def test_extraction_and_context_share_one_opening(self):
        extracted = self.book.extract(2, "images")
        self.assertEqual((self.opened, self.extractor.pages), (1, [(2, "images")]))
        self.assertEqual(extracted["context"], {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_hyphen_fixes_come_from_the_asked_page(self):
        self.assertEqual(self.book.hyphen_fixes(3), {"McGrawHill": "McGraw-Hill@3"})


if __name__ == "__main__":
    unittest.main()
