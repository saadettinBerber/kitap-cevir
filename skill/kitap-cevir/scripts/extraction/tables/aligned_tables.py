"""Çizgisiz, sütun hizalı metin tabloları (e-kitap kökenli PDF'ler).

Ne kenarlık çizgisi (ODL) ne dolgu dikdörtgeni (table_scan) olan tablolar:
tam kalın bir başlık satırı ve altında başlık sütunlarına hizalı bitişik
gövde satırları. Sayfa kırılması iki yerde tanınır: sayfanın son satırına
uzanan kısa parça ve sayfayı açan başlıksız devam. Çok satırlı hücreli ya da
sayfa ortasındaki başlıksız tablolar elle kurulur.
"""
import itertools

from extraction.tables.table_cell import TableCell

MIN_HEADER_COLUMNS = 2
COLUMN_GAP_MIN = 30          # sütunlar arasındaki en küçük boşluk (pt)
MIN_FILLED_COLUMNS = 2       # gövde satırı en az bu kadar sütunu doldurur
MIN_TABLE_ROWS = 4           # başlık dahil
MIN_SPLIT_TABLE_ROWS = 2     # sayfa sonuna düşen parça: başlık + bir satır
MIN_CONTINUED_ROWS = 2       # sayfayı açan başlıksız devam
CONTINUATION_START_ROWS = 2  # devam ilk ya da (koşu başlığının altındaki) ikinci satırda başlar
COLUMN_GUTTER = 8            # sütun, bir sonraki sütunun bu kadar solunda biter
LAST_COLUMN_REACH = 60       # son sütun ilk satırın sağ ucundan bu kadar uzar
ROW_RIGHT_SLACK = 30         # gövde satırı son sütunu bu kadar taşabilir
CENTER_TOLERANCE = 5         # parçanın ortası sütun kenarını bu kadar aşabilir
DEFAULT_MAIN_SIZE = 12.0
HEADER_ROW, NO_HEADER_ROW = 1, 0


class TableColumns:
    """Tablonun sütunları: kalın başlıktan ya da başlıksız devamın ilk satırından
    çıkar; satırlar bunlara göre ölçülür ve hücrelere dağıtılır."""

    def __init__(self, starts, right_edge):
        ends = [start - COLUMN_GUTTER for start in starts[1:]] + [right_edge + LAST_COLUMN_REACH]
        self.columns = list(zip(starts, ends))

    @classmethod
    def of_header(cls, header):
        """Kalın başlığın her parçası bir sütundur."""
        return cls(sorted(round(span.box.x0, 1) for span in header), max(span.box.x1 for span in header))

    @classmethod
    def of_row(cls, row):
        """Başlıksız satırda sütunu geniş boşluk açar; hücre içindeki stil
        parçası (italik "x") yeni sütun değildir."""
        starts = [round(cell[0].box.x0, 1) for cell in cls._gutter_cells(row)]
        return cls(starts, max(span.box.x1 for span in row))

    @staticmethod
    def is_header(row):
        """Soldan sağa dizili satır tam kalın, en az iki sütunlu ve sütunları arası açık mı?"""
        return len(row) >= MIN_HEADER_COLUMNS and TableColumns._is_bold(row) and TableColumns._has_gutters(row)

    @staticmethod
    def is_headerless_row(row):
        """Kalın olmayan, en az iki sütuna bölünen satır: başlıksız devamın ilk satırı olabilir."""
        return not TableColumns._is_bold(row) and len(TableColumns._gutter_cells(row)) >= MIN_HEADER_COLUMNS

    @staticmethod
    def _is_bold(row):
        return all("bold" in span.font.lower() for span in row)

    @staticmethod
    def _has_gutters(row):
        """Bitişik kalın parçalar (bölüm başlığı, cümle içi vurgu) sütun değildir;
        gerçek başlık sütunları arasında belirgin boşluk vardır."""
        return len(TableColumns._gutter_cells(row)) == len(row)

    @staticmethod
    def _gutter_cells(row):
        """Soldan sağa dizili parçalar, aralarındaki geniş boşluklardan bölünür."""
        cells = [[row[0]]]
        for left, right in zip(row, row[1:]):
            if right.box.x0 - left.box.x1 >= COLUMN_GAP_MIN:
                cells.append([])
            cells[-1].append(right)
        return cells

    def fits(self, row):
        """Satır sütun sınırları içinde kalıyor ve en az iki sütunu dolduruyor mu?"""
        return self._within_columns(row) and sum(1 for bucket in self.buckets(row) if bucket) >= MIN_FILLED_COLUMNS

    def _within_columns(self, row):
        left, right = self.columns[0][0], self.columns[-1][1]
        return (min(span.box.x0 for span in row) >= left - COLUMN_GUTTER
                and max(span.box.x1 for span in row) <= right + ROW_RIGHT_SLACK)

    def buckets(self, row):
        """Her sütuna düşen parçalar. İki sütunun payına giren parça soldakine gider;
        hiçbir sütuna düşmeyen parça atılır (sahipsiz boş listeye eklenir)."""
        buckets = [[] for _ in self.columns]
        for span in row:
            next((bucket for bucket, column in zip(buckets, self.columns) if self._holds(column, span)), []).append(span)
        return buckets

    @staticmethod
    def _holds(column, span):
        center = span.box.center_x
        return column[0] - CENTER_TOLERANCE <= center <= column[1] + CENTER_TOLERANCE

    def table(self, rows, header_rows):
        spans = [span for row in rows for span in row]
        block = {"type": "table", "header_rows": header_rows, "rows": [self._cells(row) for row in rows]}
        return {"y0": min(s.box.y0 for s in spans), "y1": max(s.box.y1 for s in spans), "block": block}

    def _cells(self, row):
        buckets = self.buckets(row)
        main_size = max((span.size for bucket in buckets for span in bucket), default=DEFAULT_MAIN_SIZE)
        return [TableCell(bucket, column, main_size).unit(False) for bucket, column in zip(buckets, self.columns)]


class AlignedTableFinder:
    """Sayfanın metin parçalarını satırlara dizer ve hizalı tabloları arar."""

    def __init__(self, spans):
        self.rows = self._line_rows(spans)

    @staticmethod
    def _line_rows(spans):
        rows = {}
        for span in spans:
            rows.setdefault(span.line_y, []).append(span)
        return [sorted(rows[y], key=lambda span: span.box.x0) for y in sorted(rows)]

    def tables(self):
        """[{y0, y1, block}]; bir tablonun satırları başka tablonun başlığı olamaz."""
        found, index = self._continued_table()
        while index < len(self.rows):
            rows = self._table_rows_at(index)
            is_table = self._is_table(index, rows)
            found += [TableColumns.of_header(rows[0]).table(rows, HEADER_ROW)] if is_table else []
            index += len(rows) if is_table else 1
        return found

    def _continued_table(self):
        """Önceki sayfadan süren başlıksız tablo ve taramanın süreceği satır.
        Sayfayı kendi başlığı olan bir tablo açıyorsa devam yoktur."""
        for start in range(min(CONTINUATION_START_ROWS, len(self.rows))):
            if TableColumns.is_header(self.rows[start]):
                break
            rows = self._continued_rows_at(start)
            if len(rows) >= MIN_CONTINUED_ROWS:
                return [TableColumns.of_row(rows[0]).table(rows, NO_HEADER_ROW)], start + len(rows)
        return [], 0

    def _continued_rows_at(self, start):
        first = self.rows[start]
        if not TableColumns.is_headerless_row(first):
            return []
        return [first, *itertools.takewhile(TableColumns.of_row(first).fits, self.rows[start + 1:])]

    def _is_table(self, index, rows):
        """Sayfanın son satırına uzanan tablo sonraki sayfada sürer; kısa olması
        yanlış alarm değil, sayfa kırılmasıdır."""
        reaches_page_end = index + len(rows) == len(self.rows)
        return len(rows) >= (MIN_SPLIT_TABLE_ROWS if reaches_page_end else MIN_TABLE_ROWS)

    def _table_rows_at(self, index):
        """Kalın başlık ve ona hizalı bitişik satırlar; başlık yoksa boş liste."""
        header = self.rows[index]
        if not TableColumns.is_header(header):
            return []
        return [header, *itertools.takewhile(TableColumns.of_header(header).fits, self.rows[index + 1:])]
