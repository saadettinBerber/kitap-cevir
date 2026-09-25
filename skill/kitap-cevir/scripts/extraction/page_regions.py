"""Metin katmanının bulduğu bölgeleri (tablo, ayrı satır denklemi, kod listesi)
düzen okuyucusunun okuma sırasına yerleştirir. Bölgeye düşen düzen öğeleri
yerine bölgenin tek bloğu yazılır; düzen okuyucusunun hiç görmediği içerik
(Type3 denklem) sayfa konumuna göre araya girer. Koordinatlar üst orijinlidir.
"""
import math

CODE_OVERLAP_RATIO = 0.5


class Region:
    """Sayfanın bir yatay şeridi ve onun yerine yazılacak blok; bölgeler sayfadaki
    sıralarıyla (üst kenar) karşılaştırılır."""

    def __init__(self, item):
        """item: {y0, y1, block}."""
        self._top, self._bottom = item["y0"], item["y1"]
        self._block = item["block"]

    def __lt__(self, other):
        return self._top < other._top

    def overlaps(self, other):
        return min(self._bottom, other._bottom) - max(self._top, other._top) > 0

    def covering(self, element):
        """[bu bölge] öğenin yüksekliğinin en az yarısı bu bölgedeyse; değilse []."""
        return [self] if self._covers(element) else []

    def _covers(self, element):
        box = element.box
        overlap = min(box.y1, self._bottom) - max(box.y0, self._top)
        return overlap / max(box.height, 1) >= CODE_OVERLAP_RATIO

    def standalone_above(self, top):
        """[bu bölge] bağımsızsa ve verilen üst kenarın üstünde kalıyorsa; değilse []."""
        return [self] if self._is_standalone() and self._bottom <= top else []

    def _is_standalone(self):
        """Düzen okuyucusunun hiç görmediği içerik: öğe eşleşmese de konumuna göre yazılır."""
        return self._block["type"] == "math"

    def blocks(self):
        return [self._block]


class PageRegions:
    """Bir sayfanın bölgeleri; her bölge okuma sırasına bir kez, ilk yerinde yazılır."""

    def __init__(self, regions):
        self._regions = regions

    @classmethod
    def of(cls, priority, code):
        """priority, code: {y0, y1, block}. Tablo ve denklem bölgeleri önceliklidir: içlerindeki
        tek aralıklı metin ayrıca kod bloğu olarak çıkarılmaz."""
        first = [Region(item) for item in priority]
        return cls(first + [region for region in map(Region, code) if not any(map(region.overlaps, first))])

    def place(self, elements, blocks_of):
        """Düzen öğelerini okuma sırasıyla bloklara çevirir (blocks_of), bölgeleri yerlerine koyar.
        Bir bölge birçok yerde adaydır (kapsadığı her öğe, altındaki her öğe); ilk yerinde kalır."""
        pieces = [piece for element in elements for piece in self._pieces_at(element, blocks_of)]
        in_reading_order = dict.fromkeys(pieces + self._standalone_above(math.inf))
        return [block for piece in in_reading_order for block in piece.blocks()]

    def _pieces_at(self, element, blocks_of):
        """Önce öğenin üstünde kalan bağımsız bölgeler, sonra öğeyi kapsayan ilk bölge ya da öğenin blokları."""
        covering = [region for candidate in self._regions for region in candidate.covering(element)]
        return self._standalone_above(element.box.y0) + (covering[:1] or [_ElementBlocks(blocks_of(element))])

    def _standalone_above(self, top):
        return [region for candidate in sorted(self._regions) for region in candidate.standalone_above(top)]


class _ElementBlocks:
    """Bölgeye düşmeyen bir öğenin blokları; bölge gibi okuma sırasında kendi yerini alır."""

    def __init__(self, blocks):
        self._blocks = blocks

    def blocks(self):
        return self._blocks
