"""PyMuPDF çizim katmanından çizgisiz (dolgulu hücreli) tabloları bulur.

OpenDataLoader tabloları yalnız kenarlık çizgilerinden tanır; e-kitap kökenli
PDF'lerde hücreler zebra dolgu dikdörtgenleriyle çizilir ve tablo paragraf
yığınına dönüşür. Izgara (sütunlar, bantlar) table_grid'den gelir; burada
metin parçaları satırlara ve hücrelere dağıtılır. Koordinatlar üst orijinlidir.
"""
import itertools

import fitz

from extraction.tables.aligned_tables import AlignedTableFinder
from extraction.tables.table_cell import SUPERSCRIPT_RATIO, TableCell
from extraction.tables.table_grid import MIN_COLUMNS, PageFills, TableGrid
from project import DEFAULT_EXTRACTION

MIN_ROWS = 2


class TableRow:
    """Tablonun bir satırındaki parçalar; ızgaraya göre hücrelere dağıtılır."""

    def __init__(self, spans, grid):
        self.spans = spans
        self.grid = grid
        self.main_size = max(span["size"] for span in spans)

    def is_bold(self):
        body = [s for s in self.spans if s["size"] >= self.main_size * SUPERSCRIPT_RATIO]
        return all("bold" in s["font"].lower() for s in body)

    def cells(self, is_header):
        buckets = [[] for _ in self.grid.columns]
        for span in self.spans:
            buckets[self.grid.column_of(span)].append(span)
        cells = [TableCell(bucket, column, self.main_size) for bucket, column in zip(buckets, self.grid.columns)]
        keeps_breaks = not is_header and self._has_aligned_sublines(cells)
        return [cell.unit(keeps_breaks) for cell in cells]

    @staticmethod
    def _has_aligned_sublines(cells):
        """İki ya da daha çok sütun çok satırlıysa hücre içi satırlar liste
        niteliğinde olabilir; sarılmış metin ayrıca elenir."""
        return sum(1 for cell in cells if cell.is_multiline()) >= 2


class TableBuilder:
    """Bir hücre kümesinden (tek tablo) satırları, başlığı ve hücreleri kurar."""

    def __init__(self, page_spans, fills, row_gap_ratio):
        self.page_spans = page_spans
        self.fills = fills
        self.row_gap_ratio = row_gap_ratio

    def tables_in(self, cells):
        """Kümedeki tablo [{y0, y1, block}] olarak; tablo değilse boş liste."""
        grid = TableGrid.from_cells(cells, self.fills.rects)
        if not grid.has_columns():
            return []
        rows = self._table_rows(self._group_rows(self._spans_within(self.fills.extent(cells)), grid), grid)
        if len(rows) < MIN_ROWS:
            return []
        header_rows = self._header_count(rows)
        block = {"type": "table", "header_rows": header_rows,
                 "rows": [row.cells(index < header_rows) for index, row in enumerate(rows)]}
        return [{"y0": min(s["bbox"].y0 for row in rows for s in row.spans),
                 "y1": max(s["bbox"].y1 for row in rows for s in row.spans), "block": block}]

    def _spans_within(self, area):
        return [s for s in self.page_spans if area.contains(fitz.Point(s["bbox"].x0 + 1, s["bbox"].y0 + 1))]

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
        band, previous_band = grid.band_of(span), grid.band_of(previous)
        if band is not None or previous_band is not None:
            return band != previous_band
        return span["bbox"].y0 - previous["bbox"].y0 > previous["bbox"].height * self.row_gap_ratio

    @staticmethod
    def _table_rows(rows, grid):
        """Bantlar varsa ilk bant öncesi (caption) atılır; tablo ilk tablo dışı
        satırda (gövde metni, dipnot) biter. Baştaki/sondaki tek sütunlu satırlar
        tablo dışı metindir (kaynak notu vb.)."""
        if grid.bands:
            rows = list(itertools.dropwhile(lambda row: not grid.in_band(row.spans), rows))
        kept = list(itertools.takewhile(lambda row: grid.is_table_row(row.spans), rows))
        return TableBuilder._without_single_column_edges(kept, grid)

    @staticmethod
    def _without_single_column_edges(rows, grid):
        while rows and grid.filled_columns(rows[0].spans) < MIN_COLUMNS:
            rows = rows[1:]
        while rows and grid.filled_columns(rows[-1].spans) < MIN_COLUMNS:
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

    def __init__(self, settings=None):
        settings = {**DEFAULT_EXTRACTION, **(settings or {})}
        self.footer_zone_top = settings["footer_zone_top"]
        self.row_gap_ratio = settings["table_row_gap_ratio"]

    def scan(self, pdf_path, pdf_page):
        """[{y0, y1, block}], sayfada yukarıdan aşağıya."""
        with fitz.open(pdf_path) as document:
            return sorted(self._tables_on(document[pdf_page - 1]), key=lambda table: table["y0"])

    def _tables_on(self, page):
        """Dolgulu hücre varsa tabloyu onlar belirler; hizalı tarama yalnız dolgusuz
        sayfada çalışır ki aynı tablo iki kez yakalanmasın."""
        fills = PageFills(page, page.rect.height - self.footer_zone_top)
        spans = self._page_spans(page)
        if not fills.rects:
            return AlignedTableFinder(spans).tables()
        builder = TableBuilder(spans, fills, self.row_gap_ratio)
        return [table for cells in fills.table_groups() for table in builder.tables_in(cells)]

    @staticmethod
    def _page_spans(page):
        spans = [{"bbox": fitz.Rect(span["bbox"]), "font": span["font"], "size": span["size"],
                  "text": span["text"].strip(), "line_y": round(line["bbox"][1])}
                 for block in page.get_text("dict")["blocks"]
                 for line in block.get("lines", [])
                 for span in line["spans"] if span["text"].strip()]
        return sorted(spans, key=lambda s: (s["line_y"], s["bbox"].x0))


def scan_tables(pdf_path, pdf_page, settings=None):
    """Sayfadaki dolgu tabanlı ve hizalı tabloları [{y0, y1, block}] olarak döndürür."""
    return TableScanner(settings).scan(pdf_path, pdf_page)
