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
LOOSE_TOP, LOOSE_BOTTOM = 400, 420
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

    def test_column_of_a_span_outside_every_column_is_an_error(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT - GAP_HALF_WIDTH), _cell(SECOND_LEFT + GAP_HALF_WIDTH, SECOND_RIGHT))
        with self.assertRaises(ValueError):
            grid.column_of(_span_at(SECOND_LEFT))


class BandTest(unittest.TestCase):
    def test_spans_outside_every_band_are_not_in_the_same_band(self):
        grid = TableGrid([(FIRST_LEFT, SECOND_LEFT), (SECOND_LEFT, SECOND_RIGHT)], [(TOP, BOTTOM)])
        below = span("x", (FIRST_LEFT, BOTTOM + GAP_HALF_WIDTH, FIRST_LEFT + INSIDE, BOTTOM + INSIDE))
        self.assertFalse(grid.same_band(below, below))


BAND_TOP, BAND_BOTTOM, LOWER_BAND_BOTTOM = 200, 220, 240
UPPER_TEXT, LOWER_TEXT = (202, 212), (230, 238)


def _banded_grid(lower_band_top):
    """İki sütun; ilk sütunun kenarlarına oturan iki dolgu, alttaki üsttekinin altına biniyor."""
    cells = [_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT)]
    bands = [Box(FIRST_LEFT, BAND_TOP, SECOND_LEFT, BAND_BOTTOM),
             Box(FIRST_LEFT, lower_band_top, SECOND_LEFT, LOWER_BAND_BOTTOM)]
    return TableGrid.from_cells(cells, cells + bands)


def _text_between(top_bottom):
    top, bottom = top_bottom
    return span("x", (FIRST_LEFT, top, FIRST_LEFT + INSIDE, bottom))


class BandMergeTest(unittest.TestCase):
    """Üsttekine tolerans kadar binen dolgu yeni banttır; daha çok binen aynı bandı uzatır."""

    def test_fill_overlapping_by_the_tolerance_is_a_new_band(self):
        grid = _banded_grid(BAND_BOTTOM - EDGE_TOLERANCE)
        self.assertFalse(grid.same_band(_text_between(UPPER_TEXT), _text_between(LOWER_TEXT)))

    def test_fill_overlapping_by_more_extends_the_band(self):
        grid = _banded_grid(BAND_BOTTOM - EDGE_TOLERANCE - STEP)
        self.assertTrue(grid.same_band(_text_between(UPPER_TEXT), _text_between(LOWER_TEXT)))


class ColumnOfTest(unittest.TestCase):
    def test_span_centred_on_a_column_border_belongs_to_the_left_column(self):
        grid = _grid(_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertEqual(grid.column_of(_span_at(SECOND_LEFT)), 0)


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

    def test_cells_outside_the_background_reach_down_to_the_text_bottom(self):
        """Sayfada arka planlı bir tablonun yanında arka plansız hücreler de var: arka plan
        yalnız kendi hücrelerinin sınırıdır."""
        background = fill(FIRST_LEFT, TOP, SECOND_RIGHT, BOTTOM * 2)
        inside = [fill(FIRST_LEFT, TOP, SECOND_LEFT, BOTTOM), fill(SECOND_LEFT, TOP, SECOND_RIGHT, BOTTOM)]
        loose = [fill(FIRST_LEFT, LOOSE_TOP, SECOND_LEFT, LOOSE_BOTTOM),
                 fill(SECOND_LEFT, LOOSE_TOP, SECOND_RIGHT, LOOSE_BOTTOM)]
        fills = PageFills([background, *inside, *loose], TEXT_BOTTOM)
        self.assertEqual(fills.extent([cell.box for cell in loose]).y1, TEXT_BOTTOM)


if __name__ == "__main__":
    unittest.main()
