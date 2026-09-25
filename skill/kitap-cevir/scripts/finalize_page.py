"""Çevrilmiş sayfa çıktısını sisteme işler:
  1. data/pages/page-N.js yazar (window.PAGE(...)), görselleri kopyalar
  2. progress.json'da sayfayı kaydeder, last_translated_page'i ilerletir
  3. glossary_new terimlerini glossary.md'ye ekler
  4. data/toc.js ve data/glossary.js dosyalarını yeniden üretir
  5. kavram kartları varsa kitabın kart ayarlarına göre denetler; yoksa kart
     adımının beklediğini bildirir (kartlar çeviriden sonra üretilir)

Kullanım (proje dizininde): python3 finalize_page.py _work/out/page-N.json
"""
import os
import shutil
import sys

from concept_check import CardChecker
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

    def __init__(self, project):
        self.project = project
        self.pages = TranslatedPages(project)

    def finalize(self, translated_path):
        """Sayfayı projeye işler; dönen özet, CLI'ın basacağı uyarıları taşır."""
        page = self._read(translated_path)
        page_js = self.pages.save(page)
        images = self._copy_images(page)
        progress = self._register(page.data)
        cards = page.data.get("concepts", [])
        return {"page_js": page_js, "images": images, "terms": self._rebuild_reader_data(page, progress),
                "untranslated": page.missing_translations(), "page": page.data["page"],
                "cards_pending": not cards, "card_problems": self._card_problems(cards)}

    def _card_problems(self, cards):
        """Kartlar çeviriden sonra ayrı üretilir; kartsız sayfa sorun değil, bekleyen iştir."""
        if not cards:
            return []
        return CardChecker(self.project.load_settings().concepts()).problems(cards)

    def _read(self, translated_path):
        page = PageDocument(read_json(translated_path))
        self._require_fields(page.data)
        return page

    def _rebuild_reader_data(self, page, progress):
        """Yeni terimleri sözlüğe ekler, toc.js ve glossary.js'i yeniden yazar; eklenen terim sayısı."""
        glossary = Glossary(self.project)
        added = glossary.add(page.data.get("glossary_new", []))
        ReaderData(self.project).write_toc(progress)
        glossary.write_js()
        return added

    @staticmethod
    def _require_fields(document):
        missing = [field for field in _REQUIRED_FIELDS if field not in document]
        if missing:
            raise IncompletePage(f"Eksik alanlar: {missing}")

    def _copy_images(self, page):
        sources = page.media_sources()
        if not sources:
            return 0
        src_dir = self.project.work_images(page.data["page"])
        dst_dir = self.pages.images_dir(page.data["page"])
        os.makedirs(dst_dir, exist_ok=True)
        present = [name for name in sources if os.path.isfile(os.path.join(src_dir, name))]
        for name in present:
            shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
        return len(present)

    def _register(self, document):
        """Sayfayı progress.json'a kaydeder, last_translated_page'i ilerletir."""
        progress = self.project.load_progress()
        progress.record_translation(document)
        self.project.save_progress(progress)
        return progress


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    project = Project.discover()
    result = PageFinalizer(project).finalize(sys.argv[1])
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
