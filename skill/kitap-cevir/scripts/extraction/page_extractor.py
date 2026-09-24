"""Bir PDF kitap sayfasını yapılı bloklara ayırır. İki sinyali birleştirir:
  1. Düzen okuyucusu (LayoutReader; extraction.layout_reader: odl | liteparse)
     -> başlık, paragraf, liste, görsel, caption, okuma sırası
  2. Metin ve çizim katmanı (PdfPage; PyMuPDF) -> kod listeleri, satır içi kod,
     tire onarımı (layout_scan), çizgisiz tablolar (table_scan), denklemler (math_scan)

Düzen öğesi düzeltmeleri odl_elements, sayfa bölgeleri page_zones, öğe → blok
çevirisi block_builder, metin katmanı bölgelerinin okuma sırasına yerleşimi
page_regions'dadır. Kitaba özgü eşikler progress.json -> extraction
ayarlarından gelir; varsayılanlar extraction.settings içindedir. Çıktı
references/FORMAT.md'deki blok şemasının yalnız `en` tarafıdır.
"""
from extraction.block_builder import BlockBuilder, ChapterOpener
from extraction.equations.math_scan import MathScanner
from extraction.odl_elements import OdlElements
from extraction.page_regions import PageRegions
from extraction.page_zones import PageZones
from extraction.pdf.readers import layout_reader_for
from extraction.tables.table_scan import TableScanner
from extraction.text_fixer import TextFixer
from extraction.text_layer.layout_scan import LayoutScanner

_INLINE_MATH_FIELDS = ("id", "src", "text", "latex")


class PageExtractor:
    """extraction ayarlarıyla bir PDF sayfasını blok şemasına dönüştürür."""

    def __init__(self, settings, layout_reader):
        self.settings = settings
        self.layout_reader = layout_reader
        self.zones = PageZones(self.settings)
        self.tables = TableScanner(self.settings)
        self.text_layer = LayoutScanner(self.settings)

    @classmethod
    def for_settings(cls, settings):
        """Düzen okuyucusu ayardan seçilir (layout_reader)."""
        return cls(settings, layout_reader_for(settings))

    def extract(self, page, image_dir):
        """page: PdfPage → {blocks, running_header, math}; görseller image_dir'e yazılır."""
        header, body = self.zones.split(self.layout_reader.read(page, image_dir))
        layout = self.text_layer.scan(page)
        math = MathScanner(self.settings, image_dir).scan(page)
        regions = PageRegions.from_layout(layout, self.tables.scan(page) + math["display"], self._code_block)
        body = (OdlElements(body).flatten_nested_lists().drop_nested_fragments().merge_footnote_markers()
                .with_inline_math(math["inline"]).without_code_image_links(layout["code_image_links"]).items)
        builder = BlockBuilder(self.settings, TextFixer(layout))
        return {"blocks": ChapterOpener(regions.place(body, builder.blocks_of)).merged(),
                "running_header": header, "math": self._inline_images(math)}

    def hyphen_fixes(self, page):
        """page: PdfPage; satır sonunda bölünmüş sözcüklerin onarımı ('McGraw-' + 'Hill')."""
        return self.text_layer.scan(page)["hyphen_fixes"]

    def _code_block(self, region):
        return {"type": "code", "lang": self.settings["default_code_language"], "code": region["code"]}

    @staticmethod
    def _inline_images(math):
        return [{field: item[field] for field in _INLINE_MATH_FIELDS}
                for item in math["inline"] if item["kind"] == "image"]
