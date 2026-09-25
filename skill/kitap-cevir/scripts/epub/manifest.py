"""EPUB 3 paketinin tanım dosyaları: container.xml, content.opf ve nav.xhtml."""
import mimetypes
import uuid
from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import quote

from epub.xhtml import document

XHTML_TYPE = "application/xhtml+xml"
NAV_FILE = "nav.xhtml"
NAV_ITEM = f'<item id="nav" href="text/{NAV_FILE}" media-type="{XHTML_TYPE}" properties="nav"/>'
STYLESHEET = "styles/kindle.css"
FIXED_MEDIA_TYPES = {".xhtml": XHTML_TYPE, ".css": "text/css"}
UNKNOWN_MEDIA_TYPE = "application/octet-stream"
IDENTIFIER_NAMESPACE = "kitap-cevir:"
MODIFIED_FORMAT = "%Y-%m-%dT%H:%M:%SZ"   # dcterms:modified, UTC

CONTAINER_XML = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""

CONTENT_OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id" xml:lang="tr">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{identifier}</dc:identifier>
<dc:title>{title}</dc:title>
<dc:creator>{author}</dc:creator>
<dc:language>tr</dc:language>
<meta property="dcterms:modified">{modified}</meta>
</metadata>
<manifest>
{items}
</manifest>
<spine>
{spine}
</spine>
</package>
"""


@dataclass(frozen=True)
class EpubMetadata:
    title: str
    author: str
    identifier: str
    modified: str

    @classmethod
    def for_book(cls, book, modified):
        """Kimlik kitabın slug'ından türer; yeniden gönderilen EPUB Kindle'da aynı kitap sayılır."""
        identifier = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, IDENTIFIER_NAMESPACE + book['slug'])}"
        title = f"{book['title'] or book['slug']} (Türkçe)"
        return cls(title, book["author"], identifier, modified.strftime(MODIFIED_FORMAT))


def content_opf(metadata, manifest):
    """Paket belgesi: kitabın bilgisi, paketteki dosyalar ve okuma sırası."""
    return CONTENT_OPF.format(identifier=metadata.identifier, title=escape(metadata.title),
                              author=escape(metadata.author), modified=metadata.modified,
                              items=manifest.items(), spine=manifest.spine())


class Manifest:
    """Paketteki dosyaların listesi (manifest) ve bölümlerin okuma sırası (spine)."""

    def __init__(self, chapters, image_hrefs):
        self._chapters = chapters
        self._image_hrefs = image_hrefs

    def items(self):
        chapters = [_item(_chapter_id(chapter), f"text/{chapter.href()}") for chapter in self._chapters]
        images = [_item(f"img-{index}", href) for index, href in enumerate(self._image_hrefs, 1)]
        return "\n".join([NAV_ITEM, _item("css", STYLESHEET), *chapters, *images])

    def spine(self):
        return "\n".join(f'<itemref idref="{_chapter_id(chapter)}"/>' for chapter in self._chapters)


def _item(item_id, href):
    return f'<item id="{item_id}" href="{quote(href)}" media-type="{_media_type(href)}"/>'


def _media_type(href):
    """Bölümün ve stilin türü sabittir; görselinki uzantısından tahmin edilir."""
    return FIXED_MEDIA_TYPES.get(Path(href).suffix) or mimetypes.guess_type(href)[0] or UNKNOWN_MEDIA_TYPE


def _chapter_id(chapter):
    return Path(chapter.href()).stem


def nav_xhtml(chapters):
    """İçindekiler, başlangıç yeri ve basılı sayfa listesi."""
    toc = "".join(_toc_item(chapter) for chapter in chapters)
    pages = "".join(_page_items(chapter) for chapter in chapters)
    start = f'<li><a epub:type="bodymatter" href="{chapters[0].href()}">Başla</a></li>' if chapters else ""
    return document("İçindekiler", (
        f'<nav epub:type="toc" id="toc"><h1>İçindekiler</h1><ol>{toc}</ol></nav>\n'
        f'<nav epub:type="landmarks" hidden="hidden"><ol>'
        f'<li><a epub:type="toc" href="{NAV_FILE}#toc">İçindekiler</a></li>{start}</ol></nav>\n'
        f'<nav epub:type="page-list" hidden="hidden"><ol>{pages}</ol></nav>'))


def _toc_item(chapter):
    entries = "".join(f'<li><a href="{chapter.href(anchor)}">{escape(text)}</a></li>'
                      for text, anchor in chapter.toc_entries())
    nested = f"<ol>{entries}</ol>" if entries else ""
    return f'<li><a href="{chapter.href()}">{escape(chapter.title())}</a>{nested}</li>'


def _page_items(chapter):
    return "".join(f'<li><a href="{href}">{page}</a></li>' for page, href in chapter.page_links())
