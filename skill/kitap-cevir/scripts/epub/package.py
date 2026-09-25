"""EPUB zip arşivi: mimetype ilk ve sıkıştırmasız, ardından tanım dosyaları, bölümler, görseller.
Disk bilmez: stil ve görseller içerik olarak verilir, arşiv verilen akışa yazılır.
"""
import zipfile
from xml.etree import ElementTree

from epub.manifest import CONTAINER_XML, NAV_FILE, STYLESHEET, content_opf, nav_xhtml

MIMETYPE = "application/epub+zip"
CONTENT_DIR = "OEBPS"


class MalformedXhtml(ValueError):
    """Bölüm dosyası XML olarak okunamıyor; Kindle böyle bir EPUB'ı reddeder."""


class EpubPackage:
    """Bölümler ve görseller toplanır, write_to ile tek seferde arşive yazılır."""

    def __init__(self, metadata, stylesheet):
        self.metadata = metadata
        self.stylesheet = stylesheet
        self.chapters = []
        self.images = {}

    def add_chapter(self, chapter):
        self.chapters.append(chapter)

    def add_image(self, href, content):
        self.images[href] = content

    def write_to(self, stream):
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
            archive.writestr("META-INF/container.xml", CONTAINER_XML)
            for name, content in {**self._documents(), **self.images}.items():
                archive.writestr(f"{CONTENT_DIR}/{name}", content)

    def _documents(self):
        texts = {f"text/{chapter.file_name}": chapter.xhtml() for chapter in self.chapters}
        texts[f"text/{NAV_FILE}"] = nav_xhtml(self.chapters)
        for name, text in texts.items():
            _check_well_formed(name, text)
        return {**texts, "content.opf": content_opf(self.metadata, self.chapters, list(self.images)),
                STYLESHEET: self.stylesheet}


def _check_well_formed(name, text):
    try:
        ElementTree.fromstring(text.encode("utf-8"))
    except ElementTree.ParseError as error:
        raise MalformedXhtml(f"{name}: {error}") from error
