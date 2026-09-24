"""Çevrilmiş sayfaların deposu: data/pages/page-N.js ve yanındaki page-N_images klasörü.
Sayfanın nerede durduğu ile nasıl okunup yazıldığı burada birleşir; kullananlar
yalnız sayfa numarası ve PageDocument görür.
"""
from page_document import PageDocument


class TranslatedPages:
    """Çevrilmiş sayfaların diskteki deposu; her kayda sayfa numarasıyla erişilir."""

    def __init__(self, project):
        self.project = project

    def get(self, page):
        return PageDocument.read(self.project.page_js(page))

    def save(self, document):
        """Sayfa numarası belgenin page alanından gelir; yazılan dosyanın yolu döner."""
        return document.write(self.project.page_js(document.data["page"]))

    def images_dir(self, page):
        return self.project.page_images(page)
