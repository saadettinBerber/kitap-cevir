"""Dolgu dikdörtgenlerinden tablo ızgarasını çıkarır: hücre kümeleri (tablolar),
sütunlar, satır bantları ve tablo kapsamı. Koordinatlar üst orijinlidir.
"""
import fitz

MIN_CELL_WIDTH = 15
MIN_CELL_HEIGHT = 8
EDGE_TOLERANCE = 2.0
WIDE_SPAN_RATIO = 1.2        # sütundan geniş parça = tablo dışı (caption, dipnot)
MAX_BAND_GAP_RATIO = 3.0     # iki dolgu arası boşluk / bant yüksekliği: üstü ayrı tablodur
RULE_MAX_HEIGHT = 2.0        # bundan kalını çizgi değil dolgudur
MIN_COLUMNS = 2


class PageFills:
    """Sayfanın dolgu dikdörtgenleri (hücreler, arka planlar) ve dolgusuz yatay çizgileri."""

    def __init__(self, page, text_bottom):
        drawings = page.get_drawings()
        self.rects = self._filled_rects(drawings)
        self.rules = self._horizontal_rules(drawings)
        self.backgrounds = [rect for rect in self.rects if self._is_background(rect)]
        self.cells = [rect for rect in self.rects if rect not in self.backgrounds]
        self.text_bottom = text_bottom

    @staticmethod
    def _filled_rects(drawings):
        rects = [fitz.Rect(d["rect"]) for d in drawings if d.get("fill")]
        return [r for r in rects if r.width >= MIN_CELL_WIDTH and r.height >= MIN_CELL_HEIGHT]

    @staticmethod
    def _horizontal_rules(drawings):
        """Dolgusuz yatay çizgiler: tablonun alt kenarı, alt bilgi kuralı."""
        rects = [fitz.Rect(d["rect"]) for d in drawings if not d.get("fill")]
        return [r for r in rects if r.height <= RULE_MAX_HEIGHT and r.width >= MIN_CELL_WIDTH]

    def _is_background(self, rect):
        return len([r for r in self.rects if r != rect and rect.contains(r)]) >= 2

    def table_groups(self):
        """Aynı arka plandaki hücreler tek tablodur; arka planı olmayanlar sütun
        kenarı paylaşımına göre kümelenir."""
        by_background, loose = {}, []
        for rect in self.cells:
            owner = next((i for i, b in enumerate(self.backgrounds) if b.contains(rect)), None)
            if owner is None:
                loose.append(rect)
            else:
                by_background.setdefault(owner, []).append(rect)
        return list(by_background.values()) + self._connected_groups(loose)

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
        gap = max(0.0, first.y0 - second.y1, second.y0 - first.y1)
        return shares_column and gap <= max(first.height, second.height) * MAX_BAND_GAP_RATIO

    def extent(self, cells):
        """Arka plan varsa tablo odur. Yoksa zebra dolguda ilk satır beyaz
        kalabilir (bir hücre yukarı); alt sınır altındaki ilk yatay çizgidir."""
        union = fitz.Rect(cells[0])
        for rect in cells[1:]:
            union |= rect
        for background in self.backgrounds:
            if background.contains(union):
                return background
        row_height = sorted(r.height for r in cells)[len(cells) // 2]
        return fitz.Rect(union.x0, union.y0 - row_height, union.x1, self._bottom_below(union))

    def _bottom_below(self, union):
        """Tablo, altındaki ilk yatay çizgide biter; çizgi yoksa metin alanının
        sonunda. Sayfa sonuna dek uzatmak tablonun altındaki caption'ı, yan kutuyu
        ve koşu başlığını tabloya katıyordu."""
        below = [rule.y0 for rule in self.rules
                 if rule.y0 > union.y1 and rule.x0 <= union.x1 and rule.x1 >= union.x0]
        return min(below, default=self.text_bottom)


class TableGrid:
    """Bir tablonun sütunları ve satır bantları; metin parçasını hücreye yerleştirir."""

    def __init__(self, columns, bands):
        self.columns = columns
        self.bands = bands

    @classmethod
    def from_cells(cls, cells, page_rects):
        columns = cls._columns(cells)
        bands = cls._bands(page_rects, columns) if len(columns) >= MIN_COLUMNS else []
        return cls(columns, bands)

    def has_columns(self):
        return len(self.columns) >= MIN_COLUMNS

    @classmethod
    def _columns(cls, cells):
        """Tablo sol kenarından sağa doğru sütunları döşer."""
        columns, left, right_edge = [], min(r.x0 for r in cells), max(r.x1 for r in cells)
        while left < right_edge - EDGE_TOLERANCE:
            end = cls._column_end(cells, left)
            if end is None:
                further = [r.x0 for r in cells if r.x0 > left + EDGE_TOLERANCE]
                if not further:
                    break
                left = min(further)
                continue
            columns.append((left, end))
            left = end
        return columns

    @staticmethod
    def _column_end(cells, left):
        """left'ten başlayan hücrelerin en sık görülen sağ kenarı; satır içi kod
        vurguları gibi kenardan içeride başlayan dolgular böylece sütun olmaz."""
        ends = [round(r.x1) for r in cells if abs(r.x0 - left) <= EDGE_TOLERANCE]
        if not ends:
            return None
        return max(set(ends), key=lambda x1: (ends.count(x1), -x1))

    @classmethod
    def _bands(cls, rects, columns):
        """Sütun kenarlarına oturan (tüm tabloyu kaplamayan) dolguların y aralıkları
        satır bantlarıdır; içindeki metin tek satıra aittir."""
        full_width = [(columns[0][0], columns[-1][1])]
        bands = []
        for rect in sorted(rects, key=lambda r: r.y0):
            if not cls._on_edges(rect, columns) or cls._on_edges(rect, full_width):
                continue
            if bands and rect.y0 < bands[-1][1] - EDGE_TOLERANCE:
                bands[-1] = (bands[-1][0], max(bands[-1][1], rect.y1))
            else:
                bands.append((rect.y0, rect.y1))
        return bands

    @staticmethod
    def _on_edges(rect, columns):
        return (any(abs(rect.x0 - left) <= EDGE_TOLERANCE for left, _ in columns)
                and any(abs(rect.x1 - right) <= EDGE_TOLERANCE for _, right in columns))

    def column_of(self, span):
        center = (span["bbox"].x0 + span["bbox"].x1) / 2
        return next((i for i, (left, right) in enumerate(self.columns) if left <= center <= right), None)

    def band_of(self, span):
        center = (span["bbox"].y0 + span["bbox"].y1) / 2
        return next((i for i, (top, bottom) in enumerate(self.bands) if top <= center <= bottom), None)

    def is_table_row(self, row):
        widest = max(right - left for left, right in self.columns) * WIDE_SPAN_RATIO
        return all(s["bbox"].width <= widest and self.column_of(s) is not None for s in row)

    def filled_columns(self, row):
        return len({self.column_of(span) for span in row})

    def in_band(self, row):
        return any(self.band_of(span) is not None for span in row)
