"""Çıkarım ayarlarının varsayılanları ve kapalı desen ayarı."""
import unittest

import _paths  # noqa: F401
from extraction.settings import DEFAULT_EXTRACTION, optional_pattern, with_defaults

LINK = "Click here to view code image"


class DefaultsTest(unittest.TestCase):
    def test_book_setting_overrides_the_default(self):
        self.assertEqual(with_defaults({"running_header": "none"})["running_header"], "none")

    def test_missing_setting_takes_the_default(self):
        self.assertEqual(with_defaults({})["footer_zone_top"], DEFAULT_EXTRACTION["footer_zone_top"])


class OptionalPatternTest(unittest.TestCase):
    def test_empty_pattern_matches_nothing(self):
        self.assertNotRegex(LINK, optional_pattern(""))

    def test_empty_pattern_does_not_match_empty_text(self):
        self.assertNotRegex("", optional_pattern(""))

    def test_given_pattern_matches(self):
        self.assertRegex(LINK, optional_pattern(LINK))


if __name__ == "__main__":
    unittest.main()
