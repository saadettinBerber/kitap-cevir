import unittest

from pdf_fakes import FakePdfPage, fill, span
from extraction.settings import with_defaults
from extraction.tables.table_scan import TableScanner

COLUMNS = [(70, 170), (170, 270), (270, 370)]
HEADER = ["Name", "Count", "Share"]
ROWS = [["Alpha", "1", "10%"], ["Beta", "2", "20%"], ["Gamma", "3", "30%"]]
ROW_HEIGHT = 30
TABLE_TOP = 150
CAPTION = span("Table 1-1. A caption that spans the whole table width", (70, 121, 370, 132), size=9)
BODY = span("Body text far below the table, spanning columns.", (70, 391, 370, 402), size=11)


def _row(top, texts, is_bold):
    font = "Helvetica-Bold" if is_bold else "Helvetica"
    return tuple(span(text, (left + 5, top + 10, left + 5 + 6 * len(text), top + 22), font, size=11)
                 for (left, _), text in zip(COLUMNS, texts))


def _shading(top):
    return [fill(left, top, right, top + ROW_HEIGHT) for left, right in COLUMNS]


def _zebra_page():
    """Başlık ve ikinci gövde satırı dolgulu (zebra) tablo; üstünde caption, altında gövde metni."""
    tops = [TABLE_TOP + ROW_HEIGHT * index for index in range(len(ROWS) + 1)]
    lines = [(CAPTION,), _row(tops[0], HEADER, is_bold=True)]
    lines += [_row(top, row, is_bold=False) for top, row in zip(tops[1:], ROWS)]
    return FakePdfPage(lines=lines + [(BODY,)], shapes=_shading(tops[0]) + _shading(tops[2]))


class TableScanTest(unittest.TestCase):
    def setUp(self):
        self.tables = TableScanner(with_defaults({})).scan(_zebra_page())

    def test_finds_filled_cell_table_with_header(self):
        self.assertEqual(len(self.tables), 1)
        block = self.tables[0]["block"]
        self.assertEqual(block["header_rows"], 1)
        self.assertEqual([c["en"] for c in block["rows"][0]], HEADER)
        self.assertEqual([[c["en"] for c in row] for row in block["rows"][1:]], ROWS)

    def test_caption_and_body_stay_outside_table_extent(self):
        self.assertGreater(self.tables[0]["y0"], CAPTION.box.y1)
        self.assertLess(self.tables[0]["y1"], BODY.box.y0)

    def test_page_without_fills_has_no_tables(self):
        self.assertEqual(TableScanner(with_defaults({})).scan(FakePdfPage(lines=[(span("plain", (70, 90, 100, 101)),)])), [])


if __name__ == "__main__":
    unittest.main()
