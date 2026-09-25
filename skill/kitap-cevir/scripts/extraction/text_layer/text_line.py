"""PDF'teki tek bir taban çizgisinin parçaları (sınırdan gelen Span'lar): kod mu
düz metin mi, kendisine bağlanmış alt/üst simgeler ve çıkarımda kullanılacak
metni. Koordinatlar üst orijinlidir.
"""
from dataclasses import dataclass, fields
from typing import NamedTuple

from extraction.pdf.geometry import Box
from extraction.pdf.model import Span

MONO_CHAR_WIDTH_RATIO = 0.6       # tek aralıklı karakter genişliği / punto


@dataclass(frozen=True)
class LineSpan(Span):
    """Kod fontuyla dizilip dizilmediği bilinen parça."""
    is_code: bool = False

    @classmethod
    def marked(cls, span, is_code):
        return cls(**{field.name: getattr(span, field.name) for field in fields(Span)}, is_code=is_code)


class Piece(NamedTuple):
    """Satır metnine x konumuna göre dizilen parça: span ya da alt/üst simge."""
    left: float
    right: float
    text: str
    is_script: bool = False


def _covering(boxes):
    """Kutuların hepsini kapsayan kutu; Box.union'dan farklı olarak boş kutu da sayılır."""
    return Box(min(box.x0 for box in boxes), min(box.y0 for box in boxes),
               max(box.x1 for box in boxes), max(box.y1 for box in boxes))


class TextLine:
    """Bir satırın span'ları; `scripts` ev sahibi satıra bağlanmış simgelerdir."""

    def __init__(self, spans, is_code):
        self.spans = spans
        self.is_code = is_code
        self.scripts = []
        self.baseline = spans[0].baseline
        self.box = _covering([span.box for span in spans])
        self.text = ""

    @classmethod
    def of_spans(cls, spans):
        return cls(spans, all(span.is_code for span in spans))

    @staticmethod
    def join(spans):
        """Baştaki boşluklar korunur: PDF'te kod girintisi metnin içindedir."""
        return "".join(span.text for span in spans).rstrip()

    @property
    def left(self):
        return self.box.x0

    @property
    def top(self):
        return self.box.y0

    @property
    def right(self):
        return self.box.x1

    @property
    def bottom(self):
        return self.box.y1

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def size(self):
        return self.spans[0].size

    @property
    def char_width(self):
        return self.size * MONO_CHAR_WIDTH_RATIO

    @property
    def raw_text(self):
        return self.join(self.spans)

    def absorb(self, other):
        self.spans = sorted(self.spans + other.spans, key=lambda span: span.box.x0)
        self.scripts += other.scripts
        self.box = _covering([self.box, other.box])

    def render(self):
        self.text = self._spaced_text() if uses_script_layout(self) else self.raw_text

    def _spaced_text(self):
        """Parçaları x konumuna göre boşlukla dizer; alt/üst simgeleri araya koyar."""
        pieces = [Piece(span.box.x0, span.box.x1, span.text) for span in self.spans]
        pieces += [mark.piece() for mark in self.scripts]
        text, cursor, after_script = "", None, False
        for x0, x1, piece, is_script in sorted(pieces):
            threshold = self.char_width if after_script else self.char_width / 2
            if cursor is not None and x0 - cursor > threshold:
                text += " " * max(1, round((x0 - cursor) / self.char_width))
            text += piece
            cursor = x1 if cursor is None else max(cursor, x1)
            after_script = is_script
        return text.rstrip()


def uses_script_layout(line):
    """Kod satırı ve kod formülü içeren satır boşlukla dizilir; gövde metninin
    simgesi satır metnine değil yalnız sözcük düzeltmesine gider."""
    return line.is_code or bool(line.scripts and any(span.is_code for span in line.spans))
