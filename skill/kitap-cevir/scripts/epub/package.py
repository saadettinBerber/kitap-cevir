"""EPUB zip arşivi: mimetype ilk ve sıkıştırmasız, ardından tanım dosyaları, bölümler, görseller.
Disk bilmez: stil ve görseller içerik olarak verilir, arşiv verilen akışa yazılır.
"""
import zipfile
from xml.etree import ElementTree

from epub.manifest import CONTAINER_XML, NAV_FILE, STYLESHEET, Manifest, content_opf, nav_xhtml

MIMETYPE = "application/epub+zip"
CONTENT_DIR = "OEBPS"


class MalformedXhtml(ValueError):
    """Bölüm dosyası XML olarak okunamıyor; Kindle böyle bir EPUB'ı reddeder."""


class EpubPackage:
    """Bölümler ve görseller toplanır, write_to ile tek seferde arşive yazılır."""

    def __init__(self, metadata, stylesheet):
        self._metadata = metadata
        self._stylesheet = stylesheet
        self._chapters = []
        self._images = {}

    def add_chapter(self, chapter):
        self._chapters.append(chapter)

    def add_image(self, href, content):
        self._images[href] = content

    def write_to(self, stream):
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
            archive.writestr("META-INF/container.xml", CONTAINER_XML)
            for name, content in self._contents().items():
                archive.writestr(f"{CONTENT_DIR}/{name}", content)

    def _contents(self):
        """OEBPS altındaki dosyalar: denetlenmiş XHTML belgeleri, paket belgesi, stil ve görseller."""
        opf = content_opf(self._metadata, Manifest(self._chapters, list(self._images)))
        return {**self._checked_texts(), "content.opf": opf, STYLESHEET: self._stylesheet, **self._images}

    def _checked_texts(self):
        """Bölümler ve gezinme belgesi; XML olarak okunamayan belge paketi durdurur."""
        texts = {f"text/{chapter.href()}": chapter.xhtml() for chapter in self._chapters}
        texts[f"text/{NAV_FILE}"] = nav_xhtml(self._chapters)
        for name, text in texts.items():
            _check_well_formed(name, text)
        return texts


def _check_well_formed(name, text):
    try:
        ElementTree.fromstring(text.encode("utf-8"))
    except ElementTree.ParseError as error:
        raise MalformedXhtml(f"{name}: {error}") from error
