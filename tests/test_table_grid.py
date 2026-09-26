"""Dolgu hücrelerinden sütun döşeme: sütun, hücrelerin sol kenarından en sık görülen sağ
kenarına uzanır."""
import unittest

from pdf_fakes import fill, span
from extraction.pdf.geometry import Box
from extraction.tables.table_grid import (EDGE_TOLERANCE, MIN_CELL_HEIGHT, MIN_CELL_WIDTH, WIDE_SPAN_RATIO, GridColumns,
                                          PageFills, RowBands)

TOP, BOTTOM = 100, 120
FIRST_LEFT, SECOND_LEFT, SECOND_RIGHT = 70, 170, 270
NEAR_EDGE = 120
TEXT_BOTTOM = 700
LOOSE_TOP, LOOSE_BOTTOM = 400, 420
STEP = 0.1
SPAN_HALF_WIDTH = 5
GAP_HALF_WIDTH = 10
INSIDE = 20                 # kenarın bu kadar içindeki parça ortası
FIRST_COLUMN, SECOND_COLUMN = 0, 1


def _cell(left, right):
    return Box(left, TOP, right, BOTTOM)


def _span_at(center):
    return span("x", (center - SPAN_HALF_WIDTH, TOP, center + SPAN_HALF_WIDTH, BOTTOM))


def _columns(*cells):
    return GridColumns.of_cells(list(cells))


class ColumnTilingTest(unittest.TestCase):
    def test_span_between_two_column_fills_is_outside_the_table(self):
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT - GAP_HALF_WIDTH),
                           _cell(SECOND_LEFT + GAP_HALF_WIDTH, SECOND_RIGHT))
        self.assertFalse(columns.is_table_row([_span_at(SECOND_LEFT)]))

    def test_column_after_a_gap_starts_at_the_next_fill(self):
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT - GAP_HALF_WIDTH),
                           _cell(SECOND_LEFT + GAP_HALF_WIDTH, SECOND_RIGHT))
        self.assertTrue(columns.is_table_row([_span_at(SECOND_LEFT + INSIDE)]))

    def test_most_common_right_edge_ends_the_column(self):
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, NEAR_EDGE),
                           _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertTrue(columns.is_table_row([_span_at(NEAR_EDGE + INSIDE)]))

    def test_tie_between_right_edges_takes_the_nearer_one(self):
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT), _cell(FIRST_LEFT, NEAR_EDGE),
                           _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertFalse(columns.is_table_row([_span_at(NEAR_EDGE + INSIDE)]))

    def test_fills_starting_within_the_edge_tolerance_share_a_column(self):
        """Sol kenarı birkaç kesir kayan dolgular aynı sütundandır; sütunu en sık sağ kenar bitirir."""
        near_left = FIRST_LEFT + EDGE_TOLERANCE / 2
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT), _cell(near_left, NEAR_EDGE), _cell(near_left, NEAR_EDGE),
                           _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertFalse(columns.is_table_row([_span_at(NEAR_EDGE + INSIDE)]))

    def test_span_centred_on_the_border_of_two_columns_is_in_the_table(self):
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertTrue(columns.is_table_row([_span_at(SECOND_LEFT)]))

    def test_column_of_a_span_outside_every_column_is_an_error(self):
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT - GAP_HALF_WIDTH),
                           _cell(SECOND_LEFT + GAP_HALF_WIDTH, SECOND_RIGHT))
        with self.assertRaises(ValueError):
            columns.column_of(_span_at(SECOND_LEFT))


class BandTest(unittest.TestCase):
    def test_spans_outside_every_band_are_not_in_the_same_band(self):
        below = span("x", (FIRST_LEFT, BOTTOM + GAP_HALF_WIDTH, FIRST_LEFT + INSIDE, BOTTOM + INSIDE))
        self.assertFalse(RowBands([(TOP, BOTTOM)]).same_band(below, below))


BAND_TOP, BAND_BOTTOM, LOWER_BAND_BOTTOM = 200, 220, 240
UPPER_TEXT, LOWER_TEXT = (202, 212), (230, 238)


def _bands_of(*fills):
    """İki sütunlu tablonun hücreleri ile verilen dolgulardan çıkan satır bantları."""
    cells = [_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT)]
    return RowBands.of_fills(GridColumns.of_cells(cells).band_fills(cells + list(fills)))


def _two_bands(lower_band_top):
    """İlk sütunun kenarlarına oturan iki dolgu, alttaki üsttekinin altına biniyor."""
    return _bands_of(Box(FIRST_LEFT, BAND_TOP, SECOND_LEFT, BAND_BOTTOM),
                     Box(FIRST_LEFT, lower_band_top, SECOND_LEFT, LOWER_BAND_BOTTOM))


def _text_between(top_bottom):
    top, bottom = top_bottom
    return span("x", (FIRST_LEFT, top, FIRST_LEFT + INSIDE, bottom))


class BandMergeTest(unittest.TestCase):
    """Üsttekine tolerans kadar binen dolgu yeni banttır; daha çok binen aynı bandı uzatır."""

    def test_fill_overlapping_by_the_tolerance_is_a_new_band(self):
        bands = _two_bands(BAND_BOTTOM - EDGE_TOLERANCE)
        self.assertFalse(bands.same_band(_text_between(UPPER_TEXT), _text_between(LOWER_TEXT)))

    def test_fill_overlapping_by_more_extends_the_band(self):
        bands = _two_bands(BAND_BOTTOM - EDGE_TOLERANCE - STEP)
        self.assertTrue(bands.same_band(_text_between(UPPER_TEXT), _text_between(LOWER_TEXT)))


class ColumnOfTest(unittest.TestCase):
    def test_span_centred_on_a_column_border_belongs_to_the_left_column(self):
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT))
        self.assertEqual(columns.column_of(_span_at(SECOND_LEFT)), FIRST_COLUMN)

    def test_span_belongs_to_the_column_of_its_centre(self):
        """Sol kenarı birinci sütunda olsa da ortası ikinci sütuna düşen parça ikinci sütundadır."""
        columns = _columns(_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT))
        across_the_border = span("x", (SECOND_LEFT - SPAN_HALF_WIDTH, TOP, SECOND_LEFT + INSIDE, BOTTOM))
        self.assertEqual(columns.column_of(across_the_border), SECOND_COLUMN)


def _two_columns():
    return _columns(_cell(FIRST_LEFT, SECOND_LEFT), _cell(SECOND_LEFT, SECOND_RIGHT))


def _span_centred_on(top):
    return span("x", (FIRST_LEFT, top - SPAN_HALF_WIDTH, FIRST_LEFT + INSIDE, top + SPAN_HALF_WIDTH))


def _with_band_fill(left, right):
    """BAND_TOP-BAND_BOTTOM arasında kenarları left ile right olan dolgunun bantları."""
    return _bands_of(Box(left, BAND_TOP, right, BAND_BOTTOM))


class InclusiveEdgeTest(unittest.TestCase):
    """Sütunun, bandın ve dolgu kenarı toleransının sınırları içeridedir."""

    def test_span_centred_on_the_table_left_edge_is_in_the_first_column(self):
        self.assertEqual(_two_columns().column_of(_span_at(FIRST_LEFT)), FIRST_COLUMN)

    def test_span_centred_on_the_band_top_is_in_the_band(self):
        self.assertTrue(RowBands([(TOP, BOTTOM)]).is_in_band(_span_centred_on(TOP)))

    def test_span_centred_just_above_the_band_is_outside(self):
        self.assertFalse(RowBands([(TOP, BOTTOM)]).is_in_band(_span_centred_on(TOP - STEP)))

    def test_fill_starting_the_tolerance_right_of_a_column_is_a_band(self):
        bands = _with_band_fill(FIRST_LEFT + EDGE_TOLERANCE, SECOND_LEFT)
        self.assertTrue(bands.is_in_band(_text_between(UPPER_TEXT)))

    def test_fill_starting_further_right_is_no_band(self):
        bands = _with_band_fill(FIRST_LEFT + EDGE_TOLERANCE + STEP, SECOND_LEFT)
        self.assertFalse(bands.is_in_band(_text_between(UPPER_TEXT)))

    def test_fill_ending_the_tolerance_right_of_a_column_is_a_band(self):
        bands = _with_band_fill(FIRST_LEFT, SECOND_LEFT + EDGE_TOLERANCE)
        self.assertTrue(bands.is_in_band(_text_between(UPPER_TEXT)))

    def test_fill_ending_further_right_is_no_band(self):
        bands = _with_band_fill(FIRST_LEFT, SECOND_LEFT + EDGE_TOLERANCE + STEP)
        self.assertFalse(bands.is_in_band(_text_between(UPPER_TEXT)))


def _span_of_width(width):
    centre = (FIRST_LEFT + SECOND_LEFT) / 2
    return span("x", (centre - width / 2, TOP, centre + width / 2, BOTTOM))


class WideSpanTest(unittest.TestCase):
    """Satırın parçası en geniş sütunun WIDE_SPAN_RATIO katı genişliğe kadar tabloya sığar."""
    LIMIT = (SECOND_LEFT - FIRST_LEFT) * WIDE_SPAN_RATIO

    def test_span_as_wide_as_the_limit_fits(self):
        self.assertTrue(_two_columns().is_table_row([_span_of_width(self.LIMIT)]))

    def test_wider_span_does_not_fit(self):
        self.assertFalse(_two_columns().is_table_row([_span_of_width(self.LIMIT + STEP)]))


class FilledColumnsTest(unittest.TestCase):
    def test_two_spans_in_one_column_fill_one_column(self):
        self.assertEqual(_two_columns().filled_columns([_span_at(FIRST_LEFT + INSIDE), _span_at(NEAR_EDGE)]), 1)


class RowInBandTest(unittest.TestCase):
    def test_row_with_one_span_in_a_band_is_in_the_band(self):
        bands = RowBands([(TOP, BOTTOM)])
        self.assertTrue(bands.in_band([_span_centred_on(TOP), _span_centred_on(BOTTOM + INSIDE)]))


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


BACKGROUND_BOTTOM = BOTTOM * 2
LOWER_BACKGROUND_BOTTOM = BACKGROUND_BOTTOM * 2
OVERLAP = MIN_CELL_HEIGHT


def _background_table():
    """Arka plan ve onun içindeki, ilk satırı dolduran iki hücre."""
    return [fill(FIRST_LEFT, TOP, SECOND_RIGHT, BACKGROUND_BOTTOM),
            fill(FIRST_LEFT, TOP, SECOND_LEFT, BOTTOM), fill(SECOND_LEFT, TOP, SECOND_RIGHT, BOTTOM)]


def _cell_across(edge):
    """İlk sütunda, yatay edge kenarının üstünden altına taşan hücre."""
    return fill(FIRST_LEFT, edge - OVERLAP / 2, SECOND_LEFT, edge + BOTTOM - TOP - OVERLAP / 2)


def _cells_across(edge):
    first = _cell_across(edge)
    return [first, fill(SECOND_LEFT, first.box.y0, SECOND_RIGHT, first.box.y1)]


def _boxes(drawings):
    return [drawing.box for drawing in drawings]


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

    def test_fill_only_overlapping_other_fills_is_not_a_background(self):
        """Arka plan dolguları içine alır; alt kenarından taşan dolgular onu arka plan yapmaz, o da hücredir."""
        overlapped = fill(FIRST_LEFT, TOP, SECOND_RIGHT, BACKGROUND_BOTTOM)
        groups = _groups(overlapped, *_cells_across(BACKGROUND_BOTTOM))
        self.assertIn(overlapped.box, [cell for group in groups for cell in group])

    def test_cell_reaching_out_of_the_background_is_a_table_of_its_own(self):
        table, across = _background_table(), _cell_across(BACKGROUND_BOTTOM)
        self.assertEqual(_groups(*table, across), [_boxes(table[1:]), [across.box]])

    def test_cells_reaching_out_of_the_background_reach_down_to_the_text_bottom(self):
        across = _cell_across(BACKGROUND_BOTTOM)
        fills = PageFills([*_background_table(), across], TEXT_BOTTOM)
        self.assertEqual(fills.extent([across.box]).y1, TEXT_BOTTOM)

    def test_cell_belongs_to_the_background_holding_it_not_to_one_it_overlaps(self):
        """Alttaki arka plan üsttekinin alt kenarına biner; ilk hücre sırası iki arka planın ortak şeridindedir."""
        upper = _background_table()
        lower_top = BACKGROUND_BOTTOM - OVERLAP
        lower = [fill(FIRST_LEFT, lower_top, SECOND_RIGHT, LOWER_BACKGROUND_BOTTOM),
                 *_cells_across(BACKGROUND_BOTTOM)]
        self.assertEqual(_groups(*upper, *lower), [_boxes(upper[1:]), _boxes(lower[1:])])


if __name__ == "__main__":
    unittest.main()
