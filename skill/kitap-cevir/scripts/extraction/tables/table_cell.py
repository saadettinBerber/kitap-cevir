"""Tablonun tek hücresi: hücreye düşen metin parçalarından satırlar ve üst simgeler."""
import collections
import html
from dataclasses import dataclass

SUPERSCRIPT_RATIO = 0.8      # satırın ana puntosunun altındaki parça = üst simge
WRAP_FILL_RATIO = 0.8        # satırlar sütunu bu oranda dolduruyorsa sarılmış düz metindir


class TableCell:
    """Bir hücreye düşen metin parçaları: satırları ve üst simge işaretleri."""

    def __init__(self, spans, column, main_size):
        self._spans = spans
        self._column = column
        self._main_size = main_size

    def is_multiline(self):
        return len({span.line_y for span in self._spans}) > 1

    def is_wrapped_prose(self):
        """Son satır hariç satırlar sütunu dolduruyorsa bu sarılmış düz metindir;
        satır sonları anlam taşımaz."""
        lines = self._lines()
        if len(lines) < 2:
            return True
        left, right = self._column
        fills = sorted((line.right - left) / (right - left) for line in lines[:-1])
        return fills[len(fills) // 2] >= WRAP_FILL_RATIO

    def unit(self):
        """Satırlar boşlukla birleşir; üst simge varsa birim HTML olur."""
        if not self._marks():
            return {"en": " ".join(line.text for line in self._lines())}
        return self._html_unit(" ")

    def listing_unit(self):
        """Liste niteliğindeki satırın hücresi satır sonlarını korur; sarılmış düz metin yine birleşir."""
        return self.unit() if self.is_wrapped_prose() else self._html_unit("<br>")

    def _html_unit(self, line_separator):
        text = line_separator.join(html.escape(line.text) for line in self._lines())
        sups = "".join(f"<sup>{html.escape(mark)}</sup>" for mark in self._marks())
        return {"en": text + sups, "html": True}

    def _lines(self):
        """Üst simge olmayan parçalar satırlarına, satırlar yukarıdan aşağıya."""
        rows = collections.defaultdict(list)
        for span in self._spans:
            if not self._is_mark(span):
                rows[span.line_y].append(span)
        return [CellLine.of(rows[line_y]) for line_y in sorted(rows)]

    def _marks(self):
        return [span.text for span in self._spans if self._is_mark(span)]

    def _is_mark(self, span):
        return span.size < self._main_size * SUPERSCRIPT_RATIO


@dataclass(frozen=True)
class CellLine:
    """Hücrenin bir satırı: parçaları boşlukla birleşmiş metni ve en sağdaki parçanın sağ kenarı."""
    text: str
    right: float

    @classmethod
    def of(cls, spans):
        return cls(" ".join(span.text for span in spans), max(span.box.x1 for span in spans))
