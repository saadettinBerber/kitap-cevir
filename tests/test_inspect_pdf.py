import contextlib
import io
import unittest

from pdf_fakes import PAGE_HEIGHT, PAGE_WIDTH, FakePdfDocument, FakePdfPage, span
from inspect_pdf import FolioOffsets, InspectionReport, PdfInspector

OFFSET = 2
LINE_BOX = (72, 62, 120, 72)
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
        [(offset, _, example)] = PdfInspector(_book()).offsets(1, 20).most_likely(1)
        self.assertEqual((offset, example), (OFFSET, (OFFSET + 1, 1)))

    def test_short_page_counts_its_page_number_once(self):
        [(_, votes, _)] = PdfInspector(_book()).offsets(1, 20).most_likely(1)
        self.assertEqual(votes, BODY_PAGES)

    def test_lines_run_top_to_bottom_with_their_height_from_the_bottom(self):
        [body, folio] = PdfInspector(_book()).lines(OFFSET + 1)
        self.assertEqual((body.text, body.y, body.odl_y), ("Body text of the chapter", 62, PAGE_HEIGHT - 72))
        self.assertEqual(folio.text, "1")

    def test_font_usage_counts_characters(self):
        self.assertEqual(PdfInspector(_book()).font_usage(OFFSET + 1), [(("Helvetica", 10.0), 25)])

    def test_most_used_font_comes_first(self):
        page = FakePdfPage(lines=[(span("a", LINE_BOX, "Small"), span("bigger", LINE_BOX, "Large"))])
        self.assertEqual([font for (font, _), _ in PdfInspector(FakePdfDocument([page])).font_usage(1)], ["Large", "Small"])

    def test_zero_at_the_page_edge_is_not_a_page_number(self):
        document = FakePdfDocument([_text_page(("Body", 62), ("0", 790))])
        self.assertEqual(PdfInspector(document).offsets(1, 1).most_likely(1), [])

    def test_page_texts_follow_the_asked_range(self):
        texts = PdfInspector(_book()).page_texts("1-2")
        self.assertEqual([number for number, _ in texts], [1, 2])

    def test_each_page_comes_with_its_own_text(self):
        self.assertEqual(PdfInspector(_book()).page_texts(f"{OFFSET}-{OFFSET + 1}"),
                         [(OFFSET, "Preface"), (OFFSET + 1, "Body text of the chapter\n1")])

    def test_empty_metadata_fields_are_left_out(self):
        document = FakePdfDocument([_text_page(("x", 62))], metadata={"title": "Book", "author": ""})
        self.assertEqual(PdfInspector(document).metadata(), {"title": "Book"})


class InspectionReportTest(unittest.TestCase):
    def _report(self, command, document=None):
        return _output(lambda: command(InspectionReport(PdfInspector(document or _book()))))

    def test_best_offset_is_printed_first_with_an_example(self):
        best = self._report(lambda report: report.offset(1, 20)).splitlines()[1]
        self.assertTrue(best.startswith(f"  offset={OFFSET:4}"), best)
        self.assertTrue(best.endswith(f"PDF {OFFSET + 1} = kitap 1"), best)

    def test_info_prints_page_count_size_and_filled_metadata(self):
        document = FakePdfDocument([_text_page(("x", 62))], metadata={"title": "Book", "author": ""})
        self.assertEqual(self._report(lambda report: report.info(), document),
                         f"PDF sayfa sayısı: 1\nSayfa boyutu (pt): {PAGE_WIDTH:.1f} x {PAGE_HEIGHT:.1f}\n  title: Book\n")

    def test_text_prints_each_page_under_its_number(self):
        self.assertEqual(self._report(lambda report: report.text(str(OFFSET))), f"===== PDF sayfa {OFFSET} =====\nPreface\n")

    def test_missing_page_numbers_are_reported(self):
        document = FakePdfDocument([_text_page(("No numbers here", 62))])
        self.assertIn("bulunamadı", self._report(lambda report: report.offset(1, 1), document))

    def test_layout_lists_lines_then_fonts(self):
        report = self._report(lambda report: report.layout(OFFSET + 1))
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
