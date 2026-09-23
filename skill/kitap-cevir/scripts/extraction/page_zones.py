"""Sayfanın koşu başlığı ve alt bilgi bölgeleri: ODL öğelerini başlık ve gövde
olarak ayırır. Bölge sınırları progress.json -> extraction ayarlarındadır
(running_header, header_zone_bottom, footer_zone_top); ODL koordinatları
sol-alt orijinlidir.
"""
import re

from extraction.odl_runner import bbox_of
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
        self.chapter_prefix = settings["chapter_header_prefix"]

    def _parsed(self, text):
        title = _EDGE_PAGE_NUMBER.sub("", normalize_spaces(clean_ligatures(text)))
        title = _EDGE_SEPARATOR.sub("", title).strip()
        return {"text": title, "is_chapter": title.startswith(self.chapter_prefix)}


class TopRunningHeader(RunningHeader):
    def __init__(self, settings):
        super().__init__(settings)
        self.zone_bottom = settings["header_zone_bottom"]

    def split(self, body, footer):
        """Başlık bölgesindeki ilk öğe koşu başlığıdır, kalanlar gövdedir."""
        first = next((element for element in body if bbox_of(element)[1] > self.zone_bottom), None)
        header = self._parsed(first.get("content", "")) if first else None
        return header, [element for element in body if element is not first]


class BottomRunningHeader(RunningHeader):
    def split(self, body, footer):
        """Alt koşu başlığı ("Kesit Adı | 201", "200 | Chapter 14: ..."): alt
        bölgedeki öğeler okuma sırasında birleştirilir. Yalnız sayfa numarası
        varsa bölüm açılış sayfasıdır, kesit yoktur."""
        header = self._parsed(" ".join(element.get("content", "") or "" for element in footer))
        return (header if header["text"] and not is_numeric_only(header["text"]) else None), body


class NoRunningHeader(RunningHeader):
    """E-kitap kökenli PDF'lerde koşu başlığı yoktur; sayfanın en üstü gövdedir."""

    def split(self, body, footer):
        return None, body


class PageZones:
    """Koşu başlığını okur, alt bilgiyi gövdeden atar."""

    def __init__(self, settings):
        self.footer_zone_top = settings["footer_zone_top"]
        self.running_header = RunningHeader.of(settings)

    def split(self, elements):
        """(koşu başlığı ya da None, alt bilgisi atılmış gövde öğeleri)."""
        footer = [element for element in elements if self._is_footer(element)]
        body = [element for element in elements if not self._is_footer(element)]
        return self.running_header.split(body, footer)

    def _is_footer(self, element):
        return bbox_of(element)[3] < self.footer_zone_top
