import unittest

import _paths  # noqa: F401
from page_regions import PageRegions, Region

PAGE_HEIGHT = 800


def _element(name, bottom, top):
    return {"type": "paragraph", "content": name, "bounding box": [70, bottom, 430, top]}


def _region(kind, y0, y1):
    """Üst orijinli bölge; ODL'de bottom = 800 - y1, top = 800 - y0."""
    return Region({"y0": y0, "y1": y1}, PAGE_HEIGHT, {"type": kind, "name": f"{kind}@{y0}"})


def _names(element):
    return [{"type": "para", "name": element["content"]}]


class PageRegionsTest(unittest.TestCase):
    def test_elements_inside_a_region_become_its_single_block(self):
        regions = PageRegions([_region("code", 100, 200)])
        elements = [_element("a", 720, 740), _element("code-1", 660, 690), _element("code-2", 610, 640)]
        blocks = regions.place(elements, _names)
        self.assertEqual([block.get("name") for block in blocks], ["a", "code@100"])

    def test_standalone_math_is_placed_by_position(self):
        regions = PageRegions([_region("math", 300, 340)])
        elements = [_element("above", 600, 620), _element("below", 300, 320)]
        blocks = regions.place(elements, _names)
        self.assertEqual([block["name"] for block in blocks], ["above", "math@300", "below"])

    def test_unmatched_standalone_region_goes_to_the_end(self):
        regions = PageRegions([_region("math", 700, 740)])
        blocks = regions.place([_element("body", 600, 620)], _names)
        self.assertEqual([block["name"] for block in blocks], ["body", "math@700"])

    def test_code_overlapping_a_table_is_not_a_region(self):
        layout = {"page_height": PAGE_HEIGHT,
                  "code_blocks": [{"y0": 110, "y1": 150, "code": "x"}, {"y0": 400, "y1": 420, "code": "y"}]}
        table = {"y0": 100, "y1": 200, "block": {"type": "table"}}
        regions = PageRegions.from_layout(layout, [table], lambda code: {"type": "code", "code": code["code"]})
        self.assertEqual([region.block["type"] for region in regions.regions], ["table", "code"])
        self.assertEqual(regions.regions[1].block["code"], "y")


if __name__ == "__main__":
    unittest.main()
