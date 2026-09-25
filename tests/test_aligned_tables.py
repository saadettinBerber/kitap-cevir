import dataclasses
import unittest

from pdf_fakes import FakePdfPage, fill, span
from extraction.tables.aligned_tables import COLUMN_GUTTER, AlignedTableFinder, SpanRow, TableColumns
from extraction.settings import with_defaults
from extraction.tables.table_scan import TableScanner

BOLD, REGULAR = "Helvetica-Bold", "Helvetica"
COLUMN_X = (72, 200)
ROW_GAP = 14
FIRST_ROW_Y = 100
SHIFT = 3


A4_HEIGHT = 842


def _span(text, x, y, font=REGULAR):
    return span(text, (x, y, x + 6 * len(text), y + 10), font)


def _row(texts, y, font=REGULAR):
    return [_span(text, x, y, font) for text, x in zip(texts, COLUMN_X)]


def _table_spans(body_rows):
    header = _row(("Method", "Purpose"), FIRST_ROW_Y, BOLD)
    body = [_row((f"m{index}", f"does {index}"), FIRST_ROW_Y + ROW_GAP * (index + 1)) for index in range(body_rows)]
    return header + [span for row in body for span in row]


PAGE_NUMBER = _span("21", 300, A4_HEIGHT - 27)
FILL = fill(300, 600, 400, 620)


class SpanRowTest(unittest.TestCase):
    def test_header_must_be_bold_and_have_two_columns(self):
        self.assertTrue(SpanRow(_row(("A", "B"), 0, BOLD)).is_header())
        self.assertFalse(SpanRow(_row(("A", "B"), 0)).is_header())
        self.assertFalse(SpanRow(_row(("A",), 0, BOLD)).is_header())

    def test_header_columns_need_a_gutter(self):
        chapter = [_span("Chapter 11", 72, 0, BOLD), _span(": Pipeline", 132, 0, BOLD)]
        emphasis = [_span("for instance", 72, 0, BOLD), _span("must", 149, 0, BOLD)]
        self.assertFalse(SpanRow(chapter).is_header())
        self.assertFalse(SpanRow(emphasis).is_header())
        self.assertTrue(SpanRow([_span("Feature", 72, 0, BOLD), _span("Items", 144, 0, BOLD)]).is_header())

    def test_spans_are_grouped_into_lines_from_top_to_bottom(self):
        rows = SpanRow.lines_of([_span("b", 144, 20), _span("a", 72, 20), _span("top", 72, 0)])
        self.assertEqual([[span.text for span in row.spans] for row in rows], [["top"], ["a", "b"]])


class TableColumnsTest(unittest.TestCase):
    def setUp(self):
        self.columns = TableColumns.of_header(SpanRow(_row(("Method", "Purpose"), FIRST_ROW_Y, BOLD)))

    def test_row_filling_one_column_does_not_fit(self):
        self.assertFalse(self.columns.fits(SpanRow(_row(("only",), 0))))

    def test_row_left_of_first_column_does_not_fit(self):
        self.assertFalse(self.columns.fits(SpanRow([_span("far", 20, 0), _span("x", 200, 0)])))

    def test_span_outside_every_column_is_dropped(self):
        row = SpanRow([_span("a", 72, 0), _span("b", 400, 0)])
        self.assertEqual([len(bucket) for bucket in self.columns.buckets(row)], [1, 0])

    def test_span_claimed_by_two_columns_goes_to_the_left_one(self):
        """İlk sütun ikincinin COLUMN_GUTTER solunda biter; aradaki boşluğun ortası iki sütunun
        CENTER_TOLERANCE payında da kalır."""
        center = COLUMN_X[1] - COLUMN_GUTTER / 2
        between = span("a", (center - 1, 0, center + 1, 10))
        self.assertEqual([len(bucket) for bucket in self.columns.buckets(SpanRow([between]))], [1, 0])


class AlignedTableFinderTest(unittest.TestCase):
    def test_header_with_three_body_rows_is_a_table(self):
        tables = AlignedTableFinder.of_spans(_table_spans(3)).tables()
        self.assertEqual(len(tables), 1)
        block = tables[0]["block"]
        self.assertEqual(block["header_rows"], 1)
        self.assertEqual(block["rows"][0], [{"en": "Method"}, {"en": "Purpose"}])
        self.assertEqual(block["rows"][3], [{"en": "m2"}, {"en": "does 2"}])

    def test_header_with_two_body_rows_followed_by_text_is_not_a_table(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 3)
        self.assertEqual(AlignedTableFinder.of_spans(_table_spans(2) + after).tables(), [])

    def test_table_ends_at_first_row_that_does_not_fit(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 5)
        rows = AlignedTableFinder.of_spans(_table_spans(3) + after).tables()[0]["block"]["rows"]
        self.assertEqual(len(rows), 4)

    def test_table_reaches_from_the_highest_to_the_lowest_span(self):
        """Satır parçaları aynı satırda olsa da kutuları kayabilir: üst simge yukarı, alt simge aşağı taşar."""
        last_y = FIRST_ROW_Y + ROW_GAP * 3
        raised = dataclasses.replace(span("a", (300, FIRST_ROW_Y - SHIFT, 306, FIRST_ROW_Y + 7), BOLD), line_y=FIRST_ROW_Y)
        lowered = dataclasses.replace(span("i", (260, last_y + SHIFT, 266, last_y + 13)), line_y=last_y)
        [table] = AlignedTableFinder.of_spans(_table_spans(3) + [raised, lowered]).tables()
        self.assertEqual((table["y0"], table["y1"]), (FIRST_ROW_Y - SHIFT, last_y + 13))


class SplitTableTest(unittest.TestCase):
    """Sayfa sonuna düşen tablo parçası (Effective Java s.2): başlık ve tek satır;
    tablo sonraki sayfada sürer."""

    def test_header_with_one_row_at_page_end_is_a_table(self):
        rows = AlignedTableFinder.of_spans(_table_spans(1)).tables()[0]["block"]["rows"]
        self.assertEqual(rows, [[{"en": "Method"}, {"en": "Purpose"}], [{"en": "m0"}, {"en": "does 0"}]])

    def test_header_with_one_row_followed_by_text_is_not_a_table(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 2)
        self.assertEqual(AlignedTableFinder.of_spans(_table_spans(1) + after).tables(), [])

    def test_bold_header_alone_at_page_end_is_not_a_table(self):
        self.assertEqual(AlignedTableFinder.of_spans(_table_spans(0)).tables(), [])


def _continued_rows(count, first_y=FIRST_ROW_Y):
    rows = [_row((f"JDK 1.{index}", f"Java 1.{index}"), first_y + ROW_GAP * index) for index in range(count)]
    return [span for row in rows for span in row]


class ContinuedTableTest(unittest.TestCase):
    """Önceki sayfadan süren tablo (Effective Java s.3): başlık satırı yok,
    sayfanın ilk satırından başlar."""

    def test_aligned_rows_opening_the_page_are_a_table_without_header(self):
        block = AlignedTableFinder.of_spans(_continued_rows(3)).tables()[0]["block"]
        self.assertEqual(block["header_rows"], 0)
        self.assertEqual(block["rows"][2], [{"en": "JDK 1.2"}, {"en": "Java 1.2"}])

    def test_continued_table_ends_at_body_text(self):
        after = _row(("The examples are reasonably complete",), FIRST_ROW_Y + ROW_GAP * 3)
        self.assertEqual(len(AlignedTableFinder.of_spans(_continued_rows(3) + after).tables()[0]["block"]["rows"]), 3)

    def test_styled_span_inside_a_cell_does_not_open_a_column(self):
        italic_x = [_span("JDK 1.9.", 72, FIRST_ROW_Y), _span("x", 120, FIRST_ROW_Y, "Helvetica-Oblique"),
                    _span("Java 1.9", 200, FIRST_ROW_Y)]
        rows = AlignedTableFinder.of_spans(italic_x + _continued_rows(2, FIRST_ROW_Y + ROW_GAP)).tables()[0]["block"]["rows"]
        self.assertEqual(rows[0], [{"en": "JDK 1.9. x"}, {"en": "Java 1.9"}])

    def test_running_header_line_above_does_not_hide_the_continuation(self):
        running_header = [_span("Chapter 1 Introduction", 72, FIRST_ROW_Y - ROW_GAP)]
        self.assertEqual(len(AlignedTableFinder.of_spans(running_header + _continued_rows(3)).tables()), 1)

    def test_table_with_its_own_header_below_running_header_keeps_the_header(self):
        running_header = [_span("Chapter 1 Introduction", 72, FIRST_ROW_Y - ROW_GAP)]
        block = AlignedTableFinder.of_spans(running_header + _table_spans(3)).tables()[0]["block"]
        self.assertEqual((block["header_rows"], block["rows"][0][0]), (1, {"en": "Method"}))

    def test_aligned_rows_after_body_text_are_not_a_continuation(self):
        prose = [_row((f"line {index} of a paragraph",), FIRST_ROW_Y + ROW_GAP * index)[0] for index in range(2)]
        rows = _continued_rows(3, FIRST_ROW_Y + ROW_GAP * 2)
        self.assertEqual(AlignedTableFinder.of_spans(prose + rows).tables(), [])

    def test_single_aligned_row_opening_the_page_is_not_a_table(self):
        after = _row(("The examples are reasonably complete",), FIRST_ROW_Y + ROW_GAP)
        self.assertEqual(AlignedTableFinder.of_spans(_continued_rows(1) + after).tables(), [])


class ScanTablesTest(unittest.TestCase):
    @staticmethod
    def _scan(extra_lines=(), shapes=(), body_rows=3):
        spans = _table_spans(body_rows)
        lines = [tuple(s for s in spans if s.line_y == y) for y in sorted({s.line_y for s in spans})]
        page = FakePdfPage(lines=lines + [(line,) for line in extra_lines], shapes=list(shapes), height=A4_HEIGHT)
        return TableScanner(with_defaults({})).scan(page)

    def test_unfilled_page_finds_aligned_table(self):
        self.assertEqual(len(self._scan()[0]["block"]["rows"]), 4)

    def test_page_number_in_footer_does_not_hide_the_page_end(self):
        self.assertEqual(len(self._scan([PAGE_NUMBER], body_rows=1)[0]["block"]["rows"]), 2)

    def test_page_with_fills_skips_aligned_scan(self):
        self.assertEqual(self._scan(shapes=[FILL]), [])


if __name__ == "__main__":
    unittest.main()
