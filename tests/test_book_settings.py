import unittest

import _paths  # noqa: F401
from book_settings import CARD_KINDS, BookSettings, InvalidConceptSettings
from extraction.settings import DEFAULT_EXTRACTION


class BookSettingsTest(unittest.TestCase):
    def test_extraction_merges_over_defaults(self):
        merged = BookSettings({"extraction": {"code_font_prefix": "Consolas"}}).extraction()
        self.assertEqual(merged["code_font_prefix"], "Consolas")
        self.assertEqual(merged["footnote_max_size"], DEFAULT_EXTRACTION["footnote_max_size"])

    def test_book_info_has_fallback_slug(self):
        self.assertEqual(BookSettings({}).book()["slug"], "kitap")

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
        self.assertEqual(BookSettings({"concepts": {"mode": "code"}}).concepts()["kinds"], ["code"])
        self.assertNotIn("mode", BookSettings({"concepts": {"mode": "contrast"}}).concepts())

    def test_unknown_mode_or_kind_raises(self):
        for concepts in ({"mode": "kod"}, {"kinds": ["kod"]}, {"kinds": []}):
            with self.assertRaises(InvalidConceptSettings):
                BookSettings({"concepts": concepts}).concepts()


if __name__ == "__main__":
    unittest.main()
