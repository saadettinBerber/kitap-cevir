"""Bir PDF kitap sayfasını yapılı bloklara ayırır. İki sinyali birleştirir:
  1. OpenDataLoader PDF -> başlık, paragraf, liste, görsel, caption, okuma sırası
  2. PyMuPDF -> kod listeleri, satır içi kod, tire onarımı (layout_scan),
     çizgisiz tablolar (table_scan), denklemler (math_scan)

Sayfa bölgeleri page_zones, öğe → blok çevirisi block_builder, PyMuPDF
bölgelerinin okuma sırasına yerleşimi page_regions'dadır. Kitaba özgü eşikler
progress.json -> extraction ayarlarından gelir; varsayılanlar
project.DEFAULT_EXTRACTION içindedir. Çıktı references/FORMAT.md'deki blok
şemasının yalnız `en` tarafıdır.
"""
from extraction.block_builder import BlockBuilder
from extraction.block_merge import (drop_nested_fragments, flatten_nested_lists, insert_inline_math,
                         merge_chapter_opener, merge_footnote_markers)
from extraction.text_layer.layout_scan import scan_page
from extraction.equations.math_scan import scan_math
from extraction.odl_runner import extract_odl_elements
from extraction.page_regions import PageRegions
from extraction.page_zones import PageZones
from project import DEFAULT_EXTRACTION
from extraction.tables.table_scan import scan_tables
from extraction.text_fixer import TextFixer

_INLINE_MATH_FIELDS = ("id", "src", "text", "latex")


class PageExtractor:
    """extraction ayarlarıyla bir PDF sayfasını blok şemasına dönüştürür."""

    def __init__(self, settings=None):
        self.settings = {**DEFAULT_EXTRACTION, **(settings or {})}
        self.zones = PageZones(self.settings)

    def extract(self, pdf_path, pdf_page, image_dir):
        """Sayfayı {blocks, running_header, math} olarak döndürür; görseller image_dir'e yazılır."""
        elements = extract_odl_elements(pdf_path, pdf_page, image_dir)
        layout = scan_page(pdf_path, pdf_page, self.settings)
        header, body = self.zones.split(elements)
        math = scan_math(pdf_path, pdf_page, self.settings, image_dir)
        regions = PageRegions.from_layout(
            layout, scan_tables(pdf_path, pdf_page, self.settings) + math["display"], self._code_block)
        body = merge_footnote_markers(drop_nested_fragments(flatten_nested_lists(body)))
        body = insert_inline_math(body, math["inline"], layout["page_height"])
        builder = BlockBuilder(self.settings, TextFixer(layout))
        return {"blocks": merge_chapter_opener(regions.place(body, builder.blocks_of)),
                "running_header": header, "math": self._inline_images(math)}

    def _code_block(self, region):
        return {"type": "code", "lang": self.settings["default_code_language"], "code": region["code"]}

    @staticmethod
    def _inline_images(math):
        return [{field: item[field] for field in _INLINE_MATH_FIELDS}
                for item in math["inline"] if item["kind"] == "image"]
