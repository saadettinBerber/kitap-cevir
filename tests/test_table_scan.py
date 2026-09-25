import unittest

from pdf_fakes import FakePdfPage, fill, span, stroke
from extraction.settings import with_defaults
from extraction.tables.table_grid import MAX_BAND_GAP_RATIO, PageFills
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



BACKGROUND_ROWS = ROWS + [["Delta", "4", "40%"], ["Epsilon", "5", "50%"]]
BACKGROUND_MARGIN = 5


def _background_page():
    """Yalnız başlığı ile son satırı dolgulu, hepsi tek arka planın üstünde duran tablo: iki dolgu
    öbeği arasındaki boşluk onları ayrı tablo sayacak kadar büyük. Arka planın hemen altında sütunlara
    oturan bir satır daha var."""
    tops = [TABLE_TOP + ROW_HEIGHT * index for index in range(len(BACKGROUND_ROWS) + 1)]
    lines = [_row(tops[0], HEADER, is_bold=True)]
    lines += [_row(top, row, is_bold=False) for top, row in zip(tops[1:], BACKGROUND_ROWS)]
    bottom = tops[-1] + ROW_HEIGHT
    lines += [_row(bottom + BACKGROUND_MARGIN * 2, ["Zeta", "6", "60%"], is_bold=False)]
    background = fill(COLUMNS[0][0] - BACKGROUND_MARGIN, TABLE_TOP - BACKGROUND_MARGIN,
                      COLUMNS[-1][1] + BACKGROUND_MARGIN, bottom + BACKGROUND_MARGIN)
    return FakePdfPage(lines=lines, shapes=[background] + _shading(tops[0]) + _shading(tops[-1]))


class BackgroundTableTest(unittest.TestCase):
    """Arka plan dolgusu varsa tablo odur: üstündeki hücreler tek tablodur, tablo arka planın kenarında biter."""

    def setUp(self):
        self.tables = TableScanner(with_defaults({})).scan(_background_page())

    def test_cells_on_one_background_are_one_table(self):
        self.assertEqual(len(self.tables), 1)

    def test_table_ends_at_the_background_edge(self):
        rows = self.tables[0]["block"]["rows"]
        self.assertEqual([[c["en"] for c in row] for row in rows], [HEADER] + BACKGROUND_ROWS)


class FullWidthFillTest(unittest.TestCase):
    """Bütün sütunları boydan boya kaplayan dolgu satır bandı değildir; altındaki satırlar ayrı kalır."""

    def test_rows_under_a_full_width_fill_stay_apart(self):
        body_tops = [TABLE_TOP + ROW_HEIGHT * (index + 1) for index in range(len(ROWS))]
        lines = [_row(TABLE_TOP, HEADER, is_bold=True)]
        lines += [_row(top, row, is_bold=False) for top, row in zip(body_tops, ROWS)]
        full_width = fill(COLUMNS[0][0], body_tops[0], COLUMNS[-1][1], body_tops[-1] + ROW_HEIGHT)
        page = FakePdfPage(lines=lines + [(BODY,)], shapes=_shading(TABLE_TOP) + [full_width])
        [table] = TableScanner(with_defaults({})).scan(page)
        self.assertEqual([[c["en"] for c in row] for row in table["block"]["rows"]], [HEADER] + ROWS)


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


class TableGroupTest(unittest.TestCase):
    """Aynı sütun kenarını paylaşan dolgular, aralarındaki boşluk hücre yüksekliği × oranı aşmadıkça tek tablodur."""

    TEXT_BOTTOM = 700

    def _groups(self, gap):
        second_top = TABLE_TOP + CELL_HEIGHT + gap
        fills = [fill(left, top, right, top + CELL_HEIGHT) for top in (TABLE_TOP, second_top) for left, right in TERM_COLUMNS]
        return PageFills(fills, self.TEXT_BOTTOM).table_groups()

    def test_fills_at_the_gap_ratio_are_one_table(self):
        self.assertEqual(len(self._groups(CELL_HEIGHT * MAX_BAND_GAP_RATIO)), 1)

    def test_fills_further_apart_are_two_tables(self):
        self.assertEqual(len(self._groups(CELL_HEIGHT * MAX_BAND_GAP_RATIO + STEP)), 2)


class ShortTableTest(unittest.TestCase):
    def test_header_without_body_rows_is_not_a_table(self):
        lines, shapes, _ = _header_only_table(TABLE_TOP, [])
        self.assertEqual(_tables(lines, shapes), [])


class SingleColumnEdgeTest(unittest.TestCase):
    """Tablonun başında ya da sonunda tek sütunu dolu satır tablo dışı metindir (başlık, kaynak notu)."""

    ROW = ("Availability", "How long the system is available")

    def test_single_column_band_above_the_header_is_left_out(self):
        title = _cell_lines(TABLE_TOP - CELL_HEIGHT, ("Characteristics",), "Helvetica-Bold")
        lines, shapes, _ = _header_only_table(TABLE_TOP, [self.ROW])
        title_fill = fill(TERM_COLUMNS[0][0], TABLE_TOP - CELL_HEIGHT, TERM_COLUMNS[0][1], TABLE_TOP)
        [table] = _tables(title + lines, shapes + [title_fill])
        self.assertEqual([[cell["en"] for cell in row] for row in table["block"]["rows"]],
                         [["Term", "Definition"], list(self.ROW)])

    def test_single_column_line_after_the_last_row_is_left_out(self):
        lines, shapes, _ = _header_only_table(TABLE_TOP, [self.ROW, ("a Estimated.",)])
        [table] = _tables(lines, shapes)
        self.assertEqual([[cell["en"] for cell in row] for row in table["block"]["rows"]],
                         [["Term", "Definition"], list(self.ROW)])


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
