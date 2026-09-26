"""LiteParse adaptörü: `LayoutReader` arayüzünü LiteParse ile karşılar.

LiteParse (LlamaIndex) Rust tabanlı, VLM kullanmayan hızlı bir ayrıştırıcıdır;
Java istemez, koordinatları zaten sol-üst orijinli PDF puntosudur. Yapıyı
(blok türü, kutu, metin, tablo, figür) LiteParse verir. Font ve puntoyu ise
sayfanın metin katmanından (PdfPage) alırız: LiteParse'ın puntosu kimi PDF'te
farklı ölçülür (Effective Java'da 14.4 yerine 20) ve kitap ayarlarındaki
eşikler metin katmanının puntosuyla ölçülmüştür.
"""
import collections
import itertools
import os
import re

from liteparse import LiteParse

from extraction.pdf.geometry import Box
from extraction.pdf.model import LayoutElement, PageLayout

# LiteParse türü -> düzen öğesi türü. Kod ve ızgara blokları paragraftır: gerçek
# kod listelerini metin katmanı (layout_scan) bulur ve bölgesindeki öğeleri değiştirir.
TEXT_KINDS = {"heading": "heading", "paragraph": "paragraph", "list_item": "list item",
              "code": "paragraph", "grid_fallback": "paragraph"}
FIGURE_DPI = 150
_EMPHASIS = re.compile(r"(?<!\\)(\*{1,3})(?=\S)(.+?)(?<=[^\s\\])\1")
_ESCAPED = re.compile(r"\\([\\*_])")


def layout_reader():
    return LiteParseLayoutReader(LiteParseRunner())


class LiteParseLayoutReader:
    """LiteParse sonucunu düzen öğelerine çevirir; motoru yapıcıdan alır."""

    def __init__(self, runner):
        self._runner = runner

    def read(self, page, image_dir):
        result = self._runner.parse(page, image_dir)
        if not result.pages:
            raise LiteParsePageError(f"LiteParse PDF sayfası {page.number}'i okuyamadı: {result.page_errors}")
        blocks = LiteParseBlocks(Typography(page), FigureFiles(result.images, FigureCrops(page, image_dir)))
        return PageLayout(page.height, blocks.elements(result.pages[0].blocks))


class LiteParsePageError(RuntimeError):
    """LiteParse sayfayı okuyamadı; nedeni page_errors'tadır."""


class LiteParseRunner:
    """LiteParse motoruna dokunan tek yer: bir sayfayı blokları ve görselleriyle okur."""

    def parse(self, page, image_dir):
        """Koşu başlığı ve alt bilgi korunur: onları page_zones ayırır."""
        os.makedirs(image_dir, exist_ok=True)
        parser = LiteParse(ocr_enabled=False, target_pages=str(page.number), extract_blocks=True,
                           extract_images=True, image_output_dir=image_dir, keep_headers_footers=True, quiet=True)
        return parser.parse(page.pdf_path)


class LiteParseBlocks:
    """Bir sayfanın LiteParse blokları; ardışık liste maddeleri ODL'deki gibi tek liste olur."""

    def __init__(self, typography, figures):
        self._typography = typography
        self._figures = figures

    def elements(self, blocks):
        placed = [block for block in blocks if block.bbox is not None]
        elements = []
        for is_list, run in itertools.groupby(placed, key=lambda block: block.kind == "list_item"):
            elements += [self._list(list(run))] if is_list else [e for block in run for e in self._converted(block)]
        return tuple(elements)

    def _converted(self, block):
        """Yatay çizgi (rule) ve bilinmeyen türler öğe değildir."""
        if block.kind in TEXT_KINDS:
            return [self._text_element(block)]
        if block.kind == "table":
            return [self._table(block)]
        return [self._figure(block)] if block.kind == "figure" else []

    def _text_element(self, block):
        box = _box(block.bbox)
        font, size = self._typography.of(box)
        text = plain_text(block.text) if block.text else " ".join(block.lines or [])
        return LayoutElement(TEXT_KINDS[block.kind], box, text, font=font, font_size=size)

    def _list(self, items):
        entries = tuple(map(self._text_element, items))
        return LayoutElement("list", Box.enclosing(entry.box for entry in entries),
                             is_ordered=bool(items[0].ordered), list_items=entries)

    @staticmethod
    def _table(block):
        rows = ([block.header] if block.header else []) + list(block.rows or [])
        cells = tuple(tuple(plain_text(cell.text) for cell in row) for row in rows)
        return LayoutElement("table", _box(block.bbox), table_rows=cells)

    def _figure(self, block):
        box = _box(block.bbox)
        return LayoutElement("image", box, image_file=self._figures.file_for(block.id, box))


class Typography:
    """Kutuya düşen metin parçalarının baskın fontu ve puntosu (karakter sayısıyla tartılır)."""

    def __init__(self, page):
        self._spans = [span for line in page.text_lines() for span in line]

    def of(self, box):
        """(font, punto); kutuda parça yoksa ("", 0.0)."""
        weights = collections.Counter()
        for span in self._spans:
            if box.contains_point(span.box.center_x, span.box.center_y):
                weights[(span.font, span.size)] += len(span.text.strip())
        return weights.most_common(1)[0][0] if weights else ("", 0.0)


class FigureFiles:
    """Figürlerin image_dir'deki dosyaları. LiteParse gömülü görseli yazamadıysa
    (tekrar eden görsel vb.) figür bölgesi sayfadan kırpılır."""

    def __init__(self, images, crops):
        self._names = {image.id: image.name for image in images if image.path}
        self._crops = crops

    def file_for(self, figure_id, box):
        return self._names.get(figure_id) or self._crops.file_for(figure_id, box)


class FigureCrops:
    """Figür bölgelerini sayfadan kırpıp image_dir'e yazar; LiteParse'ın adlandırmasını izler."""

    def __init__(self, page, image_dir):
        self._page = page
        self._image_dir = image_dir

    def file_for(self, figure_id, box):
        name = f"img_{figure_id}.png"
        with open(os.path.join(self._image_dir, name), "wb") as png:
            png.write(self._page.png(box, FIGURE_DPI))
        return name


def plain_text(text):
    """LiteParse metni Markdown'dır: tamamı italik/kalın satır yıldızla sarılır
    (*satır*), metindeki gerçek `*`, `_` ve `\\` ters bölüyle kaçışlanır. Düz metin
    döner. Ters tırnak kaçışlanmadığı için kaynaktakinden ayırt edilemez; olduğu
    gibi kalır, satır içi kod işaretimizle zaten aynıdır (TextFixer onu atlar)."""
    previous = None
    while previous != text:
        previous, text = text, _EMPHASIS.sub(r"\2", text)
    return _ESCAPED.sub(r"\1", text)


def _box(rect):
    return Box(rect.x, rect.y, rect.x + rect.width, rect.y + rect.height)
