"""Düzen okuyucusunun seçimi: progress.json -> extraction.layout_reader.

Adaptör modülü yalnız seçilince yüklenir; kullanılmayan okuyucunun paketinin
(opendataloader-pdf, liteparse) kurulu olması gerekmez.
"""
import importlib

# Her adaptör modülü kendi okuyucusunu `layout_reader()` fabrikasıyla bağlar.
READERS = {"odl": "extraction.pdf.odl_adapter", "liteparse": "extraction.pdf.liteparse_adapter"}


class InvalidLayoutReader(ValueError):
    """progress.json -> extraction.layout_reader bilinmeyen bir okuyucu."""


def layout_reader_for(settings):
    name = settings["layout_reader"]
    if name not in READERS:
        raise InvalidLayoutReader(f"layout_reader '{name}' geçersiz; {' | '.join(READERS)} olmalı")
    adapter = importlib.import_module(READERS[name])
    return adapter.layout_reader()
