import unittest

from pdf_fakes import FakePdfPage, fill, span, stroke
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



TERM_COLUMNS = [(72, 140), (140, 432)]
CELL_HEIGHT = 14
SECOND_TABLE_TOP = 400
BOOK_SETTINGS = {"table_row_gap_ratio": 1.1}
STEP = 0.1


def _cell_lines(top, texts, font="Helvetica"):
    """PyMuPDF her hücreyi ayrı satır olarak verir; 9 puntoluk metin hücrenin 0.4 altından başlar."""
    return [(span(text, (left + 4, top + 0.4, left + 4 + 5 * len(text), top + 12.8), font, size=9),)
            for (left, _), text in zip(TERM_COLUMNS, texts)]


def _header_only_table(top, rows):
    """Yalnız başlığı dolgulu, altı kenar çizgili tablo: gövde satırlarını metin boşluğu ayırır.
    (satırlar, çizimler, alt kenar) döner."""
    lines = _cell_lines(top, ("Term", "Definition"), "Helvetica-Bold")
    lines += [line for index, row in enumerate(rows) for line in _cell_lines(top + CELL_HEIGHT * (index + 1), row)]
    bottom = top + CELL_HEIGHT * (len(rows) + 1)
    shapes = [fill(left, top, right, top + CELL_HEIGHT) for left, right in TERM_COLUMNS]
    shapes += [stroke(left, bottom + 4, right, bottom + 4) for left, right in TERM_COLUMNS]
    return lines, shapes, bottom


def _tables(lines, shapes, settings=BOOK_SETTINGS):
    return TableScanner(with_defaults(settings)).scan(FakePdfPage(lines=lines, shapes=shapes))


class SeparateTablesTest(unittest.TestCase):
    """Aynı sayfadaki iki tablo aynı sol kenardan başlar; ortak kenar onları tek tablo yapmamalı."""

    def test_two_tables_stay_separate(self):
        first_lines, first_shapes, _ = _header_only_table(TABLE_TOP, [("Configurability", "Change aspects.")])
        second_lines, second_shapes, _ = _header_only_table(SECOND_TABLE_TOP, [("Accessibility", "Access for all users.")])
        tables = _tables(first_lines + second_lines, first_shapes + second_shapes)
        self.assertEqual([[[cell["en"] for cell in row] for row in table["block"]["rows"]] for table in tables],
                         [[["Term", "Definition"], ["Configurability", "Change aspects."]],
                          [["Term", "Definition"], ["Accessibility", "Access for all users."]]])


class RowGapTest(unittest.TestCase):
    """Bantsız gövdede satırları metin boşluğu ayırır; eşik kitaba göre gelir.
    Satırlar arası 14, metin yüksekliği 12.4: oran 1.13."""

    ROWS = [("Archivability", "Will the data need to be archived"), ("Authentication", "Security requirements for users")]

    def test_rows_split_with_book_specific_ratio(self):
        lines, shapes, _ = _header_only_table(TABLE_TOP, self.ROWS)
        self.assertEqual(len(_tables(lines, shapes)[0]["block"]["rows"]), 3)

    def test_default_ratio_would_not_split_this_typesetting(self):
        lines, shapes, _ = _header_only_table(TABLE_TOP, self.ROWS)
        self.assertLess(len(_tables(lines, shapes, settings={})[0]["block"]["rows"]), 3)


class RowGapBoundaryTest(unittest.TestCase):
    """Satırın başlangıcı öncekinin tepesinden, metin yüksekliği × oran kadar aşağıdaysa yeni satırdır."""

    RATIO = 1.25
    TEXT_HEIGHT = 12
    BODY_TOP = TABLE_TOP + CELL_HEIGHT

    def _rows(self, second_top):
        """Başlık + iki gövde satırı; ikinci gövde satırı second_top'ta başlar."""
        lines = _cell_lines(TABLE_TOP, ("Term", "Definition"), "Helvetica-Bold")
        for top, texts in ((self.BODY_TOP, ("Latency", "Time to answer")), (second_top, ("Load", "Requests per second"))):
            lines += [(span(text, (left + 4, top, left + 4 + 5 * len(text), top + self.TEXT_HEIGHT), size=9),)
                      for (left, _), text in zip(TERM_COLUMNS, texts)]
        shapes = [fill(left, TABLE_TOP, right, TABLE_TOP + CELL_HEIGHT) for left, right in TERM_COLUMNS]
        shapes += [stroke(left, second_top + 20, right, second_top + 20) for left, right in TERM_COLUMNS]
        [table] = _tables(lines, shapes, settings={"table_row_gap_ratio": self.RATIO})
        return table["block"]["rows"]

    def test_line_at_the_ratio_continues_the_row(self):
        self.assertEqual(len(self._rows(self.BODY_TOP + self.TEXT_HEIGHT * self.RATIO)), 2)

    def test_line_just_below_the_ratio_starts_a_row(self):
        self.assertEqual(len(self._rows(self.BODY_TOP + self.TEXT_HEIGHT * self.RATIO + STEP)), 3)


class TableEndTest(unittest.TestCase):
    """Tablo alt kenar çizgisinde biter; altındaki caption ve gövde metni tabloya girmemeli.
    Gövde satırı italik sözcükte parçalanıp iki sütuna düşer; sondaki tek sütunlu
    satırı atan kural caption'ı dışarıda tutamaz, yalnız çizgi tutar."""

    def test_text_below_the_rule_is_outside(self):
        lines, shapes, bottom = _header_only_table(TABLE_TOP, [("Availability", "How long the system is available")])
        caption = span("Table 4-1. Operational characteristics", (72, bottom + 20, 222, bottom + 32), size=9)
        body_top, body_bottom = bottom + 48, bottom + 63
        body = (span("See ", (72, body_top, 92, body_bottom), size=10.5),
                span("Chapter 5", (92, body_top, 138, body_bottom), "Helvetica-Oblique", 10.5),
                span(" for details.", (138, body_top, 200, body_bottom), size=10.5))
        [table] = _tables(lines + [(caption,), body], shapes)
        self.assertEqual([[cell["en"] for cell in row] for row in table["block"]["rows"]],
                         [["Term", "Definition"], ["Availability", "How long the system is available"]])

if __name__ == "__main__":
    unittest.main()
