"""Düzen öğelerinin düz listesi üzerindeki düzeltmeler; bloklar kurulmadan önce
uygulanır: gömülü liste içeriği, alt/üst simge parçaları, dipnot işaretleri,
satır içi denklemler ve e-kitabın kod görseli bağlantıları. Öğeler değişmezdir;
her düzeltme yeni bir liste kurar. Koordinatlar üst orijinlidir.
"""
import dataclasses
import re

from extraction.equations.math_scan import placeholder
from extraction.pdf.geometry import Box

_FOOTNOTE_MARKER = re.compile(r"^[a-z0-9]$")


class OdlElements:
    """Bir sayfanın düzen öğeleri; düzeltmeler zincirlenir, `items` sonucu verir."""

    def __init__(self, items):
        self.items = items

    def flatten_nested_lists(self):
        """ODL italik bir caption'ı ("Table 4-2.") numaralı liste sanıp sonrasındaki
        her şeyi maddenin `children` alanına gömebilir. Gömülü içerik (tablo satırları,
        başlık, paragraf) sıradan öğe olarak akışa döner; yoksa sessizce düşer ve
        sayfadan koca bir bölüm eksilir."""
        flat = []
        for element in self.items:
            list_items = element.list_items if element.kind == "list" else ()
            if not any(item.children for item in list_items):
                flat.append(element)
                continue
            for item in list_items:
                flat += [_nested(item), *map(_nested, item.children)]
        return OdlElements(flat)

    def drop_nested_fragments(self):
        """ODL'nin ayrı paragraf yaptığı alt/üst simge parçalarını atar; metin
        katmanı bunları zaten ev sahibi satıra bağlar (text_layer.script_marks)."""
        return OdlElements([element for element in self.items
                            if not any(self._is_fragment_of(element, host) for host in self.items)])

    @staticmethod
    def _is_fragment_of(element, host):
        """Başka öğenin kutusu içindeki tek karakterlik öğe (alt/üst simge) parçadır."""
        return element is not host and len(element.text.strip()) == 1 and host.box.contains(element.box)

    def merge_footnote_markers(self):
        """Tek harflik dipnot işaretini ('a') aynı satırdaki metnin başına ekler."""
        merged = []
        for element in self.items:
            if merged and self._is_marker(merged[-1]) and self._same_line(merged[-1], element):
                marker = merged.pop().text.strip()
                element = dataclasses.replace(element, text=f"{marker} {element.text}")
            merged.append(element)
        return OdlElements(merged)

    @staticmethod
    def _is_marker(element):
        return element.kind == "paragraph" and bool(_FOOTNOTE_MARKER.match(element.text.strip()))

    @staticmethod
    def _same_line(marker, element):
        return marker.box.vertical_overlap(element.box) > 0 and element.box.x0 > marker.box.x0

    def without_code_image_links(self, slots):
        """E-kitabın kod görseli bağlantılarını (text_layer CodeImageLinkLines) öğelerden
        çıkarır. Bağlantıya yapışmış kod satırı böylece gerçek yüksekliğine döner ve
        kod bölgesine düşer; yalnız bağlantıdan oluşan öğe atılır."""
        links = [CodeImageLink(slot) for slot in slots]
        return OdlElements([kept for element in self.items for kept in self._without_links(element, links)])

    @staticmethod
    def _without_links(element, links):
        """[bağlantılarından arınmış öğe]; öğe yalnız bağlantıdan oluşuyorsa []."""
        present = [link for link in links if link.is_in(element)]
        for link in present:
            element = link.cut_from(element)
        return [element] if element.text or not present else []

    def with_inline_math(self, items):
        """Satır içi denklemleri ev sahibi öğenin metnine yerleştirir: basit sembol
        düz metin, karmaşık denklem ⟦eq-N⟧ yer tutucusu."""
        elements = list(self.items)
        for item in items:
            insert = item["text"] if item["kind"] == "text" else placeholder(item["id"])
            host = next((index for index, element in enumerate(elements) if self._hosts(element, item)), None)
            if host is None:
                print(f"  ! satır içi denklem için öğe bulunamadı: {insert}")
                continue
            elements[host] = self._with_equation(elements[host], item, insert)
        return OdlElements(elements)

    @staticmethod
    def _hosts(element, item):
        """Öğe, denklem kutusunu dikeyde kapsıyorsa ev sahibidir."""
        return element.box.y0 <= item["bbox"].center_y <= element.box.y1

    @classmethod
    def _with_equation(cls, host, item, insert):
        text, count = cls._splice(host.text, item, insert)
        if not count:
            print(f"  ! satır içi denklem yerleştirilemedi, atlandı: {insert}")
        return dataclasses.replace(host, text=text)

    @staticmethod
    def _splice(text, item, insert):
        """insert'i ODL metninde before/after komşu kelimelerinin arasına koyar."""
        before, after = re.escape(item["before"]), re.escape(item["after"])
        if item["before"] and item["after"]:
            return re.subn(before + r"\s*" + after, f"{item['before']} {insert} {item['after']}", text, count=1)
        if item["after"]:
            return re.subn(after, f"{insert} {item['after']}", text, count=1)
        if item["before"]:
            return re.subn(before, f"{item['before']} {insert}", text, count=1)
        return f"{text} {insert}", 1


def _nested(element):
    return dataclasses.replace(element, is_nested=True)


class CodeImageLink:
    """Metin katmanının bulduğu bir kod görseli bağlantısı ve dikey şeridi."""

    def __init__(self, slot):
        self.text = slot["text"]
        self.top, self.bottom = slot["y0"], slot["y1"]

    def is_in(self, element):
        return self.text in element.text and self._overlaps_vertically(element.box)

    def _overlaps_vertically(self, box):
        return self.top < box.y1 and box.y0 < self.bottom

    def cut_from(self, element):
        text = element.text.replace(self.text, "", 1).strip()
        return dataclasses.replace(element, text=text, box=self._box_without_slot(element.box))

    def _box_without_slot(self, box):
        """Şerit kutunun üst yarısındaysa bağlantı öğenin başındadır, alt kısım
        kalır; alt yarısındaysa sonundadır, üst kısım kalır."""
        if (self.top + self.bottom) / 2 < box.center_y:
            return Box(box.x0, max(box.y0, self.bottom), box.x1, box.y1)
        return Box(box.x0, box.y0, box.x1, min(box.y1, self.top))
