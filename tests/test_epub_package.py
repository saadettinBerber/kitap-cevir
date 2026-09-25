import io
import unittest
import zipfile
from datetime import datetime, timezone

import _paths  # noqa: F401
from epub.manifest import EpubMetadata, content_opf, nav_xhtml
from epub.package import EpubPackage, MalformedXhtml

BOOK = {"slug": "demo", "title": "Demo", "author": "Yazar & Ortak"}
MODIFIED = datetime(2026, 9, 25, 10, 30, tzinfo=timezone.utc)


class _Chapter:
    """Pakete yalnız dosya adı, başlık, sayfalar, içindekiler ve XHTML lazım."""

    def __init__(self, file_name, xhtml="<html/>", pages=(5,)):
        self.file_name, self._xhtml, self.pages = file_name, xhtml, list(pages)

    def title(self):
        return "Bölüm"

    def toc_entries(self):
        return [("Giriş", "h-5-1")]

    def xhtml(self):
        return self._xhtml


def _archive(package):
    stream = io.BytesIO()
    package.write_to(stream)
    return zipfile.ZipFile(stream)


def _package(*chapters):
    package = EpubPackage(EpubMetadata.for_book(BOOK, MODIFIED), "body {}")
    for chapter in chapters:
        package.add_chapter(chapter)
    return package


class MetadataTest(unittest.TestCase):
    def test_identifier_is_stable_for_the_same_slug(self):
        later = datetime(2027, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(EpubMetadata.for_book(BOOK, MODIFIED).identifier,
                         EpubMetadata.for_book(BOOK, later).identifier)

    def test_title_is_marked_turkish(self):
        self.assertEqual(EpubMetadata.for_book(BOOK, MODIFIED).title, "Demo (Türkçe)")

    def test_book_without_title_uses_its_slug(self):
        self.assertEqual(EpubMetadata.for_book({**BOOK, "title": ""}, MODIFIED).title, "demo (Türkçe)")

    def test_modified_is_utc_timestamp(self):
        self.assertEqual(EpubMetadata.for_book(BOOK, MODIFIED).modified, "2026-09-25T10:30:00Z")


class ArchiveTest(unittest.TestCase):
    def test_mimetype_is_first_and_stored(self):
        first = _archive(_package(_Chapter("chapter-01.xhtml"))).infolist()[0]
        self.assertEqual((first.filename, first.compress_type), ("mimetype", zipfile.ZIP_STORED))

    def test_archive_holds_chapter_nav_opf_and_style(self):
        names = _archive(_package(_Chapter("chapter-01.xhtml"))).namelist()
        for name in ("OEBPS/text/chapter-01.xhtml", "OEBPS/text/nav.xhtml", "OEBPS/content.opf",
                     "OEBPS/styles/kindle.css"):
            self.assertIn(name, names)

    def test_image_content_is_written_under_its_href(self):
        package = _package(_Chapter("chapter-01.xhtml"))
        package.add_image("images/page-5/a.png", b"png")
        self.assertEqual(_archive(package).read("OEBPS/images/page-5/a.png"), b"png")

    def test_malformed_chapter_is_refused_with_its_name(self):
        with self.assertRaisesRegex(MalformedXhtml, "chapter-01"):
            _archive(_package(_Chapter("chapter-01.xhtml", xhtml="<p>")))


class ManifestTest(unittest.TestCase):
    def test_opf_lists_chapters_in_spine_and_images_in_manifest(self):
        opf = content_opf(EpubMetadata.for_book(BOOK, MODIFIED), [_Chapter("chapter-01.xhtml")],
                          ["images/page-5/a b.png"])
        self.assertIn('<itemref idref="chapter-01"/>', opf)
        self.assertIn('href="images/page-5/a%20b.png" media-type="image/png"', opf)

    def test_opf_escapes_author(self):
        self.assertIn("Yazar &amp; Ortak", content_opf(EpubMetadata.for_book(BOOK, MODIFIED), [], []))

    def test_nav_links_headings_and_printed_pages(self):
        nav = nav_xhtml([_Chapter("chapter-01.xhtml", pages=[5, 6])])
        self.assertIn('href="chapter-01.xhtml#h-5-1">Giriş', nav)
        self.assertIn('href="chapter-01.xhtml#page-6">6', nav)

    def test_nav_without_chapters_has_no_start(self):
        self.assertNotIn("bodymatter", nav_xhtml([]))


if __name__ == "__main__":
    unittest.main()
