"""Sayfanın çizim katmanından çizgisiz (dolgulu hücreli) tabloları bulur.

OpenDataLoader tabloları yalnız kenarlık çizgilerinden tanır; e-kitap kökenli
PDF'lerde hücreler zebra dolgu dikdörtgenleriyle çizilir ve tablo paragraf
yığınına dönüşür. Izgara (sütunlar, bantlar) table_grid'den gelir; burada
metin parçaları satırlara ve hücrelere dağıtılır. Koordinatlar üst orijinlidir.
"""
import dataclasses
import itertools

from extraction.tables.aligned_tables import AlignedTableFinder
from extraction.tables.table_cell import SUPERSCRIPT_RATIO
from extraction.tables.table_grid import MIN_COLUMNS, PageFills

MIN_ROWS = 2
MIN_MULTILINE_CELLS = 2      # bu kadar hücresi çok satırlı satırın hücre içi satırları liste niteliğindedir
CORNER_TOLERANCE = 1         # parçanın sol üst köşesi tablo alanının bu kadar dışında kalabilir


class TableRow:
    """Tablonun bir satırındaki parçalar; ızgaraya göre hücrelere dağıtılır."""

    def __init__(self, spans, grid):
        self._spans = spans
        self._grid = grid
        self._main_size = max(span.size for span in spans)

    @property
    def top(self):
        return min(span.box.y0 for span in self._spans)

    @property
    def bottom(self):
        return max(span.box.y1 for span in self._spans)

    def is_bold(self):
        body = [s for s in self._spans if s.size >= self._main_size * SUPERSCRIPT_RATIO]
        return all("bold" in s.font.lower() for s in body)

    def is_in_band(self):
        return self._grid.in_band(self._spans)

    def fits(self):
        """Parçaların hepsi bir sütuna düşüyor ve hiçbiri sütundan belirgin geniş değil mi?"""
        return self._grid.is_table_row(self._spans)

    def filled_columns(self):
        return self._grid.filled_columns(self._spans)

    def header_cells(self):
        return [cell.unit(row_keeps_breaks=False) for cell in self._cells()]

    def body_cells(self):
        cells = self._cells()
        keeps_breaks = self._has_aligned_sublines(cells)
        return [cell.unit(keeps_breaks) for cell in cells]

    def _cells(self):
        return self._grid.cells_of(self._spans, self._main_size)

    @staticmethod
    def _has_aligned_sublines(cells):
        """İki ya da daha çok sütun çok satırlıysa hücre içi satırlar liste
        niteliğinde olabilir; sarılmış metin ayrıca elenir."""
        return sum(1 for cell in cells if cell.is_multiline()) >= MIN_MULTILINE_CELLS


class TableBuilder:
    """Bir hücre kümesinden (tek tablo) satırları, başlığı ve hücreleri kurar."""

    def __init__(self, page_spans, fills, row_gap_ratio):
        self.page_spans = page_spans
        self.fills = fills
        self.row_gap_ratio = row_gap_ratio

    def tables_in(self, cells):
        """Kümedeki tablo [{y0, y1, block}] olarak; tablo değilse boş liste."""
        grid = self.fills.grid_of(cells)
        if not grid.has_columns():
            return []
        rows = self._table_rows(self._group_rows(self._spans_within(self.fills.extent(cells)), grid), grid)
        if len(rows) < MIN_ROWS:
            return []
        header_rows = self._header_count(rows)
        block = {"type": "table", "header_rows": header_rows,
                 "rows": [row.header_cells() if index < header_rows else row.body_cells()
                          for index, row in enumerate(rows)]}
        return [{"y0": min(row.top for row in rows), "y1": max(row.bottom for row in rows), "block": block}]

    def _spans_within(self, area):
        return [s for s in self.page_spans if area.contains_point(s.box.x0 + CORNER_TOLERANCE, s.box.y0 + CORNER_TOLERANCE)]

    def _group_rows(self, spans, grid):
        rows, previous = [], None
        for span in spans:
            if self._starts_row(span, previous, grid):
                rows.append([])
            rows[-1].append(span)
            previous = span
        return [TableRow(row, grid) for row in rows]

    def _starts_row(self, span, previous, grid):
        """Bant varsa satırı bant belirler; bantsız gövdede satır arası boşluk satır
        içi sarma boşluğundan büyüktür. Eşik kitaba göre değişir: bir kitapta satır
        içi 1.2 / satırlar arası 1.6, başkasında 0.93 / 1.26 ölçüldü."""
        if previous is None:
            return True
        if grid.is_in_band(span) or grid.is_in_band(previous):
            return not grid.same_band(span, previous)
        return span.box.y0 - previous.box.y0 > previous.box.height * self.row_gap_ratio

    @staticmethod
    def _table_rows(rows, grid):
        """Bantlar varsa ilk bant öncesi (caption) atılır; tablo ilk tablo dışı
        satırda (gövde metni, dipnot) biter. Baştaki/sondaki tek sütunlu satırlar
        tablo dışı metindir (kaynak notu vb.)."""
        if grid.has_bands():
            rows = list(itertools.dropwhile(lambda row: not row.is_in_band(), rows))
        return TableBuilder._without_single_column_edges(list(itertools.takewhile(TableRow.fits, rows)))

    @staticmethod
    def _without_single_column_edges(rows):
        while rows and rows[0].filled_columns() < MIN_COLUMNS:
            rows = rows[1:]
        while rows and rows[-1].filled_columns() < MIN_COLUMNS:
            rows = rows[:-1]
        return rows

    @staticmethod
    def _header_count(rows):
        count = 0
        while count < len(rows) and rows[count].is_bold():
            count += 1
        return count


class TableScanner:
    """Sayfadaki dolgu tabanlı ve çizgisiz sütun hizalı tabloları bulur."""

    def __init__(self, settings):
        self.footer_zone_top = settings["footer_zone_top"]
        self.row_gap_ratio = settings["table_row_gap_ratio"]

    def scan(self, page):
        """[{y0, y1, block}], sayfada yukarıdan aşağıya."""
        return sorted(self._tables_on(page), key=lambda table: table["y0"])

    def _tables_on(self, page):
        """Dolgulu hücre varsa tabloyu onlar belirler; hizalı tarama yalnız dolgusuz
        sayfada çalışır ki aynı tablo iki kez yakalanmasın."""
        body_bottom = page.height - self.footer_zone_top
        fills = PageFills(page.drawings(), body_bottom)
        spans = self._page_spans(page)
        if fills.is_empty():
            return AlignedTableFinder.of_spans([span for span in spans if span.box.y1 <= body_bottom]).tables()
        builder = TableBuilder(spans, fills, self.row_gap_ratio)
        return [table for cells in fills.table_groups() for table in builder.tables_in(cells)]

    @staticmethod
    def _page_spans(page):
        """Satır anahtarı tam sayıya yuvarlanır: aynı satırın parçaları küsuratta ayrışabilir."""
        spans = [dataclasses.replace(span, text=span.text.strip(), line_y=round(span.line_y))
                 for line in page.text_lines() for span in line]
        return sorted(spans, key=lambda s: (s.line_y, s.box.x0))
