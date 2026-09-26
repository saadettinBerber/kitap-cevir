"""Kutu geometrisinin sınır koşulları: boş kutu, kenar payı, kapsama ve kesişmede kenarlar."""
import unittest

import _paths  # noqa: F401
from extraction.pdf import geometry
from extraction.pdf.geometry import Box

SIDE = 10
MIDDLE = SIDE / 2
SQUARE = Box(0, 0, SIDE, SIDE)
MARGIN = 2


class EmptyBoxTest(unittest.TestCase):
    def test_box_without_width_is_empty(self):
        self.assertTrue(geometry.is_empty(Box(MIDDLE, 0, MIDDLE, SIDE)))

    def test_box_without_height_is_empty(self):
        self.assertTrue(geometry.is_empty(Box(0, MIDDLE, SIDE, MIDDLE)))

    def test_box_with_an_area_is_not_empty(self):
        self.assertFalse(geometry.is_empty(SQUARE))


class ExpandedTest(unittest.TestCase):
    def test_margin_moves_every_edge_outwards(self):
        self.assertEqual(geometry.expanded(SQUARE, MARGIN), Box(-MARGIN, -MARGIN, SIDE + MARGIN, SIDE + MARGIN))


class ContainsTest(unittest.TestCase):
    def test_box_contains_itself(self):
        """Kenarlar içeride sayılır: kenarı kenarına denk gelen kutu kapsanır."""
        self.assertTrue(geometry.contains(SQUARE, SQUARE))

    def test_box_reaching_past_an_edge_is_not_contained(self):
        self.assertFalse(geometry.contains(SQUARE, Box(0, 0, SIDE + MARGIN, SIDE)))


class IntersectsTest(unittest.TestCase):
    def test_box_touching_from_the_right_does_not_intersect(self):
        self.assertFalse(geometry.intersects(Box(SIDE, 0, 2 * SIDE, SIDE), SQUARE))

    def test_box_touching_from_below_does_not_intersect(self):
        self.assertFalse(geometry.intersects(Box(0, SIDE, SIDE, 2 * SIDE), SQUARE))

    def test_empty_box_inside_does_not_intersect(self):
        self.assertFalse(geometry.intersects(SQUARE, Box(MIDDLE, MIDDLE, MIDDLE, MIDDLE)))


if __name__ == "__main__":
    unittest.main()
