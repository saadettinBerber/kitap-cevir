import argparse
import json
import os
import tempfile
import unittest
from unittest import mock

from pdf_fakes import FakePdfDocument, FakePdfPage
from init_book import BookSetup, card_kinds, parse_args, slugify

PAGE_COUNT = 3


def _open_pdf(path):
    """PyMuPdfDocument.open gibi; yol yalnız kopyanın yerini gösterir, sayfalar sahtedir."""
    return FakePdfDocument(pages=[FakePdfPage() for _ in range(PAGE_COUNT)], pdf_path=path)


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


class InitBookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "kaynak.pdf")
        with open(self.pdf, "wb") as pdf:
            pdf.write(b"%PDF sahte")
        self.target = os.path.join(self.tmp.name, "proje")
        chapters = [{"num": 1, "en": "One", "tr": "Bir", "start": 1}]
        self.chapters = os.path.join(self.tmp.name, "chapters.json")
        open(self.chapters, "w", encoding="utf-8").write(json.dumps(chapters))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, extra=()):
        argv = ["--pdf", self.pdf, "--title", "Demo Kitap", "--author", "Yazar",
                "--offset", "1", "--total", "2", "--chapters", self.chapters, "--target", self.target, *extra]
        return BookSetup(parse_args(argv), _open_pdf).run()

    def test_creates_project_skeleton(self):
        self._run()
        for name in ("index.html", "CLAUDE.md", "glossary.md", "progress.json", "data/toc.js",
                     "data/glossary.js", "js/reader.js", "css/reader.css", "book.pdf", ".gitignore"):
            self.assertTrue(os.path.exists(os.path.join(self.target, name)), name)
        progress = json.load(open(os.path.join(self.target, "progress.json"), encoding="utf-8"))
        self.assertEqual(progress["pdf_total_pages"], PAGE_COUNT)
        self.assertEqual(progress["book"]["slug"], "demo-kitap")
        self.assertEqual(progress["chapters"][0]["en"], "One")

    def test_card_kinds_default_to_all(self):
        self._run()
        progress = json.load(open(os.path.join(self.target, "progress.json"), encoding="utf-8"))
        self.assertEqual(progress["concepts"], {"kinds": ["explain", "contrast", "tradeoff", "code"],
                                                "code_comment_lang": "en"})

    def test_placeholders_are_filled(self):
        self._run()
        html = open(os.path.join(self.target, "index.html"), encoding="utf-8").read()
        self.assertIn("Demo Kitap — Yazar", html)
        self.assertNotIn("{{", html)
        self.assertNotIn("{{", open(os.path.join(self.target, "CLAUDE.md"), encoding="utf-8").read())

    def test_refuses_existing_project(self):
        self._run()
        with self.assertRaises(SystemExit):
            self._run()


if __name__ == "__main__":
    unittest.main()
