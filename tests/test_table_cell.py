"""Tablo hücresinin satır sonları: yalnız liste niteliğindeki çok satırlı hücreler satır sonlarını korur."""
import unittest

from pdf_fakes import span
from extraction.tables.table_cell import TableCell

COLUMN = (70, 170)
MAIN_SIZE = 10.0


class WrappedProseTest(unittest.TestCase):
    def test_single_line_cell_stays_plain_text_when_the_row_keeps_breaks(self):
        cell = TableCell([span("one", (72, 100, 90, 110))], COLUMN, MAIN_SIZE)
        self.assertEqual(cell.unit(row_keeps_breaks=True), {"en": "one"})


if __name__ == "__main__":
    unittest.main()
