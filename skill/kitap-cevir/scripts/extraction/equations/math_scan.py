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
import itertools
import os
import re

from extraction.equations.math_geometry import FractionEquationFinder
from extraction.equations.math_line import MathLine
from extraction.text_utils import normalize_spaces

CROP_DPI = 220
CROP_PADDING = 3
LINE_MERGE_RATIO = 0.6        # ardışık denklem satırları arası boşluk / yükseklik
PLACEHOLDER = "⟦{id}⟧"


class MathScanner:
    """Kitabın denklem kurallarıyla (font öneki, kesir geometrisi, başlık kalıbı) bir sayfanın
    denklemlerini bulur; kırpıp numaralamak EquationCropper'ın işidir."""

    def __init__(self, settings):
        self._prefix = settings["math_font_prefix"]
        self._uses_geometry = settings["math_geometry"]
        self._caption = re.compile(settings["equation_caption_pattern"])

    def scan(self, page, image_dir):
        """{"display": [{y0, y1, block}], "inline": [{kind, bbox, before, after, ...}]}; PNG'ler image_dir'e yazılır.
        Ayrı satır denkleminin bandına düşen parça onun bir parçasıdır, satır içi sayılmaz."""
        lines = [MathLine(spans, self._is_math) for spans in page.text_lines()]
        rects = self._display_rects(lines) + self._geometry_rects(lines, page)
        inline_runs = [inline_run for line in lines for inline_run in line.inline_runs()
                       if not _in_band(inline_run.run.rect, rects)]
        return EquationCropper(page, image_dir).cropped(inline_runs, rects)

    def _is_math(self, span):
        """Boş önek "bu kitapta denklem fontu yok" demektir; startswith("") her fontla eşleşirdi."""
        return bool(self._prefix) and span.font.startswith(self._prefix)

    def _display_rects(self, lines):
        return self._merge_adjacent([line.rect for line in lines if line.is_display()])

    @staticmethod
    def _merge_adjacent(rects):
        merged = []
        for rect in sorted(rects, key=lambda r: r.y0):
            if merged and rect.y0 - merged[-1].y1 <= rect.height * LINE_MERGE_RATIO:
                merged[-1] = merged[-1].union(rect)
            else:
                merged.append(rect)
        return merged

    def _geometry_rects(self, lines, page):
        if not self._uses_geometry:
            return []
        line_rects = [line.rect for line in lines if not self._is_caption(line)]
        return FractionEquationFinder(line_rects).regions(page.drawings())

    def _is_caption(self, line):
        """Denklem başlığı ("Equation 3-3. Abstractness") denklemin hemen
        üstündedir ama çevrilecek bir caption'dır, PNG'ye girmemeli."""
        return bool(self._caption.match(line.text))


def _in_band(rect, bands):
    """Kutunun ortası bantlardan birinin dikey aralığında mı?"""
    return any(band.y0 <= rect.center_y <= band.y1 for band in bands)


class EquationCropper:
    """Bir sayfanın denklemlerini numaralayıp PNG olarak image_dir'e kırpar. Numara (eq-N)
    sayfadaki sıradan hesaplanır, kırpıcı sayaç tutmaz."""

    def __init__(self, page, image_dir):
        self._page = page
        self._image_dir = image_dir

    def cropped(self, inline_runs, display_rects):
        """{"display": [...], "inline": [...]}; ayrı satır denklemleri satır içi görsellerden sonra numaralanır."""
        inline = self._inline_items(inline_runs)
        return {"display": self._display_regions(display_rects, inline), "inline": inline}

    def _inline_items(self, inline_runs):
        """Numaralar 1'den başlar: görsel olan parçanın numarası, kendisine kadarki görsel sayısıdır."""
        image_counts = itertools.accumulate(int(not inline_run.run.is_simple()) for inline_run in inline_runs)
        return [self._inline_item(inline_run, count) for inline_run, count in zip(inline_runs, image_counts)]

    def _inline_item(self, inline_run, number):
        run = inline_run.run
        item = {"bbox": run.rect, "before": inline_run.before, "after": inline_run.after}
        if run.is_simple():
            return {**item, "kind": "text", "text": run.text}
        return {**item, "kind": "image", **self._equation(run.rect, number)}

    def _display_regions(self, rects, inline):
        first = 1 + sum(item["kind"] == "image" for item in inline)
        return [self._display_region(rect, number) for number, rect in enumerate(rects, first)]

    def _display_region(self, rect, number):
        equation = self._equation(rect, number)
        block = {"type": "math", **{key: equation[key] for key in ("src", "text", "latex")}}
        return {"y0": rect.y0, "y1": rect.y1, "block": block}

    def _equation(self, rect, number):
        item_id = f"eq-{number}"
        return {"id": item_id, "src": self._crop(rect, item_id),
                "text": normalize_spaces(self._page.text_in(rect)), "latex": ""}

    def _crop(self, rect, item_id):
        os.makedirs(self._image_dir, exist_ok=True)
        with open(os.path.join(self._image_dir, f"{item_id}.png"), "wb") as png:
            png.write(self._page.png(rect.expanded(CROP_PADDING), CROP_DPI))
        return f"{item_id}.png"


def placeholder(item_id):
    return PLACEHOLDER.format(id=item_id)
