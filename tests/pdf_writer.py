"""Öğrenme testleri için gerçek, tek sayfalık PDF yazar (Bl.8 · Learning Tests).

PyMuPDF'in yazma arayüzüne yalnız burada ve sayfa yazıcılarında dokunulur (Bl.8 · Clean Boundaries):
yazıcı sayfanın içeriğini söyler, write_pdf belgeyi kurup kaydeder.
"""
import fitz

LINE_FONT_SIZE = 11


class PageWriter:
    """Test sayfasını satır satır yazar; satır içinde font değişebilir. Alt sınıfın write'ı
    sayfanın içeriği, TITLE'ı belgenin başlığıdır."""
    TITLE = ""

    def __init__(self, page):
        self._page = page

    def _line(self, origin, *parts):
        """origin: ilk parçanın (x, taban çizgisi); parçalar (metin, font) çiftleridir."""
        x, y = origin
        for text, font in parts:
            self._page.insert_text((x, y), text, fontsize=LINE_FONT_SIZE, fontname=font)
            x += fitz.get_text_length(text, font, LINE_FONT_SIZE)


def write_pdf(path, page_writer):
    """page_writer: PageWriter alt sınıfı; yeni belgenin tek sayfasını o yazar."""
    document = fitz.open()
    document.set_metadata({"title": page_writer.TITLE})
    writer = page_writer(document.new_page())
    writer.write()
    document.save(path)
    document.close()
