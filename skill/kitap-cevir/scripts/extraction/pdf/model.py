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


@dataclass(frozen=True)
class Drawing:
    """Çizim katmanındaki bir şeklin kutusu: dolgu dikdörtgeni ya da çizgi."""
    box: Box
    is_filled: bool
