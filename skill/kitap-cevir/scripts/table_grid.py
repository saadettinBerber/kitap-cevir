"""Dolgu dikdörtgenlerinden tablo ızgarasını çıkarır: hücre kümeleri (tablolar),
sütunlar, satır bantları ve tablo kapsamı. Koordinatlar üst orijinlidir.
"""
import fitz

MIN_CELL_WIDTH = 15
MIN_CELL_HEIGHT = 8
EDGE_TOLERANCE = 2.0
WIDE_SPAN_RATIO = 1.2        # sütundan geniş parça = tablo dışı (caption, dipnot)
MAX_BAND_GAP_RATIO = 3.0     # iki dolgu arası boşluk / bant yüksekliği: üstü ayrı tablodur
RULE_MAX_HEIGHT = 2.0        # bundan kalını çizgi değil dolgudur
MIN_COLUMNS = 2


def filled_rects(page):
    rects = [fitz.Rect(d["rect"]) for d in page.get_drawings() if d.get("fill")]
    return [r for r in rects if r.width >= MIN_CELL_WIDTH and r.height >= MIN_CELL_HEIGHT]


def horizontal_rules(page):
    """Dolgusuz yatay çizgiler: tablonun alt kenarı, alt bilgi kuralı."""
    rects = [fitz.Rect(d["rect"]) for d in page.get_drawings() if not d.get("fill")]
    return [r for r in rects if r.height <= RULE_MAX_HEIGHT and r.width >= MIN_CELL_WIDTH]


def is_background(rect, rects):
    inner = [r for r in rects if r != rect and rect.contains(r)]
    return len(inner) >= 2


def _shares_column(first, second):
    """Aynı sütunda ya da yan yana duran hücreler aynı ızgaraya aittir."""
    return any(abs(a - b) <= EDGE_TOLERANCE
               for a in (first.x0, first.x1) for b in (second.x0, second.x1))


def _near_vertically(first, second):
    """Aynı sayfadaki iki ayrı tablo çoğu zaman aynı sol kenardan başlar; onları
    ayıran şey aradaki dikey boşluktur. Zebra bantları zincirleme bağlandığı
    için uzun bir tablo yine tek grup kalır."""
    gap = max(0.0, first.y0 - second.y1, second.y0 - first.y1)
    return gap <= max(first.height, second.height) * MAX_BAND_GAP_RATIO


def _same_grid(first, second):
    return _shares_column(first, second) and _near_vertically(first, second)


def _connected_groups(cells):
    groups = []
    for rect in cells:
        linked = [g for g in groups if any(_same_grid(rect, other) for other in g)]
        merged = [rect] + [r for g in linked for r in g]
        groups = [g for g in groups if g not in linked] + [merged]
    return groups


def group_tables(cells, backgrounds):
    """Aynı arka plandaki hücreler tek tablodur; arka planı olmayanlar sütun
    kenarı paylaşımına göre kümelenir."""
    by_background, loose = {}, []
    for rect in cells:
        owner = next((i for i, b in enumerate(backgrounds) if b.contains(rect)), None)
        if owner is None:
            loose.append(rect)
        else:
            by_background.setdefault(owner, []).append(rect)
    return list(by_background.values()) + _connected_groups(loose)


def _column_end(cells, left):
    """left'ten başlayan hücrelerin en sık görülen sağ kenarı; satır içi kod
    vurguları gibi kenardan içeride başlayan dolgular böylece sütun olmaz."""
    ends = [round(r.x1) for r in cells if abs(r.x0 - left) <= EDGE_TOLERANCE]
    if not ends:
        return None
    return max(set(ends), key=lambda x1: (ends.count(x1), -x1))


def table_columns(cells):
    """Tablo sol kenarından sağa doğru sütunları döşer."""
    columns, left, right_edge = [], min(r.x0 for r in cells), max(r.x1 for r in cells)
    while left < right_edge - EDGE_TOLERANCE:
        end = _column_end(cells, left)
        if end is None:
            further = [r.x0 for r in cells if r.x0 > left + EDGE_TOLERANCE]
            if not further:
                break
            left = min(further)
            continue
        columns.append((left, end))
        left = end
    return columns


def _on_column_edges(rect, columns):
    lefts = [c[0] for c in columns]
    rights = [c[1] for c in columns]
    return (any(abs(rect.x0 - x) <= EDGE_TOLERANCE for x in lefts)
            and any(abs(rect.x1 - x) <= EDGE_TOLERANCE for x in rights))


def row_bands(rects, columns):
    """Sütun kenarlarına oturan (tüm tabloyu kaplamayan) dolguların y aralıkları
    satır bantlarıdır; içindeki metin tek satıra aittir."""
    full_width = (columns[0][0], columns[-1][1])
    bands = []
    for rect in sorted(rects, key=lambda r: r.y0):
        if not _on_column_edges(rect, columns) or _on_column_edges(rect, [full_width]):
            continue
        if bands and rect.y0 < bands[-1][1] - EDGE_TOLERANCE:
            bands[-1] = (bands[-1][0], max(bands[-1][1], rect.y1))
        else:
            bands.append((rect.y0, rect.y1))
    return bands


def _bottom_below(union, page_info):
    """Tablo, altındaki ilk yatay çizgide biter (alt kenar); çizgi yoksa metin
    alanının sonunda. Sayfa sonuna dek uzatmak tablonun altındaki caption'ı,
    yan kutuyu ve koşu başlığını tabloya katıyordu."""
    below = [rule.y0 for rule in page_info["rules"]
             if rule.y0 > union.y1 and rule.x0 <= union.x1 and rule.x1 >= union.x0]
    return min(below, default=page_info["text_bottom"])


def extent(cells, page_info):
    """Arka plan varsa tablo odur. Yoksa zebra dolguda ilk satır beyaz
    kalabilir (bir hücre yukarı); alt sınır için _bottom_below'a bakılır."""
    union = fitz.Rect(cells[0])
    for rect in cells[1:]:
        union |= rect
    for background in page_info["backgrounds"]:
        if background.contains(union):
            return background
    row_height = sorted(r.height for r in cells)[len(cells) // 2]
    return fitz.Rect(union.x0, union.y0 - row_height, union.x1, _bottom_below(union, page_info))


def column_of(span, columns):
    center = (span["bbox"].x0 + span["bbox"].x1) / 2
    for index, (left, right) in enumerate(columns):
        if left <= center <= right:
            return index
    return None


def is_table_row(row, columns):
    widest = max(right - left for left, right in columns) * WIDE_SPAN_RATIO
    return all(s["bbox"].width <= widest and column_of(s, columns) is not None for s in row)


def filled_columns(row, columns):
    return len({column_of(span, columns) for span in row})
