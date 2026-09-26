"""Sayfanın çizim katmanından çizgisiz (dolgulu hücreli) tabloları bulur.

OpenDataLoader tabloları yalnız kenarlık çizgilerinden tanır; e-kitap kökenli
PDF'lerde hücreler zebra dolgu dikdörtgenleriyle çizilir ve tablo paragraf
yığınına dönüşür. Izgara (sütunlar, bantlar) table_grid'den gelir; burada
metin parçaları satırlara ve hücrelere dağıtılır. Koordinatlar üst orijinlidir.
"""
import dataclasses
import itertools

from extraction.pdf import geometry
from extraction.tables.aligned_tables import AlignedTableFinder
from extraction.tables.table_cell import SUPERSCRIPT_RATIO
from extraction.tables.table_grid import GridColumns, PageFills

MIN_ROWS = 2
MIN_COLUMNS = 2              # baştaki/sondaki daha az dolu sütunlu satır tablo dışı metindir
MIN_MULTILINE_CELLS = 2      # bu kadar hücresi çok satırlı satırın hücre içi satırları liste niteliğindedir
CORNER_TOLERANCE = 1         # parçanın sol üst köşesi tablo alanının bu kadar dışında kalabilir


class TableScanner:
    """Sayfadaki dolgu tabanlı ve çizgisiz sütun hizalı tabloları bulur. Tablo gövdenin alt
    sınırını aşmaz; alt bilgiyi ayıran o sınırı sayfa bölgeleri (zones) bilir."""

    def __init__(self, settings, zones):
        self._zones = zones
        self._row_gap_ratio = settings["table_row_gap_ratio"]

    def scan(self, page):
        """[{y0, y1, block}], sayfada yukarıdan aşağıya."""
        return sorted(self._tables_on(page), key=lambda table: table["y0"])

    def _tables_on(self, page):
        """Dolgulu hücre varsa tabloyu onlar belirler; hizalı tarama yalnız dolgusuz
        sayfada çalışır ki aynı tablo iki kez yakalanmasın."""
        body_bottom = self._zones.body_bottom(page.height)
        fills = PageFills(page.drawings(), body_bottom)
        spans = self._page_spans(page)
        if fills.is_empty():
            return AlignedTableFinder.of_spans([span for span in spans if span.box.y1 <= body_bottom]).tables()
        builder = TableBuilder(fills, self._row_gap_ratio)
        return [table for cells in fills.table_groups() for table in builder.tables_in(cells, spans)]

    @staticmethod
    def _page_spans(page):
        """Satır anahtarı tam sayıya yuvarlanır: aynı satırın parçaları küsuratta ayrışabilir."""
        spans = [dataclasses.replace(span, text=span.text.strip(), line_y=round(span.line_y))
                 for line in page.text_lines() for span in line]
        return sorted(spans, key=lambda s: (s.line_y, s.box.x0))


class TableBuilder:
    """Sayfanın dolgularından hücre kümesi başına (tek tablo) satırları, başlığı ve hücreleri kurar."""

    def __init__(self, fills, row_gap_ratio):
        self._fills = fills
        self._row_gap_ratio = row_gap_ratio

    def tables_in(self, cells, page_spans):
        """Kümedeki tablo [{y0, y1, block}] olarak; tablo değilse boş liste."""
        columns = GridColumns.of_cells(cells)
        table = self._table(columns, _spans_within(self._fills.extent(cells), page_spans))
        return [table.region()] if table.is_table() else []

    def _table(self, columns, spans):
        bands = self._fills.row_bands(columns)
        rows = RowSplitter(bands, self._row_gap_ratio).rows(spans)
        return FilledTable.trimmed([TableRow(row, columns) for row in rows], bands)


def _spans_within(area, spans):
    return [s for s in spans if geometry.contains_point(area, _near_corner(s.box))]


def _near_corner(box):
    """Sol üst köşenin CORNER_TOLERANCE içerisi: köşesi alanın kenarına biraz taşan parça yine içeridedir."""
    return box.x0 + CORNER_TOLERANCE, box.y0 + CORNER_TOLERANCE


class RowSplitter:
    """Parçaları tablo satırlarına böler: bant varsa satırı bant belirler; bantsız gövdede satır
    arası boşluk satır içi sarma boşluğundan büyüktür."""

    def __init__(self, bands, row_gap_ratio):
        self._bands = bands
        self._row_gap_ratio = row_gap_ratio

    def rows(self, spans):
        """[[parça]]: her satırın parçaları, yukarıdan aşağı."""
        rows = [[span] for span in spans[:1]]
        for previous, span in zip(spans, spans[1:]):
            if self._starts_row(span, previous):
                rows.append([])
            rows[-1].append(span)
        return rows

    def _starts_row(self, span, previous):
        """Eşik kitaba göre değişir: bir kitapta satır içi 1.2 / satırlar arası 1.6, başkasında
        0.93 / 1.26 ölçüldü."""
        if self._bands.is_in_band(span) or self._bands.is_in_band(previous):
            return not self._bands.same_band(span, previous)
        return span.box.y0 - previous.box.y0 > geometry.height(previous.box) * self._row_gap_ratio


class FilledTable:
    """Dolgu ızgarasına oturan tablo satırları, yukarıdan aşağıya; baştaki kalın satırlar başlıktır."""

    def __init__(self, rows):
        self._rows = rows

    @classmethod
    def trimmed(cls, rows, bands):
        """İlk bant öncesi (caption) atılır; tablo ilk tablo dışı satırda (gövde metni, dipnot) biter.
        Baştaki/sondaki tek sütunlu satırlar tablo dışı metindir (kaynak notu vb.)."""
        in_bands = itertools.dropwhile(lambda row: not row.is_in(bands), rows)
        return cls(_without_single_column_edges(list(itertools.takewhile(TableRow.fits, in_bands))))

    def is_table(self):
        return len(self._rows) >= MIN_ROWS

    def region(self):
        """{y0, y1, block}: tablonun sayfadaki dikey yeri ve bloğu."""
        header_rows = len(list(itertools.takewhile(TableRow.is_bold, self._rows)))
        rows = [row.header_cells() if index < header_rows else row.body_cells() for index, row in enumerate(self._rows)]
        block = {"type": "table", "header_rows": header_rows, "rows": rows}
        return {"y0": min(row.top for row in self._rows), "y1": max(row.bottom for row in self._rows), "block": block}


def _without_single_column_edges(rows):
    while rows and rows[0].filled_columns() < MIN_COLUMNS:
        rows = rows[1:]
    while rows and rows[-1].filled_columns() < MIN_COLUMNS:
        rows = rows[:-1]
    return rows


class TableRow:
    """Tablonun bir satırındaki parçalar; sütunlara göre hücrelere dağıtılır."""

    def __init__(self, spans, columns):
        self._spans = spans
        self._columns = columns
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

    def is_in(self, bands):
        return bands.in_band(self._spans)

    def fits(self):
        """Parçaların hepsi bir sütuna düşüyor ve hiçbiri sütundan belirgin geniş değil mi?"""
        return self._columns.is_table_row(self._spans)

    def filled_columns(self):
        return self._columns.filled_columns(self._spans)

    def header_cells(self):
        return [cell.unit() for cell in self._cells()]

    def body_cells(self):
        cells = self._cells()
        if self._has_aligned_sublines(cells):
            return [cell.listing_unit() for cell in cells]
        return [cell.unit() for cell in cells]

    def _cells(self):
        return self._columns.cells_of(self._spans, self._main_size)

    @staticmethod
    def _has_aligned_sublines(cells):
        """İki ya da daha çok sütun çok satırlıysa hücre içi satırlar liste
        niteliğinde olabilir; sarılmış metin ayrıca elenir."""
        return sum(1 for cell in cells if cell.is_multiline()) >= MIN_MULTILINE_CELLS
