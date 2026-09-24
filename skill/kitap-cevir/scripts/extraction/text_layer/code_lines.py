"""Sayfanın metin satırlarını (PdfPage.text_lines) kod çıkarımı için hazırlar: geniş boşlukta bölünen
parçaları aynı taban çizgisinde birleştirir, alt/üst simgeleri ev sahibi satıra
bağlar (script_marks), kod ile başlayıp düz metinle süren satırı ikiye ayırır,
düz metnin yanındaki kısa kod parçasını satır içi koda indirir.
"""
from extraction.text_layer.script_marks import ScriptAttacher
from extraction.text_layer.text_line import SAME_BASELINE_TOLERANCE, LineSpan, TextLine


class CodeFont:
    """Bir span'ın kod fontu olup olmadığına karar verir (progress.json -> extraction)."""

    def __init__(self, settings):
        self.prefix = settings["code_font_prefix"]
        self.max_size = settings["code_max_font_size"]

    def matches(self, span):
        return span.font.startswith(self.prefix) and span.size < self.max_size


class PageLineReader:
    """Bir sayfanın satırlarını, metinleri hazır TextLine listesi olarak okur."""

    def __init__(self, code_font):
        self.code_font = code_font

    def read(self, page):
        """page: PdfPage."""
        split = [part for line in self._raw_lines(page) for part in line.split_leading_code()]
        split.sort(key=TextLine.sort_key)
        lines = self._demote_inline_code(self._merge_code_fragments(ScriptAttacher(split).attach()))
        for line in lines:
            line.render()
        return lines

    def _raw_lines(self, page):
        lines = [TextLine.of_spans(spans)
                 for line in page.text_lines()
                 for spans in self._split_by_baseline(self._marked_spans(line))]
        return sorted(lines, key=TextLine.sort_key)

    def _marked_spans(self, line):
        return [LineSpan.marked(span, self.code_font.matches(span)) for span in line]

    @staticmethod
    def _split_by_baseline(spans):
        """PyMuPDF bazen üst simgeyi aynı satıra koyar; farklı taban çizgisindeki
        parçalar ayrı satır olur ki simge bağlama tek yoldan çalışsın. Yarım
        puntoluk font farkları (italik vb.) aynı taban çizgisi sayılır."""
        groups = []
        for span in sorted(spans, key=lambda span: span.baseline):
            if groups and abs(span.baseline - groups[-1][0].baseline) <= SAME_BASELINE_TOLERANCE:
                groups[-1].append(span)
            else:
                groups.append([span])
        return [sorted(group, key=lambda span: span.box.x0) for group in groups]

    @staticmethod
    def _merge_code_fragments(lines):
        merged = []
        for line in lines:
            if merged and merged[-1].continues_code(line):
                merged[-1].absorb(line)
            else:
                merged.append(line)
        return merged

    @staticmethod
    def _demote_inline_code(lines):
        """Düz metinle aynı taban çizgisindeki kod parçası satır içi koddur; yalnız
        satırın en solundaki uzun parça (formül kutusu + ' , or') kod satırı kalır."""
        for line in lines:
            beside = [other for other in lines if other is not line and other.is_level_with(line)]
            if not line.is_code or all(other.is_code for other in beside):
                continue
            leftmost = all(line.left <= other.left for other in beside)
            if not (leftmost and line.is_standalone_code()):
                line.is_code = False
        return lines
