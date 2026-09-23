"""Çizgisiz, sütun hizalı metin tabloları (e-kitap kökenli PDF'ler).

Ne kenarlık çizgisi (ODL) ne dolgu dikdörtgeni (table_scan) olan tablolar:
tam kalın bir başlık satırı ve altında başlık sütunlarına hizalı bitişik
gövde satırları. Yalnız basit tablolar yakalanır; çok satırlı hücreli ya da
başlıksız tablolar elle kurulur.
"""
import itertools

from extraction.tables.table_cell import TableCell

MIN_HEADER_COLUMNS = 2
MIN_FILLED_COLUMNS = 2       # gövde satırı en az bu kadar sütunu doldurur
MIN_TABLE_ROWS = 4           # başlık dahil
COLUMN_GUTTER = 8            # sütun, bir sonraki başlık sütununun bu kadar solunda biter
LAST_COLUMN_REACH = 60       # son sütun başlığın sağ ucundan bu kadar uzar
ROW_RIGHT_SLACK = 30         # gövde satırı son sütunu bu kadar taşabilir
CENTER_TOLERANCE = 5         # parçanın ortası sütun kenarını bu kadar aşabilir
DEFAULT_MAIN_SIZE = 12.0


class HeaderColumns:
    """Kalın başlık satırının sütunları; gövde satırları bunlara göre ölçülür."""

    def __init__(self, header):
        starts = sorted(round(span["bbox"].x0, 1) for span in header)
        last_end = max(span["bbox"].x1 for span in header) + LAST_COLUMN_REACH
        self.columns = list(zip(starts, [start - COLUMN_GUTTER for start in starts[1:]] + [last_end]))

    @staticmethod
    def starts_table(row):
        return len(row) >= MIN_HEADER_COLUMNS and all("bold" in span["font"].lower() for span in row)

    def fits(self, row):
        """Satır sütun sınırları içinde kalıyor ve en az iki sütunu dolduruyor mu?"""
        return self._within_columns(row) and sum(1 for bucket in self.buckets(row) if bucket) >= MIN_FILLED_COLUMNS

    def _within_columns(self, row):
        left, right = self.columns[0][0], self.columns[-1][1]
        return (min(span["bbox"].x0 for span in row) >= left - COLUMN_GUTTER
                and max(span["bbox"].x1 for span in row) <= right + ROW_RIGHT_SLACK)

    def buckets(self, row):
        """Her sütuna düşen parçalar. İki sütunun payına giren parça soldakine gider;
        hiçbir sütuna düşmeyen parça atılır (sahipsiz boş listeye eklenir)."""
        buckets = [[] for _ in self.columns]
        for span in row:
            next((bucket for bucket, column in zip(buckets, self.columns) if self._holds(column, span)), []).append(span)
        return buckets

    @staticmethod
    def _holds(column, span):
        center = (span["bbox"].x0 + span["bbox"].x1) / 2
        return column[0] - CENTER_TOLERANCE <= center <= column[1] + CENTER_TOLERANCE

    def table(self, rows):
        spans = [span for row in rows for span in row]
        block = {"type": "table", "header_rows": 1, "rows": [self._cells(row) for row in rows]}
        return {"y0": min(s["bbox"].y0 for s in spans), "y1": max(s["bbox"].y1 for s in spans), "block": block}

    def _cells(self, row):
        buckets = self.buckets(row)
        main_size = max((span["size"] for bucket in buckets for span in bucket), default=DEFAULT_MAIN_SIZE)
        return [TableCell(bucket, column, main_size).unit(False) for bucket, column in zip(buckets, self.columns)]


class AlignedTableFinder:
    """Sayfanın metin parçalarını satırlara dizer ve hizalı tabloları arar."""

    def __init__(self, spans):
        self.rows = self._line_rows(spans)

    @staticmethod
    def _line_rows(spans):
        rows = {}
        for span in spans:
            rows.setdefault(span["line_y"], []).append(span)
        return [sorted(rows[y], key=lambda span: span["bbox"].x0) for y in sorted(rows)]

    def tables(self):
        """[{y0, y1, block}]; bir tablonun satırları başka tablonun başlığı olamaz."""
        found, index = [], 0
        while index < len(self.rows):
            rows = self._table_rows_at(index)
            is_table = len(rows) >= MIN_TABLE_ROWS
            found += [HeaderColumns(rows[0]).table(rows)] if is_table else []
            index += len(rows) if is_table else 1
        return found

    def _table_rows_at(self, index):
        """Kalın başlık ve ona hizalı bitişik satırlar; başlık yoksa boş liste."""
        header = self.rows[index]
        if not HeaderColumns.starts_table(header):
            return []
        return [header, *itertools.takewhile(HeaderColumns(header).fits, self.rows[index + 1:])]
