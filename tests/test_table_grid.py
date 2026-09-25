"""Dolgu hücrelerinden sütun döşeme: sütun, hücrelerin sol kenarından en sık görülen sağ
kenarına uzanır."""
import unittest

from pdf_fakes import fill, span
from extraction.pdf.geometry import Box
from extraction.tables.table_grid import EDGE_TOLERANCE, MIN_CELL_HEIGHT, MIN_CELL_WIDTH, PageFills, TableGrid

TOP, BOTTOM = 100, 120
FIRST_LEFT, SECOND_LEFT, SECOND_RIGHT = 70, 170, 270
NEAR_EDGE = 120
TEXT_BOTTOM = 700
STEP = 0.1
SPAN_HALF_WIDTH = 5
GAP_HALF_WIDTH = 10
INSIDE = 20                 # kenarın bu kadar içindeki parça ortası


def _cell(left, right):
    return Box(left, TOP, right, BOTTOM)


def _span_at(center):
    return span("x", (center - SPAN_HALF_WIDTH, TOP, center + SPAN_HALF_WIDTH, BOTTOM))


def _grid(*cells):
    return TableGrid.from_cells(list(cells), list(cells))


class ColumnTilingTest(unittest.TestCase):
    def test_span_between_two_column_fills_is_outside_the_table(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT - GAP_HALF_WIDTH), _cell(SECOND_LEFT + GAP_HALF_WIDTH, SECOND_RIGHT))
        self.assertFalse(grid.is_table_row([_span_at(SECOND_LEFT)]))

    def test_column_after_a_gap_starts_at_the_next_fill(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT - GAP_HALF_WIDTH), _cell(SECOND_LEFT + GAP_HALF_WIDTH, SECOND_RIGHT))
        self.assertTrue(grid.is_table_row([_span_at(SECOND_LEFT + INSIDE)]))

    def test_most_common_right_edge_ends_the_column(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, NEAR_EDGE),
                     _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertTrue(grid.is_table_row([_span_at(NEAR_EDGE + INSIDE)]))

    def test_tie_between_right_edges_takes_the_nearer_one(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, NEAR_EDGE), _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertFalse(grid.is_table_row([_span_at(NEAR_EDGE + INSIDE)]))

    def test_fills_starting_within_the_edge_tolerance_share_a_column(self):
        """Sol kenarı birkaç kesir kayan dolgular aynı sütundandır; sütunu en sık sağ kenar bitirir."""
        near_left = FIRST_LEFT + EDGE_TOLERANCE / 2
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT), _cell(near_left, NEAR_EDGE), _cell(near_left, NEAR_EDGE),
                     _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertFalse(grid.is_table_row([_span_at(NEAR_EDGE + INSIDE)]))

    def test_span_centred_on_the_border_of_two_columns_is_in_the_table(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertTrue(grid.is_table_row([_span_at(SECOND_LEFT)]))


class BandTest(unittest.TestCase):
    def test_spans_outside_every_band_are_not_in_the_same_band(self):
        grid = TableGrid([(FIRST_LEFT, SECOND_LEFT), (SECOND_LEFT, SECOND_RIGHT)], [(TOP, BOTTOM)])
        below = span("x", (FIRST_LEFT, BOTTOM + GAP_HALF_WIDTH, FIRST_LEFT + INSIDE, BOTTOM + INSIDE))
        self.assertFalse(grid.same_band(below, below))


def _groups(*fills):
    return PageFills(list(fills), TEXT_BOTTOM).table_groups()


class FillSizeTest(unittest.TestCase):
    """Hücre sayılan dolgu en az MIN_CELL_WIDTH genişliğinde ve MIN_CELL_HEIGHT yüksekliğindedir."""

    def test_fill_of_the_least_cell_size_is_a_cell(self):
        self.assertEqual(len(_groups(fill(0, 0, MIN_CELL_WIDTH, MIN_CELL_HEIGHT))), 1)

    def test_narrower_fill_is_not_a_cell(self):
        self.assertEqual(_groups(fill(0, 0, MIN_CELL_WIDTH - STEP, MIN_CELL_HEIGHT)), [])

    def test_lower_fill_is_not_a_cell(self):
        self.assertEqual(_groups(fill(0, 0, MIN_CELL_WIDTH, MIN_CELL_HEIGHT - STEP)), [])


class BackgroundTest(unittest.TestCase):
    def test_fill_holding_a_single_fill_is_not_a_background(self):
        """Arka plan en az iki dolguyu içine alır; kendisi sayılmaz. Kenar paylaşmayan iki hücre iki kümedir."""
        outer = fill(FIRST_LEFT, TOP, SECOND_RIGHT, BOTTOM * 2)
        inner = fill(FIRST_LEFT + GAP_HALF_WIDTH, TOP, NEAR_EDGE, BOTTOM)
        self.assertEqual(len(_groups(outer, inner)), 2)


if __name__ == "__main__":
    unittest.main()
