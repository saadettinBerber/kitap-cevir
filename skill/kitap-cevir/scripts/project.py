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
DATA_DIR = "data"
PAGES_DIR = os.path.join(DATA_DIR, "pages")
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
    """Bir kitap projesinin dosya yolları ve progress.json erişimi; her yol proje kökünden kurulur."""

    def __init__(self, root):
        self._root = root

    @classmethod
    def discover(cls):
        """Betiklerin giriş noktası: kök çalışma dizininden ya da KITAP_ROOT'tan bulunur."""
        return cls(find_root())

    def load_progress(self):
        return Progress(read_json(self._path(PROGRESS_FILE)))

    def load_settings(self):
        return BookSettings(read_json(self._path(PROGRESS_FILE)))

    def save_progress(self, progress):
        write_json(self._path(PROGRESS_FILE), progress.as_json())

    def pdf_path(self):
        configured = self.load_settings().book_pdf()
        if os.path.isabs(configured):
            return configured
        return self._path(configured)

    def relative_to_root(self, path):
        return os.path.relpath(path, self._root)

    def glossary_md(self):
        return self._path(GLOSSARY_FILE)

    def toc_js(self):
        return self._path(DATA_DIR, "toc.js")

    def glossary_js(self):
        return self._path(DATA_DIR, "glossary.js")

    def epub_file(self, slug):
        return self._path(DIST_DIR, f"{slug}.epub")

    def page_js(self, page):
        return self._path(PAGES_DIR, _page_name(page, ".js"))

    def page_images(self, page):
        return self._path(PAGES_DIR, _page_name(page, "_images"))

    def work_input(self, page):
        return self._path(WORK_DIR, "in", _page_name(page, ".json"))

    def work_images(self, page):
        return self._path(WORK_DIR, "in", _page_name(page, "_images"))

    def work_output(self, page):
        return self._path(WORK_DIR, "out", _page_name(page, ".json"))

    def work_cards_file(self, stage, page):
        return self._path(WORK_DIR, "cards", stage, _page_name(page, ".json"))

    def work_migration_file(self, stage, page):
        """Taşımada çevirisi bekleyen (pending) ve ajanın doldurduğu (done) birimler: pending-N.json, done-N.json."""
        return self._path(WORK_DIR, "migrate", f"{stage}-{page}.json")

    def _path(self, *parts):
        return os.path.join(self._root, *parts)


def _page_name(page, suffix):
    """Sayfa dosyalarının ad kuralı: page-N.js, page-N.json, page-N_images."""
    return f"page-{page}{suffix}"
