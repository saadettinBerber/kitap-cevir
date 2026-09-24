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
from dataclasses import dataclass

from extraction.equations.math_geometry import FractionEquationFinder
from extraction.pdf.geometry import Box
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
        return Box.enclosing(span.box for span in spans)

    @property
    def rect(self):
        return self.union(self.spans)

    @property
    def text(self):
        return normalize_spaces("".join(span.text for span in self.spans))

    def is_simple(self):
        sizes = {round(span.size, 1) for span in self.spans}
        return len(self.spans) <= SIMPLE_MAX_SPANS and len(sizes) == 1

    def words(self):
        return " ".join(span.text for span in self.spans).split()


class MathLine:
    """Bir metin satırı; denklem fontundaki ve düz metindeki ardışık parçalarına bölünmüş."""

    def __init__(self, spans, is_math_span):
        self.spans = spans
        self.runs = SpanRun.split(spans, is_math_span)

    @property
    def rect(self):
        return SpanRun.union(self.spans)

    @property
    def text(self):
        return "".join(span.text for span in self.spans).strip()

    def is_display(self):
        """Satırın tamamı denklem fontunda: ayrı satır denklemi."""
        return len(self.runs) == 1 and self.runs[0].is_math

    def inline_runs(self):
        """Cümle içindeki denklem parçaları, komşu kelimeleriyle; ayrı satır denkleminde yoktur."""
        if self.is_display():
            return []
        return [InlineRun(run, self._word_before(index), self._word_after(index))
                for index, run in enumerate(self.runs) if run.is_math]

    def _word_before(self, index):
        return "".join(self.runs[index - 1].words()[-1:]) if index > 0 else ""

    def _word_after(self, index):
        return "".join(self.runs[index + 1].words()[:1]) if index + 1 < len(self.runs) else ""


@dataclass(frozen=True)
class InlineRun:
    """Satır içi denklem parçası ve cümledeki komşu kelimeleri; denklem metne bu ikisinin arasına girer."""
    run: SpanRun
    before: str
    after: str


class EquationCropper:
    """Bir sayfanın denklem bölgelerini PNG olarak kırpar; kimlikler sayfa içinde sırayla eq-N."""

    def __init__(self, page, image_dir):
        self.page = page
        self.image_dir = image_dir
        self.counter = 0

    def equation(self, rect):
        self.counter += 1
        item_id = f"eq-{self.counter}"
        return {"id": item_id, "src": self._crop(rect, item_id),
                "text": normalize_spaces(self.page.text_in(rect)), "latex": ""}

    def display_region(self, rect):
        equation = self.equation(rect)
        block = {"type": "math", **{key: equation[key] for key in ("src", "text", "latex")}}
        return {"y0": rect.y0, "y1": rect.y1, "block": block}

    def _crop(self, rect, item_id):
        os.makedirs(self.image_dir, exist_ok=True)
        with open(os.path.join(self.image_dir, f"{item_id}.png"), "wb") as png:
            png.write(self.page.png(rect.expanded(CROP_PADDING), CROP_DPI))
        return f"{item_id}.png"


class MathScanner:
    """Bir sayfanın denklemlerini bulur, PNG'lerini image_dir'e yazar."""

    def __init__(self, settings, page, image_dir):
        self.prefix = settings["math_font_prefix"]
        self.uses_geometry = settings["math_geometry"]
        self.caption = re.compile(settings["equation_caption_pattern"])
        self.page = page
        self.cropper = EquationCropper(page, image_dir)

    def scan(self):
        """{"display": [{y0, y1, block}], "inline": [{kind, bbox, before, after, ...}]}.
        Ayrı satır denkleminin bandına düşen parça onun bir parçasıdır, satır içi sayılmaz."""
        lines = [MathLine(spans, self._is_math) for spans in self.page.text_lines()]
        rects = self._display_rects(lines) + self._geometry_rects(lines)
        inline = [self._inline_item(inline_run) for line in lines for inline_run in line.inline_runs()
                  if not _in_band(inline_run.run.rect, rects)]
        return {"display": [self.cropper.display_region(rect) for rect in rects], "inline": inline}

    def _is_math(self, span):
        """Boş önek "bu kitapta denklem fontu yok" demektir; startswith("") her fontla eşleşirdi."""
        return bool(self.prefix) and span.font.startswith(self.prefix)

    def _is_caption(self, line):
        """Denklem başlığı ("Equation 3-3. Abstractness") denklemin hemen
        üstündedir ama çevrilecek bir caption'dır, PNG'ye girmemeli."""
        return bool(self.caption.match(line.text))

    def _inline_item(self, inline_run):
        run = inline_run.run
        item = {"bbox": run.rect, "before": inline_run.before, "after": inline_run.after}
        if run.is_simple():
            return {**item, "kind": "text", "text": run.text}
        return {**item, "kind": "image", **self.cropper.equation(run.rect)}

    def _display_rects(self, lines):
        return self._merge_adjacent([line.rect for line in lines if line.is_display()])

    def _geometry_rects(self, lines):
        if not self.uses_geometry:
            return []
        line_rects = [line.rect for line in lines if not self._is_caption(line)]
        return FractionEquationFinder(line_rects).regions(self.page.drawings())

    @staticmethod
    def _merge_adjacent(rects):
        merged = []
        for rect in sorted(rects, key=lambda r: r.y0):
            if merged and rect.y0 - merged[-1].y1 <= rect.height * LINE_MERGE_RATIO:
                merged[-1] = merged[-1].union(rect)
            else:
                merged.append(rect)
        return merged


def _in_band(rect, bands):
    """Kutunun ortası bantlardan birinin dikey aralığında mı?"""
    return any(band.y0 <= rect.center_y <= band.y1 for band in bands)


def placeholder(item_id):
    return PLACEHOLDER.format(id=item_id)

