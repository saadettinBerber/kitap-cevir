"""Denklemleri düz metinle dizen kitaplarda denklem bölgelerini geometriden bulur.

Type3 fontu olmayan kitaplarda tetikleyici çizim katmanıdır: kesir çizgisi dar
bir yatay çizgidir ve çevresindeki satırlar (pay, payda, denklemin sol yanı,
toplam limitleri) iki boyutlu tek bir denklem oluşturur. Tablo kenarlığı ve
alt bilgi kuralı da yatay çizgidir; ayrım metin sütununa göre yapılır.
Koordinatlar üst orijinlidir.
"""
from extraction.pdf.geometry import Box

BAR_MAX_HEIGHT = 2.0          # bundan kalını çizgi değil dolgu dikdörtgenidir
BAR_MIN_WIDTH = 4.0
BAR_GROUP_Y_TOLERANCE = 1.0   # bu kadar yakın y = aynı kural, parçalar hâlinde çizilmiş
BAR_GROUP_MAX_SPAN_RATIO = 0.3  # aynı hizadaki parçalar sütunun bu kadarını kaplıyorsa tablo kenarlığıdır
COLUMN_EDGE_TOLERANCE = 6.0   # sütun kenarından başlayan çizgi tablo ya da alt bilgi kuralıdır
EQUATION_LINE_GAP = 6.0       # denklem satırları arasındaki en büyük dikey boşluk
MAX_GROWTH_PASSES = 4


class FractionEquationFinder:
    """Bir sayfanın metin satırlarından ve çizimlerinden denklem bölgelerini çıkarır."""

    def __init__(self, line_rects):
        self._line_rects = line_rects

    def regions(self, drawings):
        if not self._line_rects:
            return []
        column = TextColumn(self._line_rects)
        bars = [bar for rule in Rule.from_drawings(drawings) if column.holds_fraction(rule) for bar in rule]
        return self._merge_overlapping([self._grow(bar) for bar in bars])

    def _grow(self, bar):
        """Kesir çizgisinden başlayıp pay, payda, denklemin sol yanı ve toplam
        limitlerini toplar; bölge büyüdükçe yeni komşular çıktığı için yinelenir."""
        region = bar
        for _ in range(MAX_GROWTH_PASSES):
            grown = self._with_neighbours(region)
            if grown == region:
                break
            region = grown
        return region

    def _with_neighbours(self, region):
        near = [rect for rect in self._line_rects if region.vertical_gap(rect) <= EQUATION_LINE_GAP]
        return Box.enclosing([region, *near])

    @staticmethod
    def _merge_overlapping(rects):
        """Aynı denklemin iki kesir çizgisi tek bölge olur."""
        merged = []
        for rect in sorted(rects, key=lambda r: r.y0):
            if merged and merged[-1].intersects(rect):
                merged[-1] = merged[-1].union(rect)
            else:
                merged.append(rect)
        return merged


class TextColumn:
    """Gövde metninin sol kenarı ve genişliği; kesir çizgisini tablo
    kenarlığından ayırmanın ölçüsü."""

    def __init__(self, line_rects):
        self._left = min(rect.x0 for rect in line_rects)
        self._width = max(rect.x1 for rect in line_rects) - self._left

    def holds_fraction(self, rule):
        """Kesir çizgisi sütunun sol kenarından başlamaz ve sütunun küçük bir
        bölümünü kaplar. Tablo kenarlığı ile alt bilgi kuralı sütunu (gerekirse
        parçalar hâlinde) boydan boya çizer; ölçü parçaya değil kurala uygulanır,
        yoksa kenardan başlayan parça elenip kalanı kesir sanılır."""
        return (rule.left > self._left + COLUMN_EDGE_TOLERANCE
                and rule.span <= self._width * BAR_GROUP_MAX_SPAN_RATIO)


class Rule:
    """Aynı y'deki yatay çizgi parçaları: tek bir kural. Tablo kenarlığı sütun
    boyunca parçalar hâlinde çizilir, kesir çizgisi kısa kalır."""

    def __init__(self, bars):
        self._bars = bars

    @classmethod
    def from_drawings(cls, drawings):
        """Çizgiler yukarıdan aşağı gezilir: bir öncekiyle aynı hizadaki çizgi onun kuralına katılır."""
        rules = []
        for bar in _bars_top_down(drawings):
            if rules and rules[-1].is_level_with(bar):
                rules[-1] = rules[-1].with_bar(bar)
            else:
                rules.append(cls([bar]))
        return rules

    def __iter__(self):
        return iter(self._bars)

    def with_bar(self, bar):
        return Rule([*self._bars, bar])

    def is_level_with(self, bar):
        return abs(bar.y0 - self._bars[0].y0) <= BAR_GROUP_Y_TOLERANCE

    @property
    def left(self):
        return min(bar.x0 for bar in self._bars)

    @property
    def span(self):
        return max(bar.x1 for bar in self._bars) - self.left


def _bars_top_down(drawings):
    return sorted((drawing.box for drawing in drawings if _is_bar(drawing.box)), key=lambda rect: rect.y0)


def _is_bar(rect):
    return rect.height <= BAR_MAX_HEIGHT and rect.width >= BAR_MIN_WIDTH
