"""PDF'teki tek bir taban çizgisinin parçaları (sınırdan gelen Span'lar): kod mu
düz metin mi, kendisine bağlanmış alt/üst simgeler ve çıkarımda kullanılacak
metni. Koordinatlar üst orijinlidir.
"""
from dataclasses import dataclass, fields

from extraction.pdf.geometry import Box
from extraction.pdf.model import Span

MONO_CHAR_WIDTH_RATIO = 0.6       # tek aralıklı karakter genişliği / punto
SAME_BASELINE_TOLERANCE = 2.0     # bu kadar yakın taban çizgisi = aynı satır
MIN_STANDALONE_CODE_CHARS = 12    # düz metinle aynı satırdaki kod parçası bundan kısaysa satır içi koddur


@dataclass(frozen=True)
class LineSpan(Span):
    """Kod fontuyla dizilip dizilmediği bilinen parça."""
    is_code: bool = False

    @classmethod
    def marked(cls, span, is_code):
        return cls(**{field.name: getattr(span, field.name) for field in fields(Span)}, is_code=is_code)


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

    @classmethod
    def code(cls, spans):
        return cls(spans, True)

    @classmethod
    def prose(cls, spans):
        return cls(spans, False)

    def with_spans(self, spans):
        """Aynı türden (kod ya da düz metin) başka bir satır."""
        return TextLine(spans, self.is_code)

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

    def sort_key(self):
        return round(self.top), self.left

    def is_level_with(self, other):
        return abs(self.baseline - other.baseline) <= SAME_BASELINE_TOLERANCE

    def continues_code(self, other):
        """Aynı taban çizgisindeki iki kod parçası tek kod satırıdır."""
        return self.is_code and other.is_code and self.is_level_with(other)

    def absorb(self, other):
        self.spans = sorted(self.spans + other.spans, key=lambda span: span.box.x0)
        self.scripts += other.scripts
        self.box = _covering([self.box, other.box])

    def split_leading_code(self):
        """'formül , or ...' gibi kod ile başlayıp düz metinle süren satırı ikiye
        ayırır; kod parçası kod satırlarıyla birleşebilsin diye. Tek harflik
        baş parça ('W be the key...') satır içi koddur, bölünmez."""
        if self.is_code or not self.spans[0].is_code:
            return [self]
        split = next(i for i, span in enumerate(self.spans) if not span.is_code)
        if len(self.join(self.spans[:split]).strip()) < MIN_STANDALONE_CODE_CHARS:
            return [self]
        return [TextLine.code(self.spans[:split]), TextLine.prose(self.spans[split:])]

    def is_standalone_code(self):
        return len(self.raw_text.strip()) >= MIN_STANDALONE_CODE_CHARS

    def word_before(self, x0, tolerance):
        """x0 konumunun solunda kalan son sözcük."""
        head = "".join(span.text for span in self.spans if span.box.x1 <= x0 + tolerance).split()
        return head[-1] if head else ""

    def uses_script_layout(self):
        """Kod satırı ve kod formülü içeren satır boşlukla dizilir; gövde metninin
        simgesi satır metnine değil yalnız sözcük düzeltmesine gider."""
        return self.is_code or bool(self.scripts and any(span.is_code for span in self.spans))

    def render(self):
        self.text = self._spaced_text() if self.uses_script_layout() else self.raw_text

    def _spaced_text(self):
        """Parçaları x konumuna göre boşlukla dizer; alt/üst simgeleri araya koyar."""
        pieces = [(span.box.x0, span.box.x1, span.text, False) for span in self.spans]
        pieces += [(mark.x0, mark.x1, mark.text, True) for mark in self.scripts]
        text, cursor, after_script = "", None, False
        for x0, x1, piece, is_script in sorted(pieces):
            threshold = self.char_width if after_script else self.char_width / 2
            if cursor is not None and x0 - cursor > threshold:
                text += " " * max(1, round((x0 - cursor) / self.char_width))
            text += piece
            cursor = x1 if cursor is None else max(cursor, x1)
            after_script = is_script
        return text.rstrip()
