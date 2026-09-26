"""Bir PDF kitap sayfasını yapılı bloklara ayırır. İki sinyali birleştirir:
  1. Düzen okuyucusu (LayoutReader; extraction.layout_reader: odl | liteparse)
     -> başlık, paragraf, liste, görsel, caption, okuma sırası
  2. Metin ve çizim katmanı (PdfPage; PyMuPDF) -> kod listeleri, satır içi kod,
     tire onarımı (layout_scan), çizgisiz tablolar (table_scan), denklemler (math_scan)

Düzen öğesi düzeltmeleri layout_elements, sayfa bölgeleri page_zones, öğe → blok
çevirisi block_builder, bölüm açılışının birleşmesi chapter_opener, metin
katmanı bölgelerinin okuma sırasına yerleşimi page_regions'dadır. Kitaba özgü
eşikler progress.json -> extraction ayarlarından gelir; varsayılanlar
extraction.settings içindedir. Çıktı references/FORMAT.md'deki blok şemasının
yalnız `en` tarafıdır.
"""
from extraction.block_builder import BlockBuilder
from extraction.chapter_opener import ChapterOpener
from extraction.equations.math_scan import MathScanner
from extraction.layout_elements import LayoutFixer
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
        self._settings = settings
        self._layout_reader = layout_reader
        self._zones = PageZones(self._settings)
        self._tables = TableScanner(self._settings)
        self._math = MathScanner(self._settings)
        self._text_layer = LayoutScanner(self._settings)

    @classmethod
    def for_settings(cls, settings):
        """Düzen okuyucusu ayardan seçilir (layout_reader)."""
        return cls(settings, layout_reader_for(settings))

    def extract(self, page, image_dir):
        """page: PdfPage → {blocks, running_header, math}; görseller image_dir'e yazılır."""
        header, body = self._zones.split(self._layout_reader.read(page, image_dir))
        layout = self._text_layer.scan(page)
        math = self._math.scan(page, image_dir)
        regions = PageRegions.of(self._tables.scan(page) + math["display"], self._code_regions(layout))
        body = LayoutFixer(math["inline"], layout["code_image_links"]).fixed(body)
        builder = BlockBuilder(self._settings, TextFixer(layout))
        return {"blocks": ChapterOpener(regions.place(body, builder.blocks_of)).merged(),
                "running_header": header, "math": self._inline_images(math)}

    def hyphen_fixes(self, page):
        """page: PdfPage; satır sonunda bölünmüş sözcüklerin onarımı ('McGraw-' + 'Hill')."""
        return self._text_layer.scan(page)["hyphen_fixes"]

    def _code_regions(self, layout):
        language = self._settings["default_code_language"]
        return [{**region, "block": {"type": "code", "lang": language, "code": region["code"]}}
                for region in layout["code_blocks"]]

    @staticmethod
    def _inline_images(math):
        return [{field: item[field] for field in _INLINE_MATH_FIELDS}
                for item in math["inline"] if item["kind"] == "image"]
