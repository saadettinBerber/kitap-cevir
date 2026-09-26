"""Sayfanın koşu başlığı ve alt bilgi bölgeleri: düzen öğelerini başlık ve gövde
olarak ayırır. Bölge sınırları progress.json -> extraction ayarlarındadır
(running_header, header_zone_bottom, footer_zone_top) ve sayfanın ALT kenarından
ölçülür; öğe kutuları sol-üst orijinlidir, karşılaştırma sayfa yüksekliğiyle yapılır.
"""
import re

from extraction.pdf.model import PageLayout
from extraction.text_utils import clean_ligatures, is_numeric_only, normalize_spaces

_EDGE_PAGE_NUMBER = re.compile(r"^\d+\s+|\s+\d+$")
_EDGE_SEPARATOR = re.compile(r"^[|·•]\s*|\s*[|·•]$")


class InvalidRunningHeader(ValueError):
    """progress.json -> extraction.running_header geçersiz ya da kaldırılmış bir ayar."""


class RunningHeader:
    """Koşu başlığının sayfadaki yeri; yer başına bir alt sınıf."""

    @staticmethod
    def of(settings):
        kinds = {"top": TopRunningHeader, "bottom": BottomRunningHeader, "none": NoRunningHeader}
        choices = " | ".join(kinds)
        if "header_at_bottom" in settings:
            raise InvalidRunningHeader(f"header_at_bottom kaldırıldı; yerine running_header: {choices} yazın")
        position = settings["running_header"]
        if position not in kinds:
            raise InvalidRunningHeader(f"running_header '{position}' geçersiz; {choices} olmalı")
        return kinds[position](settings)

    def __init__(self, settings):
        self._chapter_prefix = settings["chapter_header_prefix"]

    def _parsed(self, text):
        title = _EDGE_PAGE_NUMBER.sub("", normalize_spaces(clean_ligatures(text)))
        title = _EDGE_SEPARATOR.sub("", title).strip()
        return {"text": title, "is_chapter": title.startswith(self._chapter_prefix)}


class TopRunningHeader(RunningHeader):
    def __init__(self, settings):
        super().__init__(settings)
        self._zone_bottom = settings["header_zone_bottom"]

    def split(self, body, footer):
        """Başlık bölgesindeki ilk öğe koşu başlığıdır, kalanlar gövdedir."""
        zone_line = body.height - self._zone_bottom
        first = next((element for element in body.elements if element.box.y1 < zone_line), None)
        header = self._parsed(first.text) if first else None
        return header, [element for element in body.elements if element is not first]


class BottomRunningHeader(RunningHeader):
    def split(self, body, footer):
        """Alt koşu başlığı ("Kesit Adı | 201", "200 | Chapter 14: ..."): alt
        bölgedeki öğeler okuma sırasında birleştirilir. Yalnız sayfa numarası
        varsa bölüm açılış sayfasıdır, kesit yoktur."""
        header = self._parsed(" ".join(element.text for element in footer))
        return (header if header["text"] and not is_numeric_only(header["text"]) else None), list(body.elements)


class NoRunningHeader(RunningHeader):
    """E-kitap kökenli PDF'lerde koşu başlığı yoktur; sayfanın en üstü gövdedir."""

    def split(self, body, footer):
        return None, list(body.elements)


class PageZones:
    """Koşu başlığını okur, alt bilgiyi gövdeden atar."""

    def __init__(self, settings):
        self._footer_zone_top = settings["footer_zone_top"]
        self._running_header = RunningHeader.of(settings)

    def split(self, layout):
        """(koşu başlığı ya da None, alt bilgisi atılmış gövde öğeleri)."""
        footer_line = self.body_bottom(layout.height)
        footer = [element for element in layout.elements if element.box.y0 > footer_line]
        body = tuple(element for element in layout.elements if element.box.y0 <= footer_line)
        return self._running_header.split(PageLayout(layout.height, body), footer)

    def body_bottom(self, page_height):
        """Gövdenin alt sınırı, alt bilgi bölgesinin üst çizgisi: çizgide başlayan öğe gövdededir."""
        return page_height - self._footer_zone_top
