"""progress.json ve glossary.md'den okuyucunun veri dosyalarını üretir:
  data/toc.js       -> window.TOC  (kitap bilgisi, bölümler, çevrilmiş sayfalar)
  data/glossary.js  -> window.GLOSSARY (terim sözlüğü)

Kullanım (proje dizininde): python3 toc_builder.py   (her ikisini yeniden üretir)
"""
import json
import os
import re

from project import Project, book_info

GLOSSARY_HEADER_CELL = "İngilizce Terim"
_TABLE_ROW = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")


def _chapter_entries(progress):
    chapters = progress["chapters"]
    entries = []
    for chapter, following in zip(chapters, chapters[1:] + [None]):
        end = following["start"] - 1 if following else progress["book_total_pages"]
        entries.append({**chapter, "end": end})
    return entries


def _page_entry(info):
    if info.get("blank"):
        return {"blank": True}
    return {
        "title": {"en": info.get("title_en", ""), "tr": info.get("title_tr", "")},
        "section": {"en": info.get("section_en", ""), "tr": info.get("section_tr", "")},
        "chapter": info.get("chapter"),
    }


def _book_payload(progress):
    book = book_info(progress)
    return {"slug": book["slug"], "title": book["title"], "subtitle": book["subtitle"],
            "subtitleTr": book["subtitle_tr"], "author": book["author"],
            "series": book["series"]}


def _write_js(path, global_name, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"window.{global_name} = ")
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
        handle.write(";\n")


def write_toc(project, progress):
    payload = {
        "book": _book_payload(progress),
        "bookTotalPages": progress["book_total_pages"],
        "pdfOffset": progress["pdf_offset"],
        "lastTranslatedPage": progress["last_translated_page"],
        "chapters": _chapter_entries(progress),
        "pages": {num: _page_entry(info) for num, info in progress["pages"].items()},
    }
    _write_js(project.toc_js, "TOC", payload)
    return project.toc_js


def _is_table_row(line):
    match = _TABLE_ROW.match(line)
    if not match:
        return False
    first = match.group(1)
    return first != GLOSSARY_HEADER_CELL and not set(first) <= {"-", " "}


def read_glossary(project):
    """glossary.md'yi (önsöz satırları, terim listesi) olarak ayırır."""
    with open(project.glossary_md, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    preamble = [line for line in lines if not _is_table_row(line)]
    terms = []
    for line in lines:
        if _is_table_row(line):
            en, tr, note = _TABLE_ROW.match(line).groups()
            terms.append({"en": en, "tr": tr, "note": note})
    return preamble, terms


def _sort_key(term):
    return term["en"].casefold()


def write_glossary_md(project, preamble, terms):
    ordered = sorted(terms, key=_sort_key)
    body = "\n".join(preamble).rstrip("\n") + "\n"
    rows = "".join(f"| {t['en']} | {t['tr']} | {t['note']} |\n" for t in ordered)
    with open(project.glossary_md, "w", encoding="utf-8") as handle:
        handle.write(body + rows)
    return ordered


def add_glossary_terms(project, new_terms):
    """Yeni terimleri (varsa) sözlüğe ekler; eklenen sayısını döndürür."""
    preamble, terms = read_glossary(project)
    known = {_sort_key(t) for t in terms}
    added = [t for t in new_terms if t.get("en") and _sort_key(t) not in known]
    for term in added:
        terms.append({"en": term["en"], "tr": term.get("tr", ""),
                      "note": term.get("note", "")})
    write_glossary_md(project, preamble, terms)
    return len(added)


def write_glossary_js(project):
    _, terms = read_glossary(project)
    _write_js(project.glossary_js, "GLOSSARY", sorted(terms, key=_sort_key))
    return project.glossary_js


def rebuild(project):
    progress = project.load_progress()
    return write_toc(project, progress), write_glossary_js(project)


def main():
    project = Project()
    for path in rebuild(project):
        print("yazıldı:", project.relative(path))


if __name__ == "__main__":
    main()
