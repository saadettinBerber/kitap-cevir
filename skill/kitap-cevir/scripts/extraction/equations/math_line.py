"""Denklem fontunun satırdaki yeri: satır, denklem fontundaki ve düz metindeki
ardışık parçalarına bölünür; satır içi denklem cümleye komşu kelimeleriyle yerleşir."""
from dataclasses import dataclass

from extraction.pdf.geometry import Box
from extraction.text_utils import normalize_spaces

SIMPLE_MAX_SPANS = 3          # bu kadar parça ve tek punto = düz metne çevrilebilir sembol


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
