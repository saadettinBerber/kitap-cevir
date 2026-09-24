"""Metin katmanının bulduğu bölgeleri (tablo, ayrı satır denklemi, kod listesi)
düzen okuyucusunun okuma sırasına yerleştirir. Bölgeye düşen düzen öğeleri
yerine bölgenin tek bloğu yazılır; düzen okuyucusunun hiç görmediği içerik
(Type3 denklem) sayfa konumuna göre araya girer. Koordinatlar üst orijinlidir.
"""
CODE_OVERLAP_RATIO = 0.5


class Region:
    """Sayfanın bir yatay şeridi ve onun yerine yazılacak blok."""

    def __init__(self, item, block):
        self.top = item["y0"]
        self.bottom = item["y1"]
        self.block = block
        # Düzen okuyucusunun hiç görmediği içerik: öğe eşleşmese de konumuna göre yazılır.
        self.is_standalone = block["type"] == "math"

    def covers(self, element):
        """Öğenin yüksekliğinin en az yarısı bu bölgedeyse öğe bölgenindir."""
        box = element.box
        overlap = min(box.y1, self.bottom) - max(box.y0, self.top)
        return overlap / max(box.height, 1) >= CODE_OVERLAP_RATIO


class PageRegions:
    """Bir sayfanın bölgeleri; her bölge okuma sırasına bir kez yazılır."""

    def __init__(self, regions):
        self.regions = regions
        self.emitted = set()

    @classmethod
    def from_layout(cls, layout, priority, code_block):
        """Tablo ve denklem bölgeleri önceliklidir: içlerindeki tek aralıklı metin
        ayrıca kod bloğu olarak çıkarılmaz. code_block: kod bölgesi -> kod bloğu."""
        regions = [Region(item, item["block"]) for item in priority]
        regions += [Region(code, code_block(code)) for code in layout["code_blocks"]
                    if not any(cls._overlaps(code, item) for item in priority)]
        return cls(regions)

    @staticmethod
    def _overlaps(first, second):
        return min(first["y1"], second["y1"]) - max(first["y0"], second["y0"]) > 0

    def place(self, elements, blocks_of):
        """Düzen öğelerini okuma sırasıyla bloklara çevirir (blocks_of), bölgeleri
        yerlerine koyar."""
        blocks = []
        for element in elements:
            blocks += self._standalone_above(element.box.y0)
            index = self._index_covering(element)
            if index is None:
                blocks += blocks_of(element)
            elif index not in self.emitted:
                self.emitted.add(index)
                blocks.append(self.regions[index].block)
        return blocks + self._standalone_above(float("inf"))

    def _index_covering(self, element):
        return next((index for index, region in enumerate(self.regions) if region.covers(element)), None)

    def _standalone_above(self, top):
        """Henüz yazılmamış ve verilen üst kenarın üstünde kalan bağımsız bölgeler (sırayla)."""
        pending = [(index, region) for index, region in enumerate(self.regions)
                   if index not in self.emitted and region.is_standalone and region.bottom <= top]
        self.emitted.update(index for index, _ in pending)
        return [region.block for _, region in sorted(pending, key=lambda pair: pair[1].top)]
