"""Çevrilmiş sayfa çıktısını sisteme işler:
  1. data/pages/page-N.js yazar (window.PAGE(...)), görselleri kopyalar
  2. progress.json'da sayfayı kaydeder, last_translated_page'i ilerletir
  3. glossary_new terimlerini glossary.md'ye ekler
  4. data/toc.js ve data/glossary.js dosyalarını yeniden üretir

Kullanım (proje dizininde): python3 finalize_page.py _work/out/page-N.json
"""
import json
import os
import shutil
import sys

from project import Project
from toc_builder import add_glossary_terms, write_glossary_js, write_toc

_TRANSLATABLE_TYPES = ("heading", "caption", "footnote", "chapter")
_PRIVATE_FIELDS = ("context", "glossary_new")
_REQUIRED_FIELDS = ("id", "page", "pdf_page", "blocks")


def _text_units(block):
    if block["type"] == "para":
        return block["sentences"]
    if block["type"] == "list":
        return block["items"]
    if block["type"] == "table":
        return [cell for row in block["rows"] for cell in row]
    if block["type"] in _TRANSLATABLE_TYPES:
        return [block]
    return []


def missing_translations(document):
    return sum(1 for block in document["blocks"]
               for unit in _text_units(block)
               if unit.get("en") and not unit.get("tr"))


def _require_fields(document):
    missing = [f for f in _REQUIRED_FIELDS if f not in document]
    if missing:
        raise ValueError(f"Eksik alanlar: {missing}")


def write_page_js(project, document):
    os.makedirs(project.pages_dir, exist_ok=True)
    payload = {k: v for k, v in document.items() if k not in _PRIVATE_FIELDS}
    path = os.path.join(project.pages_dir, f"{document['id']}.js")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("window.PAGE(" + json.dumps(payload, ensure_ascii=False) + ");\n")
    return path


def _image_sources(document):
    blocks = document["blocks"]
    sources = [b["src"] for b in blocks if b["type"] in ("image", "math")]
    return sources + [m["src"] for m in document.get("math", [])]


def copy_images(project, document):
    sources = _image_sources(document)
    if not sources:
        return 0
    src_dir = os.path.join(project.work_in, f"{document['id']}_images")
    dst_dir = os.path.join(project.pages_dir, f"{document['id']}_images")
    os.makedirs(dst_dir, exist_ok=True)
    copied = 0
    for name in sources:
        source = os.path.join(src_dir, name)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(dst_dir, name))
            copied += 1
    return copied


def register_page(project, progress, document):
    page = document["page"]
    progress["pages"][str(page)] = {
        "pdf_page": document["pdf_page"],
        "chapter": document.get("chapter", {}).get("num"),
        "title_en": document.get("title", {}).get("en", ""),
        "title_tr": document.get("title", {}).get("tr", ""),
        "section_en": document.get("section", {}).get("en", ""),
        "section_tr": document.get("section", {}).get("tr", ""),
    }
    progress["last_translated_page"] = max(progress["last_translated_page"], page)
    project.save_progress(progress)


def finalize(project, translated_path):
    with open(translated_path, encoding="utf-8") as handle:
        document = json.load(handle)
    _require_fields(document)
    untranslated = missing_translations(document)
    page_js = write_page_js(project, document)
    images = copy_images(project, document)
    progress = project.load_progress()
    register_page(project, progress, document)
    added_terms = add_glossary_terms(project, document.get("glossary_new", []))
    write_toc(project, progress)
    write_glossary_js(project)
    return {"page_js": page_js, "images": images, "terms": added_terms,
            "untranslated": untranslated, "page": document["page"]}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    project = Project()
    result = finalize(project, sys.argv[1])
    print(f"✓ Sayfa {result['page']}: {project.relative(result['page_js'])} yazıldı, "
          f"{result['images']} görsel, {result['terms']} yeni terim; toc.js + glossary.js güncellendi")
    if result["untranslated"]:
        print(f"  ! UYARI: {result['untranslated']} metin biriminin 'tr' alanı boş")


if __name__ == "__main__":
    main()
