"""Çevrilmiş sayfaların deposu: data/pages/page-N.js ve yanındaki page-N_images klasörü.
Sayfanın nerede durduğu ile dosya biçimi (window.PAGE({...}) çağrısı) burada birleşir;
kullananlar yalnız sayfa numarası ve PageDocument görür.
"""
import json
import os

from page_document import PageDocument

AGENT_ONLY_FIELDS = ("context", "concepts_spec", "glossary_new")


class TranslatedPages:
    """Çevrilmiş sayfaların diskteki deposu; her kayda sayfa numarasıyla erişilir."""

    def __init__(self, project):
        self._project = project

    def get(self, page):
        with open(self._project.page_js(page), encoding="utf-8") as handle:
            return PageDocument(_page_data(handle.read()))

    def save(self, document):
        """Sayfa numarası belgenin page alanından gelir; yazılan dosyanın yolu döner."""
        path = self._project.page_js(document.number())
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_page_js(document.as_json()))
        return path

    def replace_concepts(self, page, cards):
        """Sayfanın kartları değişir; metnine dokunulmaz."""
        self.save(self.get(page).with_concepts(cards))

    def images_dir(self, page):
        return self._project.page_images(page)


def _page_data(page_js):
    return json.loads(page_js[page_js.index("(") + 1:page_js.rindex(")")])


def _page_js(data):
    """Okuyucunun yüklediği biçim: window.PAGE({...}) çağrısı; ajanın alanları dışarıda kalır."""
    return "window.PAGE(" + json.dumps(_reader_fields(data), ensure_ascii=False) + ");\n"


def _reader_fields(data):
    return {key: value for key, value in data.items() if key not in AGENT_ONLY_FIELDS}
