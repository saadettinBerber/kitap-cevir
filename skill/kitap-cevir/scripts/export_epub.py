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
    """Paketin diskle tek sınırı: sayfaları ve görselleri okur, EPUB'ı dist/ altına yazar."""

    def __init__(self, project, pages):
        self.project = project
        self.pages = pages

    def write(self, package):
        """Çevrilmiş sayfalar pakete girer; yazılan EPUB'ın yolu döner."""
        documents = self._documents()
        for chapter in chapters_of(documents):
            package.add_chapter(chapter)
        for href, source in self._present(self._images(documents)):
            package.add_image(href, _read_bytes(source))
        return self._save(package)

    def _documents(self):
        """Boş sayfaları progress.json zaten dışarıda bırakır; tek görselli sayfa şekildir, kalır."""
        return [self.pages.get(page) for page in self.project.load_progress().translated_pages()]

    def _images(self, documents):
        return [(image_href(document.number(), src), os.path.join(self.pages.images_dir(document.number()), src))
                for document in documents for src in document.media_sources()]

    @staticmethod
    def _present(images):
        """Diskte olmayan görsel uyarıyla atlanır; EPUB kırık bağlantı taşımaz."""
        missing = [source for _, source in images if not os.path.isfile(source)]
        for source in missing:
            print(f"! görsel yok, atlandı: {source}", file=sys.stderr)
        return [(href, source) for href, source in images if source not in missing]

    def _save(self, package):
        path = self.project.epub_file(self.project.load_settings().book()["slug"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as stream:
            package.write_to(stream)
        return path


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
    metadata = EpubMetadata.for_book(project.load_settings().book(), datetime.now(timezone.utc))
    package = EpubPackage(metadata, _read_text(STYLESHEET_PATH))
    path = BookExport(project, TranslatedPages(project)).write(package)
    print("yazıldı:", project.relative_to_root(path))


if __name__ == "__main__":
    main()
