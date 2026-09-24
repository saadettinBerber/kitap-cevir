import os
import tempfile
import unittest

import fitz

from pdf_fakes import real_page
from extraction.equations.math_scan import MathScanner
from extraction.settings import with_defaults

SETTINGS = {"math_geometry": True}
COLUMN_LEFT = 72
COLUMN_RIGHT = 432
BAR_Y = 208
BAR_LEFT, BAR_RIGHT = 106, 125
PROSE_Y = 260


def _fraction(page):
    """A = ma / mc: pay, payda ve aralarındaki kesir çizgisi."""
    page.insert_text(fitz.Point(87, BAR_Y - 6), "A =", fontsize=10, fontname="helvetica")
    page.insert_text(fitz.Point(BAR_LEFT, BAR_Y - 6), "ma", fontsize=10, fontname="helvetica")
    page.draw_line(fitz.Point(BAR_LEFT, BAR_Y), fitz.Point(BAR_RIGHT, BAR_Y), width=0.6)
    page.insert_text(fitz.Point(BAR_LEFT, BAR_Y + 11), "mc", fontsize=10, fontname="helvetica")


TABLE_RULE_Y = 400
TABLE_RULE_SPLIT = 246


def _table_rule(page, segmented):
    """Kenarlık tek çizgi ya da (e-kitap dizgisinde olduğu gibi) aynı hizada
    parçalar hâlinde çizilir."""
    stops = [COLUMN_LEFT, TABLE_RULE_SPLIT, COLUMN_RIGHT] if segmented else [COLUMN_LEFT, COLUMN_RIGHT]
    for left, right in zip(stops, stops[1:]):
        page.draw_line(fitz.Point(left, TABLE_RULE_Y), fitz.Point(right, TABLE_RULE_Y), width=0.6)


def _make_pdf(path, table_rule):
    document = fitz.open()
    page = document.new_page()
    _fraction(page)
    page.insert_text(fitz.Point(COLUMN_LEFT, PROSE_Y), "In the equation, ma represents abstract elements.",
                     fontsize=10.5, fontname="helvetica")
    if table_rule:
        _table_rule(page, segmented=table_rule == "segmented")
    document.save(path)
    document.close()


def _scan(table_rule=None, settings=SETTINGS):
    tmp = tempfile.TemporaryDirectory()
    pdf = os.path.join(tmp.name, "m.pdf")
    _make_pdf(pdf, table_rule)
    with real_page(pdf) as page:
        return tmp, MathScanner(with_defaults(settings), page, os.path.join(tmp.name, "images")).scan()


class GeometryMathTest(unittest.TestCase):
    """Type3 fontu olmayan kitaplarda denklemi kesir çizgisi ele verir."""

    def test_fraction_becomes_one_math_block(self):
        tmp, result = _scan()
        with tmp:
            self.assertEqual(len(result["display"]), 1)
            self.assertEqual(result["display"][0]["block"]["type"], "math")

    def test_region_covers_both_sides_of_the_bar(self):
        tmp, result = _scan()
        with tmp:
            text = result["display"][0]["block"]["text"]
            for part in ("A =", "ma", "mc"):
                self.assertIn(part, text)

    def test_body_text_below_stays_outside(self):
        tmp, result = _scan()
        with tmp:
            region = result["display"][0]
            self.assertLess(region["y1"], PROSE_Y - 10)
            self.assertNotIn("represents", result["display"][0]["block"]["text"])

    def test_full_width_rule_is_not_a_fraction_bar(self):
        tmp, result = _scan(table_rule="single")
        with tmp:
            self.assertEqual(len(result["display"]), 1)

    def test_segmented_table_rule_is_not_a_fraction_bar(self):
        """Kenarlığın sütun kenarından başlamayan parçası tek başına kesir
        çizgisine benzer; test hizanın tamamına bakılmasını korur."""
        tmp, result = _scan(table_rule="segmented")
        with tmp:
            self.assertEqual(len(result["display"]), 1)

    def test_detection_is_off_by_default(self):
        tmp, result = _scan(settings={})
        with tmp:
            self.assertEqual(result["display"], [])


if __name__ == "__main__":
    unittest.main()
