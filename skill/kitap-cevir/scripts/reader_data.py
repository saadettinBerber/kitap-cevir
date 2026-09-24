"""progress.json ve glossary.md'den okuyucunun veri dosyalarını üretir:
  data/toc.js       -> window.TOC  (kitap bilgisi, bölümler, çevrilmiş sayfalar)
  data/glossary.js  -> window.GLOSSARY (terim sözlüğü)

Kullanım (proje dizininde): python3 reader_data.py   (her ikisini yeniden üretir)
"""
import json
import os
import re

from project import Project

GLOSSARY_HEADER_CELL = "İngilizce Terim"
_TABLE_ROW = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")


class ReaderScript:
    """Okuyucunun <script> ile yüklediği, tek bir global değişken tanımlayan dosya."""

    def __init__(self, path, global_name):
        self.path = path
        self.global_name = global_name

    def write(self, payload):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(f"window.{self.global_name} = ")
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            handle.write(";\n")
        return self.path


class TableOfContents:
    """data/toc.js: kitap bilgisi, bölüm aralıkları ve çevrilmiş sayfaların özeti."""

    def __init__(self, project, progress):
        self.script = ReaderScript(project.toc_js, "TOC")
        self.book = progress.book_info()
        self.data = progress.data

    def write(self):
        data = self.data
        return self.script.write({
            "book": self._book(),
            "bookTotalPages": data["book_total_pages"],
            "pdfOffset": data["pdf_offset"],
            "lastTranslatedPage": data["last_translated_page"],
            "chapters": self._chapters(),
            "pages": {num: self._page(info) for num, info in data["pages"].items()},
        })

    def _book(self):
        book = self.book
        return {"slug": book["slug"], "title": book["title"], "subtitle": book["subtitle"],
                "subtitleTr": book["subtitle_tr"], "author": book["author"], "series": book["series"]}

    def _chapters(self):
        """Her bölüm bir sonrakinin başlangıcından bir önceki sayfada biter."""
        chapters = self.data["chapters"]
        return [{**chapter, "end": following["start"] - 1 if following else self.data["book_total_pages"]}
                for chapter, following in zip(chapters, chapters[1:] + [None])]

    @staticmethod
    def _page(info):
        if info.get("blank"):
            return {"blank": True}
        return {"title": {"en": info.get("title_en", ""), "tr": info.get("title_tr", "")},
                "section": {"en": info.get("section_en", ""), "tr": info.get("section_tr", "")},
                "chapter": info.get("chapter")}


class Glossary:
    """glossary.md: önsöz satırları + terim tablosu (alfabetik); okuyucu için data/glossary.js."""

    def __init__(self, project):
        self.path = project.glossary_md
        self.script = ReaderScript(project.glossary_js, "GLOSSARY")
        self.preamble, self.terms = self._read()

    def _read(self):
        with open(self.path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        preamble = [line for line in lines if not self._is_term_row(line)]
        terms = [dict(zip(("en", "tr", "note"), _TABLE_ROW.match(line).groups()))
                 for line in lines if self._is_term_row(line)]
        return preamble, terms

    @staticmethod
    def _is_term_row(line):
        match = _TABLE_ROW.match(line)
        if not match:
            return False
        first = match.group(1)
        return first != GLOSSARY_HEADER_CELL and not set(first) <= {"-", " "}

    @staticmethod
    def _key(term):
        return term["en"].casefold()

    def add(self, new_terms):
        """Sözlükte olmayan terimleri ekler ve glossary.md'yi yazar; eklenen sayısı."""
        known = {self._key(term) for term in self.terms}
        added = [term for key, term in self._first_of_each(new_terms).items() if key not in known]
        self.terms += [{"en": t["en"], "tr": t.get("tr", ""), "note": t.get("note", "")} for t in added]
        self._write_md()
        return len(added)

    @classmethod
    def _first_of_each(cls, terms):
        """Aynı sayfada yalnız harf büyüklüğüyle ayrılan terimlerden ilki kalır."""
        unique = {}
        for term in (term for term in terms if term.get("en")):
            unique.setdefault(cls._key(term), term)
        return unique

    def _write_md(self):
        self.terms = sorted(self.terms, key=self._key)
        rows = "".join(f"| {t['en']} | {t['tr']} | {t['note']} |\n" for t in self.terms)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(self.preamble).rstrip("\n") + "\n" + rows)

    def write_js(self):
        return self.script.write(sorted(self.terms, key=self._key))


def rebuild(project):
    return TableOfContents(project, project.load_progress()).write(), Glossary(project).write_js()


def main():
    project = Project.discover()
    for path in rebuild(project):
        print("yazıldı:", project.relative_to_root(path))


if __name__ == "__main__":
    main()
