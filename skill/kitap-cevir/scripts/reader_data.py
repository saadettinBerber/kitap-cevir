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
TERM_FIELDS = ("en", "tr", "note")
_TABLE_ROW = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")


class ReaderScript:
    """Okuyucunun <script> ile yüklediği, tek bir global değişken tanımlayan dosya."""

    def __init__(self, path, global_name):
        self._path = path
        self._global_name = global_name

    def write(self, payload):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as handle:
            handle.write(f"window.{self._global_name} = ")
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            handle.write(";\n")
        return self._path


class TableOfContents:
    """data/toc.js'in içeriği: kitap bilgisi, bölüm aralıkları ve çevrilmiş sayfaların özeti."""

    def __init__(self, settings, progress):
        self._book = settings.book()
        self._record = progress.as_json()

    def payload(self):
        record = self._record
        return {
            "book": self._book_fields(),
            "bookTotalPages": record["book_total_pages"],
            "pdfOffset": record["pdf_offset"],
            "lastTranslatedPage": record["last_translated_page"],
            "chapters": self._chapters(),
            "pages": {num: _page_summary(info) for num, info in record["pages"].items()},
        }

    def _book_fields(self):
        book = self._book
        return {"slug": book["slug"], "title": book["title"], "subtitle": book["subtitle"],
                "subtitleTr": book["subtitle_tr"], "author": book["author"], "series": book["series"]}

    def _chapters(self):
        """Her bölüm bir sonrakinin başlangıcından bir önceki sayfada biter."""
        chapters = self._record["chapters"]
        return [{**chapter, "end": following["start"] - 1 if following else self._record["book_total_pages"]}
                for chapter, following in zip(chapters, chapters[1:] + [None])]


def _page_summary(info):
    if info.get("blank"):
        return {"blank": True}
    return {"title": {"en": info.get("title_en", ""), "tr": info.get("title_tr", "")},
            "section": {"en": info.get("section_en", ""), "tr": info.get("section_tr", "")},
            "chapter": info.get("chapter")}


class Glossary:
    """glossary.md: önsöz satırlarının altında alfabetik terim tablosu."""

    def __init__(self, path):
        self.path = path
        self.preamble, self.terms = self._read()

    def _read(self):
        with open(self.path, encoding="utf-8") as handle:
            rows = [(line, _term_cells(line)) for line in handle.read().splitlines()]
        preamble = [line for line, cells in rows if not cells]
        return preamble, [dict(zip(TERM_FIELDS, cells)) for _, cells in rows if cells]

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

    def entries(self):
        """Okuyucunun sözlüğü: terimler alfabetik sırayla."""
        return sorted(self.terms, key=self._key)


def _term_cells(line):
    """Terim satırının hücreleri; tablo başlığı, ayraç ve tablo dışı satırlar için boş."""
    match = _TABLE_ROW.match(line)
    if not match or not _is_term(match.group(1)):
        return ()
    return match.groups()


def _is_term(first_cell):
    return first_cell != GLOSSARY_HEADER_CELL and not set(first_cell) <= {"-", " "}


class ReaderData:
    """Okuyucunun data/ altındaki betikleri; progress.json ile glossary.md'den yeniden yazılır."""

    def __init__(self, project):
        self._project = project

    def rebuild(self):
        """Yazılan yollar: önce toc.js, sonra glossary.js."""
        toc_js = self.write_toc(self._project.load_progress())
        return toc_js, self.write_glossary(Glossary(self._project.glossary_md()))

    def write_toc(self, progress):
        toc = TableOfContents(self._project.load_settings(), progress)
        return ReaderScript(self._project.toc_js(), "TOC").write(toc.payload())

    def write_glossary(self, glossary):
        return ReaderScript(self._project.glossary_js(), "GLOSSARY").write(glossary.entries())


def main():
    project = Project.discover()
    for path in ReaderData(project).rebuild():
        print("yazıldı:", project.relative_to_root(path))


if __name__ == "__main__":
    main()
