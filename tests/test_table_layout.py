import os
import tempfile
import unittest

import fitz

from pdf_fakes import element, real_page
from extraction.odl_elements import OdlElements
from extraction.settings import with_defaults
from extraction.tables.table_scan import TableScanner

COLUMNS = [(72, 140), (140, 432)]
HEADER_TOP = 100
ROW_HEIGHT = 14
WRAP_HEIGHT = 10           # hücre içi sarma satırı: satır arası boşluktan küçük
SECOND_TABLE_TOP = 400
SETTINGS = {"table_row_gap_ratio": 1.1, "footer_zone_top": 52}


def _cell(page, column, top, text, size=9, shaded=False):
    left, right = column
    if shaded:
        page.draw_rect(fitz.Rect(left, top, right, top + ROW_HEIGHT), color=None, fill=(0.85, 0.85, 0.85))
    page.insert_text(fitz.Point(left + 4, top + 10), text, fontsize=size,
                     fontname="helvetica-bold" if shaded else "helvetica")


def _table(page, top, terms):
    """Yalnız başlığı dolgulu tablo: gövde satırları metin boşluğundan ayrılır."""
    for column, text in zip(COLUMNS, ("Term", "Definition")):
        _cell(page, column, top, text, shaded=True)
    for index, (term, definition) in enumerate(terms):
        row_top = top + ROW_HEIGHT * (index + 1)
        _cell(page, COLUMNS[0], row_top, term)
        _cell(page, COLUMNS[1], row_top, definition)
    return top + ROW_HEIGHT * (len(terms) + 1)


def _rule(page, top):
    for left, right in COLUMNS:
        page.draw_line(fitz.Point(left, top), fitz.Point(right, top), width=0.6)


def _pdf_with(build, settings=SETTINGS):
    tmp = tempfile.TemporaryDirectory()
    path = os.path.join(tmp.name, "t.pdf")
    document = fitz.open()
    build(document.new_page())
    document.save(path)
    document.close()
    with real_page(path) as page:
        return tmp, TableScanner(with_defaults(settings)).scan(page)


class SeparateTablesTest(unittest.TestCase):
    """Aynı sayfadaki iki tablo aynı sol kenardan başlar; ortak kenar onları
    tek tablo yapmamalı."""

    def _two_tables(self, page):
        _rule(page, _table(page, HEADER_TOP, [("Configurability", "Change aspects.")]) + 4)
        _rule(page, _table(page, SECOND_TABLE_TOP, [("Accessibility", "Access for all users.")]) + 4)

    def test_two_tables_stay_separate(self):
        tmp, tables = _pdf_with(self._two_tables)
        with tmp:
            self.assertEqual(len(tables), 2)
            self.assertEqual([t["block"]["rows"][1][0]["en"] for t in tables],
                             ["Configurability", "Accessibility"])


class RowGapTest(unittest.TestCase):
    """Bantsız gövdede satırları metin boşluğu ayırır; eşik kitaba göre gelir."""

    def _wrapped(self, page):
        bottom = _table(page, HEADER_TOP, [("Archivability", "Will the data need to be archived"),
                                           ("Authentication", "Security requirements for users")])
        _rule(page, bottom + 4)

    def test_rows_split_with_book_specific_ratio(self):
        tmp, tables = _pdf_with(self._wrapped)
        with tmp:
            self.assertEqual(len(tables[0]["block"]["rows"]), 3)

    def test_default_ratio_would_not_split_this_typesetting(self):
        tmp, tables = _pdf_with(self._wrapped, settings={"footer_zone_top": 52})
        with tmp:
            self.assertLess(len(tables[0]["block"]["rows"]), 3)


class TableEndTest(unittest.TestCase):
    """Tablo alt kenar çizgisinde biter; altındaki caption ve gövde metni
    tabloya girmemeli."""

    def _table_then_text(self, page):
        bottom = _table(page, HEADER_TOP, [("Availability", "How long the system is available")])
        _rule(page, bottom + 4)
        page.insert_text(fitz.Point(72, bottom + 30), "Table 4-1. Operational characteristics", fontsize=9)
        page.insert_text(fitz.Point(72, bottom + 60), "Body text that follows the table.", fontsize=10.5)

    def test_text_below_the_rule_is_outside(self):
        tmp, tables = _pdf_with(self._table_then_text)
        with tmp:
            cells = [c["en"] for row in tables[0]["block"]["rows"] for c in row]
            self.assertEqual(len(tables[0]["block"]["rows"]), 2)
            self.assertNotIn("Table 4-1. Operational characteristics", cells)


class NestedListTest(unittest.TestCase):
    """ODL caption'ı liste sanıp sonrasını maddenin altına (children) gömebilir."""

    BOX = (70, 100, 430, 120)

    def _list_with_kids(self):
        kids = (element("Term Definition Configurability", self.BOX, font_size=9.0),
                element("Cross-Cutting", self.BOX, "heading", font_size=15.8))
        item = element("Table 4-2. Structural characteristics", self.BOX, "list item", font_size=10.0, children=kids)
        return element("", self.BOX, "list", is_ordered=True, list_items=(item,))

    def test_nested_content_returns_to_the_stream(self):
        flat = OdlElements([self._list_with_kids()]).flatten_nested_lists().items
        self.assertEqual([e.kind for e in flat], ["list item", "paragraph", "heading"])
        self.assertEqual(flat[0].text, "Table 4-2. Structural characteristics")
        self.assertTrue(all(e.is_nested for e in flat))

    def test_plain_list_is_untouched(self):
        items = (element("first", self.BOX, "list item"), element("second", self.BOX, "list item"))
        plain = element("", self.BOX, "list", list_items=items)
        self.assertEqual(OdlElements([plain]).flatten_nested_lists().items, [plain])


if __name__ == "__main__":
    unittest.main()
