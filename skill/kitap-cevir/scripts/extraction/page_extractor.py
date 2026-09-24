"""Bir PDF kitap sayfasını yapılı bloklara ayırır. İki sinyali birleştirir:
  1. OpenDataLoader PDF -> başlık, paragraf, liste, görsel, caption, okuma sırası
  2. PyMuPDF -> kod listeleri, satır içi kod, tire onarımı (layout_scan),
     çizgisiz tablolar (table_scan), denklemler (math_scan)

ODL öğe düzeltmeleri odl_elements, sayfa bölgeleri page_zones, öğe → blok
çevirisi block_builder, PyMuPDF
bölgelerinin okuma sırasına yerleşimi page_regions'dadır. Kitaba özgü eşikler
progress.json -> extraction ayarlarından gelir; varsayılanlar
project.DEFAULT_EXTRACTION içindedir. Çıktı references/FORMAT.md'deki blok
şemasının yalnız `en` tarafıdır.
"""
from extraction.block_builder import BlockBuilder, ChapterOpener
from extraction.text_layer.layout_scan import scan_page
from extraction.equations.math_scan import MathScanner
from extraction.odl_elements import OdlElements
from extraction.odl_runner import extract_odl_elements
from extraction.page_regions import PageRegions
from extraction.pdf.pymupdf_adapter import PyMuPdfDocument
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
        with PyMuPdfDocument.open(pdf_path) as document:
            return self.extract_page(document.page(pdf_page), image_dir)

    def extract_page(self, page, image_dir):
        elements = extract_odl_elements(page.pdf_path, page.number, image_dir)
        layout = scan_page(page.pdf_path, page.number, self.settings)
        header, body = self.zones.split(elements)
        math = MathScanner(self.settings, image_dir).scan(page.pdf_path, page.number)
        regions = PageRegions.from_layout(
            layout, scan_tables(page.pdf_path, page.number, self.settings) + math["display"], self._code_block)
        body = (OdlElements(body).flatten_nested_lists().drop_nested_fragments().merge_footnote_markers()
                .with_inline_math(math["inline"], layout["page_height"])
                .without_code_image_links(layout["code_image_links"], layout["page_height"]).items)
        builder = BlockBuilder(self.settings, TextFixer(layout))
        return {"blocks": ChapterOpener(regions.place(body, builder.blocks_of)).merged(),
                "running_header": header, "math": self._inline_images(math)}

    def hyphen_fixes(self, pdf_path, pdf_page):
        """Satır sonunda bölünmüş sözcüklerin onarımı ('McGraw-' + 'Hill')."""
        return scan_page(pdf_path, pdf_page, self.settings)["hyphen_fixes"]

    def _code_block(self, region):
        return {"type": "code", "lang": self.settings["default_code_language"], "code": region["code"]}

    @staticmethod
    def _inline_images(math):
        return [{field: item[field] for field in _INLINE_MATH_FIELDS}
                for item in math["inline"] if item["kind"] == "image"]
