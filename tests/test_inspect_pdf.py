import contextlib
import io
import unittest

from pdf_fakes import FakePdfDocument, FakePdfPage, span
from inspect_pdf import FolioOffsets, PdfInspector

OFFSET = 2
BODY_PAGES = 4


def _text_page(*lines):
    """Her satır (metin, üst kenar) çiftidir."""
    return FakePdfPage(lines=[(span(text, (72, top, 72 + 6 * len(text), top + 10)),) for text, top in lines])


def _book():
    """Önde OFFSET sayfa ön söz; sonra alt kenarında basılı numara taşıyan gövde sayfaları."""
    preface = [_text_page(("Preface", 62)) for _ in range(OFFSET)]
    body = [_text_page(("Body text of the chapter", 62), (str(folio), 790)) for folio in range(1, BODY_PAGES + 1)]
    return FakePdfDocument(preface + body)


def _output(command):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command()
    return buffer.getvalue()


class PdfInspectorTest(unittest.TestCase):
    def test_offset_is_voted_from_printed_page_numbers(self):
        report = _output(lambda: PdfInspector(_book()).offset(1, 20))
        best = report.splitlines()[1]
        self.assertTrue(best.startswith(f"  offset={OFFSET:4}"), best)
        self.assertTrue(best.endswith(f"PDF {OFFSET + 1} = kitap 1"), best)

    def test_offset_reports_when_no_page_numbers_exist(self):
        document = FakePdfDocument([_text_page(("No numbers here", 62))])
        report = _output(lambda: PdfInspector(document).offset(1, 1))
        self.assertIn("bulunamadı", report)

    def test_layout_lists_fonts_by_character_count(self):
        report = _output(lambda: PdfInspector(_book()).layout(OFFSET + 1))
        self.assertIn("Body text of the chapter", report)
        self.assertIn("Font / boyut / karakter sayısı", report)


class FolioOffsetsTest(unittest.TestCase):
    def test_most_voted_offset_comes_first_with_its_first_example(self):
        offsets = FolioOffsets.of_folios([(22, 20), (23, 21), (30, 5)])
        self.assertEqual(offsets.most_likely(2), [(2, 2, (22, 20)), (25, 1, (30, 5))])

    def test_negative_offset_is_not_counted(self):
        self.assertEqual(FolioOffsets.of_folios([(3, 10)]).most_likely(1), [])

    def test_zero_offset_is_counted(self):
        self.assertEqual(FolioOffsets.of_folios([(7, 7)]).most_likely(1), [(0, 1, (7, 7))])


if __name__ == "__main__":
    unittest.main()
