"""Çizgisiz, sütun hizalı metin tabloları (e-kitap kökenli PDF'ler).

Ne kenarlık çizgisi (ODL) ne dolgu dikdörtgeni (table_scan) olan tablolar:
tam kalın bir başlık satırı ve altında başlık sütunlarına hizalı bitişik
gövde satırları. Sayfa kırılması iki yerde tanınır: sayfanın son satırına
uzanan kısa parça ve sayfayı açan başlıksız devam. Çok satırlı hücreli ya da
sayfa ortasındaki başlıksız tablolar elle kurulur.
"""
import collections
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


class SpanRow:
    """Sayfanın bir satırı: aynı üst kenardaki parçalar, soldan sağa."""

    def __init__(self, spans):
        self.spans = spans

    @classmethod
    def lines_of(cls, spans):
        """Parçalar satırlarına, satırlar yukarıdan aşağıya."""
        rows = collections.defaultdict(list)
        for span in spans:
            rows[span.line_y].append(span)
        return [cls(sorted(rows[y], key=lambda span: span.box.x0)) for y in sorted(rows)]

    @property
    def left(self):
        return min(span.box.x0 for span in self.spans)

    @property
    def right(self):
        return max(span.box.x1 for span in self.spans)

    def is_header(self):
        """Tam kalın, en az iki sütunlu ve sütunları arası açık mı?"""
        return len(self.spans) >= MIN_HEADER_COLUMNS and self._is_bold() and self._has_gutters()

    def is_headerless(self):
        """Kalın olmayan, en az iki sütuna bölünen satır: başlıksız devamın ilk satırı olabilir."""
        return not self._is_bold() and len(self.gutter_cells()) >= MIN_HEADER_COLUMNS

    def gutter_cells(self):
        """Parçalar, aralarındaki geniş boşluklardan bölünür."""
        cells = [[self.spans[0]]]
        for left, right in zip(self.spans, self.spans[1:]):
            if right.box.x0 - left.box.x1 >= COLUMN_GAP_MIN:
                cells.append([])
            cells[-1].append(right)
        return cells

    def _is_bold(self):
        return all("bold" in span.font.lower() for span in self.spans)

    def _has_gutters(self):
        """Bitişik kalın parçalar (bölüm başlığı, cümle içi vurgu) sütun değildir;
        gerçek başlık sütunları arasında belirgin boşluk vardır."""
        return len(self.gutter_cells()) == len(self.spans)


class TableColumns:
    """Tablonun sütun sınırları; bir satırın parçalarını sütunlarına dağıtır."""

    def __init__(self, starts, right_edge):
        ends = [start - COLUMN_GUTTER for start in starts[1:]] + [right_edge + LAST_COLUMN_REACH]
        self.columns = list(zip(starts, ends))

    @classmethod
    def of_header(cls, header):
        """Kalın başlığın her parçası bir sütundur."""
        return cls(sorted(round(span.box.x0, 1) for span in header.spans), header.right)

    @classmethod
    def of_row(cls, row):
        """Başlıksız satırda sütunu geniş boşluk açar; hücre içindeki stil
        parçası (italik "x") yeni sütun değildir."""
        return cls([round(cell[0].box.x0, 1) for cell in row.gutter_cells()], row.right)

    def fits(self, row):
        """Satır sütun sınırları içinde kalıyor ve en az iki sütunu dolduruyor mu?"""
        return self._within_columns(row) and sum(1 for bucket in self.buckets(row) if bucket) >= MIN_FILLED_COLUMNS

    def _within_columns(self, row):
        left, right = self.columns[0][0], self.columns[-1][1]
        return row.left >= left - COLUMN_GUTTER and row.right <= right + ROW_RIGHT_SLACK

    def buckets(self, row):
        """Her sütuna düşen parçalar. İki sütunun payına giren parça soldakine gider;
        hiçbir sütuna düşmeyen parça atılır (sahipsiz boş listeye eklenir)."""
        buckets = [[] for _ in self.columns]
        for span in row.spans:
            next((bucket for bucket, column in zip(buckets, self.columns) if self._holds(column, span)), []).append(span)
        return buckets

    @staticmethod
    def _holds(column, span):
        center = span.box.center_x
        return column[0] - CENTER_TOLERANCE <= center <= column[1] + CENTER_TOLERANCE

    def table(self, rows, header_rows):
        spans = [span for row in rows for span in row.spans]
        block = {"type": "table", "header_rows": header_rows, "rows": [self._cells(row) for row in rows]}
        return {"y0": min(s.box.y0 for s in spans), "y1": max(s.box.y1 for s in spans), "block": block}

    def _cells(self, row):
        buckets = self.buckets(row)
        main_size = max((span.size for bucket in buckets for span in bucket), default=DEFAULT_MAIN_SIZE)
        return [TableCell(bucket, column, main_size).unit(False) for bucket, column in zip(buckets, self.columns)]


class AlignedTableFinder:
    """Sayfanın satırları arasında hizalı tabloları arar."""

    def __init__(self, rows):
        self.rows = rows

    @classmethod
    def of_spans(cls, spans):
        return cls(SpanRow.lines_of(spans))

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
            if self.rows[start].is_header():
                break
            rows = self._continued_rows_at(start)
            if len(rows) >= MIN_CONTINUED_ROWS:
                return [TableColumns.of_row(rows[0]).table(rows, NO_HEADER_ROW)], start + len(rows)
        return [], 0

    def _continued_rows_at(self, start):
        first = self.rows[start]
        if not first.is_headerless():
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
        if not header.is_header():
            return []
        return [header, *itertools.takewhile(TableColumns.of_header(header).fits, self.rows[index + 1:])]
