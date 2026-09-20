"""ODL öğelerini ve blokları birleştiren düzeltmeler: dipnot işaretleri ve
bölüm açılışı (numara + başlık + yazar satırı)."""
import re

_CHAPTER_AUTHOR = re.compile(r"^(?:by|with) [A-Z]")
_FOOTNOTE_MARKER = re.compile(r"^[a-z0-9]$")


def _bbox(element):
    return element.get("bounding box") or [0, 0, 0, 0]


def _is_marker(element):
    return (element.get("type") == "paragraph"
            and bool(_FOOTNOTE_MARKER.match((element.get("content") or "").strip())))


def _same_line(marker, element):
    overlap = min(_bbox(marker)[3], _bbox(element)[3]) - max(_bbox(marker)[1], _bbox(element)[1])
    return overlap > 0 and _bbox(element)[0] > _bbox(marker)[0]


def merge_footnote_markers(elements):
    """Tek harflik dipnot işaretini ('a') aynı satırdaki metnin başına ekler."""
    merged = []
    for element in elements:
        if merged and _is_marker(merged[-1]) and _same_line(merged[-1], element):
            marker = merged.pop()["content"].strip()
            element["content"] = f"{marker} {element.get('content') or ''}"
        merged.append(element)
    return merged


def _author_line(block):
    if block.get("type") != "para" or len(block["sentences"]) != 1:
        return None
    text = block["sentences"][0]["en"]
    return text if _CHAPTER_AUTHOR.match(text) else None


def merge_chapter_opener(blocks):
    """chapter_number + chapter + 'by ...' paragrafını tek chapter bloğu yapar."""
    merged, pending_number = [], None
    for block in blocks:
        if block["type"] == "chapter_number":
            pending_number = block["num"]
        elif block["type"] == "chapter":
            block["num"] = pending_number
            merged.append(block)
        elif merged and merged[-1]["type"] == "chapter" and _author_line(block):
            merged[-1]["author"] = _author_line(block)
        else:
            merged.append(block)
    return merged
