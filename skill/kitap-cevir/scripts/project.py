"""Kitap projesinin kökünü bulur, progress.json'u okur/yazar ve yolları verir.

Proje kökü: içinde progress.json bulunan ilk dizin (çalışma dizininden yukarı
doğru aranır). KITAP_ROOT ortam değişkeni ayarlıysa doğrudan o kullanılır.
Betikler skill dizininde yaşar; proje dizini her kitap için ayrıdır.
"""
import os

from book_settings import BookSettings
from json_file import read_json, write_json
from progress import Progress

PROGRESS_FILE = "progress.json"
GLOSSARY_FILE = "glossary.md"
WORK_DIR = "_work"
DIST_DIR = "dist"
ENV_ROOT = "KITAP_ROOT"


class ProjectNotFound(FileNotFoundError):
    """Çalışma dizininden yukarıda progress.json bulunamadı."""


def find_root(start=None):
    """KITAP_ROOT ayarlıysa odur; değilse başlangıç dizininden yukarı aranır."""
    if os.environ.get(ENV_ROOT):
        return os.path.abspath(os.environ[ENV_ROOT])
    return _nearest_project(os.path.abspath(start or os.getcwd()))


def _nearest_project(directory):
    """İçinde progress.json bulunan en yakın dizin: kendisi ya da bir üstü."""
    if os.path.isfile(os.path.join(directory, PROGRESS_FILE)):
        return directory
    parent = os.path.dirname(directory)
    if parent == directory:
        raise ProjectNotFound(f"{PROGRESS_FILE} bulunamadı; kitap projesinin dizininde çalıştırın "
                              f"ya da {ENV_ROOT} ortam değişkenini ayarlayın")
    return _nearest_project(parent)


class Project:
    """Bir kitap projesinin dosya yolları ve progress.json erişimi."""

    def __init__(self, root):
        self.root = root
        self.progress_path = os.path.join(self.root, PROGRESS_FILE)
        self.glossary_md = os.path.join(self.root, GLOSSARY_FILE)
        self._data_dir = os.path.join(self.root, "data")
        self._pages_dir = os.path.join(self._data_dir, "pages")
        self.toc_js = os.path.join(self._data_dir, "toc.js")
        self.glossary_js = os.path.join(self._data_dir, "glossary.js")
        self._work_in = os.path.join(self.root, WORK_DIR, "in")
        self._work_out = os.path.join(self.root, WORK_DIR, "out")
        self._work_cards = os.path.join(self.root, WORK_DIR, "cards")
        self.work_migrate = os.path.join(self.root, WORK_DIR, "migrate")
        self._dist_dir = os.path.join(self.root, DIST_DIR)

    @classmethod
    def discover(cls):
        """Betiklerin giriş noktası: kök çalışma dizininden ya da KITAP_ROOT'tan bulunur."""
        return cls(find_root())

    def load_progress(self):
        return Progress(read_json(self.progress_path))

    def load_settings(self):
        return BookSettings(read_json(self.progress_path))

    def save_progress(self, progress):
        write_json(self.progress_path, progress.data)

    def pdf_path(self):
        configured = self.load_settings().book_pdf()
        if os.path.isabs(configured):
            return configured
        return os.path.join(self.root, configured)

    def relative_to_root(self, path):
        return os.path.relpath(path, self.root)

    def epub_file(self, slug):
        return os.path.join(self._dist_dir, f"{slug}.epub")

    def page_js(self, page):
        return _page_path(self._pages_dir, page, ".js")

    def page_images(self, page):
        return _page_path(self._pages_dir, page, "_images")

    def work_input(self, page):
        return _page_path(self._work_in, page, ".json")

    def work_images(self, page):
        return _page_path(self._work_in, page, "_images")

    def work_output(self, page):
        return _page_path(self._work_out, page, ".json")

    def work_cards_file(self, stage, page):
        return _page_path(os.path.join(self._work_cards, stage), page, ".json")


def _page_path(directory, page, suffix):
    """Sayfa dosyalarının ad kuralı: page-N.js, page-N.json, page-N_images."""
    return os.path.join(directory, f"page-{page}{suffix}")
