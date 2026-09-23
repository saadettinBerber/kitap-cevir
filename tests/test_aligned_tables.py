import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from extraction.tables.aligned_tables import AlignedTableFinder, TableColumns
from extraction.tables.table_scan import scan_tables

BOLD, REGULAR = "Helvetica-Bold", "Helvetica"
COLUMN_X = (72, 200)
ROW_GAP = 14
FIRST_ROW_Y = 100


def _span(text, x, y, font=REGULAR):
    return {"bbox": fitz.Rect(x, y, x + 6 * len(text), y + 10), "font": font, "size": 10.0,
            "text": text, "line_y": y}


def _row(texts, y, font=REGULAR):
    return [_span(text, x, y, font) for text, x in zip(texts, COLUMN_X)]


def _table_spans(body_rows):
    header = _row(("Method", "Purpose"), FIRST_ROW_Y, BOLD)
    body = [_row((f"m{index}", f"does {index}"), FIRST_ROW_Y + ROW_GAP * (index + 1)) for index in range(body_rows)]
    return header + [span for row in body for span in row]


def _write_page_number(page):
    page.insert_text(fitz.Point(300, page.rect.height - 20), "21", fontsize=10, fontname="helvetica")


def _draw_fill(page):
    page.draw_rect(fitz.Rect(300, 600, 400, 620), color=None, fill=(0.9, 0.9, 0.9))


class TableColumnsTest(unittest.TestCase):
    def setUp(self):
        self.columns = TableColumns.of_header(_row(("Method", "Purpose"), FIRST_ROW_Y, BOLD))

    def test_header_must_be_bold_and_have_two_columns(self):
        self.assertTrue(TableColumns.is_header(_row(("A", "B"), 0, BOLD)))
        self.assertFalse(TableColumns.is_header(_row(("A", "B"), 0)))
        self.assertFalse(TableColumns.is_header(_row(("A",), 0, BOLD)))

    def test_header_columns_need_a_gutter(self):
        chapter = [_span("Chapter 11", 72, 0, BOLD), _span(": Pipeline", 132, 0, BOLD)]
        emphasis = [_span("for instance", 72, 0, BOLD), _span("must", 149, 0, BOLD)]
        self.assertFalse(TableColumns.is_header(chapter))
        self.assertFalse(TableColumns.is_header(emphasis))
        self.assertTrue(TableColumns.is_header([_span("Feature", 72, 0, BOLD), _span("Items", 144, 0, BOLD)]))

    def test_row_filling_one_column_does_not_fit(self):
        self.assertFalse(self.columns.fits(_row(("only",), 0)))

    def test_row_left_of_first_column_does_not_fit(self):
        self.assertFalse(self.columns.fits([_span("far", 20, 0), _span("x", 200, 0)]))

    def test_span_outside_every_column_is_dropped(self):
        self.assertEqual([len(b) for b in self.columns.buckets([_span("a", 72, 0), _span("b", 400, 0)])], [1, 0])


class AlignedTableFinderTest(unittest.TestCase):
    def test_header_with_three_body_rows_is_a_table(self):
        tables = AlignedTableFinder(_table_spans(3)).tables()
        self.assertEqual(len(tables), 1)
        block = tables[0]["block"]
        self.assertEqual(block["header_rows"], 1)
        self.assertEqual(block["rows"][0], [{"en": "Method"}, {"en": "Purpose"}])
        self.assertEqual(block["rows"][3], [{"en": "m2"}, {"en": "does 2"}])

    def test_header_with_two_body_rows_followed_by_text_is_not_a_table(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 3)
        self.assertEqual(AlignedTableFinder(_table_spans(2) + after).tables(), [])

    def test_table_ends_at_first_row_that_does_not_fit(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 5)
        rows = AlignedTableFinder(_table_spans(3) + after).tables()[0]["block"]["rows"]
        self.assertEqual(len(rows), 4)


class SplitTableTest(unittest.TestCase):
    """Sayfa sonuna düşen tablo parçası (Effective Java s.2): başlık ve tek satır;
    tablo sonraki sayfada sürer."""

    def test_header_with_one_row_at_page_end_is_a_table(self):
        rows = AlignedTableFinder(_table_spans(1)).tables()[0]["block"]["rows"]
        self.assertEqual(rows, [[{"en": "Method"}, {"en": "Purpose"}], [{"en": "m0"}, {"en": "does 0"}]])

    def test_header_with_one_row_followed_by_text_is_not_a_table(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 2)
        self.assertEqual(AlignedTableFinder(_table_spans(1) + after).tables(), [])

    def test_bold_header_alone_at_page_end_is_not_a_table(self):
        self.assertEqual(AlignedTableFinder(_table_spans(0)).tables(), [])


def _continued_rows(count, first_y=FIRST_ROW_Y):
    rows = [_row((f"JDK 1.{index}", f"Java 1.{index}"), first_y + ROW_GAP * index) for index in range(count)]
    return [span for row in rows for span in row]


class ContinuedTableTest(unittest.TestCase):
    """Önceki sayfadan süren tablo (Effective Java s.3): başlık satırı yok,
    sayfanın ilk satırından başlar."""

    def test_aligned_rows_opening_the_page_are_a_table_without_header(self):
        block = AlignedTableFinder(_continued_rows(3)).tables()[0]["block"]
        self.assertEqual(block["header_rows"], 0)
        self.assertEqual(block["rows"][2], [{"en": "JDK 1.2"}, {"en": "Java 1.2"}])

    def test_continued_table_ends_at_body_text(self):
        after = _row(("The examples are reasonably complete",), FIRST_ROW_Y + ROW_GAP * 3)
        self.assertEqual(len(AlignedTableFinder(_continued_rows(3) + after).tables()[0]["block"]["rows"]), 3)

    def test_styled_span_inside_a_cell_does_not_open_a_column(self):
        italic_x = [_span("JDK 1.9.", 72, FIRST_ROW_Y), _span("x", 120, FIRST_ROW_Y, "Helvetica-Oblique"),
                    _span("Java 1.9", 200, FIRST_ROW_Y)]
        rows = AlignedTableFinder(italic_x + _continued_rows(2, FIRST_ROW_Y + ROW_GAP)).tables()[0]["block"]["rows"]
        self.assertEqual(rows[0], [{"en": "JDK 1.9. x"}, {"en": "Java 1.9"}])

    def test_running_header_line_above_does_not_hide_the_continuation(self):
        running_header = [_span("Chapter 1 Introduction", 72, FIRST_ROW_Y - ROW_GAP)]
        self.assertEqual(len(AlignedTableFinder(running_header + _continued_rows(3)).tables()), 1)

    def test_table_with_its_own_header_below_running_header_keeps_the_header(self):
        running_header = [_span("Chapter 1 Introduction", 72, FIRST_ROW_Y - ROW_GAP)]
        block = AlignedTableFinder(running_header + _table_spans(3)).tables()[0]["block"]
        self.assertEqual((block["header_rows"], block["rows"][0][0]), (1, {"en": "Method"}))

    def test_aligned_rows_after_body_text_are_not_a_continuation(self):
        prose = [_row((f"line {index} of a paragraph",), FIRST_ROW_Y + ROW_GAP * index)[0] for index in range(2)]
        rows = _continued_rows(3, FIRST_ROW_Y + ROW_GAP * 2)
        self.assertEqual(AlignedTableFinder(prose + rows).tables(), [])

    def test_single_aligned_row_opening_the_page_is_not_a_table(self):
        after = _row(("The examples are reasonably complete",), FIRST_ROW_Y + ROW_GAP)
        self.assertEqual(AlignedTableFinder(_continued_rows(1) + after).tables(), [])


class ScanTablesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "aligned.pdf")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_pdf(self, *drawings, body_rows=3):
        document = fitz.open()
        page = document.new_page()
        rows = [(("Method", "Purpose"), "helvetica-bold")] + [((f"m{i}", f"does {i}"), "helvetica") for i in range(body_rows)]
        for index, (texts, font) in enumerate(rows):
            for text, x in zip(texts, COLUMN_X):
                page.insert_text(fitz.Point(x, FIRST_ROW_Y + ROW_GAP * index), text, fontsize=10, fontname=font)
        for draw in drawings:
            draw(page)
        document.save(self.pdf)
        document.close()

    def test_unfilled_page_finds_aligned_table(self):
        self._write_pdf()
        self.assertEqual(len(scan_tables(self.pdf, 1)[0]["block"]["rows"]), 4)

    def test_page_number_in_footer_does_not_hide_the_page_end(self):
        self._write_pdf(_write_page_number, body_rows=1)
        self.assertEqual(len(scan_tables(self.pdf, 1)[0]["block"]["rows"]), 2)

    def test_page_with_fills_skips_aligned_scan(self):
        self._write_pdf(_draw_fill)
        self.assertEqual(scan_tables(self.pdf, 1), [])


if __name__ == "__main__":
    unittest.main()
