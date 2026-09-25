"""Çevrilmiş sayfalardan Kindle için EPUB 3 üretir: dist/<slug>.epub.

Bölüm başına bir dosya; metin Türkçe akar, İngilizce aslı paragraf sonundaki EN
bağlantısıyla açılır pencerede görünür; kavram kartları bölüm sonundadır.
Send to Kindle EPUB'ı kabul eder; kitap çevrildikçe yeniden üretilip gönderilir.

Kullanım (proje dizininde): python3 export_epub.py
"""
import os
import sys
from datetime import datetime, timezone
from itertools import groupby

from epub.block_visitor import image_href
from epub.chapter import Chapter
from epub.manifest import EpubMetadata
from epub.package import EpubPackage
from project import Project
from translated_pages import TranslatedPages

STYLESHEET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "epub", "kindle.css")


class BookExport:
    """Paketin diskle tek sınırı: sayfaları ve görselleri okur, EPUB'ı verilen yola yazar."""

    def __init__(self, pages, epub_path):
        self._pages = pages
        self._epub_path = epub_path

    def write(self, package, page_numbers):
        """Verilen sayfalar pakete girer, paket EPUB olarak yazılır. Boş sayfaları progress.json zaten
        dışarıda bırakır; tek görselli sayfa şekildir, kalır."""
        documents = [self._pages.get(page) for page in page_numbers]
        for chapter in chapters_of(documents):
            package.add_chapter(chapter)
        for href, source in self._present(self._images(documents)):
            package.add_image(href, _read_bytes(source))
        self._save(package)

    def _images(self, documents):
        return [(image_href(document.number(), src), os.path.join(self._pages.images_dir(document.number()), src))
                for document in documents for src in document.media_sources()]

    @staticmethod
    def _present(images):
        """Diskte olmayan görsel uyarıyla atlanır; EPUB kırık bağlantı taşımaz."""
        missing = [source for _, source in images if not os.path.isfile(source)]
        for source in missing:
            print(f"! görsel yok, atlandı: {source}", file=sys.stderr)
        return [(href, source) for href, source in images if source not in missing]

    def _save(self, package):
        os.makedirs(os.path.dirname(self._epub_path), exist_ok=True)
        with open(self._epub_path, "wb") as stream:
            package.write_to(stream)


def chapters_of(documents):
    """Ardışık aynı bölüm numaralı sayfalar bir bölüm dosyasıdır."""
    groups = groupby(documents, key=lambda document: document.chapter().get("num"))
    return [_chapter(index, list(group)) for index, (_, group) in enumerate(groups, 1)]


def _chapter(index, documents):
    chapter = Chapter(f"chapter-{index:02d}.xhtml", documents[0].chapter())
    for document in documents:
        chapter.add(document)
    return chapter


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def _read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def main():
    project = Project.discover()
    book = project.load_settings().book()
    epub_path = project.epub_file(book["slug"])
    export = BookExport(TranslatedPages(project), epub_path)
    export.write(_package(book), project.load_progress().translated_pages())
    print("yazıldı:", project.relative_to_root(epub_path))


def _package(book):
    metadata = EpubMetadata.for_book(book, datetime.now(timezone.utc))
    return EpubPackage(metadata, _read_text(STYLESHEET_PATH))


if __name__ == "__main__":
    main()
