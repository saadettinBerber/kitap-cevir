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


def content_opf(metadata, chapters, image_hrefs):
    items = [NAV_ITEM, _item("css", STYLESHEET, "text/css")]
    items += [_item(_chapter_id(chapter), f"text/{chapter.href()}", XHTML_TYPE) for chapter in chapters]
    items += [_item(f"img-{index}", href, _media_type(href)) for index, href in enumerate(image_hrefs, 1)]
    spine = [f'<itemref idref="{_chapter_id(chapter)}"/>' for chapter in chapters]
    return CONTENT_OPF.format(identifier=metadata.identifier, title=escape(metadata.title),
                              author=escape(metadata.author), modified=metadata.modified,
                              items="\n".join(items), spine="\n".join(spine))


def nav_xhtml(chapters):
    """İçindekiler, başlangıç yeri ve basılı sayfa listesi."""
    toc = "".join(_toc_item(chapter) for chapter in chapters)
    pages = "".join(f'<li><a href="{href}">{page}</a></li>' for chapter in chapters for page, href in chapter.page_links())
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


def _item(item_id, href, media_type):
    return f'<item id="{item_id}" href="{quote(href)}" media-type="{media_type}"/>'


def _chapter_id(chapter):
    return Path(chapter.href()).stem


def _media_type(href):
    return mimetypes.guess_type(href)[0] or "application/octet-stream"
