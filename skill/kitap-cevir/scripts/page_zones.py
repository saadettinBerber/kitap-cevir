"""Sayfanın koşu başlığı ve alt bilgi bölgeleri: ODL öğelerini başlık ve gövde
olarak ayırır. Bölge sınırları progress.json -> extraction ayarlarındadır
(header_zone_bottom, footer_zone_top, header_at_bottom); ODL koordinatları
sol-alt orijinlidir.
"""
import re

from odl_runner import bbox_of
from text_utils import clean_ligatures, is_numeric_only, normalize_spaces

_EDGE_PAGE_NUMBER = re.compile(r"^\d+\s+|\s+\d+$")
_EDGE_SEPARATOR = re.compile(r"^[|·•]\s*|\s*[|·•]$")


class PageZones:
    """Koşu başlığını okur, alt bilgiyi gövdeden atar."""

    def __init__(self, settings):
        self.header_at_bottom = settings["header_at_bottom"]
        self.header_zone_bottom = settings["header_zone_bottom"]
        self.footer_zone_top = settings["footer_zone_top"]
        self.chapter_prefix = settings["chapter_header_prefix"]

    def split(self, elements):
        """(koşu başlığı ya da None, alt bilgisi atılmış gövde öğeleri)."""
        if self.header_at_bottom:
            header, body = self._bottom_header(elements), list(elements)
        else:
            header, body = self._top_header(elements)
        return header, [element for element in body if not self._is_footer(element)]

    def _is_footer(self, element):
        return bbox_of(element)[3] < self.footer_zone_top

    def _top_header(self, elements):
        """Başlık bölgesindeki ilk öğe koşu başlığıdır, kalanlar gövdedir."""
        header, body = None, []
        for element in elements:
            if bbox_of(element)[1] > self.header_zone_bottom and header is None:
                header = self._running_header(element.get("content", ""))
            else:
                body.append(element)
        return header, body

    def _bottom_header(self, elements):
        """Alt koşu başlığı ("Kesit Adı | 201", "200 | Chapter 14: ..."): alt
        bölgedeki öğeler okuma sırasında birleştirilir. Yalnız sayfa numarası
        varsa bölüm açılış sayfasıdır, kesit yoktur."""
        parts = [element.get("content", "") or "" for element in elements if self._is_footer(element)]
        header = self._running_header(" ".join(parts))
        return header if header["text"] and not is_numeric_only(header["text"]) else None

    def _running_header(self, text):
        title = _EDGE_PAGE_NUMBER.sub("", normalize_spaces(clean_ligatures(text)))
        title = _EDGE_SEPARATOR.sub("", title).strip()
        return {"text": title, "is_chapter": title.startswith(self.chapter_prefix)}
