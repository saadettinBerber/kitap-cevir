import unittest

import _paths  # noqa: F401
from book_settings import CARD_KINDS, DEFAULT_BOOK, BookSettings, InvalidConceptSettings
from extraction.settings import DEFAULT_EXTRACTION


class BookSettingsTest(unittest.TestCase):
    def test_configured_extraction_setting_wins(self):
        merged = BookSettings({"extraction": {"code_font_prefix": "Consolas"}}).extraction()
        self.assertEqual(merged["code_font_prefix"], "Consolas")

    def test_unconfigured_extraction_setting_has_its_default(self):
        merged = BookSettings({"extraction": {"code_font_prefix": "Consolas"}}).extraction()
        self.assertEqual(merged["footnote_max_size"], DEFAULT_EXTRACTION["footnote_max_size"])

    def test_book_info_has_fallback_slug(self):
        self.assertEqual(BookSettings({}).book()["slug"], "kitap")

    def test_configured_slug_names_the_book(self):
        self.assertEqual(BookSettings({"book": {"slug": "demo"}}).slug(), "demo")

    def test_unconfigured_slug_is_the_fallback(self):
        self.assertEqual(BookSettings({}).slug(), DEFAULT_BOOK["slug"])

    def test_translator_reads_images_by_default(self):
        self.assertTrue(BookSettings({}).translator_has_vision())

    def test_translator_without_vision_is_configured(self):
        self.assertFalse(BookSettings({"translator": {"vision": False}}).translator_has_vision())

    def test_concepts_default_allows_every_kind(self):
        self.assertEqual(BookSettings({}).concepts(),
                         {"kinds": list(CARD_KINDS), "code_langs": ["java"], "code_comment_lang": "en"})

    def test_code_langs_follow_book_language(self):
        merged = BookSettings({"extraction": {"default_code_language": "python"}}).concepts()
        self.assertEqual(merged["code_langs"], ["python"])

    def test_kinds_override_default(self):
        merged = BookSettings({"concepts": {"kinds": ["tradeoff", "explain"]}}).concepts()
        self.assertEqual(merged["kinds"], ["tradeoff", "explain"])

    def test_legacy_mode_maps_to_kinds(self):
        self.assertEqual(BookSettings({"concepts": {"mode": "contrast"}}).concepts()["kinds"], ["contrast", "code"])

    def test_legacy_mode_is_not_passed_on(self):
        self.assertNotIn("mode", BookSettings({"concepts": {"mode": "contrast"}}).concepts())

    def test_explicit_kinds_win_over_legacy_mode(self):
        merged = BookSettings({"concepts": {"mode": "code", "kinds": ["tradeoff"]}}).concepts()
        self.assertEqual(merged["kinds"], ["tradeoff"])

    def test_unknown_legacy_mode_is_refused(self):
        with self.assertRaises(InvalidConceptSettings):
            BookSettings({"concepts": {"mode": "kod"}}).concepts()

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(InvalidConceptSettings):
            BookSettings({"concepts": {"kinds": ["kod"]}}).concepts()

    def test_empty_kind_list_is_refused(self):
        with self.assertRaises(InvalidConceptSettings):
            BookSettings({"concepts": {"kinds": []}}).concepts()


if __name__ == "__main__":
    unittest.main()
