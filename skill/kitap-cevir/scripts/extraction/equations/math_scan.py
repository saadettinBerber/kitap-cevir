"""MathML kökenli denklemleri bulur. E-kitaptan üretilen PDF'lerde denklemler
Type3 glif fontlarıyla dizilir; ODL bu glifleri düşürür, metin katmanı ise
alt/üst simgeleri düzleştirir. Burada denklem bölgeleri PNG olarak kırpılır;
LaTeX üretimi görsel okuyabilen çevirmene bırakılır (references/FORMAT.md).

Denklemleri düz metinle dizen kitaplarda (Type3 fontu yok) tetikleyici
geometridir (`math_geometry`, bkz. math_geometry.py).

Ayrı satır denklemi -> `math` bloğu; satır içi denklem -> cümlede ⟦eq-N⟧ yer
tutucusu (tek sembol gibi basit olanlar düz metin olarak yerine konur).
Koordinatlar üst orijinlidir.
"""
import os
import re

import fitz

from extraction.equations.math_geometry import FractionEquationFinder
from project import DEFAULT_EXTRACTION
from extraction.text_utils import normalize_spaces

CROP_DPI = 220
CROP_PADDING = 3
SIMPLE_MAX_SPANS = 3          # bu kadar parça ve tek punto = düz metne çevrilebilir sembol
LINE_MERGE_RATIO = 0.6        # ardışık denklem satırları arası boşluk / yükseklik
PLACEHOLDER = "⟦{id}⟧"


class SpanRun:
    """Bir satırdaki aynı türden (denklem fontu ya da düz metin) ardışık parçalar."""

    def __init__(self, spans, is_math):
        self.spans = spans
        self.is_math = is_math

    @classmethod
    def split(cls, spans, is_math_span):
        runs = []
        for span in spans:
            is_math = is_math_span(span)
            if runs and runs[-1].is_math == is_math:
                runs[-1].spans.append(span)
            else:
                runs.append(cls([span], is_math))
        return runs

    @staticmethod
    def union(spans):
        rect = fitz.Rect(spans[0]["bbox"])
        for span in spans[1:]:
            rect |= span["bbox"]
        return rect

    @property
    def rect(self):
        return self.union(self.spans)

    @property
    def text(self):
        return normalize_spaces("".join(span["text"] for span in self.spans))

    def is_simple(self):
        sizes = {round(span["size"], 1) for span in self.spans}
        return len(self.spans) <= SIMPLE_MAX_SPANS and len(sizes) == 1

    def words(self):
        return " ".join(span["text"] for span in self.spans).split()


class EquationCropper:
    """Denklem bölgelerini PNG olarak kırpar; kimlikler sayfa içinde sırayla eq-N."""

    def __init__(self, image_dir):
        self.image_dir = image_dir
        self.counter = 0

    def equation(self, page, rect):
        self.counter += 1
        item_id = f"eq-{self.counter}"
        return {"id": item_id, "src": self._crop(page, rect, item_id),
                "text": normalize_spaces(page.get_text("text", clip=rect)), "latex": ""}

    def display_region(self, page, rect):
        equation = self.equation(page, rect)
        block = {"type": "math", **{key: equation[key] for key in ("src", "text", "latex")}}
        return {"y0": rect.y0, "y1": rect.y1, "block": block}

    def _crop(self, page, rect, item_id):
        os.makedirs(self.image_dir, exist_ok=True)
        clip = fitz.Rect(rect.x0 - CROP_PADDING, rect.y0 - CROP_PADDING,
                         rect.x1 + CROP_PADDING, rect.y1 + CROP_PADDING)
        page.get_pixmap(dpi=CROP_DPI, clip=clip).save(os.path.join(self.image_dir, f"{item_id}.png"))
        return f"{item_id}.png"


class MathScanner:
    """Bir sayfanın denklemlerini bulur, PNG'lerini image_dir'e yazar."""

    def __init__(self, settings, image_dir):
        settings = {**DEFAULT_EXTRACTION, **(settings or {})}
        self.prefix = settings["math_font_prefix"]
        self.uses_geometry = settings["math_geometry"]
        self.caption = re.compile(settings["equation_caption_pattern"])
        self.cropper = EquationCropper(image_dir)

    def scan(self, pdf_path, pdf_page):
        """{"display": [{y0, y1, block}], "inline": [{kind, bbox, before, after, ...}]}"""
        with fitz.open(pdf_path) as document:
            return self._scan_page(document[pdf_page - 1])

    def _scan_page(self, page):
        display, inline, line_rects = [], [], []
        for spans in self._lines(page):
            if not self._is_caption(spans):
                line_rects.append(SpanRun.union(spans))
            runs = SpanRun.split(spans, self._is_math)
            if len(runs) == 1 and runs[0].is_math:
                display.append(spans)
            else:
                inline += self._inline_items(page, runs)
        regions = self._display_regions(page, display) + self._geometry_regions(page, line_rects)
        return {"display": regions, "inline": inline}

    @staticmethod
    def _lines(page):
        lines = (line for block in page.get_text("dict")["blocks"] for line in block.get("lines", []))
        for line in lines:
            spans = [{"bbox": fitz.Rect(s["bbox"]), "font": s["font"], "size": s["size"],
                      "text": s["text"]} for s in line["spans"] if s["text"].strip()]
            if spans:
                yield spans

    def _is_math(self, span):
        return span["font"].startswith(self.prefix)

    def _is_caption(self, spans):
        """Denklem başlığı ("Equation 3-3. Abstractness") denklemin hemen
        üstündedir ama çevrilecek bir caption'dır, PNG'ye girmemeli."""
        return bool(self.caption.match("".join(s["text"] for s in spans).strip()))

    def _inline_items(self, page, runs):
        return [self._inline_item(page, runs, index) for index, run in enumerate(runs) if run.is_math]

    def _inline_item(self, page, runs, index):
        before = runs[index - 1].words()[-1:] if index > 0 else []
        after = runs[index + 1].words()[:1] if index + 1 < len(runs) else []
        run = runs[index]
        item = {"bbox": run.rect, "before": "".join(before), "after": "".join(after)}
        if run.is_simple():
            return {**item, "kind": "text", "text": run.text}
        return {**item, "kind": "image", **self.cropper.equation(page, item["bbox"])}

    def _display_regions(self, page, lines):
        rects = self._merge_adjacent([SpanRun.union(spans) for spans in lines])
        return [self.cropper.display_region(page, rect) for rect in rects]

    def _geometry_regions(self, page, line_rects):
        if not self.uses_geometry:
            return []
        rects = FractionEquationFinder(line_rects).regions(page)
        return [self.cropper.display_region(page, rect) for rect in rects]

    @staticmethod
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

