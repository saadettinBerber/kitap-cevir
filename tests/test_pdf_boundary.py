"""PDF kütüphaneleri sınırının testleri (Bl.8 · Clean Boundaries): Box'ın
PyMuPDF Rect'iyle aynı davrandığı sınır koşulları, PyMuPDF adaptörünün
öğrenme testleri ve ODL ağacının `LayoutElement`e çevrilmesi."""
import importlib.util
import os
import tempfile
import unittest

import fitz

from pdf_fakes import FakeLayoutReader, FakePdfPage, element, real_page, span
from extraction.page_extractor import PageExtractor
from extraction.pdf.geometry import Box
from extraction.pdf.odl_adapter import OdlLayoutReader, OdlTree
from extraction.pdf.pymupdf_adapter import PyMuPdfDocument, image_size
from extraction.pdf.readers import InvalidLayoutReader, layout_reader_for
from extraction.settings import with_defaults

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

    def test_baseline_is_the_insertion_point_inside_the_box(self):
        with real_page(self.pdf) as page:
            top = page.text_lines()[0][0]
        self.assertEqual(top.baseline, 100)
        self.assertLess(top.box.y0, top.baseline)
        self.assertLess(top.baseline, top.box.y1)

    def test_plain_text_follows_reading_order(self):
        with real_page(self.pdf) as page:
            self.assertEqual(page.text().split(), ["Top", "line", "Bottom", "line"])

    def test_document_counts_its_pages(self):
        with PyMuPdfDocument.open(self.pdf) as document:
            self.assertEqual(document.page_count, 1)

    def test_document_reads_the_plain_text_of_a_page(self):
        with PyMuPdfDocument.open(self.pdf) as document:
            self.assertEqual(document.page_text(1).split(), ["Top", "line", "Bottom", "line"])

    def test_document_metadata_is_a_dict_even_when_empty(self):
        with PyMuPdfDocument.open(self.pdf) as document:
            self.assertIsInstance(document.metadata, dict)

    def test_page_knows_where_it_comes_from(self):
        with real_page(self.pdf) as page:
            self.assertEqual((page.pdf_path, page.number, page.width, page.height), (self.pdf, 1, 595, 842))

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

    def test_image_size_is_read_in_pixels(self):
        path = os.path.join(self.tmp.name, "clip.png")
        with real_page(self.pdf) as page, open(path, "wb") as png:
            png.write(page.png(Box(0, 0, 144, 72), 72))
        self.assertEqual(image_size(path), (144, 72))


def _write_code_line_pdf(path):
    """Kod satırı: '10' üstünde küçük '23', aynı taban çizgisinde uzakta '236 days'."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text(fitz.Point(72, 100), "(3 x 10", fontsize=11, fontname="courier")
    page.insert_text(fitz.Point(120, 95), "23", fontsize=7, fontname="courier")
    page.insert_text(fitz.Point(132, 100), ") =", fontsize=11, fontname="courier")
    page.insert_text(fitz.Point(200, 100), "236 days", fontsize=11, fontname="courier")
    document.save(path)
    document.close()


class PyMuPdfLineGroupingTest(unittest.TestCase):
    """Sahte sayfaların satır dizilişi bu davranışa dayanır (test_layout_scan)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "code.pdf")
        _write_code_line_pdf(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    def _lines(self):
        with real_page(self.pdf) as page:
            return page.text_lines()

    def test_raised_script_shares_the_line_with_its_own_baseline(self):
        first = self._lines()[0]
        self.assertEqual([(s.text, s.baseline) for s in first], [("(3 x 10", 100), ("23", 95), (") =", 100)])

    def test_far_piece_on_the_same_baseline_is_a_line_of_its_own(self):
        self.assertEqual([[s.text for s in line] for line in self._lines()], [["(3 x 10", "23", ") ="], ["236 days"]])


class OdlTreeTest(unittest.TestCase):
    """ODL'nin sol-alt orijinli ağacı, Java çalıştırmadan çevrilir."""

    HEIGHT = 800

    def _layout(self, *kids):
        return OdlTree({"kids": list(kids)}, self.HEIGHT).layout()

    def test_box_is_flipped_to_top_left(self):
        [paragraph] = self._layout({"type": "paragraph", "content": "x", "bounding box": [70, 500, 430, 520]}).elements
        self.assertEqual(paragraph.box, Box(70, 280, 430, 300))

    def test_missing_box_sits_on_the_page_bottom(self):
        [paragraph] = self._layout({"type": "paragraph", "content": "x"}).elements
        self.assertEqual((paragraph.box.y0, paragraph.box.y1), (self.HEIGHT, self.HEIGHT))

    def test_nested_kids_are_flattened_in_reading_order(self):
        tree = {"type": "section", "kids": [{"type": "heading", "content": "H", "font size": 18},
                                            {"type": "paragraph", "content": None}]}
        heading, paragraph = self._layout(tree).elements
        self.assertEqual((heading.kind, heading.font_size), ("heading", 18))
        self.assertEqual((paragraph.kind, paragraph.text, paragraph.font_size), ("paragraph", "", 0))

    def test_list_items_keep_their_children(self):
        kid = {"type": "paragraph", "content": "buried"}
        odl_list = {"type": "list", "numbering style": "arabic numbers",
                    "list items": [{"type": "list item", "content": "one", "kids": [kid]}]}
        [layout_list] = self._layout(odl_list).elements
        self.assertTrue(layout_list.is_ordered)
        self.assertEqual(layout_list.list_items[0].children[0].text, "buried")

    def test_table_cells_join_their_texts(self):
        cell = {"kids": [{"content": "Alpha"}, {"content": "beta"}]}
        [table] = self._layout({"type": "table", "rows": [{"cells": [cell, {"kids": []}]}]}).elements
        self.assertEqual(table.table_rows, (("Alpha beta", ""),))

    def test_image_keeps_only_the_file_name(self):
        [image] = self._layout({"type": "image", "source": "/tmp/work/page-3_images/imageFile1.png"}).elements
        self.assertEqual(image.image_file, "imageFile1.png")


class ReplaceableLayoutReaderTest(unittest.TestCase):
    """Düzen okuyucusu ve sayfa dışarıdan verilir; test ne PDF açar ne ODL (Java) çalıştırır."""

    def test_extraction_runs_on_a_fake_page(self):
        page = FakePdfPage(lines=[(span("Top line.", (72, 90, 300, 104), size=11),)])
        reader = FakeLayoutReader([element("Top line.", (72, 90, 300, 104), font_size=11)])
        settings = with_defaults({"running_header": "none"})
        with tempfile.TemporaryDirectory() as images:
            extracted = PageExtractor(settings, reader).extract(page, images)
        self.assertEqual(extracted["blocks"], [{"type": "para", "sentences": [{"en": "Top line."}]}])
        self.assertIsNone(extracted["running_header"])


class LayoutReaderChoiceTest(unittest.TestCase):
    """extraction.layout_reader okuyucuyu seçer; yanlış ad kurulumda reddedilir."""

    def test_unknown_reader_is_rejected_with_the_choices(self):
        with self.assertRaisesRegex(InvalidLayoutReader, "odl \\| liteparse"):
            layout_reader_for({"layout_reader": "pdfminer"})

    def test_odl_is_the_default(self):
        self.assertIsInstance(PageExtractor.for_settings(with_defaults({})).layout_reader, OdlLayoutReader)

    @unittest.skipUnless(importlib.util.find_spec("liteparse"), "liteparse kurulu değil")
    def test_liteparse_is_chosen_by_name(self):
        reader = layout_reader_for({"layout_reader": "liteparse"})
        self.assertEqual(type(reader).__name__, "LiteParseLayoutReader")


if __name__ == "__main__":
    unittest.main()
