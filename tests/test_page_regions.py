"""Sayfa bölgelerinin okuma sırasına yerleşimi. Şeritler üst orijinlidir; öğe ve bölge
sayfa genişliğindedir, bloğun adı ya öğenin metni ya da bölgenin türü@üst kenarıdır."""
import unittest

from pdf_fakes import element
from extraction.page_regions import PageRegions, Region

LEFT, RIGHT = 70, 430


class _Strip:
    """Sayfanın bir yatay şeridi; üzerine öğe ya da bölge kurulur."""

    def __init__(self, top, bottom):
        self._top, self._bottom = top, bottom

    def element(self, name):
        return element(name, (LEFT, self._top, RIGHT, self._bottom))

    def item(self, kind):
        """Metin katmanının bulduğu bölge: {y0, y1, block}."""
        return {"y0": self._top, "y1": self._bottom, "block": {"type": kind, "name": f"{kind}@{self._top}"}}

    def region(self, kind):
        return Region(self.item(kind))


HIGH = _Strip(60, 80)
REGION = _Strip(100, 200)
REGION_TOP_HALF = _Strip(110, 140)
REGION_BOTTOM_HALF = _Strip(160, 190)
HALF_INSIDE_REGION = _Strip(180, 220)
LESS_THAN_HALF_INSIDE_REGION = _Strip(181, 221)
BELOW_REGION = _Strip(300, 320)
OVERLAPPING_REGION_BOTTOM = _Strip(190, 260)
TOUCHING_REGION_BOTTOM = _Strip(200, 260)
INSIDE_OVERLAPPING = _Strip(210, 250)
UPPER_MIDDLE = _Strip(200, 240)
MIDDLE = _Strip(300, 340)
JUST_BELOW_MIDDLE = _Strip(340, 360)
LOW = _Strip(480, 500)
BOTTOM = _Strip(700, 740)


def _names(layout_element):
    return [{"type": "para", "name": layout_element.text}]


def _placed(regions, *elements):
    return [block["name"] for block in regions.place(list(elements), _names)]


class PageRegionsTest(unittest.TestCase):
    def test_elements_inside_a_region_become_its_single_block(self):
        regions = PageRegions([REGION.region("code")])
        placed = _placed(regions, HIGH.element("a"), REGION_TOP_HALF.element("code-1"), REGION_BOTTOM_HALF.element("code-2"))
        self.assertEqual(placed, ["a", "code@100"])

    def test_standalone_math_is_placed_by_position(self):
        regions = PageRegions([MIDDLE.region("math")])
        placed = _placed(regions, UPPER_MIDDLE.element("above"), LOW.element("below"))
        self.assertEqual(placed, ["above", "math@300", "below"])

    def test_unmatched_standalone_region_goes_to_the_end(self):
        regions = PageRegions([BOTTOM.region("math")])
        self.assertEqual(_placed(regions, UPPER_MIDDLE.element("body")), ["body", "math@700"])

    def test_standalone_regions_above_an_element_come_in_page_order(self):
        regions = PageRegions([MIDDLE.region("math"), UPPER_MIDDLE.region("math")])
        self.assertEqual(_placed(regions, LOW.element("below")), ["math@200", "math@300", "below"])

    def test_standalone_region_covering_an_element_takes_its_place(self):
        regions = PageRegions([REGION.region("math")])
        placed = _placed(regions, HIGH.element("above"), REGION_TOP_HALF.element("inside"), BELOW_REGION.element("below"))
        self.assertEqual(placed, ["above", "math@100", "below"])

    def test_element_half_inside_a_region_is_covered(self):
        regions = PageRegions([REGION.region("code")])
        self.assertEqual(_placed(regions, HALF_INSIDE_REGION.element("half")), ["code@100"])

    def test_element_less_than_half_inside_a_region_is_not_covered(self):
        regions = PageRegions([REGION.region("code")])
        self.assertEqual(_placed(regions, LESS_THAN_HALF_INSIDE_REGION.element("edge")), ["edge"])

    def test_standalone_region_ending_at_an_element_top_comes_before_it(self):
        regions = PageRegions([MIDDLE.region("math")])
        self.assertEqual(_placed(regions, JUST_BELOW_MIDDLE.element("below")), ["math@300", "below"])

    def test_first_region_covering_an_element_takes_its_place(self):
        regions = PageRegions([REGION.region("table"), REGION.region("code")])
        self.assertEqual(_placed(regions, REGION_TOP_HALF.element("inside")), ["table@100"])

    def test_code_touching_a_table_is_a_region(self):
        regions = PageRegions.of([REGION.item("table")], [TOUCHING_REGION_BOTTOM.item("code")])
        self.assertEqual(_placed(regions, TOUCHING_REGION_BOTTOM.element("under the code")), ["code@200"])

    def test_code_overlapping_a_table_is_not_a_region(self):
        regions = PageRegions.of([REGION.item("table")], [OVERLAPPING_REGION_BOTTOM.item("code")])
        self.assertEqual(_placed(regions, INSIDE_OVERLAPPING.element("under the code")), ["under the code"])

    def test_code_apart_from_tables_is_a_region(self):
        regions = PageRegions.of([REGION.item("table")], [LOW.item("code")])
        self.assertEqual(_placed(regions, LOW.element("under the code")), ["code@480"])


if __name__ == "__main__":
    unittest.main()
