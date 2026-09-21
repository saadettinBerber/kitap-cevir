"""MathML kökenli denklemleri bulur. E-kitaptan üretilen PDF'lerde denklemler
Type3 glif fontlarıyla dizilir; ODL bu glifleri düşürür, metin katmanı ise
alt/üst simgeleri düzleştirir. Burada denklem bölgeleri PNG olarak kırpılır;
LaTeX üretimi görsel okuyabilen çevirmene bırakılır (references/FORMAT.md).

Denklemleri düz metinle dizen kitaplarda (Type3 fontu yok) tetikleyici
geometridir: kesir çizgisi çizim katmanında dar bir yatay çizgidir ve
çevresindeki satırlar iki boyutlu bir denklem oluşturur (`math_geometry`).

Ayrı satır denklemi -> `math` bloğu; satır içi denklem -> cümlede ⟦eq-N⟧ yer
tutucusu (tek sembol gibi basit olanlar düz metin olarak yerine konur).
Koordinatlar üst orijinlidir.
"""
import os
import re

import fitz

from project import DEFAULT_EXTRACTION
from text_utils import normalize_spaces

CROP_DPI = 220
CROP_PADDING = 3
SIMPLE_MAX_SPANS = 3          # bu kadar parça ve tek punto = düz metne çevrilebilir sembol
LINE_MERGE_RATIO = 0.6        # ardışık denklem satırları arası boşluk / yükseklik
PLACEHOLDER = "⟦{id}⟧"

BAR_MAX_HEIGHT = 2.0          # bundan kalını çizgi değil dolgu dikdörtgenidir
BAR_MIN_WIDTH = 4.0
BAR_GROUP_Y_TOLERANCE = 1.0   # bu kadar yakın y = aynı kural, parçalar hâlinde çizilmiş
BAR_GROUP_MAX_SPAN_RATIO = 0.3  # aynı hizadaki parçalar sütunun bu kadarını kaplıyorsa tablo kenarlığıdır
COLUMN_EDGE_TOLERANCE = 6.0   # sütun kenarından başlayan çizgi tablo ya da alt bilgi kuralıdır
EQUATION_LINE_GAP = 6.0       # denklem satırları arasındaki en büyük dikey boşluk
MAX_GROWTH_PASSES = 4


def _page_lines(page):
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [{"bbox": fitz.Rect(s["bbox"]), "font": s["font"], "size": s["size"],
                      "text": s["text"]} for s in line["spans"] if s["text"].strip()]
            if spans:
                yield spans


def _runs(spans, is_math):
    runs, current, current_math = [], [], None
    for span in spans:
        math = is_math(span)
        if current and math != current_math:
            runs.append((current_math, current))
            current = []
        current.append(span)
        current_math = math
    if current:
        runs.append((current_math, current))
    return runs


def _union(spans):
    rect = fitz.Rect(spans[0]["bbox"])
    for span in spans[1:]:
        rect |= span["bbox"]
    return rect


def _is_simple(spans):
    sizes = {round(s["size"], 1) for s in spans}
    return len(spans) <= SIMPLE_MAX_SPANS and len(sizes) == 1


def _edge_word(spans, take_last):
    words = " ".join(s["text"] for s in spans).split()
    if not words:
        return ""
    return words[-1] if take_last else words[0]


class MathScanner:
    """Bir sayfanın denklemlerini bulur, PNG'lerini image_dir'e yazar."""

    def __init__(self, settings, image_dir):
        settings = {**DEFAULT_EXTRACTION, **(settings or {})}
        self.prefix = settings["math_font_prefix"]
        self.geometry = settings["math_geometry"]
        self.caption = re.compile(settings["equation_caption_pattern"])
        self.image_dir = image_dir
        self.counter = 0

    def _is_math(self, span):
        return span["font"].startswith(self.prefix)

    def _next_id(self):
        self.counter += 1
        return f"eq-{self.counter}"

    def _crop(self, page, rect, item_id):
        os.makedirs(self.image_dir, exist_ok=True)
        clip = fitz.Rect(rect.x0 - CROP_PADDING, rect.y0 - CROP_PADDING,
                         rect.x1 + CROP_PADDING, rect.y1 + CROP_PADDING)
        page.get_pixmap(dpi=CROP_DPI, clip=clip).save(os.path.join(self.image_dir, f"{item_id}.png"))
        return f"{item_id}.png"

    def _equation(self, page, rect):
        item_id = self._next_id()
        return {"id": item_id, "src": self._crop(page, rect, item_id),
                "text": normalize_spaces(page.get_text("text", clip=rect)), "latex": ""}

    def _display_regions(self, page, lines):
        return [self._region_of(page, rect)
                for rect in _merge_adjacent([_union(spans) for spans in lines])]

    def _geometry_regions(self, page, line_rects):
        """Kesir çizgisi olan kitaplarda denklem bölgeleri; Type3 fontu yoktur,
        tetikleyici çizim katmanıdır."""
        if not self.geometry or not line_rects:
            return []
        column = _text_column(line_rects)
        regions = [_grow_region(bar, line_rects) for bar in _fraction_bars(page, column)]
        return [self._region_of(page, rect) for rect in _merge_overlapping(regions)]

    def _is_caption(self, spans):
        """Denklem başlığı ("Equation 3-3. Abstractness") denklemin hemen
        üstündedir ama çevrilecek bir caption'dır, PNG'ye girmemeli."""
        return bool(self.caption.match("".join(s["text"] for s in spans).strip()))

    def _region_of(self, page, rect):
        equation = self._equation(page, rect)
        block = {"type": "math", **{k: equation[k] for k in ("src", "text", "latex")}}
        return {"y0": rect.y0, "y1": rect.y1, "block": block}

    def _inline_item(self, page, runs, index):
        _, spans = runs[index]
        before = _edge_word(runs[index - 1][1], take_last=True) if index > 0 else ""
        after = _edge_word(runs[index + 1][1], take_last=False) if index + 1 < len(runs) else ""
        item = {"bbox": _union(spans), "before": before, "after": after}
        if _is_simple(spans):
            return {**item, "kind": "text", "text": normalize_spaces("".join(s["text"] for s in spans))}
        return {**item, "kind": "image", **self._equation(page, item["bbox"])}

    def scan(self, pdf_path, pdf_page):
        document = fitz.open(pdf_path)
        try:
            page = document[pdf_page - 1]
            display, inline, line_rects = [], [], []
            for spans in _page_lines(page):
                if not self._is_caption(spans):
                    line_rects.append(_union(spans))
                runs = _runs(spans, self._is_math)
                if len(runs) == 1 and runs[0][0]:
                    display.append(spans)
                    continue
                inline += [self._inline_item(page, runs, i) for i, (math, _) in enumerate(runs) if math]
            regions = self._display_regions(page, display) + self._geometry_regions(page, line_rects)
            return {"display": regions, "inline": inline}
        finally:
            document.close()


def _merge_adjacent(rects):
    merged = []
    for rect in sorted(rects, key=lambda r: r.y0):
        if merged and rect.y0 - merged[-1].y1 <= rect.height * LINE_MERGE_RATIO:
            merged[-1] |= rect
        else:
            merged.append(fitz.Rect(rect))
    return merged


def _merge_overlapping(rects):
    """Aynı denklemin iki kesir çizgisi tek bölge olur."""
    merged = []
    for rect in sorted(rects, key=lambda r: r.y0):
        if merged and merged[-1].intersects(rect):
            merged[-1] |= rect
        else:
            merged.append(fitz.Rect(rect))
    return merged


def _vertical_gap(first, second):
    return max(0.0, first.y0 - second.y1, second.y0 - first.y1)


def _text_column(rects):
    """Gövde metninin sol kenarı ve genişliği; kesir çizgisini tablo
    kenarlığından ayırmak için ölçü budur."""
    left = min(rect.x0 for rect in rects)
    return left, max(rect.x1 for rect in rects) - left


def _is_rule(rect):
    return rect.height <= BAR_MAX_HEIGHT and rect.width >= BAR_MIN_WIDTH


def _collinear_groups(bars):
    """Aynı y'deki çizgiler tek kuraldır; tablo kenarlığı sütun boyunca parçalar
    hâlinde çizilir, kesir çizgisi kısa kalır."""
    groups = []
    for bar in sorted(bars, key=lambda rect: rect.y0):
        if groups and abs(bar.y0 - groups[-1][0].y0) <= BAR_GROUP_Y_TOLERANCE:
            groups[-1].append(bar)
        else:
            groups.append([bar])
    return groups


def _group_span(group):
    return max(rect.x1 for rect in group) - min(rect.x0 for rect in group)


def _is_fraction_group(group, left, width):
    """Kesir çizgisi metin sütununun sol kenarından başlamaz ve sütunun küçük
    bir bölümünü kaplar. Tablo kenarlığı ile alt bilgi kuralı sütunu (gerekirse
    parçalar hâlinde) boydan boya çizer; testler parçaya değil hizaya uygulanır,
    yoksa kenardan başlayan parça elenip kalanı kesir sanılır."""
    return (min(rect.x0 for rect in group) > left + COLUMN_EDGE_TOLERANCE
            and _group_span(group) <= width * BAR_GROUP_MAX_SPAN_RATIO)


def _fraction_bars(page, column):
    left, width = column
    rules = [d["rect"] for d in page.get_drawings() if _is_rule(d["rect"])]
    return [bar for group in _collinear_groups(rules)
            if _is_fraction_group(group, left, width) for bar in group]


def _grow_region(bar, rects):
    """Kesir çizgisinden başlayıp pay, payda, denklemin sol yanı ve toplam
    limitlerini toplar; bölge büyüdükçe yeni komşular çıktığı için yinelenir."""
    region = fitz.Rect(bar)
    for _ in range(MAX_GROWTH_PASSES):
        grown = fitz.Rect(region)
        for rect in rects:
            if _vertical_gap(region, rect) <= EQUATION_LINE_GAP:
                grown |= rect
        if grown == region:
            break
        region = grown
    return region


def placeholder(item_id):
    return PLACEHOLDER.format(id=item_id)


def scan_math(pdf_path, pdf_page, settings, image_dir):
    """{"display": [{y0, y1, block}], "inline": [{kind, bbox, before, after, ...}]}"""
    return MathScanner(settings, image_dir).scan(pdf_path, pdf_page)
