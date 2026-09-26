import contextlib
import io
import unittest

from pdf_fakes import FONT, PAGE_HEIGHT, PAGE_WIDTH, SIZE, FakePdfDocument, FakePdfPage, span
from inspect_pdf import DEFAULT_LAST_PAGE, TOP_CANDIDATES, FolioOffsets, InspectionReport, PdfInspector, parse_args

OFFSET = 2
BODY_PAGES = 4
LEFT, TOP, FOLIO_TOP = 72, 62, 790
CHAR_WIDTH, LINE_HEIGHT = 6, 10
LINE_BOX = (LEFT, TOP, 120, TOP + LINE_HEIGHT)
LAST_SCANNED = 20
BODY = "Body text of the chapter"


def _text_page(*lines):
    """Her satır (metin, üst kenar) çiftidir."""
    return FakePdfPage(lines=[(span(text, (LEFT, top, LEFT + CHAR_WIDTH * len(text), top + LINE_HEIGHT)),)
                              for text, top in lines])


def _book():
    """Önde OFFSET sayfa ön söz; sonra alt kenarında basılı numara taşıyan gövde sayfaları."""
    preface = [_text_page(("Preface", TOP)) for _ in range(OFFSET)]
    body = [_text_page((BODY, TOP), (str(folio), FOLIO_TOP)) for folio in range(1, BODY_PAGES + 1)]
    return FakePdfDocument(preface + body)


class _DocumentWithMetadata(FakePdfDocument):
    """Tek sayfalık, metadata'sı verilen belge."""

    def __init__(self, metadata):
        super().__init__([_text_page(("x", TOP))])
        self._metadata = metadata

    @property
    def metadata(self):
        return self._metadata


def _output(command):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command()
    return buffer.getvalue()


class PdfInspectorTest(unittest.TestCase):
    def test_offset_is_voted_from_printed_page_numbers(self):
        [(offset, _, example)] = PdfInspector(_book()).likely_offsets(1, LAST_SCANNED)
        self.assertEqual((offset, example), (OFFSET, (OFFSET + 1, 1)))

    def test_short_page_counts_its_page_number_once(self):
        [(_, votes, _)] = PdfInspector(_book()).likely_offsets(1, LAST_SCANNED)
        self.assertEqual(votes, BODY_PAGES)

    def test_lines_run_top_to_bottom_with_their_height_from_the_bottom(self):
        [body, folio] = PdfInspector(_book()).lines(OFFSET + 1)
        self.assertEqual((body.text, body.y, body.odl_y), (BODY, TOP, PAGE_HEIGHT - (TOP + LINE_HEIGHT)))
        self.assertEqual(folio.text, "1")

    def test_font_usage_counts_characters(self):
        self.assertEqual(PdfInspector(_book()).font_usage(OFFSET + 1), [((FONT, SIZE), len(BODY) + len("1"))])

    def test_most_used_font_comes_first(self):
        fonts = (span("bb", LINE_BOX, "Middle"), span("a", LINE_BOX, "Small"), span("cccc", LINE_BOX, "Large"))
        usage = PdfInspector(FakePdfDocument([FakePdfPage(lines=[fonts])])).font_usage(1)
        self.assertEqual([font for (font, _), _ in usage], ["Large", "Middle", "Small"])

    def test_zero_at_the_page_edge_is_not_a_page_number(self):
        document = FakePdfDocument([_text_page(("Body", TOP), ("0", FOLIO_TOP))])
        self.assertEqual(PdfInspector(document).likely_offsets(1, 1), [])

    def test_page_texts_follow_the_asked_range(self):
        texts = PdfInspector(_book()).page_texts("1-2")
        self.assertEqual([number for number, _ in texts], [1, 2])

    def test_each_page_comes_with_its_own_text(self):
        self.assertEqual(PdfInspector(_book()).page_texts(f"{OFFSET}-{OFFSET + 1}"),
                         [(OFFSET, "Preface"), (OFFSET + 1, f"{BODY}\n1")])

    def test_empty_metadata_fields_are_left_out(self):
        document = _DocumentWithMetadata({"title": "Book", "author": ""})
        self.assertEqual(PdfInspector(document).metadata(), {"title": "Book"})


class InspectionReportTest(unittest.TestCase):
    def _report(self, command, document=None):
        return _output(lambda: command(InspectionReport(PdfInspector(document or _book()))))

    def test_best_offset_is_printed_first_with_an_example(self):
        best = self._report(lambda report: report.offset(1, LAST_SCANNED)).splitlines()[1]
        self.assertTrue(best.startswith(f"  offset={OFFSET:4}"), best)
        self.assertTrue(best.endswith(f"PDF {OFFSET + 1} = kitap 1"), best)

    def test_info_prints_page_count_size_and_filled_metadata(self):
        document = _DocumentWithMetadata({"title": "Book", "author": ""})
        self.assertEqual(self._report(lambda report: report.info(), document),
                         f"PDF sayfa sayısı: 1\nSayfa boyutu (pt): {PAGE_WIDTH:.1f} x {PAGE_HEIGHT:.1f}\n"
                         "  title: Book\n")

    def test_text_prints_each_page_under_its_number(self):
        self.assertEqual(self._report(lambda report: report.text(str(OFFSET))),
                         f"===== PDF sayfa {OFFSET} =====\nPreface\n")

    def test_only_the_top_candidates_are_printed(self):
        """Her sayfa kendini kitabın ilk sayfası sayar, yani başka bir ofset önerir;
        başlık satırının altında yalnız en olası adaylar kalır."""
        pages = [_text_page(("Body", TOP), ("1", FOLIO_TOP)) for _ in range(TOP_CANDIDATES + 1)]
        printed = self._report(lambda report: report.offset(1, len(pages)), FakePdfDocument(pages))
        self.assertEqual(len(printed.splitlines()) - 1, TOP_CANDIDATES)

    def test_missing_page_numbers_are_reported(self):
        document = FakePdfDocument([_text_page(("No numbers here", TOP))])
        self.assertIn("bulunamadı", self._report(lambda report: report.offset(1, 1), document))

    def test_layout_lists_lines_then_fonts(self):
        report = self._report(lambda report: report.layout(OFFSET + 1))
        self.assertIn(BODY, report)
        self.assertIn("Font / boyut / karakter sayısı", report)


class FolioOffsetsTest(unittest.TestCase):
    def test_most_voted_offset_comes_first_with_its_first_example(self):
        offsets = FolioOffsets.of_folios([(22, 20), (23, 21), (30, 5)])
        self.assertEqual(offsets.most_likely(2), [(2, 2, (22, 20)), (25, 1, (30, 5))])

    def test_negative_offset_is_not_counted(self):
        self.assertEqual(FolioOffsets.of_folios([(3, 10)]).most_likely(1), [])

    def test_zero_offset_is_counted(self):
        self.assertEqual(FolioOffsets.of_folios([(7, 7)]).most_likely(1), [(0, 1, (7, 7))])


class _EchoReport:
    """Çağrılan rapor komutunu ve argümanlarını geri verir."""

    def info(self):
        return ("info",)

    def text(self, pages):
        return ("text", pages)

    def layout(self, number):
        return ("layout", number)

    def offset(self, first, last):
        return ("offset", first, last)


def _command(*argv):
    args = parse_args(["book.pdf", *argv])
    return args.run(_EchoReport(), args)


class CommandLineTest(unittest.TestCase):
    def test_info_runs_the_info_report(self):
        self.assertEqual(_command("info"), ("info",))

    def test_text_passes_the_page_range(self):
        self.assertEqual(_command("text", "5-9"), ("text", "5-9"))

    def test_layout_takes_the_page_as_a_number(self):
        self.assertEqual(_command("layout", "40"), ("layout", 40))

    def test_offset_scans_up_to_the_default_last_page(self):
        self.assertEqual(_command("offset"), ("offset", 1, DEFAULT_LAST_PAGE))

    def test_offset_takes_the_asked_range(self):
        self.assertEqual(_command("offset", "--from", "20", "--to", "200"), ("offset", 20, 200))


if __name__ == "__main__":
    unittest.main()
