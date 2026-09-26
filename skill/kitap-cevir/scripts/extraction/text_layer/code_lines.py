"""Sayfanın metin satırlarını (PdfPage.text_lines) kod çıkarımı için hazırlar: geniş boşlukta bölünen
parçaları aynı taban çizgisinde birleştirir, alt/üst simgeleri ev sahibi satıra
bağlar (script_marks), kod ile başlayıp düz metinle süren satırı ikiye ayırır,
düz metnin yanındaki kısa kod parçasını satır içi koda indirir.

Prosedürel (Bl.6): TextLine bir veri yapısıdır; satır türleri (kod, düz metin) sabit,
satırlar üzerindeki işlemler ise çoğalıyor. Satır işlemleri bu yüzden onu kullanan
sınıfın yanında fonksiyon olarak durur, satırın kendisine eklenmez.
"""
from dataclasses import replace

from extraction.text_layer.script_marks import ScriptAttacher
from extraction.text_layer.text_line import LineSpan, Piece, TextLine, char_width, uses_script_layout

SAME_BASELINE_TOLERANCE = 2.0     # bu kadar yakın taban çizgisi = aynı satır
MIN_STANDALONE_CODE_CHARS = 12    # düz metinle aynı satırdaki kod parçası bundan kısaysa satır içi koddur


class CodeFont:
    """Bir span'ın kod fontu olup olmadığına karar verir (progress.json -> extraction)."""

    def __init__(self, settings):
        self._prefix = settings["code_font_prefix"]
        self._max_size = settings["code_max_font_size"]

    def matches(self, span):
        return span.font.startswith(self._prefix) and span.size < self._max_size


class PageLineReader:
    """Bir sayfanın satırlarını, metinleri dizilmiş TextLine listesi olarak okur."""

    def __init__(self, code_font):
        self._code_font = code_font

    def read(self, page):
        """page: PdfPage."""
        split = sorted((part for line in self._raw_lines(page) for part in _split_leading_code(line)),
                       key=_reading_order)
        return [_typeset(line) for line in _demote_inline_code(_merge_code_fragments(ScriptAttacher(split).attach()))]

    def _raw_lines(self, page):
        lines = [TextLine.of_spans(spans)
                 for line in page.text_lines()
                 for spans in self._split_by_baseline(self._marked_spans(line))]
        return sorted(lines, key=_reading_order)

    def _marked_spans(self, line):
        return [LineSpan.marked(span, self._code_font.matches(span)) for span in line]

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


def _reading_order(line):
    return round(line.box.y0), line.box.x0


def _split_leading_code(line):
    """'formül , or ...' gibi kod ile başlayıp düz metinle süren satırı ikiye
    ayırır; kod parçası kod satırlarıyla birleşebilsin diye. Tek harflik
    baş parça ('W be the key...') satır içi koddur, bölünmez."""
    if line.is_code or not line.spans[0].is_code:
        return [line]
    split = next(index for index, span in enumerate(line.spans) if not span.is_code)
    code = TextLine.of(line.spans[:split], True)
    if len(code.raw_text.strip()) < MIN_STANDALONE_CODE_CHARS:
        return [line]
    return [code, TextLine.of(line.spans[split:], False)]


def _merge_code_fragments(lines):
    """Aynı taban çizgisindeki iki kod parçası tek kod satırıdır."""
    merged = []
    for line in lines:
        if merged and _continues_code(merged[-1], line):
            merged[-1] = _joined(merged[-1], line)
        else:
            merged.append(line)
    return merged


def _continues_code(line, other):
    return line.is_code and other.is_code and _is_level_with(line, other)


def _joined(line, other):
    """İki parçanın tek satırı; okuma sırasında önce gelen parçanın taban çizgisi kalır."""
    spans = sorted(line.spans + other.spans, key=_left_edge)
    return replace(TextLine.of(spans, line.is_code), baseline=line.baseline, scripts=line.scripts + other.scripts)


def _left_edge(span):
    return span.box.x0


def _is_level_with(line, other):
    return abs(line.baseline - other.baseline) <= SAME_BASELINE_TOLERANCE


def _demote_inline_code(lines):
    """Düz metinle aynı taban çizgisindeki kod parçası satır içi koddur. Sırayla karar verilir:
    önceki satırların indirilmiş hâli sonrakilerin komşusudur."""
    decided = list(lines)
    for index, line in enumerate(lines):
        beside = [other for position, other in enumerate(decided) if position != index and _is_level_with(other, line)]
        if _is_inline_code(line, beside):
            decided[index] = replace(line, is_code=False)
    return decided


def _is_inline_code(line, beside):
    """Yalnız satırın en solundaki uzun parça (formül kutusu + ' , or') kod satırı kalır."""
    if not line.is_code or all(other.is_code for other in beside):
        return False
    leftmost = all(line.box.x0 <= other.box.x0 for other in beside)
    return not (leftmost and _is_standalone_code(line))


def _is_standalone_code(line):
    return len(line.raw_text.strip()) >= MIN_STANDALONE_CODE_CHARS


def _typeset(line):
    """Satırın çıkarımda kullanılacak metni: boşlukla dizilmiş ya da ham metin."""
    return replace(line, text=_spaced_text(line) if uses_script_layout(line) else line.raw_text)


def _spaced_text(line):
    """Parçaları x konumuna göre boşlukla dizer; alt/üst simgeleri araya koyar."""
    pieces = [Piece(span.box.x0, span.box.x1, span.text) for span in line.spans]
    pieces += [mark.piece() for mark in line.scripts]
    width = char_width(line)
    text, cursor, after_script = "", None, False
    for x0, x1, piece, is_script in sorted(pieces):
        threshold = width if after_script else width / 2
        if cursor is not None and x0 - cursor > threshold:
            text += " " * max(1, round((x0 - cursor) / width))
        text += piece
        cursor = x1 if cursor is None else max(cursor, x1)
        after_script = is_script
    return text.rstrip()
