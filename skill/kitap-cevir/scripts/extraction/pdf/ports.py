"""Çıkarım akışlarının istediği arayüzler (Bl.8 · Using Code That Does Not Yet
Exist). Adaptörler bunlara uyar; testler kendi sahte nesnelerini verir."""
from typing import Protocol

from extraction.pdf.geometry import Box
from extraction.pdf.model import Drawing, PageLayout, Span

FIRST_PAGE_NUMBER = 1       # PDF sayfaları 1'den sayılır; kütüphaneler ve listeler 0'dan


class PdfPage(Protocol):
    """Bir PDF sayfasının metin, çizim ve görüntü katmanı. Kimliği ve boyutu salt okunur sorgulardır."""

    @property
    def pdf_path(self) -> str:
        """Sayfanın PDF dosyası; dış düzen okuyucuları sayfayı dosyadan okur."""

    @property
    def number(self) -> int:
        """FIRST_PAGE_NUMBER'dan başlayan PDF sayfa numarası."""

    @property
    def width(self) -> float: ...

    @property
    def height(self) -> float: ...

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

    @property
    def page_count(self) -> int: ...

    @property
    def metadata(self) -> dict:
        """Dolu metadata alanları (başlık, yazar…); boş değerli alan yoktur."""

    def has_page(self, number: int) -> bool:
        """Numara FIRST_PAGE_NUMBER ile son sayfa arasında mı?"""

    def page(self, number: int) -> PdfPage:
        """FIRST_PAGE_NUMBER'dan başlayan numarasıyla sayfa."""

    def page_text(self, number: int) -> str:
        """Sayfanın düz metni; bkz. PdfPage.text."""


class LayoutReader(Protocol):
    """Sayfanın düzenini (başlık, paragraf, liste, tablo, görsel) okuyan motor."""

    def read(self, page: PdfPage, image_dir: str) -> PageLayout:
        """Görseller image_dir'e yazılır; öğe `image_file` ile dosyayı adlandırır."""
