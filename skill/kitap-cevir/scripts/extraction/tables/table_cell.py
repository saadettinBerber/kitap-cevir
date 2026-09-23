"""Tablonun tek hücresi: hücreye düşen metin parçalarından satırlar ve üst simgeler."""
import html

SUPERSCRIPT_RATIO = 0.8      # satırın ana puntosunun altındaki parça = üst simge
WRAP_FILL_RATIO = 0.8        # satırlar sütunu bu oranda dolduruyorsa sarılmış düz metindir


class TableCell:
    """Bir hücreye düşen metin parçaları: satırları ve üst simge işaretleri."""

    def __init__(self, spans, column, main_size):
        self.spans = spans
        self.column = column
        self.lines, self.marks = self._lines_and_marks(main_size)

    def _lines_and_marks(self, main_size):
        lines, marks = {}, []
        for span in self.spans:
            if span["size"] < main_size * SUPERSCRIPT_RATIO:
                marks.append(span["text"])
            else:
                line = lines.setdefault(span["line_y"], {"words": [], "x1": 0})
                line["words"].append(span["text"])
                line["x1"] = max(line["x1"], span["bbox"].x1)
        ordered = [lines[key] for key in sorted(lines)]
        return [{"text": " ".join(ln["words"]), "x1": ln["x1"]} for ln in ordered], marks

    def is_multiline(self):
        return len({span["line_y"] for span in self.spans}) > 1

    def is_wrapped_prose(self):
        """Son satır hariç satırlar sütunu dolduruyorsa bu sarılmış düz metindir;
        satır sonları anlam taşımaz."""
        if len(self.lines) < 2:
            return True
        left, right = self.column
        fills = sorted((ln["x1"] - left) / (right - left) for ln in self.lines[:-1])
        return fills[len(fills) // 2] >= WRAP_FILL_RATIO

    def unit(self, row_keeps_breaks):
        keep_breaks = row_keeps_breaks and not self.is_wrapped_prose()
        if not self.marks and not keep_breaks:
            return {"en": " ".join(ln["text"] for ln in self.lines)}
        separator = "<br>" if keep_breaks else " "
        text = separator.join(html.escape(ln["text"]) for ln in self.lines)
        sups = "".join(f"<sup>{html.escape(mark)}</sup>" for mark in self.marks)
        return {"en": text + sups, "html": True}
