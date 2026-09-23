"""Çevrilmiş sayfa çıktısını sisteme işler:
  1. data/pages/page-N.js yazar (window.PAGE(...)), görselleri kopyalar
  2. progress.json'da sayfayı kaydeder, last_translated_page'i ilerletir
  3. glossary_new terimlerini glossary.md'ye ekler
  4. data/toc.js ve data/glossary.js dosyalarını yeniden üretir
  5. kavram kartlarını kitabın kart ayarlarına göre denetler (uyarı basar)

Kullanım (proje dizininde): python3 finalize_page.py _work/out/page-N.json
"""
import os
import shutil
import sys

from concept_check import CardChecker
from json_file import read_json
from page_document import PageDocument
from project import Project, concepts_settings
from reader_data import Glossary, TableOfContents

_REQUIRED_FIELDS = ("id", "page", "pdf_page", "blocks")


class IncompletePage(ValueError):
    """Çevirmen çıktısında zorunlu alan eksik."""


class PageFinalizer:
    """Çevirmen çıktısını projeye işler: sayfa dosyası, görseller, ilerleme, sözlük, içindekiler."""

    def __init__(self, project):
        self.project = project

    def finalize(self, translated_path):
        """Sayfayı projeye işler; dönen özet, CLI'ın basacağı uyarıları taşır."""
        page = self._read(translated_path)
        page_js = page.write(self.project.pages_dir)
        images = self._copy_images(page)
        progress = self._register(page.data)
        return {"page_js": page_js, "images": images, "terms": self._rebuild_reader_data(page, progress),
                "untranslated": page.missing_translations(), "page": page.data["page"],
                "card_problems": CardChecker(concepts_settings(progress)).problems(page.data.get("concepts", []))}

    def _read(self, translated_path):
        page = PageDocument(read_json(translated_path))
        self._require_fields(page.data)
        return page

    def _rebuild_reader_data(self, page, progress):
        """Yeni terimleri sözlüğe ekler, toc.js ve glossary.js'i yeniden yazar; eklenen terim sayısı."""
        glossary = Glossary(self.project)
        added = glossary.add(page.data.get("glossary_new", []))
        TableOfContents(self.project, progress).write()
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
        src_dir = os.path.join(self.project.work_in, f"{page.data['id']}_images")
        dst_dir = os.path.join(self.project.pages_dir, f"{page.data['id']}_images")
        os.makedirs(dst_dir, exist_ok=True)
        present = [name for name in sources if os.path.isfile(os.path.join(src_dir, name))]
        for name in present:
            shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
        return len(present)

    def _register(self, document):
        """Sayfayı progress.json'a kaydeder, last_translated_page'i ilerletir."""
        progress = self.project.load_progress()
        progress["pages"][str(document["page"])] = {
            "pdf_page": document["pdf_page"],
            "chapter": document.get("chapter", {}).get("num"),
            "title_en": document.get("title", {}).get("en", ""),
            "title_tr": document.get("title", {}).get("tr", ""),
            "section_en": document.get("section", {}).get("en", ""),
            "section_tr": document.get("section", {}).get("tr", ""),
        }
        progress["last_translated_page"] = max(progress["last_translated_page"], document["page"])
        self.project.save_progress(progress)
        return progress


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    project = Project()
    result = PageFinalizer(project).finalize(sys.argv[1])
    print(f"✓ Sayfa {result['page']}: {project.relative(result['page_js'])} yazıldı, "
          f"{result['images']} görsel, {result['terms']} yeni terim; toc.js + glossary.js güncellendi")
    if result["untranslated"]:
        print(f"  ! UYARI: {result['untranslated']} metin biriminin 'tr' alanı boş")
    for problem in result["card_problems"]:
        print(f"  ! KART: {problem}")


if __name__ == "__main__":
    main()
