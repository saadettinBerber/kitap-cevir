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

from block_merge import merge_chapter_opener, merge_footnote_markers
from layout_scan import scan_page
from odl_runner import extract_odl_elements
from project import DEFAULT_EXTRACTION
from table_scan import scan_tables
from text_fixer import TextFixer
from text_utils import (clean_ligatures, is_numeric_only, normalize_spaces,
                        split_sentences, strip_list_marker)

CODE_OVERLAP_RATIO = 0.5
_EDGE_PAGE_NUMBER = re.compile(r"^\d+\s+|\s+\d+$")
_BIBLIOGRAPHY_ENTRY = re.compile(r"^\[[A-Za-z0-9]+\]:")


def _bbox(element):
    return element.get("bounding box") or [0, 0, 0, 0]


def _to_odl_region(item, page_height, block):
    """Üst orijinli PyMuPDF aralığını ODL'nin sol-alt orijinine çevirir."""
    return {"bottom": page_height - item["y1"], "top": page_height - item["y0"], "block": block}


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
        self.fixer = None

    def extract(self, pdf_path, pdf_page, image_dir):
        """Sayfayı {blocks, running_header} olarak döndürür; görseller image_dir'e yazılır."""
        elements = extract_odl_elements(pdf_path, pdf_page, image_dir)
        layout = scan_page(pdf_path, pdf_page, self.settings)
        header, body = self._split_header(elements)
        self.fixer = TextFixer(layout)
        regions = self._regions(layout, scan_tables(pdf_path, pdf_page))
        blocks = self._build_blocks(merge_footnote_markers(self._drop_footer(body)), regions)
        return {"blocks": blocks, "running_header": header}

    def _regions(self, layout, tables):
        """Tablo bölgeleri önceliklidir: tablo hücrelerindeki tek aralıklı metin
        ayrıca kod bloğu olarak çıkarılmaz."""
        height = layout["page_height"]
        regions = [_to_odl_region(t, height, t["block"]) for t in tables]
        for code in layout["code_blocks"]:
            if not any(_overlaps(code, t) for t in tables):
                regions.append(_to_odl_region(code, height, self._code_block(code)))
        return regions

    def _split_header(self, elements):
        header, body = None, []
        for element in elements:
            if _bbox(element)[1] > self.settings["header_zone_bottom"] and header is None:
                header = self._running_header(element.get("content", ""))
            else:
                body.append(element)
        return header, body

    def _running_header(self, text):
        title = _EDGE_PAGE_NUMBER.sub("", normalize_spaces(clean_ligatures(text)))
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
        if size >= self.settings["chapter_number_min_size"] and text.isdigit():
            return [{"type": "chapter_number", "num": int(text)}]
        if size >= self.settings["chapter_title_min_size"]:
            return [{"type": "chapter", "en": text}]
        if self.listing_caption.match(text):
            return [{"type": "caption", "kind": "listing", "en": text}]
        return [{"type": "heading", "level": self._heading_level(size), "en": text}]

    def _is_bold_heading(self, font):
        return self.settings["bold_heading_font"] in font and "Bold" in font

    def _paragraph_blocks(self, element):
        text = self.fixer.plain(element.get("content"))
        if not text or is_numeric_only(text):
            return []
        font = element.get("font") or ""
        if self.table_caption.match(text):
            return [{"type": "caption", "kind": "table", "en": self.fixer.rich(text)}]
        if (element.get("font size") or 0) <= self.settings["footnote_max_size"]:
            return [{"type": "footnote", "en": self.fixer.rich(text)}]
        if self._is_bold_heading(font):
            return [{"type": "heading", "level": 3, "en": text}]
        block = {"type": "para", "sentences": _sentence_objects(self.fixer.rich(text))}
        style = _paragraph_style(text, font)
        if style:
            block["style"] = style
        return [block] if block["sentences"] else []

    def _element_blocks(self, element):
        kind = element.get("type")
        if kind == "heading":
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
        emitted, blocks = set(), []
        for element in elements:
            index = _region_index(element, regions)
            if index is None:
                blocks.extend(self._element_blocks(element))
            elif index not in emitted:
                emitted.add(index)
                blocks.append(regions[index]["block"])
        return merge_chapter_opener(blocks)


def extract_page(pdf_path, pdf_page, image_dir, settings=None):
    """Kısa yol: PageExtractor(settings).extract(...)"""
    return PageExtractor(settings).extract(pdf_path, pdf_page, image_dir)
