import unittest

import _paths  # noqa: F401
from extraction.settings import DEFAULT_EXTRACTION
from progress import CARD_KINDS, InvalidConceptSettings, Progress


class SettingsTest(unittest.TestCase):
    def test_extraction_merges_over_defaults(self):
        merged = Progress({"extraction": {"code_font_prefix": "Consolas"}}).extraction_settings()
        self.assertEqual(merged["code_font_prefix"], "Consolas")
        self.assertEqual(merged["footnote_max_size"], DEFAULT_EXTRACTION["footnote_max_size"])

    def test_book_info_has_fallback_slug(self):
        self.assertEqual(Progress({}).book_info()["slug"], "kitap")

    def test_concepts_default_allows_every_kind(self):
        self.assertEqual(Progress({}).concepts_settings(),
                         {"kinds": list(CARD_KINDS), "code_langs": ["java"], "code_comment_lang": "en"})

    def test_code_langs_follow_book_language(self):
        merged = Progress({"extraction": {"default_code_language": "python"}}).concepts_settings()
        self.assertEqual(merged["code_langs"], ["python"])

    def test_kinds_override_default(self):
        merged = Progress({"concepts": {"kinds": ["tradeoff", "explain"]}}).concepts_settings()
        self.assertEqual(merged["kinds"], ["tradeoff", "explain"])

    def test_legacy_mode_maps_to_kinds(self):
        self.assertEqual(Progress({"concepts": {"mode": "code"}}).concepts_settings()["kinds"], ["code"])
        self.assertNotIn("mode", Progress({"concepts": {"mode": "contrast"}}).concepts_settings())

    def test_unknown_mode_or_kind_raises(self):
        for concepts in ({"mode": "kod"}, {"kinds": ["kod"]}, {"kinds": []}):
            with self.assertRaises(InvalidConceptSettings):
                Progress({"concepts": concepts}).concepts_settings()


if __name__ == "__main__":
    unittest.main()
