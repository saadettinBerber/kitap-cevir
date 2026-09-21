"""Bir PDF kitap sayfasını yapılı bloklara ayırır. İki sinyali birleştirir:
  1. OpenDataLoader PDF -> başlık, paragraf, liste, görsel, caption, okuma sırası
  2. PyMuPDF (layout_scan) -> girintili kod listeleri, satır içi kod, tire onarımı

Kitaba özgü eşikler (koşu başlığı bölgesi, alt bilgi bölgesi, başlık font
boyutları, listing caption deseni) progress.json -> extraction ayarlarından
gelir; varsayılanlar project.DEFAULT_EXTRACTION içindedir.
Çıktı references/FORMAT.md'deki blok şemasının yalnız `en` tarafıdır.
"""
import os
import re

from block_merge import (drop_nested_fragments, flatten_nested_lists, insert_inline_math,
                         merge_chapter_opener, merge_footnote_markers)
from layout_scan import scan_page
from math_scan import scan_math
from odl_runner import extract_odl_elements
from project import DEFAULT_EXTRACTION
from table_scan import scan_tables
from text_fixer import TextFixer
from text_utils import (clean_ligatures, is_numeric_only, normalize_spaces,
                        split_sentences, strip_list_marker)

CODE_OVERLAP_RATIO = 0.5
MAX_HEADING_CHARS = 100
_EDGE_PAGE_NUMBER = re.compile(r"^\d+\s+|\s+\d+$")
_EDGE_SEPARATOR = re.compile(r"^[|·•]\s*|\s*[|·•]$")
_BIBLIOGRAPHY_ENTRY = re.compile(r"^\[[A-Za-z0-9]+\]:")


def _bbox(element):
    return element.get("bounding box") or [0, 0, 0, 0]


def _to_odl_region(item, page_height, block):
    """Üst orijinli PyMuPDF aralığını ODL'nin sol-alt orijinine çevirir.
    `standalone`: ODL'nin hiç görmediği içerik (Type3 denklem) — öğe eşleşmese
    de konumuna göre yazılır; kod/tablo bölgeleri yalnız öğe eşleşince yazılır."""
    return {"bottom": page_height - item["y1"], "top": page_height - item["y0"],
            "block": block, "standalone": block["type"] == "math"}


def _looks_like_paragraph(text):
    """ODL karışık fontlu (satır içi kod/denklem) gövde satırını başlık sanabilir;
    uzun ya da noktalamayla biten 'başlık' gövde metnidir."""
    return len(text) > MAX_HEADING_CHARS or text.endswith((".", ":", ";", ","))


def _regions_above(regions, top, emitted):
    """Henüz yazılmamış ve verilen üst kenarın üstünde kalan bölgeler (sırayla)."""
    pending = [(i, r) for i, r in enumerate(regions)
               if i not in emitted and r["standalone"] and r["bottom"] >= top]
    for index, _ in pending:
        emitted.add(index)
    return [r["block"] for _, r in sorted(pending, key=lambda ir: -ir[1]["top"])]


def _overlaps(first, second):
    return min(first["y1"], second["y1"]) - max(first["y0"], second["y0"]) > 0


def _region_index(element, regions):
    bottom, top = _bbox(element)[1], _bbox(element)[3]
    element_height = max(top - bottom, 1)
    for index, region in enumerate(regions):
        overlap = min(top, region["top"]) - max(bottom, region["bottom"])
        if overlap / element_height >= CODE_OVERLAP_RATIO:
            return index
    return None


def _sentence_objects(text):
    return [{"en": s} for s in split_sentences(text) if not is_numeric_only(s)]


def _paragraph_style(text, font):
    if _BIBLIOGRAPHY_ENTRY.match(text):
        return "reference"
    return "quote" if "Italic" in font else None


def _list_block(element, fixer):
    items = [{"en": strip_list_marker(fixer.rich(fixer.plain(item.get("content"))))}
             for item in element.get("list items", [])]
    ordered = element.get("numbering style", "unordered") != "unordered"
    return [{"type": "list", "ordered": ordered, "items": items}]


def _cell_text(cell, fixer):
    parts = [kid.get("content", "") for kid in cell.get("kids", [])]
    return {"en": fixer.rich(fixer.plain(" ".join(parts)))}


def _table_block(element, fixer):
    rows = [[_cell_text(cell, fixer) for cell in row.get("cells", [])]
            for row in element.get("rows", [])]
    return [{"type": "table", "rows": rows}] if rows else []


class PageExtractor:
    """extraction ayarlarıyla ODL öğelerini blok şemasına dönüştürür."""

    def __init__(self, settings=None):
        self.settings = {**DEFAULT_EXTRACTION, **(settings or {})}
        self.listing_caption = re.compile(self.settings["listing_caption_pattern"])
        self.table_caption = re.compile(self.settings["table_caption_pattern"])
        self.equation_caption = re.compile(self.settings["equation_caption_pattern"])
        label = self.settings["chapter_label_pattern"]
        self.chapter_label = re.compile(label) if label else None
        self.fixer = None

    def extract(self, pdf_path, pdf_page, image_dir):
        """Sayfayı {blocks, running_header} olarak döndürür; görseller image_dir'e yazılır."""
        elements = extract_odl_elements(pdf_path, pdf_page, image_dir)
        layout = scan_page(pdf_path, pdf_page, self.settings)
        header, body = self._split_header(elements)
        self.fixer = TextFixer(layout)
        math = scan_math(pdf_path, pdf_page, self.settings, image_dir)
        regions = self._regions(layout, scan_tables(pdf_path, pdf_page, self.settings) + math["display"])
        body = flatten_nested_lists(self._drop_footer(body))
        body = merge_footnote_markers(drop_nested_fragments(body))
        body = insert_inline_math(body, math["inline"], layout["page_height"])
        inline_images = [{k: i[k] for k in ("id", "src", "text", "latex")}
                         for i in math["inline"] if i["kind"] == "image"]
        return {"blocks": self._build_blocks(body, regions), "running_header": header,
                "math": inline_images}

    def _regions(self, layout, priority):
        """Tablo ve denklem bölgeleri önceliklidir: içlerindeki tek aralıklı metin
        ayrıca kod bloğu olarak çıkarılmaz."""
        height = layout["page_height"]
        regions = [_to_odl_region(r, height, r["block"]) for r in priority]
        for code in layout["code_blocks"]:
            if not any(_overlaps(code, r) for r in priority):
                regions.append(_to_odl_region(code, height, self._code_block(code)))
        return regions

    def _split_header(self, elements):
        """Koşu başlığı üstte (varsayılan) ya da altta olabilir; alttaki öğeleri
        gövdeden ayrıca ayıklamak gerekmez, _drop_footer zaten atar."""
        if self.settings["header_at_bottom"]:
            return self._bottom_header(elements), list(elements)
        header, body = None, []
        for element in elements:
            if _bbox(element)[1] > self.settings["header_zone_bottom"] and header is None:
                header = self._running_header(element.get("content", ""))
            else:
                body.append(element)
        return header, body

    def _bottom_header(self, elements):
        """Alt koşu başlığı ("Kesit Adı | 201", "200 | Chapter 14: ..."): alt
        bölgedeki öğeler okuma sırasında birleştirilir. Yalnız sayfa numarası
        varsa bölüm açılış sayfasıdır, kesit yoktur."""
        footer_top = self.settings["footer_zone_top"]
        parts = [e.get("content", "") or "" for e in elements if _bbox(e)[3] < footer_top]
        header = self._running_header(" ".join(parts))
        title = header["text"]
        return header if title and not is_numeric_only(title) else None

    def _running_header(self, text):
        title = _EDGE_PAGE_NUMBER.sub("", normalize_spaces(clean_ligatures(text)))
        title = _EDGE_SEPARATOR.sub("", title).strip()
        prefix = self.settings["chapter_header_prefix"]
        return {"text": title, "is_chapter": title.startswith(prefix)}

    def _drop_footer(self, elements):
        return [e for e in elements if _bbox(e)[3] >= self.settings["footer_zone_top"]]

    def _code_block(self, region):
        return {"type": "code", "lang": self.settings["default_code_language"],
                "code": region["code"]}

    def _heading_level(self, size):
        if size >= self.settings["section_min_size"]:
            return 1
        return 2 if size >= self.settings["subsection_min_size"] else 3

    def _heading_blocks(self, element):
        text = self.fixer.plain(element.get("content"))
        size = element.get("font size") or 0
        if not text:
            return []
        if _looks_like_paragraph(text):
            return self._paragraph_blocks(element)
        if size >= self.settings["chapter_number_min_size"] and text.isdigit():
            return [{"type": "chapter_number", "num": int(text)}]
        if size >= self.settings["chapter_title_min_size"]:
            return [{"type": "chapter", "en": text}]
        if self.listing_caption.match(text):
            return [{"type": "caption", "kind": "listing", "en": text}]
        return [{"type": "heading", "level": self._heading_level(size), "en": text}]

    def _is_bold_heading(self, font):
        return self.settings["bold_heading_font"] in font and "bold" in font.lower()

    def _paragraph_blocks(self, element):
        text = self.fixer.plain(element.get("content"))
        if not text or is_numeric_only(text):
            return []
        font = element.get("font") or ""
        if self.table_caption.match(text):
            return [{"type": "caption", "kind": "table", "en": self.fixer.rich(text)}]
        if self.equation_caption.match(text):
            return [{"type": "caption", "kind": "equation", "en": self.fixer.rich(text)}]
        if (element.get("font size") or 0) <= self.settings["footnote_max_size"]:
            return [{"type": "footnote", "en": self.fixer.rich(text)}]
        if self._is_bold_heading(font):
            return [{"type": "heading", "level": 3, "en": text}]
        block = {"type": "para", "sentences": _sentence_objects(self.fixer.rich(text))}
        style = _paragraph_style(text, font)
        if style:
            block["style"] = style
        return [block] if block["sentences"] else []

    def _chapter_label(self, element):
        """Bölüm etiketi satırı (CHAPTER 7 gibi); ODL kimi kitapta bunu paragraf
        sanar, merge_chapter_opener numarayı bölüm başlığına taşır."""
        if self.chapter_label is None:
            return None
        match = self.chapter_label.match(self.fixer.plain(element.get("content")))
        return {"type": "chapter_number", "num": int(match.group(1))} if match else None

    def _is_nested_heading(self, element):
        """Liste maddesine gömülmüş öğelerin tipini ODL düzleştirir (hepsi
        paragraf olur); başlık puntosundaki bir öğe aslında başlıktır."""
        return (element.get("nested")
                and (element.get("font size") or 0) >= self.settings["subsection_min_size"])

    def _element_blocks(self, element):
        label = self._chapter_label(element)
        if label:
            return [label]
        kind = element.get("type")
        if kind == "heading" or (kind == "paragraph" and self._is_nested_heading(element)):
            return self._heading_blocks(element)
        if kind == "paragraph":
            return self._paragraph_blocks(element)
        if kind == "list":
            return _list_block(element, self.fixer)
        if kind == "image":
            return [{"type": "image", "src": os.path.basename(element.get("source", ""))}]
        if kind == "caption":
            return [{"type": "caption", "en": self.fixer.rich(self.fixer.plain(element.get("content")))}]
        if kind == "table":
            return _table_block(element, self.fixer)
        return []

    def _build_blocks(self, elements, regions):
        """ODL öğesi düşmeyen bölgeler (ODL'nin hiç görmediği denklemler)
        sayfa konumuna göre araya eklenir."""
        emitted, blocks = set(), []
        for element in elements:
            blocks.extend(_regions_above(regions, _bbox(element)[3], emitted))
            index = _region_index(element, regions)
            if index is None:
                blocks.extend(self._element_blocks(element))
            elif index not in emitted:
                emitted.add(index)
                blocks.append(regions[index]["block"])
        blocks.extend(_regions_above(regions, float("-inf"), emitted))
        return merge_chapter_opener(blocks)


def extract_page(pdf_path, pdf_page, image_dir, settings=None):
    """Kısa yol: PageExtractor(settings).extract(...)"""
    return PageExtractor(settings).extract(pdf_path, pdf_page, image_dir)
