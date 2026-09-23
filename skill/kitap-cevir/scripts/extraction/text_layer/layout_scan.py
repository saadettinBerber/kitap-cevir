"""PyMuPDF ile sayfa düzenini tarar: kod satırları (girintili), satır içi kod
parçaları ve tire ile bölünmüş özel isimler. Satır hazırlığı code_lines'tadır.

OpenDataLoader kod listelerini satır satır paragraf sanır, girintiyi atar ve
"McGraw-\\nHill" gibi tireleri siler; bu modül o kayıpları telafi eder.
Kod fontu ve boyut eşiği progress.json -> extraction ayarlarından gelir.
"""
import re

import fitz

from extraction.text_layer.code_lines import page_lines
from extraction.text_layer.script_marks import ScriptFixes
from project import DEFAULT_EXTRACTION

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


def _group_code_lines(lines):
    groups, current = [], []
    for line in lines:
        if line.is_code:
            current.append(line)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _indent_of(line, left_edge):
    return max(0, round((line.left - left_edge) / line.char_width))


def _blank_lines_before(line, previous):
    if previous is None:
        return 0
    gap = line.top - previous.top
    return 1 if gap > line.height * BLANK_LINE_GAP_RATIO else 0


def _code_block(group):
    left_edge = min(line.left for line in group)
    rendered, previous = [], None
    for line in group:
        rendered.extend([""] * _blank_lines_before(line, previous))
        rendered.append(" " * _indent_of(line, left_edge) + line.text)
        previous = line
    return {"y0": group[0].top, "y1": group[-1].bottom,
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
        if line.is_code:
            continue
        if line.uses_script_layout():
            tokens.append(line.text.strip())
            continue
        for span in line.spans:
            token = _clean_token(span["text"])
            if span["is_code"] and _is_markable_token(token):
                tokens.append(token)
    return list(dict.fromkeys(tokens))


def _hyphen_pair(line, next_line):
    text, following = line.text.rstrip(), next_line.text.lstrip()
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
        lines = page_lines(page, code_font)
        fixes = ScriptFixes(lines)
        return {
            "page_height": page.rect.height,
            "code_blocks": [_code_block(g) for g in _group_code_lines(lines)],
            "inline_code": _inline_code_tokens(lines),
            "hyphen_fixes": {**_hyphenated_names(lines), **fixes.for_code()},
            "script_fixes": fixes.for_prose(),
        }
    finally:
        document.close()


def page_plain_text(pdf_path, pdf_page):
    document = fitz.open(pdf_path)
    try:
        return document[pdf_page - 1].get_text()
    finally:
        document.close()
