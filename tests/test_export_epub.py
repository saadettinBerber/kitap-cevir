import contextlib
import io
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone

import _paths  # noqa: F401
from epub.manifest import EpubMetadata
from epub.package import EpubPackage
from export_epub import BookExport, chapters_of
from page_document import PageDocument
from project import Project
from translated_pages import TranslatedPages

BOOK = {"slug": "demo", "title": "Demo", "author": "Yazar"}
MODIFIED = datetime(2026, 9, 25, tzinfo=timezone.utc)
CHAPTER = 1
IMAGE = "a.png"
MISSING_IMAGE = "yok.png"
ILLUSTRATED_PAGE, LEFT_OUT_PAGE, PAGE_WITHOUT_IMAGE_FILE = 1, 2, 3
EXPORTED_PAGES = [ILLUSTRATED_PAGE, PAGE_WITHOUT_IMAGE_FILE]


def _chapter(chapter_num):
    return {"num": chapter_num, "en": f"C{chapter_num}", "tr": f"B{chapter_num}"}


def _document(page, chapter_num):
    return PageDocument({"page": page, "chapter": _chapter(chapter_num), "blocks": []})


def _illustrated(page, src):
    return PageDocument({"page": page, "chapter": _chapter(CHAPTER), "blocks": [{"type": "image", "src": src}]})


class ChaptersOfTest(unittest.TestCase):
    def test_consecutive_pages_of_a_chapter_share_a_file(self):
        chapters = chapters_of([_document(1, 1), _document(2, 1), _document(3, 2)])
        self.assertEqual([[page for page, _ in chapter.page_links()] for chapter in chapters], [[1, 2], [3]])

    def test_chapter_files_are_numbered_in_order(self):
        chapters = chapters_of([_document(1, 0), _document(2, 1)])
        self.assertEqual([chapter.href() for chapter in chapters], ["chapter-01.xhtml", "chapter-02.xhtml"])

    def test_no_pages_no_chapters(self):
        self.assertEqual(chapters_of([]), [])


class BookExportTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pages = TranslatedPages(Project(tmp.name))
        self.epub_path = os.path.join(tmp.name, "dist", "demo.epub")
        self._save_pages()

    def _save_pages(self):
        for document in (_illustrated(ILLUSTRATED_PAGE, IMAGE), _document(LEFT_OUT_PAGE, CHAPTER),
                         _illustrated(PAGE_WITHOUT_IMAGE_FILE, MISSING_IMAGE)):
            self.pages.save(document)
        os.makedirs(self.pages.images_dir(ILLUSTRATED_PAGE))
        with open(os.path.join(self.pages.images_dir(ILLUSTRATED_PAGE), IMAGE), "wb") as handle:
            handle.write(b"png")

    def _export(self):
        """Paketi yazar; stderr'e düşen uyarıları döner."""
        package = EpubPackage(EpubMetadata.for_book(BOOK, MODIFIED), "")
        with contextlib.redirect_stderr(io.StringIO()) as warnings:
            BookExport(self.pages, self.epub_path).write(package, EXPORTED_PAGES)
        return warnings.getvalue()

    def _exported_files(self):
        self._export()
        with zipfile.ZipFile(self.epub_path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def test_epub_is_written_to_the_given_path(self):
        self._export()
        self.assertTrue(zipfile.is_zipfile(self.epub_path))

    def test_page_not_given_is_left_out(self):
        chapter = self._exported_files()["OEBPS/text/chapter-01.xhtml"].decode("utf-8")
        self.assertNotIn(f'id="page-{LEFT_OUT_PAGE}"', chapter)

    def test_present_image_is_packed(self):
        self.assertEqual(self._exported_files()[f"OEBPS/images/page-{ILLUSTRATED_PAGE}/{IMAGE}"], b"png")

    def test_missing_image_is_reported(self):
        self.assertIn(MISSING_IMAGE, self._export())

    def test_missing_image_is_skipped(self):
        self.assertNotIn(f"OEBPS/images/page-{PAGE_WITHOUT_IMAGE_FILE}/{MISSING_IMAGE}", self._exported_files())


if __name__ == "__main__":
    unittest.main()
