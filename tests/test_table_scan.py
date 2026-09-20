import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from table_scan import scan_tables

COLUMNS = [(70, 170), (170, 270), (270, 370)]
HEADER = ["Name", "Count", "Share"]
ROWS = [["Alpha", "1", "10%"], ["Beta", "2", "20%"], ["Gamma", "3", "30%"]]
ROW_HEIGHT = 30
TABLE_TOP = 150


def _draw_row(page, top, texts, is_bold, shaded):
    for (left, right), text in zip(COLUMNS, texts):
        if shaded:
            page.draw_rect(fitz.Rect(left, top, right, top + ROW_HEIGHT), color=None, fill=(0.9, 0.9, 0.9))
        font = "helvetica-bold" if is_bold else "helvetica"
        page.insert_text(fitz.Point(left + 5, top + 20), text, fontsize=11, fontname=font)


def _make_pdf(path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text(fitz.Point(70, 130), "Table 1-1. A caption that spans the whole table width", fontsize=9)
    _draw_row(page, TABLE_TOP, HEADER, is_bold=True, shaded=True)
    for index, row in enumerate(ROWS):
        top = TABLE_TOP + ROW_HEIGHT * (index + 1)
        _draw_row(page, top, row, is_bold=False, shaded=index % 2 == 1)
    page.insert_text(fitz.Point(70, 400), "Body text far below the table, spanning columns.", fontsize=11)
    document.save(path)
    document.close()


class TableScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "t.pdf")
        _make_pdf(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_filled_cell_table_with_header(self):
        tables = scan_tables(self.pdf, 1)
        self.assertEqual(len(tables), 1)
        block = tables[0]["block"]
        self.assertEqual(block["header_rows"], 1)
        self.assertEqual([c["en"] for c in block["rows"][0]], HEADER)
        self.assertEqual([[c["en"] for c in row] for row in block["rows"][1:]], ROWS)

    def test_caption_and_body_stay_outside_table_extent(self):
        table = scan_tables(self.pdf, 1)[0]
        self.assertGreater(table["y0"], 130)
        self.assertLess(table["y1"], 400)

    def test_page_without_fills_has_no_tables(self):
        document = fitz.open()
        document.new_page().insert_text(fitz.Point(70, 100), "plain", fontsize=11)
        plain = os.path.join(self.tmp.name, "plain.pdf")
        document.save(plain)
        self.assertEqual(scan_tables(plain, 1), [])


if __name__ == "__main__":
    unittest.main()
