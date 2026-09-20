"""MathML kökenli denklemleri bulur. E-kitaptan üretilen PDF'lerde denklemler
Type3 glif fontlarıyla dizilir; ODL bu glifleri düşürür, metin katmanı ise
alt/üst simgeleri düzleştirir. Burada denklem bölgeleri PNG olarak kırpılır;
LaTeX üretimi görsel okuyabilen çevirmene bırakılır (references/FORMAT.md).

Ayrı satır denklemi -> `math` bloğu; satır içi denklem -> cümlede ⟦eq-N⟧ yer
tutucusu (tek sembol gibi basit olanlar düz metin olarak yerine konur).
Koordinatlar üst orijinlidir.
"""
import os

import fitz

from text_utils import normalize_spaces

CROP_DPI = 220
CROP_PADDING = 3
SIMPLE_MAX_SPANS = 3          # bu kadar parça ve tek punto = düz metne çevrilebilir sembol
LINE_MERGE_RATIO = 0.6        # ardışık denklem satırları arası boşluk / yükseklik
PLACEHOLDER = "⟦{id}⟧"


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
        self.prefix = settings["math_font_prefix"]
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
        regions = []
        for rect in _merge_adjacent([_union(spans) for spans in lines]):
            equation = self._equation(page, rect)
            block = {"type": "math", **{k: equation[k] for k in ("src", "text", "latex")}}
            regions.append({"y0": rect.y0, "y1": rect.y1, "block": block})
        return regions

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
            display, inline = [], []
            for spans in _page_lines(page):
                runs = _runs(spans, self._is_math)
                if len(runs) == 1 and runs[0][0]:
                    display.append(spans)
                    continue
                inline += [self._inline_item(page, runs, i) for i, (math, _) in enumerate(runs) if math]
            return {"display": self._display_regions(page, display), "inline": inline}
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


def placeholder(item_id):
    return PLACEHOLDER.format(id=item_id)


def scan_math(pdf_path, pdf_page, settings, image_dir):
    """{"display": [{y0, y1, block}], "inline": [{kind, bbox, before, after, ...}]}"""
    return MathScanner(settings, image_dir).scan(pdf_path, pdf_page)
