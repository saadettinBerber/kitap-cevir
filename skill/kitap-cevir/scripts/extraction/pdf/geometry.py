"""Sayfa üzerindeki dikdörtgen ve onun geometrisi. Koordinatlar sol-üst orijinli, y aşağı büyür.

Prosedürel (Bl.6): Box yalnız dört kenarını taşıyan bir veri yapısıdır ve yeni bir kutu türü
beklenmez; akışlar ise yeni geometri işlemleri getirir (birleşim, kesişim, boşluk, kapsama…).
İşlemler bu modülün fonksiyonlarıdır ki yenisi Box'a dokunmadan eklensin. Boş kutu davranışı
PyMuPDF'in `Rect`'iyle aynıdır (Bl.8 · Clean Boundaries).
"""
import functools
from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float


def width(box):
    return box.x1 - box.x0


def height(box):
    return box.y1 - box.y0


def center_x(box):
    return (box.x0 + box.x1) / 2


def center_y(box):
    return (box.y0 + box.y1) / 2


def center(box):
    """(x, y): contains_point'in noktası."""
    return center_x(box), center_y(box)


def is_empty(box):
    return box.x0 >= box.x1 or box.y0 >= box.y1


def enclosing(boxes):
    """Kutuların hepsini kapsayan en küçük kutu."""
    return functools.reduce(union, boxes)


def union(box, other):
    """Boş kutu birleşime bir şey katmaz; PyMuPDF'in `Rect |` davranışı da budur."""
    if is_empty(other):
        return box
    if is_empty(box):
        return other
    return Box(min(box.x0, other.x0), min(box.y0, other.y0), max(box.x1, other.x1), max(box.y1, other.y1))


def expanded(box, margin):
    return Box(box.x0 - margin, box.y0 - margin, box.x1 + margin, box.y1 + margin)


def contains(outer, inner):
    return outer.x0 <= inner.x0 <= inner.x1 <= outer.x1 and outer.y0 <= inner.y0 <= inner.y1 <= outer.y1


def contains_point(box, point):
    """point: (x, y). Sağ ve alt kenar dışarıda kalır: bitişik iki kutu aynı noktayı paylaşmaz."""
    x, y = point
    return box.x0 <= x < box.x1 and box.y0 <= y < box.y1


def intersects(box, other):
    return (not is_empty(box) and not is_empty(other)
            and box.x0 < other.x1 and other.x0 < box.x1
            and box.y0 < other.y1 and other.y0 < box.y1)


def vertical_overlap(box, other):
    """Dikeyde ortak yükseklik; kutular ayrıksa aradaki boşluğun eksi değeri."""
    return min(box.y1, other.y1) - max(box.y0, other.y0)


def vertical_gap(box, other):
    return max(0.0, -vertical_overlap(box, other))
