import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from backfill_images import ImagePlacement, PageImages

LARGE_PX, TINY_PX = 120, 10


def _para(text):
    return {"type": "para", "sentences": [{"en": text, "tr": text}]}


def _save_png(folder, name, side):
    fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, side, side), 0).save(os.path.join(folder, name))


class PageImagesTest(unittest.TestCase):
    def test_images_are_anchored_to_preceding_text_and_ornaments_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            _save_png(folder, "fig.png", LARGE_PX)
            _save_png(folder, "dot.png", TINY_PX)
            blocks = [_para("Layers separate concerns."), {"type": "image", "src": "fig.png"},
                      {"type": "code", "code": "x = 1"}, {"type": "image", "src": "dot.png"},
                      {"type": "image", "src": "missing.png"}]
            self.assertEqual(PageImages(blocks, folder).anchored(), [("fig.png", "layers separate concerns")])


class ImagePlacementTest(unittest.TestCase):
    def setUp(self):
        self.blocks = [{"type": "heading", "en": "Styles", "tr": "Tarzlar"},
                       _para("Layers separate concerns."), _para("Microservices are small.")]
        self.placement = ImagePlacement(self.blocks)

    def test_image_goes_below_the_matching_block(self):
        self.placement.add("fig.png", "layers separate concerns")
        self.assertEqual(self.blocks[2], {"type": "image", "src": "fig.png"})

    def test_unmatched_image_goes_below_page_headings(self):
        self.placement.add("fig.png", "")
        self.assertEqual(self.blocks[1], {"type": "image", "src": "fig.png"})

    def test_has_sees_only_images_already_on_the_page(self):
        self.assertFalse(self.placement.has("fig.png"))
        self.placement.add("fig.png", "")
        self.assertTrue(self.placement.has("fig.png"))


if __name__ == "__main__":
    unittest.main()
