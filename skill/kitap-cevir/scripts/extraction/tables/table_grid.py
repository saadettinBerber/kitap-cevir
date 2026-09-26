"""Dolgu dikdörtgenlerinden tablo ızgarasını çıkarır: hücre kümeleri (tablolar),
sütunlar, satır bantları ve tablo kapsamı. Koordinatlar üst orijinlidir.
"""
import collections

from extraction.pdf.geometry import Box
from extraction.tables.table_cell import CellText, TableCell

MIN_CELL_WIDTH = 15
MIN_CELL_HEIGHT = 8
EDGE_TOLERANCE = 2.0
WIDE_SPAN_RATIO = 1.2        # sütundan geniş parça = tablo dışı (caption, dipnot)
MAX_BAND_GAP_RATIO = 3.0     # iki dolgu arası boşluk / bant yüksekliği: üstü ayrı tablodur
RULE_MAX_HEIGHT = 2.0        # bundan kalını çizgi değil dolgudur
MIN_COLUMNS = 2
MIN_BACKGROUND_CELLS = 2     # arka plan en az bu kadar dolguyu içine alır


class PageFills:
    """Sayfanın dolgu dikdörtgenleri (hücreler, arka planlar) ve dolgusuz yatay çizgileri."""

    def __init__(self, drawings, text_bottom):
        self._rects = self._filled_rects(drawings)
        self._rules = self._horizontal_rules(drawings)
        self._text_bottom = text_bottom

    @staticmethod
    def _filled_rects(drawings):
        rects = [drawing.box for drawing in drawings if drawing.is_filled]
        return [r for r in rects if r.width >= MIN_CELL_WIDTH and r.height >= MIN_CELL_HEIGHT]

    @staticmethod
    def _horizontal_rules(drawings):
        """Dolgusuz yatay çizgiler: tablonun alt kenarı, alt bilgi kuralı."""
        rects = [drawing.box for drawing in drawings if not drawing.is_filled]
        return [r for r in rects if r.height <= RULE_MAX_HEIGHT and r.width >= MIN_CELL_WIDTH]

    def is_empty(self):
        return not self._rects

    def row_bands(self, columns):
        """Tablonun satır bantları; bantlar yalnız tablonun hücrelerinden değil sayfanın bütün
        dolgularından çıkar."""
        return RowBands.of_fills(columns.band_fills(self._rects))

    def table_groups(self):
        """Aynı arka plandaki hücreler tek tablodur; arka planı olmayanlar sütun
        kenarı paylaşımına göre kümelenir."""
        backgrounds = self._backgrounds()
        cells = [rect for rect in self._rects if rect not in backgrounds]
        owned = [rect for rect in cells if _is_on_any(rect, backgrounds)]
        loose = [rect for rect in cells if not _is_on_any(rect, backgrounds)]
        return _grouped_by_background(owned, backgrounds) + self._connected_groups(loose)

    def _backgrounds(self):
        """Başka dolguları içine alan dolgular: tablonun arka planı."""
        return [rect for rect in self._rects if self._is_background(rect)]

    def _is_background(self, rect):
        return len([r for r in self._rects if r != rect and rect.contains(r)]) >= MIN_BACKGROUND_CELLS

    @classmethod
    def _connected_groups(cls, cells):
        groups = []
        for rect in cells:
            linked = [g for g in groups if any(cls._same_grid(rect, other) for other in g)]
            merged = [rect] + [r for g in linked for r in g]
            groups = [g for g in groups if g not in linked] + [merged]
        return groups

    @staticmethod
    def _same_grid(first, second):
        """Aynı sütunda ya da yan yana duran hücreler aynı ızgaraya aittir. Aynı
        sayfadaki iki ayrı tablo çoğu zaman aynı sol kenardan başlar; onları
        ayıran aradaki dikey boşluktur. Zebra bantları zincirleme bağlandığı için
        uzun bir tablo yine tek grup kalır."""
        shares_column = any(abs(a - b) <= EDGE_TOLERANCE
                            for a in (first.x0, first.x1) for b in (second.x0, second.x1))
        return shares_column and first.vertical_gap(second) <= max(first.height, second.height) * MAX_BAND_GAP_RATIO

    def extent(self, cells):
        """Arka plan varsa tablo odur. Yoksa hücrelerin üst kenarından altındaki ilk yatay çizgiye uzanır."""
        union = Box.enclosing(cells)
        for background in self._backgrounds():
            if background.contains(union):
                return background
        return Box(union.x0, union.y0, union.x1, self._bottom_below(union))

    def _bottom_below(self, union):
        """Tablo, altındaki ilk yatay çizgide biter; çizgi yoksa metin alanının
        sonunda. Sayfa sonuna dek uzatmak tablonun altındaki caption'ı, yan kutuyu
        ve koşu başlığını tabloya katıyordu."""
        below = [rule.y0 for rule in self._rules
                 if rule.y0 > union.y1 and rule.x0 <= union.x1 and rule.x1 >= union.x0]
        return min(below, default=self._text_bottom)


def _is_on_any(rect, backgrounds):
    return any(background.contains(rect) for background in backgrounds)


def _grouped_by_background(cells, backgrounds):
    """Her hücre onu içine alan ilk arka planın kümesindedir; kümeler ilk hücrelerinin sırasıyla gelir."""
    groups = collections.defaultdict(list)
    for rect in cells:
        groups[next(background for background in backgrounds if background.contains(rect))].append(rect)
    return list(groups.values())


class GridColumns:
    """Bir tablonun sütunları; metin parçasını sütununa, satırın parçalarını hücrelerine yerleştirir."""

    def __init__(self, columns):
        self._columns = columns

    @classmethod
    def of_cells(cls, cells):
        return cls(ColumnTiling(cells).columns())

    def is_tabular(self):
        return len(self._columns) >= MIN_COLUMNS

    def band_fills(self, rects):
        """Sütun kenarlarına oturan ama tüm tabloyu kaplamayan dolgular, yukarıdan aşağı."""
        full_width = [(self._columns[0][0], self._columns[-1][1])]
        return [rect for rect in sorted(rects, key=lambda r: r.y0)
                if _on_edges(rect, self._columns) and not _on_edges(rect, full_width)]

    def column_of(self, span):
        """Parçanın ortasının düştüğü sütun; iki sütunun ortak kenarındaki orta soldakindedir."""
        holding = self._columns_holding(span)
        if not holding:
            raise ValueError(f"parçanın ortası hiçbir sütuna düşmüyor: {span.text!r}")
        return holding[0]

    def is_table_row(self, row):
        widest = max(right - left for left, right in self._columns) * WIDE_SPAN_RATIO
        return all(s.box.width <= widest and self._columns_holding(s) for s in row)

    def _columns_holding(self, span):
        center = span.box.center_x
        return [index for index, (left, right) in enumerate(self._columns) if left <= center <= right]

    def cells_of(self, row, main_size):
        """Satırın parçaları sütunlarının hücrelerine dağılmış olarak; her parça bir
        sütuna düşmelidir."""
        columns = [self.column_of(span) for span in row]
        return [TableCell(CellText([span for span, column in zip(row, columns) if column == index], main_size), bounds)
                for index, bounds in enumerate(self._columns)]

    def filled_columns(self, row):
        return len({self.column_of(span) for span in row})


def _on_edges(rect, columns):
    return (any(abs(rect.x0 - left) <= EDGE_TOLERANCE for left, _ in columns)
            and any(abs(rect.x1 - right) <= EDGE_TOLERANCE for _, right in columns))


class RowBands:
    """Tablonun satır bantları (y aralıkları); bandın içindeki metin tek satıra aittir."""

    def __init__(self, bands):
        self._bands = bands

    @classmethod
    def of_fills(cls, fills):
        """fills yukarıdan aşağı sıralı; üsttekine tolerans kadar binen dolgu yeni banttır,
        daha çok binen onu uzatır."""
        bands = []
        for rect in fills:
            if bands and rect.y0 < bands[-1][1] - EDGE_TOLERANCE:
                bands[-1] = (bands[-1][0], max(bands[-1][1], rect.y1))
            else:
                bands.append((rect.y0, rect.y1))
        return cls(bands)

    def in_band(self, row):
        return any(self.is_in_band(span) for span in row)

    def is_in_band(self, span):
        return bool(self._bands_holding(span))

    def same_band(self, span, other):
        """İki parçanın ortası aynı bantta mı? İki bandın ortak kenarındaki orta üstteki banttadır."""
        first = self._bands_holding(span)[:1]
        return bool(first) and first == self._bands_holding(other)[:1]

    def _bands_holding(self, span):
        center = span.box.center_y
        return [index for index, (top, bottom) in enumerate(self._bands) if top <= center <= bottom]


class ColumnTiling:
    """Hücrelerden sütun döşemesi: tablonun sol kenarından sağa, her sütun kendi sol kenarından
    başlayan hücrelerin en sık görülen sağ kenarına uzanır."""

    def __init__(self, cells):
        self._cells = cells
        self._right_edge = max(r.x1 for r in cells)

    def columns(self):
        columns, left = [], min(r.x0 for r in self._cells)
        while left < self._right_edge - EDGE_TOLERANCE:
            column = self._column_from(left)
            columns += column
            left = column[0][1] if column else self._next_start(left)
        return columns

    def _column_from(self, left):
        """left'ten başlayan sütun; hiçbir hücre left'ten başlamıyorsa boş liste. Satır içi kod
        vurguları gibi kenardan içeride başlayan dolgular böylece sütun olmaz. Eşit sıklıkta
        sağ kenarlardan yakın olanı seçilir."""
        ends = [round(r.x1) for r in self._cells if abs(r.x0 - left) <= EDGE_TOLERANCE]
        return [(left, max(set(ends), key=lambda x1: (ends.count(x1), -x1)))] if ends else []

    def _next_start(self, left):
        return min((r.x0 for r in self._cells if r.x0 > left + EDGE_TOLERANCE), default=self._right_edge)
