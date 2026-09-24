"""Kitap projesinin kökünü bulur, progress.json'u okur/yazar ve yolları verir.

Proje kökü: içinde progress.json bulunan ilk dizin (çalışma dizininden yukarı
doğru aranır). KITAP_ROOT ortam değişkeni ayarlıysa doğrudan o kullanılır.
Betikler skill dizininde yaşar; proje dizini her kitap için ayrıdır.
"""
import glob
import os
import re

from json_file import read_json, write_json
from progress import Progress

PROGRESS_FILE = "progress.json"
GLOSSARY_FILE = "glossary.md"
WORK_DIR = "_work"
ENV_ROOT = "KITAP_ROOT"
_PAGE_FILE = re.compile(r"page-(\d+)\.js$")


class ProjectNotFound(FileNotFoundError):
    """Çalışma dizininden yukarıda progress.json bulunamadı."""


def find_root(start=None):
    if os.environ.get(ENV_ROOT):
        return os.path.abspath(os.environ[ENV_ROOT])
    current = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(current, PROGRESS_FILE)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise ProjectNotFound(
                f"{PROGRESS_FILE} bulunamadı; kitap projesinin dizininde çalıştırın "
                f"ya da {ENV_ROOT} ortam değişkenini ayarlayın")
        current = parent


class Project:
    """Bir kitap projesinin dosya yolları ve progress.json erişimi."""

    def __init__(self, root):
        self.root = root
        self.progress_path = os.path.join(self.root, PROGRESS_FILE)
        self.glossary_md = os.path.join(self.root, GLOSSARY_FILE)
        self.data_dir = os.path.join(self.root, "data")
        self.pages_dir = os.path.join(self.data_dir, "pages")
        self.toc_js = os.path.join(self.data_dir, "toc.js")
        self.glossary_js = os.path.join(self.data_dir, "glossary.js")
        self.work_in = os.path.join(self.root, WORK_DIR, "in")
        self.work_out = os.path.join(self.root, WORK_DIR, "out")
        self.work_cards = os.path.join(self.root, WORK_DIR, "cards")
        self.work_migrate = os.path.join(self.root, WORK_DIR, "migrate")

    @classmethod
    def discover(cls):
        """Betiklerin giriş noktası: kök çalışma dizininden ya da KITAP_ROOT'tan bulunur."""
        return cls(find_root())

    def load_progress(self):
        return Progress(read_json(self.progress_path))

    def save_progress(self, progress):
        write_json(self.progress_path, progress.data)

    def pdf_path(self, progress):
        configured = progress.book_pdf()
        if os.path.isabs(configured):
            return configured
        return os.path.join(self.root, configured)

    def relative(self, path):
        return os.path.relpath(path, self.root)

    def page_js(self, page):
        return _page_path(self.pages_dir, page, ".js")

    def page_images(self, page):
        return _page_path(self.pages_dir, page, "_images")

    def work_input(self, page):
        return _page_path(self.work_in, page, ".json")

    def work_images(self, page):
        return _page_path(self.work_in, page, "_images")

    def work_output(self, page):
        return _page_path(self.work_out, page, ".json")

    def work_cards_file(self, stage, page):
        return _page_path(os.path.join(self.work_cards, stage), page, ".json")

    def translated_pages(self):
        matches = (_PAGE_FILE.search(path) for path in glob.glob(os.path.join(self.pages_dir, "page-*.js")))
        return sorted(int(match.group(1)) for match in matches if match)


def _page_path(directory, page, suffix):
    """Sayfa dosyalarının ad kuralı: page-N.js, page-N.json, page-N_images."""
    return os.path.join(directory, f"page-{page}{suffix}")
