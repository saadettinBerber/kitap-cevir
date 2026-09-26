"""Metin birimlerini XHTML parçasına çeviren işlemler. Veri (metin) sabit, işlemler
çoğalır, durum yoktur; sınıfa sarılmaz. Okuyucudaki karşılığı js/blocks.js → unitHtml.
"""
import re
from html import escape
from html.parser import HTMLParser

INLINE_TAGS = ("code", "strong", "em", "sup")
VOID_TAGS = ("br",)
_BACKTICK_CODE = re.compile(r"`([^`]+)`")
_TAG = re.compile(r"<[^>]+>")

XHTML_DOCUMENT = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="tr" lang="tr">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<link rel="stylesheet" type="text/css" href="../styles/kindle.css"/>
</head>
<body>
{body}
</body>
</html>
"""


def document(title, body):
    return XHTML_DOCUMENT.format(title=escape(title), body=body)


def plain_inline(text):
    """Düz metin kaçışlanır; `kod` parçaları <code> olur."""
    return _BACKTICK_CODE.sub(r"<code>\1</code>", escape(text))


def safe_inline(html):
    """Birimin güvenli HTML'i (FORMAT.md): izinli etiketler XHTML olarak kalır, ötekilerin yalnız metni."""
    parser = _SafeInlineParser()
    parser.feed(html)
    parser.close()
    return parser.xhtml()


def unit_html(unit, field):
    value = unit.get(field) or ""
    return safe_inline(value) if unit.get("html") else plain_inline(value)


def translated_html(unit):
    """Birimin Türkçesi; çevrilmemişse okuyucudaki gibi İngilizcesine düşer."""
    return unit_html(unit, "tr" if unit.get("tr") else "en")


def visible_text(html):
    return _TAG.sub("", html)


def code_block(code):
    """Kod olduğu gibi kalır; satır sonu ve girinti <pre> ile korunur."""
    return f'<pre class="code"><code>{escape(code)}</code></pre>'


class _SafeInlineParser(HTMLParser):
    """Açık kalan izinli etiketleri sonda kapatır; Kindle bozuk XHTML'i reddeder."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts = []
        self._open_tags = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            self._parts.append(f"<{tag}/>")
        elif tag in INLINE_TAGS:
            self._open(tag)

    def _open(self, tag):
        self._parts.append(f"<{tag}>")
        self._open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self._open_tags:
            self._close_through(tag)

    def _close_through(self, tag):
        """İçeride açık kalmış etiketler önce kapanır; kesişen etiketler XHTML'de iç içe olmalıdır."""
        while self._open_tags[-1] != tag:
            self._close_last()
        self._close_last()

    def _close_last(self):
        self._parts.append(f"</{self._open_tags.pop()}>")

    def handle_data(self, data):
        self._parts.append(escape(data))

    def xhtml(self):
        closing = "".join(f"</{tag}>" for tag in reversed(self._open_tags))
        return "".join(self._parts) + closing
