"""ODL'nin düz öğe listesi üzerindeki düzeltmeler; bloklar kurulmadan önce
uygulanır: gömülü liste içeriği, alt/üst simge parçaları, dipnot işaretleri,
satır içi denklemler ve e-kitabın kod görseli bağlantıları. ODL koordinatları
sol-alt orijinlidir.
"""
import re

from extraction.equations.math_scan import placeholder
from extraction.odl_runner import bbox_of

_FOOTNOTE_MARKER = re.compile(r"^[a-z0-9]$")


class OdlElements:
    """Bir sayfanın ODL öğeleri; düzeltmeler zincirlenir, `items` sonucu verir.
    Dipnot işareti ve satır içi denklem öğe metnini yerinde değiştirir."""

    def __init__(self, items):
        self.items = items

    def flatten_nested_lists(self):
        """ODL italik bir caption'ı ("Table 4-2.") numaralı liste sanıp sonrasındaki
        her şeyi maddenin `kids` alanına gömebilir. Gömülü içerik (tablo satırları,
        başlık, paragraf) sıradan öğe olarak akışa döner; yoksa sessizce düşer ve
        sayfadan koca bir bölüm eksilir."""
        flat = []
        for element in self.items:
            list_items = element.get("list items", []) if element.get("type") == "list" else []
            if not any(item.get("kids") for item in list_items):
                flat.append(element)
                continue
            for item in list_items:
                flat.append({**item, "nested": True})
                flat += [{**kid, "nested": True} for kid in item.get("kids", [])]
        return OdlElements(flat)

    def drop_nested_fragments(self):
        """ODL'nin ayrı paragraf yaptığı alt/üst simge parçalarını atar; metin
        katmanı bunları zaten ev sahibi satıra bağlar (text_layer.script_marks)."""
        return OdlElements([element for element in self.items
                            if not any(self._is_fragment_of(element, host) for host in self.items)])

    @staticmethod
    def _is_fragment_of(element, host):
        """Başka öğenin kutusu içindeki tek karakterlik öğe (alt/üst simge) parçadır."""
        inner, outer = bbox_of(element), bbox_of(host)
        return (element is not host and len((element.get("content") or "").strip()) == 1
                and outer[0] <= inner[0] and inner[2] <= outer[2]
                and outer[1] <= inner[1] and inner[3] <= outer[3])

    def merge_footnote_markers(self):
        """Tek harflik dipnot işaretini ('a') aynı satırdaki metnin başına ekler."""
        merged = []
        for element in self.items:
            if merged and self._is_marker(merged[-1]) and self._same_line(merged[-1], element):
                marker = merged.pop()["content"].strip()
                element["content"] = f"{marker} {element.get('content') or ''}"
            merged.append(element)
        return OdlElements(merged)

    @staticmethod
    def _is_marker(element):
        return (element.get("type") == "paragraph"
                and bool(_FOOTNOTE_MARKER.match((element.get("content") or "").strip())))

    @staticmethod
    def _same_line(marker, element):
        overlap = min(bbox_of(marker)[3], bbox_of(element)[3]) - max(bbox_of(marker)[1], bbox_of(element)[1])
        return overlap > 0 and bbox_of(element)[0] > bbox_of(marker)[0]

    def without_code_image_links(self, slots, page_height):
        """E-kitabın kod görseli bağlantılarını (text_layer CodeImageLinkLines) öğelerden
        çıkarır. Bağlantıya yapışmış kod satırı böylece gerçek yüksekliğine döner ve
        kod bölgesine düşer; yalnız bağlantıdan oluşan öğe atılır."""
        links = [CodeImageLink(slot, page_height) for slot in slots]
        return OdlElements([kept for element in self.items for kept in self._without_links(element, links)])

    @staticmethod
    def _without_links(element, links):
        """[bağlantılarından arınmış öğe]; öğe yalnız bağlantıdan oluşuyorsa []."""
        present = [link for link in links if link.is_in(element)]
        for link in present:
            element = link.cut_from(element)
        return [element] if element.get("content") or not present else []

    def with_inline_math(self, items, page_height):
        """Satır içi denklemleri ev sahibi öğenin metnine yerleştirir: basit sembol
        düz metin, karmaşık denklem ⟦eq-N⟧ yer tutucusu."""
        for item in items:
            insert = item["text"] if item["kind"] == "text" else placeholder(item["id"])
            host = next((e for e in self.items if self._hosts(e, item, page_height)), None)
            if host is None:
                print(f"  ! satır içi denklem için öğe bulunamadı: {insert}")
                continue
            host["content"], count = self._splice(host.get("content") or "", item, insert)
            if not count:
                print(f"  ! satır içi denklem yerleştirilemedi, sona eklendi: {insert}")
        return self

    @staticmethod
    def _hosts(element, item, page_height):
        """Öğe, denklem kutusunu dikeyde kapsıyorsa ev sahibidir (denklem üst orijinli)."""
        top, bottom = page_height - item["bbox"].y0, page_height - item["bbox"].y1
        center = (top + bottom) / 2
        return bbox_of(element)[1] <= center <= bbox_of(element)[3]

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


class CodeImageLink:
    """Metin katmanının bulduğu bir kod görseli bağlantısı ve şeridi, ODL koordinatında."""

    def __init__(self, slot, page_height):
        self.text = slot["text"]
        self.bottom, self.top = page_height - slot["y1"], page_height - slot["y0"]

    def is_in(self, element):
        return self.text in (element.get("content") or "") and self._overlaps_vertically(bbox_of(element))

    def _overlaps_vertically(self, box):
        return self.bottom < box[3] and box[1] < self.top

    def cut_from(self, element):
        content = element["content"].replace(self.text, "", 1).strip()
        return {**element, "content": content, "bounding box": self._box_without_slot(bbox_of(element))}

    def _box_without_slot(self, box):
        """Şerit kutunun üst yarısındaysa bağlantı öğenin başındadır, alt kısım
        kalır; alt yarısındaysa sonundadır, üst kısım kalır."""
        x0, bottom, x1, top = box
        if (self.bottom + self.top) / 2 > (bottom + top) / 2:
            return [x0, bottom, x1, min(top, self.bottom)]
        return [x0, max(bottom, self.top), x1, top]
