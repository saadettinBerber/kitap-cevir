import contextlib
import io
import unittest

import fitz

import _paths  # noqa: F401
from inspect_pdf import PdfInspector

OFFSET = 2
BODY_PAGES = 4


def _book():
    """Önde OFFSET sayfa ön söz; sonra alt kenarında basılı numara taşıyan gövde sayfaları."""
    document = fitz.open()
    for _ in range(OFFSET):
        document.new_page().insert_text((72, 72), "Preface")
    for folio in range(1, BODY_PAGES + 1):
        page = document.new_page()
        page.insert_text((72, 72), "Body text of the chapter")
        page.insert_text((300, 800), str(folio))
    return document


def _output(command):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command()
    return buffer.getvalue()


class PdfInspectorTest(unittest.TestCase):
    def test_offset_is_voted_from_printed_page_numbers(self):
        with _book() as document:
            report = _output(lambda: PdfInspector(document).offset(1, 20))
        best = report.splitlines()[1]
        self.assertTrue(best.startswith(f"  offset={OFFSET:4}"), best)
        self.assertTrue(best.endswith(f"PDF {OFFSET + 1} = kitap 1"), best)

    def test_offset_reports_when_no_page_numbers_exist(self):
        with fitz.open() as document:
            document.new_page().insert_text((72, 72), "No numbers here")
            report = _output(lambda: PdfInspector(document).offset(1, 1))
        self.assertIn("bulunamadı", report)

    def test_layout_lists_fonts_by_character_count(self):
        with _book() as document:
            report = _output(lambda: PdfInspector(document).layout(OFFSET + 1))
        self.assertIn("Body text of the chapter", report)
        self.assertIn("Font / boyut / karakter sayısı", report)


if __name__ == "__main__":
    unittest.main()
