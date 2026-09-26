"""Çevrilmiş sayfa çıktısını sisteme işler:
  1. data/pages/page-N.js yazar (window.PAGE(...)), görselleri kopyalar
  2. progress.json'da sayfayı kaydeder, last_translated_page'i ilerletir
  3. glossary_new terimlerini glossary.md'ye ekler
  4. data/toc.js ve data/glossary.js dosyalarını yeniden üretir
  5. kavram kartları varsa kitabın kart ayarlarına göre denetler; yoksa kart
     adımının beklediğini bildirir (kartlar çeviriden sonra üretilir)

Kullanım (proje dizininde): python3 finalize_page.py _work/out/page-N.json
"""
import sys

from concept_check import CardChecker
from image_folder import ImageFolder
from json_file import read_json
from page_document import PageDocument
from project import Project
from reader_data import Glossary, ReaderData
from translated_pages import TranslatedPages

_REQUIRED_FIELDS = ("id", "page", "pdf_page", "blocks")


class IncompletePage(ValueError):
    """Çevirmen çıktısında zorunlu alan eksik."""


class PageFinalizer:
    """Çevirmen çıktısını projeye işler: sayfa dosyası, görseller, ilerleme, sözlük, içindekiler."""

    def __init__(self, project, settings):
        self._project = project
        self._settings = settings
        self._pages = TranslatedPages(project)

    @classmethod
    def for_project(cls, project):
        return cls(project, project.load_settings())

    def finalize(self, translated_path):
        """Sayfayı projeye işler; dönen özet, CLI'ın basacağı uyarıları taşır."""
        page = _read_page(translated_path)
        report = self._report(page)
        self._write(page)
        return report

    def _report(self, page):
        """Yazmadan önce sorulur: yeni terimler ancak sözlüğe eklenmeden önce sayılabilir."""
        new_terms = Glossary(self._project.glossary_md()).unknown(page.new_terms())
        return {"images": len(self._present_images(page)), "terms": len(new_terms), **self._notes(page)}

    def _present_images(self, page):
        """Sayfanın andığı görsellerden çevirmen girdisinde bulunanlar."""
        work_images = self._work_images(page)
        return [src for src in page.media_sources() if work_images.has(src)]

    def _work_images(self, page):
        return ImageFolder(self._project.work_images(page.number()))

    def _write(self, page):
        self._pages.save(page)
        self._copy_images(page)
        self._register(page)
        self._rebuild_reader_data(page)

    def _copy_images(self, page):
        """Görsel anmayan sayfaya görsel klasörü kurulmaz."""
        if page.media_sources():
            self._work_images(page).copy(self._present_images(page), self._pages.images_dir(page.number()))

    def _register(self, page):
        """Sayfayı progress.json'a kaydeder, last_translated_page'i ilerletir."""
        progress = self._project.load_progress()
        progress.record_translation(page)
        self._project.save_progress(progress)

    def _rebuild_reader_data(self, page):
        """Yeni terimleri sözlüğe ekler, toc.js ve glossary.js'i kaydedilmiş ilerlemeden yeniden yazar."""
        glossary = Glossary(self._project.glossary_md())
        glossary.add(page.new_terms())
        reader_data = ReaderData(self._project)
        reader_data.write_toc(self._project.load_progress())
        reader_data.write_glossary(glossary)

    def _notes(self, page):
        cards = page.concepts()
        return {"page_js": self._project.page_js(page.number()), "untranslated": page.missing_translations(),
                "page": page.number(), "cards_pending": not cards, "card_problems": self._card_problems(cards)}

    def _card_problems(self, cards):
        """Kartlar çeviriden sonra ayrı üretilir; kartsız sayfa sorun değil, bekleyen iştir."""
        if not cards:
            return []
        return CardChecker(self._settings.concepts()).problems(cards)


def _read_page(translated_path):
    document = read_json(translated_path)
    _require_fields(document)
    return PageDocument(document)


def _require_fields(document):
    missing = [field for field in _REQUIRED_FIELDS if field not in document]
    if missing:
        raise IncompletePage(f"Eksik alanlar: {missing}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    project = Project.discover()
    _print_result(project, PageFinalizer.for_project(project).finalize(sys.argv[1]))


def _print_result(project, result):
    print(f"✓ Sayfa {result['page']}: {project.relative_to_root(result['page_js'])} yazıldı, "
          f"{result['images']} görsel, {result['terms']} yeni terim; toc.js + glossary.js güncellendi")
    _print_notes(result)


def _print_notes(result):
    if result["untranslated"]:
        print(f"  ! UYARI: {result['untranslated']} metin biriminin 'tr' alanı boş")
    if result["cards_pending"]:
        print(f"  kartlar bekliyor: regen_concepts.py prepare {result['page']} (SKILL.md → C)")
    for problem in result["card_problems"]:
        print(f"  ! KART: {problem}")


if __name__ == "__main__":
    main()
