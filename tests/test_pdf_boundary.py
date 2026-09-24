"""PDF kütüphaneleri sınırının testleri (Bl.8 · Clean Boundaries): Box'ın
PyMuPDF Rect'iyle aynı davrandığı sınır koşulları ve PyMuPDF adaptörünün
öğrenme testleri."""
import os
import tempfile
import unittest

import fitz

from pdf_fakes import real_page
from extraction.pdf.geometry import Box

PNG_SIGNATURE = b"\x89PNG"


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


def _write_pdf(path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text(fitz.Point(72, 100), "Top line", fontsize=11, fontname="helvetica")
    page.insert_text(fitz.Point(72, 700), "Bottom line", fontsize=11, fontname="helvetica")
    page.insert_text(fitz.Point(72, 400), "   ", fontsize=11, fontname="helvetica")
    page.draw_rect(fitz.Rect(72, 200, 300, 230), color=None, fill=(0.9, 0.9, 0.9))
    page.draw_line(fitz.Point(72, 300), fitz.Point(300, 300), width=0.6)
    document.save(path)
    document.close()


class PyMuPdfAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "a.pdf")
        _write_pdf(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lines_are_top_left_and_blank_spans_do_not_cross(self):
        with real_page(self.pdf) as page:
            texts = [[s.text for s in line] for line in page.text_lines()]
            top, bottom = (line[0] for line in page.text_lines())
        self.assertEqual(texts, [["Top line"], ["Bottom line"]])
        self.assertLess(top.box.y0, 100)
        self.assertEqual(top.line_y, top.box.y0)
        self.assertGreater(bottom.box.y0, 600)

    def test_page_knows_where_it_comes_from(self):
        with real_page(self.pdf) as page:
            self.assertEqual((page.pdf_path, page.number, page.height), (self.pdf, 1, 842))

    def test_fill_and_line_are_told_apart(self):
        with real_page(self.pdf) as page:
            drawings = page.drawings()
        self.assertEqual([d.is_filled for d in drawings], [True, False])
        self.assertEqual(drawings[0].box, Box(72, 200, 300, 230))
        self.assertTrue(drawings[1].box.is_empty())

    def test_clip_text_and_png(self):
        with real_page(self.pdf) as page:
            self.assertEqual(page.text_in(Box(60, 80, 300, 110)).strip(), "Top line")
            self.assertTrue(page.png(Box(60, 80, 300, 110), 72).startswith(PNG_SIGNATURE))

if __name__ == "__main__":
    unittest.main()
