import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from backfill_images import ImageFolder, ImagePlacement, PageImages

LARGE_PX, TINY_PX = 120, 10
ANCHOR = "layers separate concerns"


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
            self.assertEqual(PageImages(blocks, ImageFolder(folder)).anchored(), [("fig.png", "layers separate concerns")])


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



class AnchorMatchTest(unittest.TestCase):
    """Çapa, blok metninin başıyla karşılaştırılır; etiket ve büyük harf sayılmaz."""

    def _placed_at(self, anchor, *texts):
        blocks = [{"type": "heading", "en": "Styles", "tr": "Tarzlar"}] + [_para(text) for text in texts]
        ImagePlacement(blocks).add("fig.png", anchor)
        return blocks.index({"type": "image", "src": "fig.png"})

    def test_markup_is_ignored(self):
        text = '<a href="chapter-4.html#layered-architecture">Layers</a> separate concerns'
        self.assertEqual(self._placed_at(ANCHOR, text, "Other."), 2)

    def test_case_is_ignored(self):
        self.assertEqual(self._placed_at(ANCHOR, "LAYERS SEPARATE CONCERNS", "Other."), 2)

    def test_long_block_matches_by_its_beginning(self):
        """PDF'teki çapa önceki bloğun ilk ANCHOR_CHARS harfidir; çevrilmiş blok ise paragrafın tamamı."""
        text = "Layers separate concerns. " + "Each layer talks only to the one below it. " * 5
        self.assertEqual(self._placed_at(ANCHOR, "Other.", text), 3)

    def test_similarity_at_the_threshold_matches(self):
        """11 ortak harf / 40 harf: oran 2 × 11 / 40 = 0.55."""
        self.assertEqual(self._placed_at("a" * 11 + "b" * 9, "Other.", "a" * 11 + "c" * 9), 3)

    def test_similarity_below_the_threshold_does_not_match(self):
        """10 ortak harf / 40 harf: oran 0.5."""
        self.assertEqual(self._placed_at("a" * 10 + "b" * 10, "Other.", "a" * 10 + "c" * 10), 1)

    def test_unmatched_image_on_a_page_of_headings_goes_last(self):
        blocks = [{"type": "heading", "en": "Styles", "tr": "Tarzlar"}]
        ImagePlacement(blocks).add("fig.png", "")
        self.assertEqual(blocks[-1], {"type": "image", "src": "fig.png"})

if __name__ == "__main__":
    unittest.main()
