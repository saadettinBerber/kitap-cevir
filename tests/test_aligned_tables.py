"""Çizgisiz, sütun hizalı metin tabloları: kalın başlık satırı ve ona hizalı gövde satırları;
sayfa sonuna düşen parça ve sayfayı açan başlıksız devam."""
import dataclasses
import unittest

from pdf_fakes import FakePdfPage, fill, span
from extraction.pdf.geometry import Box
from extraction.settings import DEFAULT_EXTRACTION, with_defaults
from extraction.tables.aligned_tables import COLUMN_GUTTER, AlignedTableFinder, SpanRow, TableColumns
from extraction.tables.table_scan import TableScanner

BOLD, ITALIC = "Helvetica-Bold", "Helvetica-Oblique"
COLUMN_X = (72, 200)
ROW_GAP = 14
FIRST_ROW_Y = 100
CHAR_WIDTH, LINE_HEIGHT = 6, 10
SHIFT = 3
A4_HEIGHT = 842
HEADER = [{"en": "Method"}, {"en": "Purpose"}]


def _span(text, origin):
    """origin: parçanın sol üst köşesi (x, y)."""
    x, y = origin
    return span(text, (x, y, x + CHAR_WIDTH * len(text), y + LINE_HEIGHT))


def _in_font(font, pieces):
    return [dataclasses.replace(piece, font=font) for piece in pieces]


def _bold(pieces):
    return _in_font(BOLD, pieces)


def _shifted(shift, piece):
    """Satırında kalan ama kutusu shift kadar aşağı kayan parça (alt simge; eksi değerde üst simge)."""
    box = piece.box
    return dataclasses.replace(piece, box=Box(box.x0, box.y0 + shift, box.x1, box.y1 + shift))


def _row(texts, y):
    return [_span(text, (x, y)) for text, x in zip(texts, COLUMN_X)]


def _table_spans(body_rows):
    header = _bold(_row(("Method", "Purpose"), FIRST_ROW_Y))
    body = [_row((f"m{index}", f"does {index}"), FIRST_ROW_Y + ROW_GAP * (index + 1)) for index in range(body_rows)]
    return header + [span for row in body for span in row]


def _tables(spans):
    return AlignedTableFinder.of_spans(spans).tables()


def _rows(spans):
    """Bulunan ilk tablonun satırları."""
    return _tables(spans)[0]["block"]["rows"]


class SpanRowTest(unittest.TestCase):
    def test_bold_row_of_two_columns_is_a_header(self):
        self.assertTrue(SpanRow(_bold(_row(("A", "B"), 0))).is_header())

    def test_regular_row_is_not_a_header(self):
        self.assertFalse(SpanRow(_row(("A", "B"), 0)).is_header())

    def test_bold_single_column_is_not_a_header(self):
        self.assertFalse(SpanRow(_bold(_row(("A",), 0))).is_header())

    def test_bold_chapter_title_pieces_without_a_gutter_are_not_a_header(self):
        self.assertFalse(SpanRow(_bold([_span("Chapter 11", (72, 0)), _span(": Pipeline", (132, 0))])).is_header())

    def test_bold_emphasis_in_a_sentence_is_not_a_header(self):
        self.assertFalse(SpanRow(_bold([_span("for instance", (72, 0)), _span("must", (149, 0))])).is_header())

    def test_bold_pieces_with_a_gutter_are_a_header(self):
        self.assertTrue(SpanRow(_bold([_span("Feature", (72, 0)), _span("Items", (144, 0))])).is_header())

    def test_spans_are_grouped_into_lines_from_top_to_bottom(self):
        rows = SpanRow.lines_of([_span("b", (144, 20)), _span("a", (72, 20)), _span("top", (72, 0))])
        self.assertEqual([[span.text for span in row] for row in rows], [["top"], ["a", "b"]])


class TableColumnsTest(unittest.TestCase):
    def setUp(self):
        self.columns = TableColumns.of_header(SpanRow(_bold(_row(("Method", "Purpose"), FIRST_ROW_Y))))

    def test_row_filling_one_column_does_not_fit(self):
        self.assertFalse(self.columns.fits(SpanRow(_row(("only",), 0))))

    def test_row_left_of_first_column_does_not_fit(self):
        self.assertFalse(self.columns.fits(SpanRow([_span("far", (20, 0)), _span("x", (200, 0))])))

    def test_span_outside_every_column_is_dropped(self):
        row = SpanRow([_span("a", (72, 0)), _span("b", (400, 0))])
        self.assertEqual([len(bucket) for bucket in self.columns.buckets(row)], [1, 0])

    def test_span_claimed_by_two_columns_goes_to_the_left_one(self):
        """İlk sütun ikincinin COLUMN_GUTTER solunda biter; aradaki boşluğun ortası iki sütunun
        CENTER_TOLERANCE payında da kalır."""
        center = COLUMN_X[1] - COLUMN_GUTTER / 2
        between = span("a", (center - 1, 0, center + 1, LINE_HEIGHT))
        self.assertEqual([len(bucket) for bucket in self.columns.buckets(SpanRow([between]))], [1, 0])


class AlignedTableFinderTest(unittest.TestCase):
    def test_header_with_three_body_rows_is_one_table(self):
        self.assertEqual(len(_tables(_table_spans(3))), 1)

    def test_bold_first_row_is_the_header(self):
        self.assertEqual(_tables(_table_spans(3))[0]["block"]["header_rows"], 1)

    def test_rows_hold_the_cell_texts(self):
        rows = _rows(_table_spans(3))
        self.assertEqual((rows[0], rows[3]), (HEADER, [{"en": "m2"}, {"en": "does 2"}]))

    def test_header_with_two_body_rows_followed_by_text_is_not_a_table(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 3)
        self.assertEqual(_tables(_table_spans(2) + after), [])

    def test_table_ends_at_first_row_that_does_not_fit(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 5)
        self.assertEqual(len(_rows(_table_spans(3) + after)), 4)

    def test_table_reaches_from_the_highest_to_the_lowest_span(self):
        """Satır parçaları aynı satırda olsa da kutuları kayabilir: üst simge yukarı, alt simge
        aşağı taşar."""
        last_y = FIRST_ROW_Y + ROW_GAP * 3
        raised = _shifted(-SHIFT, *_bold([_span("a", (300, FIRST_ROW_Y))]))
        lowered = _shifted(SHIFT, _span("i", (260, last_y)))
        [table] = _tables(_table_spans(3) + [raised, lowered])
        self.assertEqual((table["y0"], table["y1"]), (FIRST_ROW_Y - SHIFT, last_y + SHIFT + LINE_HEIGHT))


class SplitTableTest(unittest.TestCase):
    """Sayfa sonuna düşen tablo parçası (Effective Java s.2): başlık ve tek satır;
    tablo sonraki sayfada sürer."""

    def test_header_with_one_row_at_page_end_is_a_table(self):
        self.assertEqual(_rows(_table_spans(1)), [HEADER, [{"en": "m0"}, {"en": "does 0"}]])

    def test_header_with_one_row_followed_by_text_is_not_a_table(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 2)
        self.assertEqual(_tables(_table_spans(1) + after), [])

    def test_bold_header_alone_at_page_end_is_not_a_table(self):
        self.assertEqual(_tables(_table_spans(0)), [])


def _continued_rows(count, first_y=FIRST_ROW_Y):
    rows = [_row((f"JDK 1.{index}", f"Java 1.{index}"), first_y + ROW_GAP * index) for index in range(count)]
    return [span for row in rows for span in row]


RUNNING_HEADER = [_span("Chapter 1 Introduction", (72, FIRST_ROW_Y - ROW_GAP))]


class ContinuedTableTest(unittest.TestCase):
    """Önceki sayfadan süren tablo (Effective Java s.3): başlık satırı yok,
    sayfanın ilk satırından başlar."""

    def test_aligned_rows_opening_the_page_are_a_table_without_header(self):
        self.assertEqual(_tables(_continued_rows(3))[0]["block"]["header_rows"], 0)

    def test_continuation_rows_hold_the_cell_texts(self):
        self.assertEqual(_rows(_continued_rows(3))[2], [{"en": "JDK 1.2"}, {"en": "Java 1.2"}])

    def test_continued_table_ends_at_body_text(self):
        after = _row(("The examples are reasonably complete",), FIRST_ROW_Y + ROW_GAP * 3)
        self.assertEqual(len(_rows(_continued_rows(3) + after)), 3)

    def test_styled_span_inside_a_cell_does_not_open_a_column(self):
        italic_x = [_span("JDK 1.9.", (72, FIRST_ROW_Y)), *_in_font(ITALIC, [_span("x", (120, FIRST_ROW_Y))]),
                    _span("Java 1.9", (200, FIRST_ROW_Y))]
        rows = _rows(italic_x + _continued_rows(2, FIRST_ROW_Y + ROW_GAP))
        self.assertEqual(rows[0], [{"en": "JDK 1.9. x"}, {"en": "Java 1.9"}])

    def test_running_header_line_above_does_not_hide_the_continuation(self):
        self.assertEqual(len(_tables(RUNNING_HEADER + _continued_rows(3))), 1)

    def test_table_with_its_own_header_below_running_header_keeps_the_header(self):
        block = _tables(RUNNING_HEADER + _table_spans(3))[0]["block"]
        self.assertEqual((block["header_rows"], block["rows"][0][0]), (1, {"en": "Method"}))

    def test_aligned_rows_after_body_text_are_not_a_continuation(self):
        prose = [_row((f"line {index} of a paragraph",), FIRST_ROW_Y + ROW_GAP * index)[0] for index in range(2)]
        self.assertEqual(_tables(prose + _continued_rows(3, FIRST_ROW_Y + ROW_GAP * 2)), [])

    def test_single_aligned_row_opening_the_page_is_not_a_table(self):
        after = _row(("The examples are reasonably complete",), FIRST_ROW_Y + ROW_GAP)
        self.assertEqual(_tables(_continued_rows(1) + after), [])


PAGE_NUMBER = _span("21", (300, A4_HEIGHT - 27))
FILL = fill(300, 600, 400, 620)
BODY_BOTTOM = A4_HEIGHT - DEFAULT_EXTRACTION["footer_zone_top"]


def _table_lines(body_rows):
    """Tablonun parçaları, PyMuPDF'teki gibi satır satır."""
    spans = _table_spans(body_rows)
    return [tuple(s for s in spans if s.line_y == y) for y in sorted({s.line_y for s in spans})]


def _scan(lines, shapes=()):
    return TableScanner(with_defaults({})).scan(FakePdfPage(lines=lines, shapes=list(shapes), height=A4_HEIGHT))


def _mark_ending_at(bottom):
    return span("21", (300, bottom - LINE_HEIGHT, 312, bottom))


class ScanTablesTest(unittest.TestCase):
    def test_unfilled_page_finds_aligned_table(self):
        self.assertEqual(len(_scan(_table_lines(3))[0]["block"]["rows"]), 4)

    def test_page_number_in_footer_does_not_hide_the_page_end(self):
        self.assertEqual(len(_scan(_table_lines(1) + [(PAGE_NUMBER,)])[0]["block"]["rows"]), 2)

    def test_page_with_fills_skips_aligned_scan(self):
        self.assertEqual(_scan(_table_lines(3), [FILL]), [])


class BodyBottomTest(unittest.TestCase):
    """Alt kenarı gövdenin sınırında biten parça gövdededir: sayfa sonuna düşen kısa tabloyu
    sayfanın son satırı olmaktan çıkarır. Sınırı aşan parça alt bilgidir."""

    def test_line_ending_on_the_body_bottom_belongs_to_the_body(self):
        self.assertEqual(_scan(_table_lines(1) + [(_mark_ending_at(BODY_BOTTOM),)]), [])

    def test_line_ending_just_below_the_body_bottom_is_footer(self):
        self.assertEqual(len(_scan(_table_lines(1) + [(_mark_ending_at(BODY_BOTTOM + 0.1),)])), 1)


if __name__ == "__main__":
    unittest.main()
