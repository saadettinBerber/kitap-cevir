"""PyMuPDF ile sayfa düzenini tarar: kod satırları (girintili), satır içi kod
parçaları ve tire ile bölünmüş özel isimler.

OpenDataLoader kod listelerini satır satır paragraf sanır, girintiyi atar ve
"McGraw-\\nHill" gibi tireleri siler; bu modül o kayıpları telafi eder.
Kod fontu ve boyut eşiği progress.json -> extraction ayarlarından gelir.
"""
import re

import fitz

from project import DEFAULT_EXTRACTION

MONO_CHAR_WIDTH_RATIO = 0.6       # tek aralıklı karakter genişliği / punto
BLANK_LINE_GAP_RATIO = 1.6        # bu oranın üstündeki dikey boşluk = boş satır
MIN_INLINE_TOKEN_LENGTH = 2
_PLAIN_LOWERCASE_WORD = re.compile(r"^[a-z]+$")
_EDGE_PUNCTUATION = ".,;:()[]{}\"'“”‘’"


class CodeFont:
    """Bir span'ın kod fontu olup olmadığına karar verir."""

    def __init__(self, settings):
        self.prefix = settings["code_font_prefix"]
        self.max_size = settings["code_max_font_size"]

    def matches(self, span):
        return span["font"].startswith(self.prefix) and span["size"] < self.max_size


def _line_spans(line, code_font):
    spans = [span for span in line["spans"] if span["text"].strip()]
    for span in spans:
        span["is_code"] = code_font.matches(span)
    return spans


def _line_text(spans):
    """Baştaki boşluklar korunur: PDF'te kod girintisi metnin içindedir."""
    return "".join(span["text"] for span in spans).rstrip()


def _page_lines(page, code_font):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = _line_spans(line, code_font)
            if spans:
                lines.append({"spans": spans, "bbox": line["bbox"],
                              "text": _line_text(spans),
                              "is_code": all(span["is_code"] for span in spans)})
    lines.sort(key=lambda ln: (round(ln["bbox"][1]), ln["bbox"][0]))
    return lines


def _group_code_lines(lines):
    groups, current = [], []
    for line in lines:
        if line["is_code"]:
            current.append(line)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _indent_of(line, left_edge):
    char_width = line["spans"][0]["size"] * MONO_CHAR_WIDTH_RATIO
    return max(0, round((line["bbox"][0] - left_edge) / char_width))


def _blank_lines_before(line, previous):
    if previous is None:
        return 0
    line_height = line["bbox"][3] - line["bbox"][1]
    gap = line["bbox"][1] - previous["bbox"][1]
    return 1 if gap > line_height * BLANK_LINE_GAP_RATIO else 0


def _code_block(group):
    left_edge = min(line["bbox"][0] for line in group)
    rendered, previous = [], None
    for line in group:
        rendered.extend([""] * _blank_lines_before(line, previous))
        rendered.append(" " * _indent_of(line, left_edge) + line["text"])
        previous = line
    return {"y0": group[0]["bbox"][1], "y1": group[-1]["bbox"][3],
            "code": "\n".join(rendered)}


def _clean_token(text):
    return text.strip().strip(_EDGE_PUNCTUATION)


def _is_markable_token(token):
    """Düz küçük harfli kelimeler (if, render) sayfa genelinde yanlış
    eşleşebileceği için yalnız tanımlayıcı görünümlü parçalar işaretlenir."""
    return (len(token) >= MIN_INLINE_TOKEN_LENGTH
            and not _PLAIN_LOWERCASE_WORD.match(token))


def _inline_code_tokens(lines):
    tokens = []
    for line in lines:
        if line["is_code"]:
            continue
        for span in line["spans"]:
            token = _clean_token(span["text"])
            if span["is_code"] and _is_markable_token(token):
                tokens.append(token)
    return list(dict.fromkeys(tokens))


def _hyphen_pair(line, next_line):
    text, following = line["text"].rstrip(), next_line["text"].lstrip()
    if not text.endswith("-") or not following[:1].isupper():
        return None
    head = text[:-1].split()[-1] if text[:-1].split() else ""
    tail = _clean_token(following.split()[0])
    return (head + tail, head + "-" + tail) if head and tail else None


def _hyphenated_names(lines):
    """ODL'nin sildiği tireleri geri koymak için {yanlış: doğru} eşlemesi
    ('McGrawHill' -> 'McGraw-Hill')."""
    fixes = {}
    for line, next_line in zip(lines, lines[1:]):
        pair = _hyphen_pair(line, next_line)
        if pair:
            fixes[pair[0]] = pair[1]
    return fixes


def scan_page(pdf_path, pdf_page, settings=None):
    code_font = CodeFont(settings or DEFAULT_EXTRACTION)
    document = fitz.open(pdf_path)
    try:
        page = document[pdf_page - 1]
        lines = _page_lines(page, code_font)
        return {
            "page_height": page.rect.height,
            "code_blocks": [_code_block(g) for g in _group_code_lines(lines)],
            "inline_code": _inline_code_tokens(lines),
            "hyphen_fixes": _hyphenated_names(lines),
        }
    finally:
        document.close()


def page_plain_text(pdf_path, pdf_page):
    document = fitz.open(pdf_path)
    try:
        return document[pdf_page - 1].get_text()
    finally:
        document.close()
