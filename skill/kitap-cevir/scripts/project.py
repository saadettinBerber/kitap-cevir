"""Kitap projesinin kökünü bulur, progress.json'u okur/yazar ve yolları verir.

Proje kökü: içinde progress.json bulunan ilk dizin (çalışma dizininden yukarı
doğru aranır). KITAP_ROOT ortam değişkeni ayarlıysa doğrudan o kullanılır.
Betikler skill dizininde yaşar; proje dizini her kitap için ayrıdır.
"""
import glob
import json
import os
import re

from json_file import read_json

PROGRESS_FILE = "progress.json"
GLOSSARY_FILE = "glossary.md"
WORK_DIR = "_work"
ENV_ROOT = "KITAP_ROOT"
_PAGE_FILE = re.compile(r"page-(\d+)\.js$")

DEFAULT_EXTRACTION = {
    "code_font_prefix": "Courier",
    "code_max_font_size": 9.5,
    "header_zone_bottom": 610,
    "footer_zone_top": 30,
    "running_header": "top",
    "layout_reader": "odl",
    "chapter_number_min_size": 40,
    "chapter_title_min_size": 20,
    "section_min_size": 13.5,
    "subsection_min_size": 11,
    "footnote_max_size": 7.5,
    "bold_heading_font": "Arial",
    "listing_caption_pattern": "^Listing \\d+-\\d+",
    "table_row_gap_ratio": 1.5,
    "table_caption_pattern": "^Table \\d+[-.]\\d+",
    "equation_caption_pattern": "^Equation \\d+[-.]\\d+",
    "math_font_prefix": "Type3",
    "math_geometry": False,
    "chapter_header_prefix": "Chapter ",
    "chapter_label_pattern": "",
    "code_image_link_pattern": "",
    "default_code_language": "java",
}

DEFAULT_BOOK = {"slug": "kitap", "title": "", "subtitle": "", "subtitle_tr": "",
                "author": "", "series": ""}

CARD_KINDS = ("explain", "contrast", "tradeoff", "code")
_LEGACY_MODE_KINDS = {"code": ["code"], "contrast": ["contrast", "code"], "explain": ["explain"]}
DEFAULT_CODE_COMMENT_LANG = "en"


class ProjectNotFound(FileNotFoundError):
    """Çalışma dizininden yukarıda progress.json bulunamadı."""


class InvalidConceptSettings(ValueError):
    """progress.json -> concepts geçersiz bir kart türü ya da mod içeriyor."""


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

    def __init__(self, root=None):
        self.root = root or find_root()
        self.progress_path = os.path.join(self.root, PROGRESS_FILE)
        self.glossary_md = os.path.join(self.root, GLOSSARY_FILE)
        self.data_dir = os.path.join(self.root, "data")
        self.pages_dir = os.path.join(self.data_dir, "pages")
        self.toc_js = os.path.join(self.data_dir, "toc.js")
        self.glossary_js = os.path.join(self.data_dir, "glossary.js")
        self.work_in = os.path.join(self.root, WORK_DIR, "in")
        self.work_out = os.path.join(self.root, WORK_DIR, "out")
        self.work_cards = os.path.join(self.root, WORK_DIR, "cards")

    def load_progress(self):
        return read_json(self.progress_path)

    def save_progress(self, progress):
        with open(self.progress_path, "w", encoding="utf-8") as handle:
            json.dump(progress, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    def pdf_path(self, progress):
        configured = progress["book_pdf"]
        if os.path.isabs(configured):
            return configured
        return os.path.join(self.root, configured)

    def relative(self, path):
        return os.path.relpath(path, self.root)

    def page_js(self, page):
        return os.path.join(self.pages_dir, f"page-{page}.js")

    def translated_pages(self):
        matches = (_PAGE_FILE.search(path) for path in glob.glob(os.path.join(self.pages_dir, "page-*.js")))
        return sorted(int(match.group(1)) for match in matches if match)


def extraction_settings(progress):
    return {**DEFAULT_EXTRACTION, **progress.get("extraction", {})}


def book_info(progress):
    return {**DEFAULT_BOOK, **progress.get("book", {})}


def _configured_concepts(progress):
    """progress.json -> concepts; eski tek `mode` anahtarı izinli tür listesine çevrilir."""
    configured = dict(progress.get("concepts", {}))
    mode = configured.pop("mode", None)
    if mode is None or "kinds" in configured:
        return configured
    if mode not in _LEGACY_MODE_KINDS:
        raise InvalidConceptSettings(f"Bilinmeyen kavram kartı modu: {mode!r}")
    return {**configured, "kinds": _LEGACY_MODE_KINDS[mode]}


def concepts_settings(progress):
    """Kavram kartı ayarları: izinli kart türleri, kod örneği dilleri, kod yorum dili."""
    merged = {"kinds": list(CARD_KINDS),
              "code_langs": [extraction_settings(progress)["default_code_language"]],
              "code_comment_lang": DEFAULT_CODE_COMMENT_LANG,
              **_configured_concepts(progress)}
    unknown = [kind for kind in merged["kinds"] if kind not in CARD_KINDS]
    if unknown or not merged["kinds"]:
        raise InvalidConceptSettings(f"Geçersiz kart türleri: {merged['kinds']!r}; "
                                     f"geçerli değerler: {', '.join(CARD_KINDS)}")
    return merged


def translator_has_vision(progress):
    """Çevirmen model görsel okuyabiliyor mu (denklem PNG'sinden latex üretimi)."""
    return bool(progress.get("translator", {}).get("vision", True))
