"""Sayfa üzerindeki dikdörtgen. Koordinatlar sol-üst orijinli, y aşağı büyür."""
import functools
from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @classmethod
    def enclosing(cls, boxes):
        """Kutuların hepsini kapsayan en küçük kutu."""
        return functools.reduce(cls.union, boxes)

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0

    def is_empty(self):
        return self.x0 >= self.x1 or self.y0 >= self.y1

    def union(self, other):
        """Boş kutu birleşime bir şey katmaz; PyMuPDF'in `Rect |` davranışı da budur."""
        if other.is_empty():
            return self
        if self.is_empty():
            return other
        return Box(min(self.x0, other.x0), min(self.y0, other.y0),
                   max(self.x1, other.x1), max(self.y1, other.y1))

    def expanded(self, margin):
        return Box(self.x0 - margin, self.y0 - margin, self.x1 + margin, self.y1 + margin)

    def contains(self, other):
        return (self.x0 <= other.x0 <= other.x1 <= self.x1
                and self.y0 <= other.y0 <= other.y1 <= self.y1)

    def contains_point(self, x, y):
        """Sağ ve alt kenar dışarıda kalır: bitişik iki kutu aynı noktayı paylaşmaz."""
        return self.x0 <= x < self.x1 and self.y0 <= y < self.y1

    def intersects(self, other):
        return (not self.is_empty() and not other.is_empty()
                and self.x0 < other.x1 and other.x0 < self.x1
                and self.y0 < other.y1 and other.y0 < self.y1)

    def vertical_overlap(self, other):
        """Dikeyde ortak yükseklik; kutular ayrıksa aradaki boşluğun eksi değeri."""
        return min(self.y1, other.y1) - max(self.y0, other.y0)

    def vertical_gap(self, other):
        return max(0.0, -self.vertical_overlap(other))

    @property
    def center_x(self):
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self):
        return (self.y0 + self.y1) / 2
