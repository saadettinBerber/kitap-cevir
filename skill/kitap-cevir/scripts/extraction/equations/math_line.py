"""Denklem fontunun satırdaki yeri: satır, denklem fontundaki ve düz metindeki
ardışık parçalarına bölünür; satır içi denklem cümleye komşu kelimeleriyle yerleşir."""
import itertools
from dataclasses import dataclass

from extraction.pdf.geometry import Box
from extraction.text_utils import normalize_spaces

SIMPLE_MAX_SPANS = 3          # bu kadar parça ve tek punto = düz metne çevrilebilir sembol


class SpanRun:
    """Bir satırdaki aynı türden (denklem fontu ya da düz metin) ardışık parçalar.
    Tür iki alt sınıftır; türe göre dallanma yalnız `split` fabrikasındadır (G23)."""

    def __init__(self, spans):
        self._spans = spans

    @staticmethod
    def split(spans, is_math_span):
        return [(MathRun if is_math else ProseRun)(list(run))
                for is_math, run in itertools.groupby(spans, key=is_math_span)]

    @property
    def rect(self):
        return _enclosing(self._spans)

    @property
    def text(self):
        return normalize_spaces("".join(span.text for span in self._spans))

    def is_simple(self):
        sizes = {round(span.size, 1) for span in self._spans}
        return len(self._spans) <= SIMPLE_MAX_SPANS and len(sizes) == 1

    def first_word(self):
        return "".join(self._words()[:1])

    def last_word(self):
        return "".join(self._words()[-1:])

    def _words(self):
        return " ".join(span.text for span in self._spans).split()


class MathRun(SpanRun):
    def is_math(self):
        return True


class ProseRun(SpanRun):
    def is_math(self):
        return False


class MathLine:
    """Bir metin satırı; denklem fontundaki ve düz metindeki ardışık parçalarına bölünür."""

    def __init__(self, spans, is_math_span):
        self._spans = spans
        self._is_math_span = is_math_span

    @property
    def rect(self):
        return _enclosing(self._spans)

    @property
    def text(self):
        return "".join(span.text for span in self._spans).strip()

    def is_display(self):
        """Satırın tamamı denklem fontunda: ayrı satır denklemi."""
        runs = self._runs()
        return len(runs) == 1 and runs[0].is_math()

    def inline_runs(self):
        """Cümle içindeki denklem parçaları, komşu kelimeleriyle; ayrı satır denkleminde yoktur."""
        if self.is_display():
            return []
        runs = self._runs()
        befores = ["", *(run.last_word() for run in runs[:-1])]
        afters = [*(run.first_word() for run in runs[1:]), ""]
        return [InlineRun(run, before, after) for run, before, after in zip(runs, befores, afters) if run.is_math()]

    def _runs(self):
        return SpanRun.split(self._spans, self._is_math_span)


def _enclosing(spans):
    return Box.enclosing(span.box for span in spans)


@dataclass(frozen=True)
class InlineRun:
    """Satır içi denklem parçası ve cümledeki komşu kelimeleri; denklem metne bu ikisinin arasına girer."""
    run: SpanRun
    before: str
    after: str
