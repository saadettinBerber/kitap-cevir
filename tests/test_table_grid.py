"""Dolgu hücrelerinden sütun döşeme: sütun, hücrelerin sol kenarından en sık görülen sağ kenarına uzanır."""
import unittest

from pdf_fakes import span
from extraction.pdf.geometry import Box
from extraction.tables.table_grid import TableGrid

TOP, BOTTOM = 100, 120
FIRST_LEFT, SECOND_LEFT, SECOND_RIGHT = 70, 170, 270
NEAR_EDGE = 120
SPAN_HALF_WIDTH = 5


def _cell(left, right):
    return Box(left, TOP, right, BOTTOM)


def _span_at(center):
    return span("x", (center - SPAN_HALF_WIDTH, TOP, center + SPAN_HALF_WIDTH, BOTTOM))


def _grid(*cells):
    return TableGrid.from_cells(list(cells), list(cells))


class ColumnTilingTest(unittest.TestCase):
    def test_span_between_two_column_fills_is_outside_the_table(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT - 10), _cell(SECOND_LEFT + 10, SECOND_RIGHT))
        self.assertFalse(grid.is_table_row([_span_at(SECOND_LEFT)]))

    def test_column_after_a_gap_starts_at_the_next_fill(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT - 10), _cell(SECOND_LEFT + 10, SECOND_RIGHT))
        self.assertTrue(grid.is_table_row([_span_at(SECOND_LEFT + 20)]))

    def test_most_common_right_edge_ends_the_column(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, NEAR_EDGE),
                     _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertTrue(grid.is_table_row([_span_at(NEAR_EDGE + 20)]))

    def test_tie_between_right_edges_takes_the_nearer_one(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, NEAR_EDGE), _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertFalse(grid.is_table_row([_span_at(NEAR_EDGE + 20)]))


if __name__ == "__main__":
    unittest.main()
