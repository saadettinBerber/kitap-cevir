"""Düzen öğelerinin düz listesi üzerindeki düzeltmeler; bloklar kurulmadan önce
uygulanır: gömülü liste içeriği, alt/üst simge parçaları, dipnot işaretleri,
satır içi denklemler ve e-kitabın kod görseli bağlantıları. Öğeler değişmezdir;
her düzeltme yeni bir liste kurar. Koordinatlar üst orijinlidir.
"""
import dataclasses
import re
import unicodedata
from typing import NamedTuple

from extraction.equations.math_scan import placeholder
from extraction.pdf import geometry

_FOOTNOTE_MARKER = re.compile(r"^[a-z0-9]$")


class FixedElements(NamedTuple):
    """LayoutFixer'ın sonucu: düzeltilmiş öğeler ve yerleştirilemeyen satır içi denklemlerin uyarıları.
    Uyarıları basmak komutun işidir; düzen kodu yan etkisiz kalır."""
    elements: list
    skipped_equations: tuple


class LayoutFixer:
    """Bir sayfanın düzen öğelerini düzen okuyucusunun bilinen kusurlarından arındırır;
    satır içi denklemler ve kod görseli bağlantıları metin katmanının o sayfadaki bulgularıdır."""

    def __init__(self, inline_math, code_image_links):
        self._equations = [InlineEquation(item) for item in inline_math]
        self._links = [CodeImageLink(slot) for slot in code_image_links]

    def fixed(self, elements):
        """FixedElements. Gömülü içerik önce akışa döner ki sonraki düzeltmeler onu da görsün; metin
        düzeltmeleri (denklem, bağlantı) öğelerin son hâline uygulanır."""
        structured = self._merge_footnote_markers(self._drop_nested_fragments(self._flatten_nested_lists(elements)))
        with_math, skipped = self._with_inline_math(structured)
        return FixedElements(self._without_code_image_links(with_math), skipped)

    @staticmethod
    def _flatten_nested_lists(elements):
        """ODL italik bir caption'ı ("Table 4-2.") numaralı liste sanıp sonrasındaki
        her şeyi maddenin `children` alanına gömebilir. Gömülü içerik (tablo satırları,
        başlık, paragraf) sıradan öğe olarak akışa döner; yoksa sessizce düşer ve
        sayfadan koca bir bölüm eksilir."""
        return [flat for element in elements for flat in LayoutFixer._flattened(element)]

    @staticmethod
    def _flattened(element):
        """[öğe]; gömülü içerikli listenin yerine maddeleri ve onların gömülü öğeleri."""
        list_items = element.list_items if element.kind == "list" else ()
        if not any(item.children for item in list_items):
            return [element]
        return [nested for item in list_items for nested in map(_nested, (item, *item.children))]

    @staticmethod
    def _drop_nested_fragments(elements):
        """ODL'nin ayrı paragraf yaptığı alt/üst simge parçalarını atar; metin
        katmanı bunları zaten ev sahibi satıra bağlar (text_layer.script_marks)."""
        return [element for element in elements
                if not any(LayoutFixer._is_fragment_of(element, host) for host in elements)]

    @staticmethod
    def _is_fragment_of(element, host):
        """Başka öğenin kutusu içindeki tek karakterlik öğe (alt/üst simge) parçadır."""
        return element is not host and len(element.text.strip()) == 1 and geometry.contains(host.box, element.box)

    @staticmethod
    def _merge_footnote_markers(elements):
        """Tek harflik dipnot işaretini ('a') aynı satırdaki metnin başına ekler."""
        merged = []
        for element in elements:
            if merged and LayoutFixer._is_marker(merged[-1]) and LayoutFixer._same_line(merged[-1], element):
                marker = merged.pop().text.strip()
                element = dataclasses.replace(element, text=f"{marker} {element.text}")
            merged.append(element)
        return merged

    @staticmethod
    def _is_marker(element):
        return element.kind == "paragraph" and bool(_FOOTNOTE_MARKER.match(element.text.strip()))

    @staticmethod
    def _same_line(marker, element):
        return geometry.vertical_overlap(marker.box, element.box) > 0 and element.box.x0 > marker.box.x0

    def _with_inline_math(self, elements):
        """(öğeler, atlanan denklemlerin uyarıları). Satır içi denklemleri ev sahibi öğenin metnine
        yerleştirir: basit sembol düz metin, karmaşık denklem ⟦eq-N⟧ yer tutucusu."""
        skipped = ()
        for equation in self._equations:
            elements, warnings = equation.placed_in(elements)
            skipped += warnings
        return elements, skipped

    def _without_code_image_links(self, elements):
        """E-kitabın kod görseli bağlantılarını (text_layer CodeImageLinkLines) öğelerden
        çıkarır. Bağlantıya yapışmış kod satırı böylece gerçek yüksekliğine döner ve
        kod bölgesine düşer; yalnız bağlantıdan oluşan öğe atılır."""
        return [kept for element in elements for kept in self._without_links(element)]

    def _without_links(self, element):
        """[bağlantılarından arınmış öğe]; öğe yalnız bağlantıdan oluşuyorsa []."""
        present = [link for link in self._links if link.is_in(element)]
        for link in present:
            element = link.cut_from(element)
        return [element] if element.text or not present else []


def _nested(element):
    return dataclasses.replace(element, is_nested=True)


class InlineEquation:
    """Metin katmanının bulduğu bir satır içi denklem; öğe metnine komşu kelimeleri arasında girer."""

    def __init__(self, item):
        self._box = item["bbox"]
        self._before, self._after = item["before"], item["after"]
        self._text = item["text"]
        self._insert = item["text"] if item["kind"] == "text" else placeholder(item["id"])

    def placed_in(self, elements):
        """(öğeler, uyarılar). Denklem, kutusunu dikeyde kapsayan ilk öğenin metnine girer; öyle öğe
        yoksa öğeler değişmez ve atlandığı uyarısı döner."""
        hosts = [index for index, element in enumerate(elements) if self._is_hosted_by(element)]
        if not hosts:
            return elements, (f"satır içi denklem için öğe bulunamadı: {self._insert}",)
        return self._spliced_into(elements, hosts[0])

    def _is_hosted_by(self, element):
        return element.box.y0 <= geometry.center_y(self._box) <= element.box.y1

    def _spliced_into(self, elements, host):
        """Komşu kelimeler ev sahibinin metninde yoksa öğeler değişmez ve atlandığı uyarısı döner."""
        text, count = self._splice(elements[host].text)
        if not count:
            return elements, (f"satır içi denklem yerleştirilemedi, atlandı: {self._insert}",)
        return elements[:host] + [dataclasses.replace(elements[host], text=text)] + elements[host + 1:], ()

    def _splice(self, text):
        """insert'i metinde before/after komşu kelimelerinin arasına koyar."""
        if self._before and self._after:
            return self._between_neighbours(text)
        if self._after:
            return re.subn(_word(self._after), lambda match: f"{self._insert} {match[0]}", text, count=1)
        if self._before:
            return re.subn(_word(self._before), lambda match: f"{match[0]} {self._insert}", text, count=1)
        return f"{text} {self._insert}", 1

    def _between_neighbours(self, text):
        """Önce bitişik komşular: ODL denklem glifini metinden düşürür. Yoksa araları en çok
        denklemin kendi metni kadar olan komşular: LiteParse glifi düzleşmiş metin olarak bırakır."""
        spliced, count = self._replace_between(text, 0)
        return (spliced, count) if count else self._replace_between(text, len(self._text))

    def _replace_between(self, text, gap):
        """Aralarında en çok gap harf bulunan ilk komşu çifti; aradaki metnin yerini insert alır.
        Boşluk olabildiğince uzun tutulur: sonraki kelime (',') denklemin içinde de geçebilir."""
        pattern = rf"(?P<before>{_word(self._before)})\s*.{{0,{gap}}}\s*(?P<after>{_word(self._after)})"
        return re.subn(pattern, lambda match: f"{match['before']} {self._insert} {match['after']}", text, count=1)


def _word(word):
    """Komşu kelime tam kelime olarak aranır: harfle başlayan ya da biten yanı başka bir harfe
    yapışık olamaz ('for', 'perform'un içinde değildir). Noktalama (',', '.') serbesttir."""
    left = r"(?<!\w)" if word[:1].isalnum() else ""
    right = r"(?!\w)" if word[-1:].isalnum() else ""
    return left + _spellings(word) + right


def _spellings(word):
    """Kelimenin metindeki yazılışları: olduğu gibi ya da bağlı harfsiz (LiteParse ﬁ'yi fi yazar)."""
    return "(?:" + "|".join(re.escape(form) for form in sorted({word, unicodedata.normalize("NFKC", word)})) + ")"


class CodeImageLink:
    """Metin katmanının bulduğu bir kod görseli bağlantısı ve dikey şeridi."""

    def __init__(self, slot):
        self._text = slot["text"]
        self._top, self._bottom = slot["y0"], slot["y1"]

    def is_in(self, element):
        return self._text in element.text and self._overlaps_vertically(element.box)

    def _overlaps_vertically(self, box):
        return self._top < box.y1 and box.y0 < self._bottom

    def cut_from(self, element):
        text = element.text.replace(self._text, "", 1).strip()
        return dataclasses.replace(element, text=text, box=self._box_without_slot(element.box))

    def _box_without_slot(self, box):
        """Şerit kutunun üst yarısındaysa bağlantı öğenin başındadır, alt kısım
        kalır; alt yarısındaysa sonundadır, üst kısım kalır."""
        if (self._top + self._bottom) / 2 < geometry.center_y(box):
            return geometry.Box(box.x0, max(box.y0, self._bottom), box.x1, box.y1)
        return geometry.Box(box.x0, box.y0, box.x1, min(box.y1, self._top))
