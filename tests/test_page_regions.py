import unittest

from pdf_fakes import element
from extraction.page_regions import PageRegions, Region


def _element(name, top, bottom):
    return element(name, (70, top, 430, bottom))


def _region(kind, y0, y1):
    return Region({"y0": y0, "y1": y1}, {"type": kind, "name": f"{kind}@{y0}"})


def _names(layout_element):
    return [{"type": "para", "name": layout_element.text}]


class PageRegionsTest(unittest.TestCase):
    def test_elements_inside_a_region_become_its_single_block(self):
        regions = PageRegions([_region("code", 100, 200)])
        elements = [_element("a", 60, 80), _element("code-1", 110, 140), _element("code-2", 160, 190)]
        blocks = regions.place(elements, _names)
        self.assertEqual([block.get("name") for block in blocks], ["a", "code@100"])

    def test_standalone_math_is_placed_by_position(self):
        regions = PageRegions([_region("math", 300, 340)])
        elements = [_element("above", 180, 200), _element("below", 480, 500)]
        blocks = regions.place(elements, _names)
        self.assertEqual([block["name"] for block in blocks], ["above", "math@300", "below"])

    def test_unmatched_standalone_region_goes_to_the_end(self):
        regions = PageRegions([_region("math", 700, 740)])
        blocks = regions.place([_element("body", 180, 200)], _names)
        self.assertEqual([block["name"] for block in blocks], ["body", "math@700"])

    def test_standalone_regions_above_an_element_come_in_page_order(self):
        regions = PageRegions([_region("math", 300, 340), _region("math", 200, 240)])
        blocks = regions.place([_element("below", 480, 500)], _names)
        self.assertEqual([block["name"] for block in blocks], ["math@200", "math@300", "below"])

    def test_standalone_region_covering_an_element_takes_its_place(self):
        regions = PageRegions([_region("math", 100, 200)])
        elements = [_element("above", 60, 80), _element("inside", 110, 190), _element("below", 300, 320)]
        blocks = regions.place(elements, _names)
        self.assertEqual([block["name"] for block in blocks], ["above", "math@100", "below"])

    def test_element_half_inside_a_region_is_covered(self):
        blocks = PageRegions([_region("code", 100, 200)]).place([_element("half", 180, 220)], _names)
        self.assertEqual([block["name"] for block in blocks], ["code@100"])

    def test_element_less_than_half_inside_a_region_is_not_covered(self):
        blocks = PageRegions([_region("code", 100, 200)]).place([_element("edge", 181, 221)], _names)
        self.assertEqual([block["name"] for block in blocks], ["edge"])

    def test_code_overlapping_a_table_is_not_a_region(self):
        layout = {"code_blocks": [{"y0": 110, "y1": 150, "code": "x"}, {"y0": 400, "y1": 420, "code": "y"}]}
        table = {"y0": 100, "y1": 200, "block": {"type": "table"}}
        regions = PageRegions.from_layout(layout, [table], lambda code: {"type": "code", "code": code["code"]})
        self.assertEqual([region.block["type"] for region in regions.regions], ["table", "code"])
        self.assertEqual(regions.regions[1].block["code"], "y")


if __name__ == "__main__":
    unittest.main()
