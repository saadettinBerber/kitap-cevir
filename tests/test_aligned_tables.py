import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from extraction.tables.aligned_tables import AlignedTableFinder, HeaderColumns
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


def _draw_fill(page):
    page.draw_rect(fitz.Rect(300, 600, 400, 620), color=None, fill=(0.9, 0.9, 0.9))


class HeaderColumnsTest(unittest.TestCase):
    def setUp(self):
        self.columns = HeaderColumns(_row(("Method", "Purpose"), FIRST_ROW_Y, BOLD))

    def test_header_must_be_bold_and_have_two_columns(self):
        self.assertTrue(HeaderColumns.starts_table(_row(("A", "B"), 0, BOLD)))
        self.assertFalse(HeaderColumns.starts_table(_row(("A", "B"), 0)))
        self.assertFalse(HeaderColumns.starts_table(_row(("A",), 0, BOLD)))

    def test_header_columns_need_a_gutter(self):
        chapter = [_span("Chapter 11", 72, 0, BOLD), _span(": Pipeline", 132, 0, BOLD)]
        emphasis = [_span("for instance", 72, 0, BOLD), _span("must", 149, 0, BOLD)]
        self.assertFalse(HeaderColumns.starts_table(chapter))
        self.assertFalse(HeaderColumns.starts_table(emphasis))
        self.assertTrue(HeaderColumns.starts_table([_span("Feature", 72, 0, BOLD), _span("Items", 144, 0, BOLD)]))

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

    def test_header_with_two_body_rows_is_not_a_table(self):
        self.assertEqual(AlignedTableFinder(_table_spans(2)).tables(), [])

    def test_table_ends_at_first_row_that_does_not_fit(self):
        after = _row(("tail",), FIRST_ROW_Y + ROW_GAP * 5)
        rows = AlignedTableFinder(_table_spans(3) + after).tables()[0]["block"]["rows"]
        self.assertEqual(len(rows), 4)


class ScanTablesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "aligned.pdf")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_pdf(self, *drawings):
        document = fitz.open()
        page = document.new_page()
        rows = [(("Method", "Purpose"), "helvetica-bold")] + [((f"m{i}", f"does {i}"), "helvetica") for i in range(3)]
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

    def test_page_with_fills_skips_aligned_scan(self):
        self._write_pdf(_draw_fill)
        self.assertEqual(scan_tables(self.pdf, 1), [])


if __name__ == "__main__":
    unittest.main()
