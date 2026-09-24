"""Çıkarım akışlarının istediği arayüzler (Bl.8 · Using Code That Does Not Yet
Exist). Adaptörler bunlara uyar; testler kendi sahte nesnelerini verir."""
from typing import Protocol

from extraction.pdf.geometry import Box
from extraction.pdf.model import Drawing, Span


class PdfPage(Protocol):
    """Bir PDF sayfasının metin, çizim ve görüntü katmanı."""
    pdf_path: str
    number: int                 # 1'den başlayan PDF sayfa numarası
    height: float

    def text_lines(self) -> list[tuple[Span, ...]]:
        """Satırlar ve parçaları, kütüphanenin okuma sırasıyla; boş satır yok."""

    def drawings(self) -> list[Drawing]: ...

    def text_in(self, box: Box) -> str: ...

    def png(self, box: Box, dpi: int) -> bytes:
        """Kutunun görüntüsü, PNG baytları."""
