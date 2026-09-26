import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from pdf_fakes import FakePdfDocument, FakePdfPage
from init_book import BookSetup, card_kinds, parse_args, report, slugify

PAGE_COUNT = 3


class SlugifyTest(unittest.TestCase):
    def test_turkish_characters_and_spaces(self):
        self.assertEqual(slugify("Çevik Yazılım: Şık Kod!"), "cevik-yazilim-sik-kod")

    def test_empty_falls_back(self):
        self.assertEqual(slugify("!!!"), "kitap")


class CardKindsTest(unittest.TestCase):
    """--card-kinds: virgülle ayrılmış, izinli kart türleri."""

    def test_order_is_kept_and_spaces_are_trimmed(self):
        self.assertEqual(card_kinds(" tradeoff, explain "), ["tradeoff", "explain"])

    def test_empty_items_are_skipped(self):
        self.assertEqual(card_kinds("code,,contrast,"), ["code", "contrast"])

    def test_unknown_kind_is_rejected_by_name(self):
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "kod"):
            card_kinds("code,kod")

    def test_empty_list_is_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            card_kinds(" , ")


REQUIRED = ["--pdf", "kitap.pdf", "--title", "Demo Kitap", "--author", "Yazar", "--offset", "1", "--total", "2"]


class ParseArgsTest(unittest.TestCase):
    def test_card_kinds_default_to_all(self):
        self.assertEqual(parse_args(REQUIRED).card_kinds, ["explain", "contrast", "tradeoff", "code"])

    def test_card_kinds_can_be_chosen(self):
        chosen = parse_args(REQUIRED + ["--card-kinds", "tradeoff, explain"]).card_kinds
        self.assertEqual(chosen, ["tradeoff", "explain"])

    def test_unknown_card_kind_stops_the_command(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            parse_args(REQUIRED + ["--card-kinds", "code,kod"])


class RecordingPdfOpener:
    """PyMuPdfDocument.open gibi; açılan yolları kaydeder, sayfalar sahtedir."""

    def __init__(self):
        self.opened = []

    def __call__(self, path):
        self.opened.append(path)
        return FakePdfDocument(pages=[FakePdfPage() for _ in range(PAGE_COUNT)])


class _BookSetupTestCase(unittest.TestCase):
    """Sahte PDF'le yeni bir kitap projesi kurar; testi yoktur."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = self._write(os.path.join(self.tmp.name, "kaynak.pdf"), "%PDF sahte")
        self.target = os.path.join(self.tmp.name, "proje")
        self.opener = RecordingPdfOpener()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _write(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def _run(self, *extra, pdf=None):
        argv = ["--pdf", pdf or self.pdf, "--title", "Demo Kitap", "--author", "Yazar",
                "--offset", "1", "--total", "2", "--target", self.target, *extra]
        return BookSetup(parse_args(argv), self.opener).run()

    def _progress(self):
        with open(os.path.join(self.target, "progress.json"), encoding="utf-8") as handle:
            return json.load(handle)


class BookSetupTest(_BookSetupTestCase):
    def test_creates_project_skeleton(self):
        self._run()
        for name in ("index.html", "CLAUDE.md", "glossary.md", "progress.json", "data/toc.js",
                     "data/glossary.js", "js/reader.js", "css/reader.css", "book.pdf", ".gitignore"):
            self.assertTrue(os.path.exists(os.path.join(self.target, name)), name)

    def test_page_count_is_read_from_the_project_copy(self):
        self._run()
        self.assertEqual((self.opener.opened, self._progress()["pdf_total_pages"]),
                         ([os.path.join(self.target, "book.pdf")], PAGE_COUNT))

    def _run_with_pdf_inside(self):
        self._run(pdf=self._write(os.path.join(self.target, "kaynak", "kitap.pdf"), "%PDF sahte"))

    def test_pdf_inside_the_project_is_named_relative_to_it(self):
        self._run_with_pdf_inside()
        self.assertEqual(self._progress()["book_pdf"], os.path.join("kaynak", "kitap.pdf"))

    def test_pdf_inside_the_project_is_not_copied(self):
        self._run_with_pdf_inside()
        self.assertFalse(os.path.exists(os.path.join(self.target, "book.pdf")))

    def test_slug_comes_from_the_title(self):
        self._run()
        self.assertEqual(self._progress()["book"]["slug"], "demo-kitap")

    def test_chapters_come_from_the_given_table(self):
        chapters = self._write(os.path.join(self.tmp.name, "chapters.json"),
                               json.dumps([{"num": 1, "en": "One", "tr": "Bir", "start": 1}]))
        self._run("--chapters", chapters)
        self.assertEqual(self._progress()["chapters"][0]["en"], "One")

    def test_chapters_are_empty_without_a_table(self):
        self._run()
        self.assertEqual(self._progress()["chapters"], [])

    def test_card_kinds_default_to_all(self):
        self._run()
        self.assertEqual(self._progress()["concepts"], {"kinds": ["explain", "contrast", "tradeoff", "code"],
                                                        "code_comment_lang": "en"})

    def _text(self, name):
        with open(os.path.join(self.target, name), encoding="utf-8") as handle:
            return handle.read()

    def test_title_and_author_fill_the_reader_page(self):
        self._run()
        self.assertIn("Demo Kitap — Yazar", self._text("index.html"))

    def test_no_placeholder_is_left(self):
        self._run()
        self.assertEqual([name for name in ("index.html", "CLAUDE.md", "glossary.md") if "{{" in self._text(name)], [])

    def test_refuses_existing_project(self):
        self._run()
        with self.assertRaises(SystemExit):
            self._run()


class ReportTest(_BookSetupTestCase):
    def _report(self):
        project = self._run("--card-kinds", "tradeoff,explain")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            report(self.target, project)
        return output.getvalue().splitlines()

    def test_report_names_the_project_folder(self):
        self.assertEqual(self._report()[0], f"✓ Kitap projesi kuruldu: {self.target}")

    def test_report_describes_the_book(self):
        expected = ["  kitap: Demo Kitap — Yazar", f"  PDF: book.pdf ({PAGE_COUNT} sayfa), ofset 1, kitap 2 sayfa",
                    "  bölüm sayısı: 0", "  kart türleri: tradeoff, explain"]
        self.assertEqual(self._report()[1:1 + len(expected)], expected)

if __name__ == "__main__":
    unittest.main()
