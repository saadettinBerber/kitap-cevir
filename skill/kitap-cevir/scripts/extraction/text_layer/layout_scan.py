"""PyMuPDF ile sayfa düzenini tarar: kod listeleri (girintili), satır içi kod
parçaları, tire ile bölünmüş özel isimler ve alt/üst simge düzeltmeleri. Satır
hazırlığı code_lines'tadır.

OpenDataLoader kod listelerini satır satır paragraf sanır, girintiyi atar ve
"McGraw-\\nHill" gibi tireleri siler; bu modül o kayıpları telafi eder.
Kod fontu ve boyut eşiği progress.json -> extraction ayarlarından gelir.
"""
import re

import fitz

from extraction.text_layer.code_lines import CodeFont, PageLineReader
from extraction.text_layer.script_marks import ScriptFixes
from project import DEFAULT_EXTRACTION

BLANK_LINE_GAP_RATIO = 1.6        # bu oranın üstündeki dikey boşluk = boş satır
MIN_INLINE_TOKEN_LENGTH = 2
_PLAIN_LOWERCASE_WORD = re.compile(r"^[a-z]+$")
_EDGE_PUNCTUATION = ".,;:()[]{}\"'“”‘’"


def _clean_token(text):
    return text.strip().strip(_EDGE_PUNCTUATION)


class CodeListing:
    """Ardışık kod satırları: girintisi ve boş satırlarıyla tek bir kod bloğu."""

    def __init__(self, lines):
        self.lines = lines

    @classmethod
    def group(cls, lines):
        listings, current = [], []
        for line in lines:
            if line.is_code:
                current.append(line)
            elif current:
                listings.append(cls(current))
                current = []
        return listings + [cls(current)] if current else listings

    def region(self):
        """{y0, y1, code}: sayfadaki yeri ve girintisi korunmuş kodu."""
        left_edge = min(line.left for line in self.lines)
        rendered, previous = [], None
        for line in self.lines:
            rendered.extend([""] * self._blank_lines_before(line, previous))
            rendered.append(" " * max(0, round((line.left - left_edge) / line.char_width)) + line.text)
            previous = line
        return {"y0": self.lines[0].top, "y1": self.lines[-1].bottom, "code": "\n".join(rendered)}

    @staticmethod
    def _blank_lines_before(line, previous):
        if previous is None:
            return 0
        return 1 if line.top - previous.top > line.height * BLANK_LINE_GAP_RATIO else 0


class ProseRepairs:
    """Gövde metni satırlarından ODL metnine uygulanacak onarımlar."""

    def __init__(self, lines):
        self.lines = lines

    def inline_code_tokens(self):
        """Ters tırnakla işaretlenecek satır içi kod parçaları (tekrarsız, sırayla)."""
        tokens = []
        for line in self.lines:
            if line.is_code:
                continue
            if line.uses_script_layout():
                tokens.append(line.text.strip())
                continue
            tokens += [token for token in map(_clean_token, (s["text"] for s in line.spans if s["is_code"]))
                       if self._is_markable(token)]
        return list(dict.fromkeys(tokens))

    @staticmethod
    def _is_markable(token):
        """Düz küçük harfli kelimeler (if, render) sayfa genelinde yanlış
        eşleşebileceği için yalnız tanımlayıcı görünümlü parçalar işaretlenir."""
        return len(token) >= MIN_INLINE_TOKEN_LENGTH and not _PLAIN_LOWERCASE_WORD.match(token)

    def hyphenated_names(self):
        """ODL'nin sildiği tireleri geri koymak için {yanlış: doğru} eşlemesi
        ('McGrawHill' -> 'McGraw-Hill')."""
        pairs = (self._hyphen_pair(line, next_line) for line, next_line in zip(self.lines, self.lines[1:]))
        return {wrong: right for wrong, right in pairs if wrong}

    @staticmethod
    def _hyphen_pair(line, next_line):
        text, following = line.text.rstrip(), next_line.text.lstrip()
        if not text.endswith("-") or not following[:1].isupper():
            return "", ""
        head = text[:-1].split()[-1] if text[:-1].split() else ""
        tail = _clean_token(following.split()[0])
        return (head + tail, head + "-" + tail) if head and tail else ("", "")


class LayoutScanner:
    """Bir sayfanın metin katmanını kod listelerine ve metin onarımlarına çevirir."""

    def __init__(self, settings=None):
        self.code_font = CodeFont(settings or DEFAULT_EXTRACTION)

    def scan(self, pdf_path, pdf_page):
        with fitz.open(pdf_path) as document:
            return self._scan_page(document[pdf_page - 1])

    def _scan_page(self, page):
        lines = PageLineReader(self.code_font).read(page)
        repairs, scripts = ProseRepairs(lines), ScriptFixes(lines)
        return {"page_height": page.rect.height,
                "code_blocks": [listing.region() for listing in CodeListing.group(lines)],
                "inline_code": repairs.inline_code_tokens(),
                "hyphen_fixes": {**repairs.hyphenated_names(), **scripts.for_code()},
                "script_fixes": scripts.for_prose()}


def scan_page(pdf_path, pdf_page, settings=None):
    """{page_height, code_blocks, inline_code, hyphen_fixes, script_fixes}"""
    return LayoutScanner(settings).scan(pdf_path, pdf_page)
