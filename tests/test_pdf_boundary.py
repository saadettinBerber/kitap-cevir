"""PDF kütüphaneleri sınırının testleri (Bl.8 · Clean Boundaries): Box'ın
PyMuPDF Rect'iyle aynı davrandığı sınır koşulları."""
import unittest

import _paths  # noqa: F401
from extraction.pdf.geometry import Box


class BoxTest(unittest.TestCase):
    def test_union_ignores_an_empty_box(self):
        line, bar = Box(0, 0, 10, 10), Box(5, 20, 9, 20)
        self.assertEqual(line.union(bar), line)
        self.assertEqual(bar.union(line), line)

    def test_enclosing_spans_all_boxes(self):
        self.assertEqual(Box.enclosing([Box(0, 0, 1, 1), Box(5, 6, 7, 8)]), Box(0, 0, 7, 8))

    def test_point_on_right_or_bottom_edge_is_outside(self):
        box = Box(0, 0, 10, 10)
        self.assertEqual([box.contains_point(x, y) for x, y in [(0, 0), (10, 5), (5, 10), (9.99, 9.99)]],
                         [True, False, False, True])

    def test_touching_boxes_do_not_intersect(self):
        self.assertFalse(Box(0, 0, 10, 10).intersects(Box(10, 0, 20, 10)))
        self.assertTrue(Box(0, 0, 10, 10).intersects(Box(9, 9, 20, 20)))

    def test_vertical_gap_is_zero_when_overlapping(self):
        self.assertEqual(Box(0, 0, 10, 10).vertical_gap(Box(0, 5, 10, 20)), 0.0)
        self.assertEqual(Box(0, 0, 10, 10).vertical_gap(Box(0, 14, 10, 20)), 4)
        self.assertEqual(Box(0, 14, 10, 20).vertical_gap(Box(0, 0, 10, 10)), 4)

if __name__ == "__main__":
    unittest.main()
