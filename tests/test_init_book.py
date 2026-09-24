import argparse
import json
import os
import tempfile
import unittest
from unittest import mock

from pdf_fakes import FakePdfDocument, FakePdfPage
from init_book import BookSetup, card_kinds, parse_args, slugify

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
        self.assertEqual(parse_args(REQUIRED + ["--card-kinds", "tradeoff, explain"]).card_kinds, ["tradeoff", "explain"])

    def test_unknown_card_kind_stops_the_command(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            parse_args(REQUIRED + ["--card-kinds", "code,kod"])


def _open_pdf(path):
    """PyMuPdfDocument.open gibi; yol yalnız kopyanın yerini gösterir, sayfalar sahtedir."""
    return FakePdfDocument(pages=[FakePdfPage() for _ in range(PAGE_COUNT)], pdf_path=path)


class BookSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = self._write(os.path.join(self.tmp.name, "kaynak.pdf"), "%PDF sahte")
        self.target = os.path.join(self.tmp.name, "proje")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _write(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def _run(self, *extra):
        argv = ["--pdf", self.pdf, "--title", "Demo Kitap", "--author", "Yazar",
                "--offset", "1", "--total", "2", "--target", self.target, *extra]
        return BookSetup(parse_args(argv), _open_pdf).run()

    def _progress(self):
        with open(os.path.join(self.target, "progress.json"), encoding="utf-8") as handle:
            return json.load(handle)

    def test_creates_project_skeleton(self):
        self._run()
        for name in ("index.html", "CLAUDE.md", "glossary.md", "progress.json", "data/toc.js",
                     "data/glossary.js", "js/reader.js", "css/reader.css", "book.pdf", ".gitignore"):
            self.assertTrue(os.path.exists(os.path.join(self.target, name)), name)

    def test_page_count_comes_from_the_pdf(self):
        self._run()
        self.assertEqual(self._progress()["pdf_total_pages"], PAGE_COUNT)

    def test_slug_comes_from_the_title(self):
        self._run()
        self.assertEqual(self._progress()["book"]["slug"], "demo-kitap")

    def test_chapters_come_from_the_given_table(self):
        chapters = self._write(os.path.join(self.tmp.name, "chapters.json"),
                               json.dumps([{"num": 1, "en": "One", "tr": "Bir", "start": 1}]))
        self._run("--chapters", chapters)
        self.assertEqual(self._progress()["chapters"][0]["en"], "One")

    def test_card_kinds_default_to_all(self):
        self._run()
        self.assertEqual(self._progress()["concepts"], {"kinds": ["explain", "contrast", "tradeoff", "code"],
                                                        "code_comment_lang": "en"})

    def test_placeholders_are_filled(self):
        self._run()
        with open(os.path.join(self.target, "index.html"), encoding="utf-8") as html:
            text = html.read()
        self.assertIn("Demo Kitap — Yazar", text)
        self.assertNotIn("{{", text)
        with open(os.path.join(self.target, "CLAUDE.md"), encoding="utf-8") as claude_md:
            self.assertNotIn("{{", claude_md.read())

    def test_refuses_existing_project(self):
        self._run()
        with self.assertRaises(SystemExit):
            self._run()

if __name__ == "__main__":
    unittest.main()
