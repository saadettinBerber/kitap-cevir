"""PDF'teki tek bir taban çizgisinin parçaları (sınırdan gelen Span'lar): kod mu
düz metin mi, kendisine bağlanmış alt/üst simgeler ve çıkarımda kullanılacak
metni. Koordinatlar üst orijinlidir.

Satır bir veri yapısıdır (Bl.6 · Data/Object Anti-Symmetry): satır türleri sabit,
satırlar üzerindeki işlemler çoğalıyor; işlemler onları kullanan sınıflardadır
(code_lines, script_marks, layout_scan). Satır değişmez; her adım yeni satır kurar.
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


@dataclass(frozen=True)
class TextLine:
    """Bir satırın span'ları ve onlardan türeyen kutu, taban çizgisi, punto ve ham metin; `scripts` ev
    sahibi satıra bağlanmış simgeler, `text` çıkarımda kullanılacak dizilmiş metindir. Span'ları
    değişen satır `of` ile yeniden kurulur ki türeyen alanlar span'larla tutarlı kalsın."""
    spans: tuple
    is_code: bool
    box: Box
    baseline: float
    size: float
    raw_text: str
    scripts: tuple = ()
    text: str = ""

    @classmethod
    def of(cls, spans, is_code):
        """Baştaki boşluklar ham metinde korunur: PDF'te kod girintisi metnin içindedir."""
        raw_text = "".join(span.text for span in spans).rstrip()
        first = spans[0]
        return cls(tuple(spans), is_code, _covering([span.box for span in spans]), first.baseline, first.size, raw_text)

    @classmethod
    def of_spans(cls, spans):
        """Bütün span'ları kod fontuyla dizilmiş satır kod satırıdır."""
        return TextLine.of(spans, all(span.is_code for span in spans))


def uses_script_layout(line):
    """Kod satırı ve kod formülü içeren satır boşlukla dizilir; gövde metninin
    simgesi satır metnine değil yalnız sözcük düzeltmesine gider."""
    return line.is_code or bool(line.scripts and any(span.is_code for span in line.spans))


def char_width(line):
    """Satırın puntosunda tek aralıklı bir karakterin genişliği; kod girintisi ve boşluklar bununla sayılır."""
    return line.size * MONO_CHAR_WIDTH_RATIO
