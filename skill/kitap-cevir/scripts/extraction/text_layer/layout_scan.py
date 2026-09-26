"""Sayfanın metin katmanından (PdfPage) düzeni tarar: kod listeleri (girintili), satır içi kod
parçaları, tire ile bölünmüş özel isimler, alt/üst simge düzeltmeleri ve
e-kitabın kod görseli bağlantıları. Satır hazırlığı code_lines'tadır.

OpenDataLoader kod listelerini satır satır paragraf sanır, girintiyi atar ve
"McGraw-\\nHill" gibi tireleri siler; bu modül o kayıpları telafi eder.
Kod fontu ve boyut eşiği progress.json -> extraction ayarlarından gelir.
"""
import itertools
import re

from extraction.settings import optional_pattern
from extraction.text_layer.code_lines import CodeFont, PageLineReader
from extraction.text_layer.script_marks import ScriptFixes
from extraction.text_layer.text_line import char_width, uses_script_layout

BLANK_LINE_GAP_RATIO = 1.6        # bu oranın üstündeki dikey boşluk = boş satır
MIN_INLINE_TOKEN_LENGTH = 2
_PLAIN_LOWERCASE_WORD = re.compile(r"^[a-z]+$")
_EDGE_PUNCTUATION = ".,;:()[]{}\"'“”‘’"


def _is_code(line):
    return line.is_code


def _clean_token(text):
    return text.strip().strip(_EDGE_PUNCTUATION)


class CodeListing:
    """Ardışık kod satırları: girintisi ve boş satırlarıyla tek bir kod bloğu."""

    def __init__(self, lines):
        self._lines = lines

    @classmethod
    def group(cls, lines):
        """Ardışık kod satırlarının her kesintisiz dizisi bir listedir."""
        return [cls(list(run)) for is_code, run in itertools.groupby(lines, key=_is_code) if is_code]

    def region(self):
        """{y0, y1, code}: sayfadaki yeri ve girintisi korunmuş kodu."""
        left_edge = min(line.box.x0 for line in self._lines)
        rendered, previous = [], None
        for line in self._lines:
            rendered.extend([""] * self._blank_lines_before(line, previous))
            rendered.append(" " * max(0, round((line.box.x0 - left_edge) / char_width(line))) + line.text)
            previous = line
        return {"y0": self._lines[0].box.y0, "y1": self._lines[-1].box.y1, "code": "\n".join(rendered)}

    @staticmethod
    def _blank_lines_before(line, previous):
        if previous is None:
            return 0
        return 1 if line.box.y0 - previous.box.y0 > line.box.height * BLANK_LINE_GAP_RATIO else 0


class ProseRepairs:
    """Gövde metni satırlarından ODL metnine uygulanacak onarımlar."""

    def __init__(self, lines):
        self._lines = lines

    def inline_code_tokens(self):
        """Ters tırnakla işaretlenecek satır içi kod parçaları (tekrarsız, sırayla)."""
        tokens = [token for line in self._lines if not line.is_code for token in self._tokens_of(line)]
        return list(dict.fromkeys(tokens))

    def _tokens_of(self, line):
        """Kod formüllü satır bütünüyle tek parçadır; düz metin satırında kod fontlu parçalar."""
        if uses_script_layout(line):
            return [line.text.strip()]
        code = (_clean_token(span.text) for span in line.spans if span.is_code)
        return [token for token in code if self._is_markable(token)]

    @staticmethod
    def _is_markable(token):
        """Düz küçük harfli kelimeler (if, render) sayfa genelinde yanlış
        eşleşebileceği için yalnız tanımlayıcı görünümlü parçalar işaretlenir."""
        return len(token) >= MIN_INLINE_TOKEN_LENGTH and not _PLAIN_LOWERCASE_WORD.match(token)

    def hyphenated_names(self):
        """ODL'nin sildiği tireleri geri koymak için {yanlış: doğru} eşlemesi
        ('McGrawHill' -> 'McGraw-Hill')."""
        pairs = (self._hyphen_pair(line, next_line) for line, next_line in zip(self._lines, self._lines[1:]))
        return {wrong: right for wrong, right in pairs if wrong}

    @staticmethod
    def _hyphen_pair(line, next_line):
        text, following = line.text.rstrip(), next_line.text.lstrip()
        if not text.endswith("-") or not following[:1].isupper():
            return "", ""
        head = text[:-1].split()[-1] if text[:-1].split() else ""
        tail = _clean_token(following.split()[0])
        return (head + tail, head + "-" + tail) if head and tail else ("", "")


class CodeImageLinkLines:
    """E-kitap kökenli PDF'lerde her kod listesinin üstündeki bağlantı satırları
    ("Click here to view code image"). Desen satırın tamamıyla eşleşir: metin
    içinde bağlantıdan söz eden cümle bağlantı değildir. Desen boşsa kapalıdır."""

    def __init__(self, lines, pattern):
        self._lines = lines
        self._pattern = optional_pattern(pattern)

    def slots(self):
        """{text, y0, y1}: bağlantı satırı, komşu satırlara kadarki boşluğuyla.
        ODL bağlantıyı komşu satırla tek öğede birleştirir; şerit öğeden
        kesilince kalan satırlar gerçek yüksekliğine döner."""
        return [self._slot(line) for line in self._lines if self._is_link(line)]

    def _is_link(self, line):
        return bool(self._pattern.fullmatch(line.text.strip()))

    def _slot(self, link):
        top, bottom = link.box.y0, link.box.y1
        slot_top = max((line.box.y1 for line in self._lines if line.box.y1 <= top), default=top)
        slot_bottom = min((line.box.y0 for line in self._lines if line.box.y0 >= bottom), default=bottom)
        return {"text": link.text.strip(), "y0": slot_top, "y1": slot_bottom}


class LayoutScanner:
    """Bir sayfanın metin katmanını kod listelerine, metin onarımlarına ve
    bağlantı şeritlerine çevirir."""

    def __init__(self, settings):
        self._code_font = CodeFont(settings)
        self._code_image_link_pattern = settings["code_image_link_pattern"]

    def scan(self, page):
        """page: PdfPage → {page_height, code_blocks, inline_code, hyphen_fixes, script_fixes, code_image_links}"""
        lines = PageLineReader(self._code_font).read(page)
        repairs, scripts = ProseRepairs(lines), ScriptFixes(lines)
        return {"page_height": page.height,
                "code_blocks": [listing.region() for listing in CodeListing.group(lines)],
                "inline_code": repairs.inline_code_tokens(),
                "hyphen_fixes": {**repairs.hyphenated_names(), **scripts.for_code()},
                "script_fixes": scripts.for_prose(),
                "code_image_links": CodeImageLinkLines(lines, self._code_image_link_pattern).slots()}
