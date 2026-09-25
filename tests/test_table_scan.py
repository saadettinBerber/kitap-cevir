"""Dolgu dikdörtgenli tabloların taranması. İki dizgi sınanır: her satırı ayrı dolgulu
hücrelerden oluşan zebra tablo ve yalnız başlığı dolgulu, gövde satırlarını metin boşluğunun
ayırdığı terim tablosu."""
import dataclasses
import unittest

from pdf_fakes import FakePdfPage, fill, span, stroke
from extraction.pdf.geometry import Box
from extraction.settings import with_defaults
from extraction.tables.table_grid import MAX_BAND_GAP_RATIO, MIN_CELL_WIDTH, RULE_MAX_HEIGHT, PageFills
from extraction.tables.table_scan import TableScanner

BOLD = "Helvetica-Bold"
STEP = 0.1
FRACTION = 0.2
SHIFT = 3

COLUMNS = [(70, 170), (170, 270), (270, 370)]
HEADER = ["Name", "Count", "Share"]
ROWS = [["Alpha", "1", "10%"], ["Beta", "2", "20%"], ["Gamma", "3", "30%"]]
ROW_HEIGHT = 30
TABLE_TOP = 150
PADDING, TEXT_DROP, TEXT_HEIGHT, CHAR_WIDTH = 5, 10, 12, 6
BODY_SIZE = 11
MARK_SIZE = BODY_SIZE / 2
CAPTION = span("Table 1-1. A caption that spans the whole table width", (70, 121, 370, 132), size=9)
BODY = span("Body text far below the table, spanning columns.", (70, 391, 370, 402), size=BODY_SIZE)


def _bold(line):
    return tuple(dataclasses.replace(piece, font=BOLD) for piece in line)


def _cell_row(y0, texts):
    """Zebra sütunlarına oturan metin satırı; boş metin o sütunu boş bırakır."""
    return tuple(span(text, (left + PADDING, y0, left + PADDING + CHAR_WIDTH * len(text), y0 + TEXT_HEIGHT),
                      size=BODY_SIZE)
                 for (left, _), text in zip(COLUMNS, texts) if text)


class ZebraLayout:
    """COLUMNS sütunlu tablo: kalın başlığı TABLE_TOP'ta, her satırı ROW_HEIGHT yüksekliğinde; metin
    hücresinin sol üst köşesinden biraz içeride. Hangi satırın dolgulu olduğunu test seçer."""

    def __init__(self, rows):
        self._rows = rows

    def lines(self):
        body = [self._line(index + 1, row) for index, row in enumerate(self._rows)]
        return [_bold(self._line(0, HEADER))] + body

    def shading(self, index):
        top = self.top(index)
        return [fill(left, top, right, top + ROW_HEIGHT) for left, right in COLUMNS]

    def top(self, index):
        return TABLE_TOP + ROW_HEIGHT * index

    def bottom(self):
        return self.top(len(self._rows) + 1)

    def _line(self, index, texts):
        return _cell_row(self.top(index) + TEXT_DROP, texts)


def _scan(page):
    return TableScanner(with_defaults({})).scan(page)


def _texts(table):
    return [[cell["en"] for cell in row] for row in table["block"]["rows"]]


def _zebra_page():
    """Başlık ve ikinci gövde satırı dolgulu (zebra) tablo; üstünde caption, altında gövde metni."""
    layout = ZebraLayout(ROWS)
    return FakePdfPage(lines=[(CAPTION,)] + layout.lines() + [(BODY,)], shapes=layout.shading(0) + layout.shading(2))


class ZebraTableTest(unittest.TestCase):
    def setUp(self):
        self.tables = _scan(_zebra_page())

    def test_filled_cells_make_one_table(self):
        self.assertEqual(len(self.tables), 1)

    def test_bold_first_row_is_the_header(self):
        self.assertEqual(self.tables[0]["block"]["header_rows"], 1)

    def test_rows_hold_the_cell_texts(self):
        self.assertEqual(_texts(self.tables[0]), [HEADER] + ROWS)

    def test_table_spans_from_the_header_text_to_the_last_row_text(self):
        last_text_top = ZebraLayout(ROWS).top(len(ROWS)) + TEXT_DROP
        self.assertEqual((self.tables[0]["y0"], self.tables[0]["y1"]),
                         (TABLE_TOP + TEXT_DROP, last_text_top + TEXT_HEIGHT))

    def test_raised_or_lowered_pieces_widen_the_table_extent(self):
        """Üst simge satırının üstüne, alt simge altına taşar; tablo onları da kapsar."""
        layout = ZebraLayout(ROWS)
        header_top, last_top = TABLE_TOP + TEXT_DROP, layout.top(len(ROWS)) + TEXT_DROP
        raised = dataclasses.replace(span("a", (360, header_top - SHIFT, 364, header_top + MARK_SIZE)),
                                     line_y=header_top)
        lowered = dataclasses.replace(span("i", (360, last_top + SHIFT, 364, last_top + TEXT_HEIGHT + SHIFT)),
                                      line_y=last_top)
        header, *body = layout.lines()
        page = FakePdfPage(lines=[header + (raised,)] + body[:-1] + [body[-1] + (lowered,)], shapes=layout.shading(0))
        [table] = _scan(page)
        self.assertEqual((table["y0"], table["y1"]), (header_top - SHIFT, last_top + TEXT_HEIGHT + SHIFT))

    def test_caption_and_body_stay_outside_table_extent(self):
        self.assertGreater(self.tables[0]["y0"], CAPTION.box.y1)
        self.assertLess(self.tables[0]["y1"], BODY.box.y0)

    def test_lines_read_bottom_up_still_give_rows_top_down(self):
        page = _zebra_page()
        self.assertEqual(_texts(_scan(FakePdfPage(lines=page.lines[::-1], shapes=page.shapes))[0]), [HEADER] + ROWS)

    def test_cell_text_is_stripped(self):
        layout = ZebraLayout([[" Alpha ", "1", "10%"]])
        [table] = _scan(FakePdfPage(lines=layout.lines(), shapes=layout.shading(0) + layout.shading(1)))
        self.assertEqual(_texts(table)[1][0], "Alpha")

    def test_page_without_fills_has_no_tables(self):
        self.assertEqual(_scan(FakePdfPage(lines=[(span("plain", (70, 90, 100, 101)),)])), [])


BACKGROUND_ROWS = ROWS + [["Delta", "4", "40%"], ["Epsilon", "5", "50%"]]
ROW_BELOW = ["Zeta", "6", "60%"]
BACKGROUND_MARGIN = 5


def _background_page():
    """Yalnız başlığı ile son satırı dolgulu, hepsi tek arka planın üstünde duran tablo: iki dolgu
    öbeği arasındaki boşluk onları ayrı tablo sayacak kadar büyük. Arka planın hemen altında sütunlara
    oturan bir satır daha var."""
    layout, last = ZebraLayout(BACKGROUND_ROWS + [ROW_BELOW]), len(BACKGROUND_ROWS)
    background = fill(COLUMNS[0][0] - BACKGROUND_MARGIN, TABLE_TOP - BACKGROUND_MARGIN,
                      COLUMNS[-1][1] + BACKGROUND_MARGIN, layout.top(last + 1) + BACKGROUND_MARGIN)
    return FakePdfPage(lines=layout.lines(), shapes=[background] + layout.shading(0) + layout.shading(last))


class BackgroundTableTest(unittest.TestCase):
    """Arka plan dolgusu varsa tablo odur: üstündeki hücreler tek tablodur, tablo arka planın kenarında biter."""

    def setUp(self):
        self.tables = _scan(_background_page())

    def test_cells_on_one_background_are_one_table(self):
        self.assertEqual(len(self.tables), 1)

    def test_table_ends_at_the_background_edge(self):
        self.assertEqual(_texts(self.tables[0]), [HEADER] + BACKGROUND_ROWS)


class FullWidthFillTest(unittest.TestCase):
    """Bütün sütunları boydan boya kaplayan dolgu satır bandı değildir; altındaki satırlar ayrı kalır."""

    def test_rows_under_a_full_width_fill_stay_apart(self):
        layout = ZebraLayout(ROWS)
        full_width = fill(COLUMNS[0][0], layout.top(1), COLUMNS[-1][1], layout.bottom())
        [table] = _scan(FakePdfPage(lines=layout.lines() + [(BODY,)], shapes=layout.shading(0) + [full_width]))
        self.assertEqual(_texts(table), [HEADER] + ROWS)


SUBLINE_DROPS = (2, 16)      # bir bandın içindeki iki alt satırın üst kenarı, satırın tepesinden


def _split_row(top, *sublines):
    """Alt satırlara bölünmüş tablo satırı; her alt satır sütun metinleridir, SUBLINE_DROPS aralıklarıyla."""
    return [_cell_row(top + drop, texts) for drop, texts in zip(SUBLINE_DROPS, sublines)]


def _shaded_rows(lines):
    """Başlığı ve ilk gövde satırı dolgulu tablonun bulunan satırları."""
    layout = ZebraLayout([])
    [table] = _scan(FakePdfPage(lines=lines, shapes=layout.shading(0) + layout.shading(1)))
    return table["block"]["rows"]


class HeaderTest(unittest.TestCase):
    def test_small_regular_mark_does_not_unbold_the_header(self):
        mark = span("a", (360, TABLE_TOP + TEXT_DROP, 364, TABLE_TOP + TEXT_DROP + MARK_SIZE), size=MARK_SIZE)
        header = _bold(_cell_row(TABLE_TOP + TEXT_DROP, HEADER)) + (mark,)
        layout = ZebraLayout(ROWS)
        [table] = _scan(FakePdfPage(lines=[header] + layout.lines()[1:], shapes=layout.shading(0)))
        self.assertEqual(table["block"]["header_rows"], 1)

    def test_consecutive_bold_rows_are_all_header(self):
        layout = ZebraLayout(ROWS)
        header, first, *rest = layout.lines()
        page = FakePdfPage(lines=[header, _bold(first), *rest], shapes=layout.shading(0) + layout.shading(1))
        [table] = _scan(page)
        self.assertEqual(table["block"]["header_rows"], 2)


class LineBreakTest(unittest.TestCase):
    """Bir gövde satırında iki ya da daha çok hücre çok satırlıysa hücre içi satırlar liste
    niteliğindedir, korunur. Başlıkta korunmaz."""

    BODY_TOP = TABLE_TOP + ROW_HEIGHT

    def _header(self):
        return [_bold(_cell_row(TABLE_TOP + TEXT_DROP, HEADER))]

    def test_two_multiline_cells_keep_their_breaks(self):
        rows = _shaded_rows(self._header() + _split_row(self.BODY_TOP, ("a", "c", "e"), ("b", "d", "")))
        self.assertEqual(rows[1], [{"en": "a<br>b", "html": True}, {"en": "c<br>d", "html": True}, {"en": "e"}])

    def test_cell_whose_lines_fill_its_column_joins_them_in_a_listing_row(self):
        """Sarılmış düz metnin ölçüsü hücrenin kendi sütunudur."""
        left, right = COLUMNS[0]
        top = self.BODY_TOP + SUBLINE_DROPS[0]
        filling = span("wrapped", (left + PADDING, top, right - PADDING, top + TEXT_HEIGHT), size=BODY_SIZE)
        first, second = _split_row(self.BODY_TOP, ("", "c", "e"), ("b", "d", ""))
        rows = _shaded_rows(self._header() + [(filling,) + first, second])
        self.assertEqual(rows[1][:2], [{"en": "wrapped b"}, {"en": "c<br>d", "html": True}])

    def test_one_multiline_cell_joins_its_lines(self):
        rows = _shaded_rows(self._header() + _split_row(self.BODY_TOP, ("a", "c", "e"), ("b", "", "")))
        self.assertEqual(rows[1][0], {"en": "a b"})

    def test_header_joins_its_lines_even_when_multiline(self):
        header = [_bold(line) for line in _split_row(TABLE_TOP, ("Na", "Co", "Sh"), ("me", "unt", ""))]
        rows = _shaded_rows(header + [_cell_row(self.BODY_TOP + TEXT_DROP, ROWS[0])])
        self.assertEqual(rows[0], [{"en": "Na me"}, {"en": "Co unt"}, {"en": "Sh"}])

    def test_pieces_of_a_line_whose_tops_differ_in_fractions_stay_one_line(self):
        y0 = self.BODY_TOP + TEXT_DROP
        hello = dataclasses.replace(span("Hello", (75, y0, 105, y0 + TEXT_HEIGHT)), line_y=y0 + FRACTION)
        world = dataclasses.replace(span("World", (110, y0, 140, y0 + TEXT_HEIGHT)), line_y=y0 - FRACTION)
        rows = _shaded_rows(self._header() + [(hello, world) + _cell_row(y0, ("", "1", "10%"))])
        self.assertEqual(rows[1][0], {"en": "Hello World"})


class RowBandTest(unittest.TestCase):
    """Sütun kenarlarına oturan dolguların dikey aralıkları satır bantlarıdır; örtüşen dolgular
    tek banttır. Bandın içindeki metin tek satıra aittir."""

    BODY_TOP = TABLE_TOP + ROW_HEIGHT
    LOW_LINE = BODY_TOP + ROW_HEIGHT + TEXT_DROP / 2    # ilk gövde bandının hemen altından başlayan alt satır

    def _first_body_cell(self, *extra_fills):
        layout = ZebraLayout([])
        lines = [_bold(_cell_row(TABLE_TOP + TEXT_DROP, HEADER)), _cell_row(self.BODY_TOP + TEXT_DROP, ("a", "c", "e")),
                 _cell_row(self.LOW_LINE, ("b", "", ""))]
        [table] = _scan(FakePdfPage(lines=lines, shapes=list(extra_fills) + layout.shading(0) + layout.shading(1)))
        return table["block"]["rows"][1][0]

    def test_fill_overlapping_a_band_widens_it(self):
        column = COLUMNS[0]
        lower = fill(column[0], self.BODY_TOP + ROW_HEIGHT - TEXT_DROP, column[1], self.LOW_LINE + ROW_HEIGHT)
        self.assertEqual(self._first_body_cell(lower), {"en": "a b"})

    def test_fill_inside_a_taller_band_does_not_shrink_it(self):
        column = COLUMNS[0]
        taller = fill(column[0], self.BODY_TOP, column[1], self.LOW_LINE + ROW_HEIGHT)
        self.assertEqual(self._first_body_cell(taller), {"en": "a b"})

    def test_band_starts_a_row_right_under_close_unbanded_text(self):
        """Bandın metni üstteki bantsız satıra satır boşluğu eşiğinden yakın olsa da yeni satırdır."""
        unbanded_top = self.BODY_TOP + TEXT_DROP
        banded_top = unbanded_top + TEXT_HEIGHT
        band = [fill(left, banded_top - TEXT_DROP / 2, right, banded_top + ROW_HEIGHT) for left, right in COLUMNS]
        lines = [_bold(_cell_row(TABLE_TOP + TEXT_DROP, HEADER)), _cell_row(unbanded_top, ROWS[0]),
                 _cell_row(banded_top, ROWS[1])]
        [table] = _scan(FakePdfPage(lines=lines, shapes=ZebraLayout([]).shading(0) + band))
        self.assertEqual(_texts(table), [HEADER] + ROWS[:2])

    def test_text_centred_on_the_band_edge_belongs_to_the_band(self):
        """Başlık metninin ortası başlık bandının alt kenarında: bant kenarı banda dahildir."""
        layout = ZebraLayout(ROWS[:1])
        centred = _bold(_cell_row(layout.top(1) - TEXT_HEIGHT / 2, HEADER))
        body = _cell_row(layout.top(1) + TEXT_DROP, ROWS[0])
        [table] = _scan(FakePdfPage(lines=[centred, body], shapes=layout.shading(0) + layout.shading(1)))
        self.assertEqual(_texts(table), [HEADER, ROWS[0]])


FAR_SUBLINE_DROPS = (2, 22)  # alt satırlar arası boşluk varsayılan satır boşluğu eşiğini aşar
SPLIT_HEADER = (("Na", "Co", "Sh"), ("me", "unt", ""))


class PageBandTest(unittest.TestCase):
    """Satır bantları yalnız tablonun kendi hücrelerinden değil sayfanın bütün dolgularından çıkar.
    Alt çizgisi olmayan tablo, sütunlarını paylaşan uzaktaki dolgulu satırı da içine alır (o satır
    tek başına tablo olamayacak kadar kısadır); satırın iki alt satırı, arası satır boşluğundan büyük
    olsa da, bandında tek satırdır."""

    def test_band_of_another_table_joins_its_lines_into_one_row(self):
        upper = ZebraLayout(ROWS[:1])
        lower_top = upper.bottom() + ROW_HEIGHT * (MAX_BAND_GAP_RATIO + 1)
        apart = [_bold(_cell_row(lower_top + drop, texts)) for drop, texts in zip(FAR_SUBLINE_DROPS, SPLIT_HEADER)]
        lower_fills = [fill(left, lower_top, right, lower_top + ROW_HEIGHT) for left, right in COLUMNS]
        [table] = _scan(FakePdfPage(lines=upper.lines() + apart, shapes=upper.shading(0) + lower_fills))
        self.assertEqual(_texts(table)[-1][0], "Na<br>me")


class WideSpanTest(unittest.TestCase):
    def test_row_with_a_span_wider_than_the_widest_column_ends_the_table(self):
        layout = ZebraLayout(ROWS)
        y0 = layout.bottom() + TEXT_DROP
        wide = span("A sentence across two columns", (COLUMNS[0][0], y0, COLUMNS[1][1] - PADDING, y0 + TEXT_HEIGHT))
        row = (wide,) + _cell_row(y0, ("", "", "x"))
        [table] = _scan(FakePdfPage(lines=layout.lines() + [row], shapes=layout.shading(0) + layout.shading(2)))
        self.assertEqual(_texts(table), [HEADER] + ROWS)


AREA_TOP_SHIFT = 0.5         # parçanın tepesi tablo alanının bu kadar üstünde


class TableAreaTest(unittest.TestCase):
    def test_text_starting_within_a_point_above_the_area_belongs_to_the_table(self):
        layout = ZebraLayout(ROWS[:1])
        area_top = TABLE_TOP + TEXT_DROP + AREA_TOP_SHIFT
        cells = [fill(left, area_top + AREA_TOP_SHIFT, right, layout.top(1)) for left, right in COLUMNS]
        background = fill(COLUMNS[0][0] - BACKGROUND_MARGIN, area_top, COLUMNS[-1][1] + BACKGROUND_MARGIN,
                          layout.bottom() + BACKGROUND_MARGIN)
        [table] = _scan(FakePdfPage(lines=layout.lines(), shapes=[background] + cells))
        self.assertEqual(_texts(table), [HEADER, ROWS[0]])


TERM_COLUMNS = [(72, 140), (140, 432)]
TERM_HEADER = ("Term", "Definition")
CELL_HEIGHT = 14
SECOND_TABLE_TOP = 400
BOOK_SETTINGS = {"table_row_gap_ratio": 1.1}
CELL_INSET, CELL_TEXT_DROP, CELL_TEXT_BOTTOM, CELL_CHAR_WIDTH = 4, 0.4, 12.8, 5
CELL_SIZE = 9
RULE_GAP = 4
RULE_TOP = TABLE_TOP + CELL_HEIGHT * 2 + RULE_GAP   # tek gövde satırlı terim tablosunun alt çizgisi


def _cell_lines(top, texts):
    """PyMuPDF her hücreyi ayrı satır olarak verir; 9 puntoluk metin hücrenin 0.4 altından başlar."""
    return [(span(text, (left + CELL_INSET, top + CELL_TEXT_DROP,
                         left + CELL_INSET + CELL_CHAR_WIDTH * len(text), top + CELL_TEXT_BOTTOM), size=CELL_SIZE),)
            for (left, _), text in zip(TERM_COLUMNS, texts)]


def _with_height(line, height):
    return tuple(dataclasses.replace(piece, box=Box(piece.box.x0, piece.box.y0, piece.box.x1, piece.box.y0 + height))
                 for piece in line)


def _bold_lines(lines):
    return [_bold(line) for line in lines]


def _scan_book(page):
    return TableScanner(with_defaults(BOOK_SETTINGS)).scan(page)


class TermTableLayout:
    """Yalnız başlığı dolgulu, altı kenar çizgili iki sütunlu tablo: gövde satırlarını metin
    boşluğu ayırır."""

    def __init__(self, top, rows):
        self._top = top
        self._rows = rows

    def page(self):
        return FakePdfPage(lines=self.lines(), shapes=self.shapes())

    def lines(self):
        body = [line for index, row in enumerate(self._rows) for line in _cell_lines(self._row_top(index + 1), row)]
        return _bold_lines(_cell_lines(self._top, TERM_HEADER)) + body

    def shapes(self):
        return self.header_fills() + self.bottom_rules()

    def header_fills(self):
        return [fill(left, self._top, right, self._top + CELL_HEIGHT) for left, right in TERM_COLUMNS]

    def bottom_rules(self):
        rule_y = self.bottom() + RULE_GAP
        return [stroke(left, rule_y, right, rule_y) for left, right in TERM_COLUMNS]

    def bottom(self):
        return self._row_top(len(self._rows) + 1)

    def _row_top(self, index):
        return self._top + CELL_HEIGHT * index


class SeparateTablesTest(unittest.TestCase):
    """Aynı sayfadaki iki tablo aynı sol kenardan başlar; ortak kenar onları tek tablo yapmamalı."""

    def test_two_tables_stay_separate(self):
        first = TermTableLayout(TABLE_TOP, [("Configurability", "Change aspects.")])
        second = TermTableLayout(SECOND_TABLE_TOP, [("Accessibility", "Access for all users.")])
        tables = _scan_book(FakePdfPage(lines=first.lines() + second.lines(), shapes=first.shapes() + second.shapes()))
        self.assertEqual([_texts(table) for table in tables],
                         [[list(TERM_HEADER), ["Configurability", "Change aspects."]],
                          [list(TERM_HEADER), ["Accessibility", "Access for all users."]]])


    def test_tables_come_from_top_to_bottom_whatever_the_drawing_order(self):
        first = TermTableLayout(TABLE_TOP, [("Configurability", "Change aspects.")])
        second = TermTableLayout(SECOND_TABLE_TOP, [("Accessibility", "Access for all users.")])
        tables = _scan_book(FakePdfPage(lines=first.lines() + second.lines(), shapes=second.shapes() + first.shapes()))
        self.assertEqual([_texts(table)[1][0] for table in tables], ["Configurability", "Accessibility"])


class RowGapTest(unittest.TestCase):
    """Bantsız gövdede satırları metin boşluğu ayırır; eşik kitaba göre gelir.
    Satırlar arası 14, metin yüksekliği 12.4: oran 1.13."""

    ROWS = [("Archivability", "Will the data need to be archived"),
            ("Authentication", "Security requirements for users")]

    def test_rows_split_with_book_specific_ratio(self):
        [table] = _scan_book(TermTableLayout(TABLE_TOP, self.ROWS).page())
        self.assertEqual(len(_texts(table)), len(self.ROWS) + 1)

    def test_default_ratio_would_not_split_this_typesetting(self):
        [table] = _scan(TermTableLayout(TABLE_TOP, self.ROWS).page())
        self.assertLess(len(_texts(table)), len(self.ROWS) + 1)


class RowGapBoundaryTest(unittest.TestCase):
    """Satırın başlangıcı öncekinin tepesinden, önceki metnin yüksekliği × oran kadar aşağıdaysa
    yeni satırdır."""

    RATIO = 1.25
    TEXT_HEIGHT = 12
    BODY_TOP = TABLE_TOP + CELL_HEIGHT
    RULE_Y = BODY_TOP + 5 * TEXT_HEIGHT
    FIRST_ROW, SECOND_ROW = ("Latency", "Time to answer"), ("Load", "Requests per second")

    def _row(self, top, texts):
        return [(span(text, (left + CELL_INSET, top, left + CELL_INSET + CELL_CHAR_WIDTH * len(text),
                             top + self.TEXT_HEIGHT), size=CELL_SIZE),)
                for (left, _), text in zip(TERM_COLUMNS, texts)]

    def _row_count(self, second_row):
        """Başlık, bir gövde satırı ve verilen ikinci gövde satırı."""
        lines = _bold_lines(_cell_lines(TABLE_TOP, TERM_HEADER)) + self._row(self.BODY_TOP, self.FIRST_ROW)
        rules = [stroke(left, self.RULE_Y, right, self.RULE_Y) for left, right in TERM_COLUMNS]
        page = FakePdfPage(lines=lines + second_row, shapes=TermTableLayout(TABLE_TOP, []).header_fills() + rules)
        [table] = TableScanner(with_defaults({"table_row_gap_ratio": self.RATIO})).scan(page)
        return len(_texts(table))

    def test_line_at_the_ratio_continues_the_row(self):
        second_top = self.BODY_TOP + self.TEXT_HEIGHT * self.RATIO
        self.assertEqual(self._row_count(self._row(second_top, self.SECOND_ROW)), 2)

    def test_line_just_below_the_ratio_starts_a_row(self):
        second_top = self.BODY_TOP + self.TEXT_HEIGHT * self.RATIO + STEP
        self.assertEqual(self._row_count(self._row(second_top, self.SECOND_ROW)), 3)

    def test_gap_is_measured_by_the_previous_line_height(self):
        """Alttaki satır daha yüksek olsa da ölçü üstteki satırdır."""
        second_top = self.BODY_TOP + self.TEXT_HEIGHT * self.RATIO + STEP
        tall = [_with_height(line, self.TEXT_HEIGHT * 2) for line in self._row(second_top, self.SECOND_ROW)]
        self.assertEqual(self._row_count(tall), 3)


class TableGroupTest(unittest.TestCase):
    """Aynı sütun kenarını paylaşan dolgular, aralarındaki boşluk hücre yüksekliği × oranı
    aşmadıkça tek tablodur."""

    TEXT_BOTTOM = 700

    def _groups(self, gap):
        tops = (TABLE_TOP, TABLE_TOP + CELL_HEIGHT + gap)
        fills = [fill(left, top, right, top + CELL_HEIGHT) for top in tops for left, right in TERM_COLUMNS]
        return PageFills(fills, self.TEXT_BOTTOM).table_groups()

    def test_fills_at_the_gap_ratio_are_one_table(self):
        self.assertEqual(len(self._groups(CELL_HEIGHT * MAX_BAND_GAP_RATIO)), 1)

    def test_fills_further_apart_are_two_tables(self):
        self.assertEqual(len(self._groups(CELL_HEIGHT * MAX_BAND_GAP_RATIO + STEP)), 2)


class ShortTableTest(unittest.TestCase):
    def test_header_without_body_rows_is_not_a_table(self):
        self.assertEqual(_scan_book(TermTableLayout(TABLE_TOP, []).page()), [])


class SingleColumnEdgeTest(unittest.TestCase):
    """Tablonun başında ya da sonunda tek sütunu dolu satır tablo dışı metindir (başlık, kaynak notu)."""

    ROW = ("Availability", "How long the system is available")

    def test_single_column_band_above_the_header_is_left_out(self):
        table = TermTableLayout(TABLE_TOP, [self.ROW])
        title = _bold_lines(_cell_lines(TABLE_TOP - CELL_HEIGHT, ("Characteristics",)))
        title_fill = fill(TERM_COLUMNS[0][0], TABLE_TOP - CELL_HEIGHT, TERM_COLUMNS[0][1], TABLE_TOP)
        [found] = _scan_book(FakePdfPage(lines=title + table.lines(), shapes=table.shapes() + [title_fill]))
        self.assertEqual(_texts(found), [list(TERM_HEADER), list(self.ROW)])

    def test_single_column_line_after_the_last_row_is_left_out(self):
        [found] = _scan_book(TermTableLayout(TABLE_TOP, [self.ROW, ("a Estimated.",)]).page())
        self.assertEqual(_texts(found), [list(TERM_HEADER), list(self.ROW)])


class BottomRuleTest(unittest.TestCase):
    """Tablo altındaki ilk yatay çizgide biter. Çizgi sayılan: en çok RULE_MAX_HEIGHT kalınlığında, en az
    MIN_CELL_WIDTH uzunluğunda ve tablonun altında yatayda onunla örtüşen dolgusuz çizim."""

    ROW = ("Availability", "How long the system is available")
    EXTRA = ("Extra", "Row after the table")

    def _rows_under(self, rule):
        """Tablo, altında bir çizgi ve çizginin altında sütunlara oturan bir satır."""
        table = TermTableLayout(TABLE_TOP, [self.ROW])
        extra = _cell_lines(table.bottom() + CELL_HEIGHT * 2, self.EXTRA)
        [found] = _scan_book(FakePdfPage(lines=table.lines() + extra, shapes=table.header_fills() + [rule]))
        return _texts(found)

    def _rule(self, height=0, span=None):
        left, right = TERM_COLUMNS[0][0], TERM_COLUMNS[-1][1]
        return stroke(left, RULE_TOP, span or right, RULE_TOP + height)

    def test_rule_as_thick_as_the_limit_ends_the_table(self):
        self.assertEqual(self._rows_under(self._rule(height=RULE_MAX_HEIGHT)), [list(TERM_HEADER), list(self.ROW)])

    def test_thicker_stroke_is_not_a_rule(self):
        self.assertIn(list(self.EXTRA), self._rows_under(self._rule(height=RULE_MAX_HEIGHT + STEP)))

    def test_stroke_shorter_than_a_cell_is_not_a_rule(self):
        left = TERM_COLUMNS[0][0]
        self.assertIn(list(self.EXTRA), self._rows_under(self._rule(span=left + MIN_CELL_WIDTH - STEP)))

    def test_rule_beside_the_table_does_not_end_it(self):
        right = TERM_COLUMNS[-1][1]
        beside = stroke(right + MIN_CELL_WIDTH, RULE_TOP, right + 3 * MIN_CELL_WIDTH, RULE_TOP)
        self.assertIn(list(self.EXTRA), self._rows_under(beside))


class TableEndTest(unittest.TestCase):
    """Tablo alt kenar çizgisinde biter; altındaki caption ve gövde metni tabloya girmemeli.
    Gövde satırı italik sözcükte parçalanıp iki sütuna düşer; sondaki tek sütunlu
    satırı atan kural caption'ı dışarıda tutamaz, yalnız çizgi tutar."""

    ROW = ("Availability", "How long the system is available")
    CAPTION_DROP, CAPTION_HEIGHT, BODY_DROP, BODY_HEIGHT = 20, 12, 48, 15
    PROSE_SIZE = 10.5

    def _caption(self, bottom):
        top = bottom + self.CAPTION_DROP
        caption = "Table 4-1. Operational characteristics"
        return (span(caption, (72, top, 222, top + self.CAPTION_HEIGHT), size=CELL_SIZE),)

    def _prose(self, bottom):
        top = bottom + self.BODY_DROP
        return (span("See ", (72, top, 92, top + self.BODY_HEIGHT), size=self.PROSE_SIZE),
                span("Chapter 5", (92, top, 138, top + self.BODY_HEIGHT), "Helvetica-Oblique", self.PROSE_SIZE),
                span(" for details.", (138, top, 200, top + self.BODY_HEIGHT), size=self.PROSE_SIZE))

    def test_text_below_the_rule_is_outside(self):
        table = TermTableLayout(TABLE_TOP, [self.ROW])
        below = [self._caption(table.bottom()), self._prose(table.bottom())]
        [found] = _scan_book(FakePdfPage(lines=table.lines() + below, shapes=table.shapes()))
        self.assertEqual(_texts(found), [list(TERM_HEADER), list(self.ROW)])


if __name__ == "__main__":
    unittest.main()
