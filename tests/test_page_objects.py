import os
import tempfile
import unittest

from pdf_fakes import span
from extraction.chapter_opener import ChapterOpener
from extraction.pdf.geometry import Box
from extraction.tables.table_grid import TableGrid
from extraction.tables.table_cell import TableCell
from extraction.text_layer.layout_scan import CodeImageLinkLines, CodeListing, ProseRepairs
from page_document import PageDocument


class _Line:
    """TextLine'ın satır nesnelerinin (CodeListing, ProseRepairs, CodeImageLinkLines) gördüğü yüzü."""

    def __init__(self, text, top=0.0, left=0.0, is_code=False):
        self.text, self.top, self.left, self.is_code = text, top, left, is_code
        self.height, self.bottom, self.char_width, self.spans = 10.0, top + 10.0, 6.0, []

    def uses_script_layout(self):
        return False


class PageDocumentTest(unittest.TestCase):
    PAGE = {"id": "page-2", "page": 2, "context": {"prev_tail": "gizli"},
            "blocks": [{"type": "heading", "en": "H", "tr": "B"},
                       {"type": "table", "rows": [[{"en": "a", "tr": ""}, {"en": "b", "tr": "b"}]]},
                       {"type": "code", "code": "x"}]}

    def test_text_units_skip_code_and_count_missing(self):
        page = PageDocument(self.PAGE)
        self.assertEqual([unit["en"] for unit in page.text_units()], ["H", "a", "b"])
        self.assertEqual(page.missing_translations(), 1)

    def test_write_drops_private_fields_and_reads_back(self):
        with tempfile.TemporaryDirectory() as pages_dir:
            path = PageDocument(self.PAGE).write(os.path.join(pages_dir, "page-2.js"))
            self.assertEqual(os.path.basename(path), "page-2.js")
            self.assertNotIn("context", PageDocument.read(path).data)


class ChapterOpenerTest(unittest.TestCase):
    def test_number_title_and_author_become_one_block(self):
        blocks = [{"type": "chapter_number", "num": 3}, {"type": "chapter", "en": "Modularity"},
                  {"type": "para", "sentences": [{"en": "by Jane Doe"}]}]
        self.assertEqual(ChapterOpener(blocks).merged(),
                         [{"type": "chapter", "en": "Modularity", "num": 3, "author": "by Jane Doe"}])


class TableGridTest(unittest.TestCase):
    CELLS = [Box(70, 100, 170, 120), Box(170, 100, 400, 120),
             Box(70, 140, 170, 160), Box(170, 140, 400, 160)]

    def test_columns_are_tiled_from_cell_edges(self):
        grid = TableGrid.from_cells(self.CELLS, self.CELLS)
        self.assertEqual(grid.columns, [(70, 170), (170, 400)])
        self.assertTrue(grid.has_columns())

    def test_span_is_placed_by_its_center(self):
        grid = TableGrid([(70, 170), (170, 400)], [])
        self.assertEqual(grid.column_of(span("x", (180, 100, 220, 110))), 1)


class TableCellTest(unittest.TestCase):
    @staticmethod
    def _span(text, line_y, size=10.0, x1=160.0):
        return span(text, (72, line_y, x1, line_y + size), size=size)

    def test_small_trailing_span_becomes_superscript(self):
        cell = TableCell([self._span("Latency", 100), self._span("a", 100, size=6)], (70, 170), 10.0)
        self.assertEqual(cell.unit(row_keeps_breaks=False), {"en": "Latency<sup>a</sup>", "html": True})

    def test_short_lines_keep_breaks_when_row_asks(self):
        cell = TableCell([self._span("one", 100, x1=90), self._span("two", 112, x1=90)], (70, 170), 10.0)
        self.assertEqual(cell.unit(row_keeps_breaks=True), {"en": "one<br>two", "html": True})


class LayoutObjectsTest(unittest.TestCase):
    def test_code_listing_keeps_indent_and_blank_line(self):
        lines = [_Line("def f():", top=100, left=72, is_code=True),
                 _Line("return 1", top=112, left=84, is_code=True),
                 _Line("x = f()", top=140, left=72, is_code=True)]
        [listing] = CodeListing.group(lines)
        self.assertEqual(listing.region()["code"], "def f():\n  return 1\n\nx = f()")

    def test_hyphen_split_name_is_repaired(self):
        repairs = ProseRepairs([_Line("published by McGraw-"), _Line("Hill in 2019.")])
        self.assertEqual(repairs.hyphenated_names(), {"McGrawHill": "McGraw-Hill"})


class CodeImageLinkLinesTest(unittest.TestCase):
    """E-kitabın kod görseli bağlantısı bir satırdır; şeridi komşu satırlara kadar uzanır."""

    LINK = "Click here to view code image"

    def test_link_slot_reaches_the_neighbouring_lines(self):
        lines = [_Line("prose", top=40), _Line(self.LINK, top=60), _Line("// code", top=80, is_code=True)]
        self.assertEqual(CodeImageLinkLines(lines, self.LINK).slots(), [{"text": self.LINK, "y0": 50, "y1": 80}])

    def test_link_without_neighbours_keeps_its_own_height(self):
        self.assertEqual(CodeImageLinkLines([_Line(self.LINK, top=60)], self.LINK).slots(),
                         [{"text": self.LINK, "y0": 60, "y1": 70}])

    def test_line_quoting_the_link_in_prose_is_not_a_link(self):
        lines = [_Line(f"you will see a “{self.LINK}” link", top=60)]
        self.assertEqual(CodeImageLinkLines(lines, self.LINK).slots(), [])

    def test_no_links_without_a_pattern(self):
        self.assertEqual(CodeImageLinkLines([_Line(self.LINK, top=60)], "").slots(), [])


if __name__ == "__main__":
    unittest.main()
