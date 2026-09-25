"""Çıkarım akışlarının istediği arayüzler (Bl.8 · Using Code That Does Not Yet
Exist). Adaptörler bunlara uyar; testler kendi sahte nesnelerini verir."""
from typing import Protocol

from extraction.pdf.geometry import Box
from extraction.pdf.model import Drawing, PageLayout, Span

FIRST_PAGE_NUMBER = 1       # PDF sayfaları 1'den sayılır; kütüphaneler ve listeler 0'dan


class PdfPage(Protocol):
    """Bir PDF sayfasının metin, çizim ve görüntü katmanı."""
    pdf_path: str
    number: int                 # FIRST_PAGE_NUMBER'dan başlayan PDF sayfa numarası
    width: float
    height: float

    def text_lines(self) -> list[tuple[Span, ...]]:
        """Satırlar ve parçaları, kütüphanenin okuma sırasıyla; boş satır yok."""

    def text(self) -> str:
        """Sayfanın düz metni, kütüphanenin okuma sırasıyla."""

    def drawings(self) -> list[Drawing]: ...

    def text_in(self, box: Box) -> str: ...

    def png(self, box: Box, dpi: int) -> bytes:
        """Kutunun görüntüsü, PNG baytları."""


class PdfDocument(Protocol):
    """Açık bir PDF; `with` bloğunun sonunda kapanır."""
    page_count: int
    metadata: dict              # başlık, yazar…; boş değerler olabilir

    def page(self, number: int) -> PdfPage:
        """FIRST_PAGE_NUMBER'dan başlayan numarasıyla sayfa."""

    def page_text(self, number: int) -> str:
        """Sayfanın düz metni; bkz. PdfPage.text."""


class LayoutReader(Protocol):
    """Sayfanın düzenini (başlık, paragraf, liste, tablo, görsel) okuyan motor."""

    def read(self, page: PdfPage, image_dir: str) -> PageLayout:
        """Görseller image_dir'e yazılır; öğe `image_file` ile dosyayı adlandırır."""
