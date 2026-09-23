"""ODL öğelerini ve blokları birleştiren düzeltmeler: dipnot işaretleri,
bölüm açılışı (numara + başlık + yazar satırı) ve satır içi denklemler."""
import re

from math_scan import placeholder
from odl_runner import bbox_of

_CHAPTER_AUTHOR = re.compile(r"^(?:by|with) [A-Z]")
_FOOTNOTE_MARKER = re.compile(r"^[a-z0-9]$")


def _is_marker(element):
    return (element.get("type") == "paragraph"
            and bool(_FOOTNOTE_MARKER.match((element.get("content") or "").strip())))


def _same_line(marker, element):
    overlap = min(bbox_of(marker)[3], bbox_of(element)[3]) - max(bbox_of(marker)[1], bbox_of(element)[1])
    return overlap > 0 and bbox_of(element)[0] > bbox_of(marker)[0]


def flatten_nested_lists(elements):
    """ODL italik bir caption'ı ("Table 4-2.") numaralı liste sanıp sonrasındaki
    her şeyi maddenin `kids` alanına gömebilir. Gömülü içerik (tablo satırları,
    başlık, paragraf) sıradan öğe olarak akışa döner; yoksa sessizce düşer ve
    sayfadan koca bir bölüm eksilir."""
    flat = []
    for element in elements:
        items = element.get("list items", []) if element.get("type") == "list" else []
        if not any(item.get("kids") for item in items):
            flat.append(element)
            continue
        for item in items:
            flat.append({**item, "nested": True})
            flat += [{**kid, "nested": True} for kid in item.get("kids", [])]
    return flat


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


def _splice(text, item, insert):
    """insert'i ODL metninde before/after komşu kelimelerinin arasına koyar."""
    before, after = re.escape(item["before"]), re.escape(item["after"])
    if item["before"] and item["after"]:
        return re.subn(before + r"\s*" + after, f"{item['before']} {insert} {item['after']}", text, count=1)
    if item["after"]:
        return re.subn(after, f"{insert} {item['after']}", text, count=1)
    if item["before"]:
        return re.subn(before, f"{item['before']} {insert}", text, count=1)
    return f"{text} {insert}", 1


def _hosts(element, item, page_height):
    """Öğe, denklem kutusunu dikeyde kapsıyorsa ev sahibidir (ODL sol-alt orijin)."""
    top, bottom = page_height - item["bbox"].y0, page_height - item["bbox"].y1
    center = (top + bottom) / 2
    return bbox_of(element)[1] <= center <= bbox_of(element)[3]


def insert_inline_math(elements, items, page_height):
    """Satır içi denklemleri ev sahibi ODL öğesinin metnine yerleştirir:
    basit sembol düz metin, karmaşık denklem ⟦eq-N⟧ yer tutucusu."""
    for item in items:
        insert = item["text"] if item["kind"] == "text" else placeholder(item["id"])
        host = next((e for e in elements if _hosts(e, item, page_height)), None)
        if host is None:
            print(f"  ! satır içi denklem için öğe bulunamadı: {insert}")
            continue
        host["content"], count = _splice(host.get("content") or "", item, insert)
        if not count:
            print(f"  ! satır içi denklem yerleştirilemedi, sona eklendi: {insert}")
    return elements


def _is_fragment_of(element, host):
    """Başka öğenin kutusu içindeki tek karakterlik öğe (alt/üst simge) parçadır."""
    inner, outer = bbox_of(element), bbox_of(host)
    return (element is not host and len((element.get("content") or "").strip()) == 1
            and outer[0] <= inner[0] and inner[2] <= outer[2]
            and outer[1] <= inner[1] and inner[3] <= outer[3])


def drop_nested_fragments(elements):
    """ODL'nin ayrı paragraf yaptığı alt/üst simge parçalarını atar; metin
    katmanı bunları zaten ev sahibi satıra bağlar (code_lines)."""
    return [e for e in elements if not any(_is_fragment_of(e, host) for host in elements)]
