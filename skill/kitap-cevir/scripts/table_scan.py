"""PyMuPDF çizim katmanından çizgisiz (dolgulu hücreli) tabloları bulur.

OpenDataLoader tabloları yalnız kenarlık çizgilerinden tanır; e-kitap kökenli
PDF'lerde hücreler zebra dolgu dikdörtgenleriyle çizilir ve tablo paragraf
yığınına dönüşür. Izgara (sütunlar, bantlar) table_grid'den gelir; burada
metin parçaları satırlara ve hücrelere dağıtılır. Koordinatlar üst orijinlidir.
"""
import html

import fitz

from project import DEFAULT_EXTRACTION
from table_grid import (MIN_COLUMNS, column_of, extent, filled_columns, filled_rects,
                        group_tables, horizontal_rules, is_background, is_table_row,
                        row_bands, table_columns)

SUPERSCRIPT_RATIO = 0.8      # satırın ana puntosunun altındaki parça = üst simge
WRAP_FILL_RATIO = 0.8        # satırlar sütunu bu oranda dolduruyorsa sarılmış düz metindir
MIN_ROWS = 2


def _page_spans(page):
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    spans.append({"bbox": fitz.Rect(span["bbox"]), "font": span["font"],
                                  "size": span["size"], "text": span["text"].strip(),
                                  "line_y": round(line["bbox"][1])})
    return sorted(spans, key=lambda s: (s["line_y"], s["bbox"].x0))


def _spans_within(spans, area):
    return [s for s in spans if area.contains(fitz.Point(s["bbox"].x0 + 1, s["bbox"].y0 + 1))]


def _band_of(span, bands):
    center = (span["bbox"].y0 + span["bbox"].y1) / 2
    return next((i for i, (top, bottom) in enumerate(bands) if top <= center <= bottom), None)


def _starts_row(span, previous, bands, gap_ratio):
    """Bant varsa satırı bant belirler; bantsız gövdede satır arası boşluk satır
    içi sarma boşluğundan büyüktür. Eşik kitaba göre değişir: bir kitapta satır
    içi 1.2 / satırlar arası 1.6, başkasında 0.93 / 1.26 ölçüldü."""
    if previous is None:
        return True
    band, previous_band = _band_of(span, bands), _band_of(previous, bands)
    if band is not None or previous_band is not None:
        return band != previous_band
    gap = span["bbox"].y0 - previous["bbox"].y0
    return gap > previous["bbox"].height * gap_ratio


def _group_rows(spans, bands, gap_ratio):
    rows, previous = [], None
    for span in spans:
        if _starts_row(span, previous, bands, gap_ratio):
            rows.append([])
        rows[-1].append(span)
        previous = span
    return rows


def _in_band(row, bands):
    return any(_band_of(span, bands) is not None for span in row)


def _table_rows(rows, bands, columns):
    """Bantlar varsa ilk bant öncesi (caption) atılır; tablo ilk tablo dışı
    satırda (gövde metni, dipnot) biter."""
    if bands:
        while rows and not _in_band(rows[0], bands):
            rows = rows[1:]
    kept = []
    for row in rows:
        if not is_table_row(row, columns):
            break
        kept.append(row)
    return kept


def _trim_single_column_rows(rows, columns):
    """Baştaki/sondaki tek sütunlu satırlar tablo dışı metindir (kaynak notu vb.)."""
    while rows and filled_columns(rows[0], columns) < MIN_COLUMNS:
        rows = rows[1:]
    while rows and filled_columns(rows[-1], columns) < MIN_COLUMNS:
        rows = rows[:-1]
    return rows


def _cell_lines(spans, main_size):
    """Hücre metnini satırlara ({text, x1}) ve üst simge işaretlerine ayırır."""
    lines, marks = {}, []
    for span in spans:
        if span["size"] < main_size * SUPERSCRIPT_RATIO:
            marks.append(span["text"])
        else:
            line = lines.setdefault(span["line_y"], {"words": [], "x1": 0})
            line["words"].append(span["text"])
            line["x1"] = max(line["x1"], span["bbox"].x1)
    ordered = [lines[key] for key in sorted(lines)]
    return [{"text": " ".join(ln["words"]), "x1": ln["x1"]} for ln in ordered], marks


def _is_wrapped_prose(lines, column):
    """Son satır hariç satırlar sütunu dolduruyorsa bu sarılmış düz metindir;
    satır sonları anlam taşımaz."""
    if len(lines) < 2:
        return True
    fills = sorted((ln["x1"] - column[0]) / (column[1] - column[0]) for ln in lines[:-1])
    return fills[len(fills) // 2] >= WRAP_FILL_RATIO


def _cell_unit(bucket, column, row_info):
    lines, marks = _cell_lines(bucket, row_info["main_size"])
    keep_breaks = row_info["keep_breaks"] and not _is_wrapped_prose(lines, column)
    if not marks and not keep_breaks:
        return {"en": " ".join(ln["text"] for ln in lines)}
    separator = "<br>" if keep_breaks else " "
    text = separator.join(html.escape(ln["text"]) for ln in lines)
    sups = "".join(f"<sup>{html.escape(m)}</sup>" for m in marks)
    return {"en": text + sups, "html": True}


def _has_aligned_sublines(buckets):
    """İki ya da daha çok sütun çok satırlıysa hücre içi satırlar liste
    niteliğinde olabilir; sarılmış metin ayrıca elenir."""
    multiline = sum(1 for bucket in buckets if len({s["line_y"] for s in bucket}) > 1)
    return multiline >= 2


def _row_cells(row, columns, is_header):
    buckets = [[] for _ in columns]
    for span in row:
        buckets[column_of(span, columns)].append(span)
    row_info = {"main_size": max(s["size"] for s in row),
                "keep_breaks": not is_header and _has_aligned_sublines(buckets)}
    return [_cell_unit(bucket, column, row_info) for bucket, column in zip(buckets, columns)]


def _is_bold_row(row):
    main_size = max(s["size"] for s in row)
    body = [s for s in row if s["size"] >= main_size * SUPERSCRIPT_RATIO]
    return all("bold" in s["font"].lower() for s in body)


def _header_count(rows):
    count = 0
    for row in rows:
        if not _is_bold_row(row):
            break
        count += 1
    return count


def _row_bounds(rows):
    top = min(s["bbox"].y0 for row in rows for s in row)
    bottom = max(s["bbox"].y1 for row in rows for s in row)
    return top, bottom


def _table_from(cells, page_info):
    columns = table_columns(cells)
    if len(columns) < MIN_COLUMNS:
        return None
    within = _spans_within(page_info["spans"], extent(cells, page_info))
    bands = row_bands(page_info["rects"], columns)
    rows = _table_rows(_group_rows(within, bands, page_info["row_gap_ratio"]), bands, columns)
    rows = _trim_single_column_rows(rows, columns)
    if len(rows) < MIN_ROWS:
        return None
    top, bottom = _row_bounds(rows)
    header_rows = _header_count(rows)
    block = {"type": "table", "header_rows": header_rows,
             "rows": [_row_cells(r, columns, i < header_rows) for i, r in enumerate(rows)]}
    return {"y0": top, "y1": bottom, "block": block}


def scan_tables(pdf_path, pdf_page, settings=None):
    """Sayfadaki dolgu tabanlı tabloları [{y0, y1, block}] olarak döndürür."""
    settings = {**DEFAULT_EXTRACTION, **(settings or {})}
    document = fitz.open(pdf_path)
    try:
        page = document[pdf_page - 1]
        rects = filled_rects(page)
        backgrounds = [r for r in rects if is_background(r, rects)]
        cells = [r for r in rects if r not in backgrounds]
        page_info = {"spans": _page_spans(page), "backgrounds": backgrounds,
                     "rects": rects, "rules": horizontal_rules(page),
                     "text_bottom": page.rect.height - settings["footer_zone_top"],
                     "row_gap_ratio": settings["table_row_gap_ratio"]}
        tables = [_table_from(group, page_info) for group in group_tables(cells, backgrounds)]
        return sorted([t for t in tables if t], key=lambda t: t["y0"])
    finally:
        document.close()
