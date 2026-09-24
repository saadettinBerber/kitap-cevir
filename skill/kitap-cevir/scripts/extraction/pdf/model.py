"""Sınırı geçen düz veri nesneleri. Hangi kütüphaneden geldiklerini bilmezler;
testler bunları elle kurarak akışları PDF'siz sınar. Kutular `Box`tur."""
from dataclasses import dataclass

from extraction.pdf.geometry import Box


@dataclass(frozen=True)
class Span:
    """Aynı fontla dizilmiş metin parçası. Boş metinli parçalar sınırı geçmez."""
    text: str
    font: str
    size: float
    box: Box
    line_y: float           # satırının üst kenarı; aynı satırın parçaları aynı değeri taşır
    baseline: float         # harflerin oturduğu çizgi; simge ondan yukarı ya da aşağı kayar


@dataclass(frozen=True)
class Drawing:
    """Çizim katmanındaki bir şeklin kutusu: dolgu dikdörtgeni ya da çizgi."""
    box: Box
    is_filled: bool


@dataclass(frozen=True)
class LayoutElement:
    """Düzen okuyucusunun (ODL, LiteParse…) okuma sırasındaki bir öğesi.

    kind: heading | paragraph | caption | list | list item | table | image.
    Türe özgü alanlar yalnız o türde doludur: liste maddeleri `list_items`,
    maddenin altına gömülü öğeler `children`, tablo hücre metinleri `table_rows`,
    görselin image_dir içindeki dosya adı `image_file`.
    """
    kind: str
    box: Box
    text: str = ""
    font: str = ""
    font_size: float = 0.0
    is_nested: bool = False     # liste maddesinden düzleştirilmiş öğe
    is_ordered: bool = False
    list_items: tuple = ()
    children: tuple = ()
    table_rows: tuple = ()
    image_file: str = ""


@dataclass(frozen=True)
class PageLayout:
    """Bir sayfanın düzen öğeleri, okuma sırasıyla."""
    height: float
    elements: tuple
