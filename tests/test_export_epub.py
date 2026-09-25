import contextlib
import io
import json
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

BOOK = {"slug": "demo", "title": "Demo", "author": "Yazar"}
MODIFIED = datetime(2026, 9, 25, tzinfo=timezone.utc)


def _document(page, chapter_num, blocks=()):
    chapter = {"num": chapter_num, "en": f"C{chapter_num}", "tr": f"B{chapter_num}"}
    return PageDocument({"page": page, "chapter": chapter, "blocks": list(blocks)})


class _Pages:
    """TranslatedPages sahtesi: belgeler bellekte, görsel klasörü geçici dizinde."""

    def __init__(self, documents, images_root):
        self.documents = {document.number(): document for document in documents}
        self.images_root = images_root

    def get(self, page):
        return self.documents[page]

    def images_dir(self, page):
        return os.path.join(self.images_root, f"page-{page}_images")


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
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        progress = {"book": BOOK, "book_pdf": "b.pdf", "pdf_offset": 0, "book_total_pages": 3,
                    "last_translated_page": 3, "chapters": [],
                    "pages": {"1": {"chapter": 1}, "2": {"blank": True}, "3": {"chapter": 1}}}
        with open(os.path.join(self.tmp.name, "progress.json"), "w", encoding="utf-8") as handle:
            json.dump(progress, handle)
        image = {"type": "image", "src": "a.png"}
        documents = [_document(1, 1, [image]), _document(3, 1, [{"type": "image", "src": "yok.png"}])]
        self.pages = _Pages(documents, self.tmp.name)
        os.makedirs(self.pages.images_dir(1))
        with open(os.path.join(self.pages.images_dir(1), "a.png"), "wb") as handle:
            handle.write(b"png")

    def _export(self):
        package = EpubPackage(EpubMetadata.for_book(BOOK, MODIFIED), "")
        with contextlib.redirect_stderr(io.StringIO()) as warnings:
            path = BookExport(Project(self.tmp.name), self.pages).write(package)
        return path, warnings.getvalue()

    def test_epub_is_written_under_dist_with_the_slug(self):
        path, _ = self._export()
        self.assertEqual(path, os.path.join(self.tmp.name, "dist", "demo.epub"))

    def test_blank_page_is_left_out(self):
        path, _ = self._export()
        chapter = zipfile.ZipFile(path).read("OEBPS/text/chapter-01.xhtml").decode("utf-8")
        self.assertNotIn('id="page-2"', chapter)

    def test_present_image_is_packed(self):
        path, _ = self._export()
        self.assertEqual(zipfile.ZipFile(path).read("OEBPS/images/page-1/a.png"), b"png")

    def test_missing_image_is_reported_and_skipped(self):
        path, warnings = self._export()
        self.assertIn("yok.png", warnings)
        self.assertNotIn("OEBPS/images/page-3/yok.png", zipfile.ZipFile(path).namelist())


if __name__ == "__main__":
    unittest.main()
