"""Çevrilmiş sayfaların deposu: data/pages/page-N.js ve yanındaki page-N_images klasörü.
Sayfanın nerede durduğu ile dosya biçimi (window.PAGE({...}) çağrısı) burada birleşir;
kullananlar yalnız sayfa numarası ve PageDocument görür.
"""
import json
import os

from page_document import PageDocument

PRIVATE_FIELDS = ("context", "concepts_spec", "glossary_new")   # agent girdisinde var, okuyucuya gitmez


class TranslatedPages:
    """Çevrilmiş sayfaların diskteki deposu; her kayda sayfa numarasıyla erişilir."""

    def __init__(self, project):
        self.project = project

    def get(self, page):
        with open(self.project.page_js(page), encoding="utf-8") as handle:
            source = handle.read()
        return PageDocument(json.loads(source[source.index("(") + 1:source.rindex(")")]))

    def save(self, document):
        """Sayfa numarası belgenin page alanından gelir; yazılan dosyanın yolu döner."""
        path = self.project.page_js(document.data["page"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("window.PAGE(" + json.dumps(_reader_fields(document.data), ensure_ascii=False) + ");\n")
        return path

    def images_dir(self, page):
        return self.project.page_images(page)


def _reader_fields(data):
    return {key: value for key, value in data.items() if key not in PRIVATE_FIELDS}
