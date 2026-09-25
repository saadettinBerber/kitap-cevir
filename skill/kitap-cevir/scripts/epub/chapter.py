"""Bir bölümün EPUB dosyası: sayfaların tek akışı, sonunda kavram kartları ve açılır notlar."""
from html import escape

from epub.block_visitor import EpubBlockVisitor
from epub.cards import CARDS_ANCHOR, CARDS_TITLE, cards_section
from epub.fragments import Fragment, notes_section
from epub.xhtml import document

PAGE_MARK = '<span epub:type="pagebreak" role="doc-pagebreak" id="page-{n}" title="{n}"/>'


def page_mark(page):
    """Basılı sayfanın yeri; Kindle'ın sayfa listesi (nav → page-list) buraya bağlanır."""
    return PAGE_MARK.format(n=page)


class ChapterFlow:
    """Sayfalar tek akışa dizilir; sayfa sonunda yarım kalan paragraf devamıyla birleşir."""

    def __init__(self):
        self.fragments = []

    def add_page(self, page, fragments):
        if self._is_continued_by(fragments):
            self._continue_paragraph(page, fragments)
        else:
            self._start_page(page, fragments)

    def english(self):
        return [en for fragment in self.fragments for en in fragment.english()]

    def render(self):
        first_notes = self._first_note_numbers()
        return "\n".join(fragment.render(first) for fragment, first in zip(self.fragments, first_notes))

    def toc_entries(self):
        return [entry for fragment in self.fragments for entry in fragment.toc_entries()]

    def _is_continued_by(self, fragments):
        return bool(fragments and self.fragments) and self.fragments[-1].continues_into(fragments[0])

    def _continue_paragraph(self, page, fragments):
        self.fragments[-1] = self.fragments[-1].join(fragments[0], page_mark(page))
        self.fragments += fragments[1:]

    def _start_page(self, page, fragments):
        self.fragments += [Fragment(page_mark(page)), *fragments]

    def _first_note_numbers(self):
        numbers, next_note = [], 1
        for fragment in self.fragments:
            numbers.append(next_note)
            next_note += len(fragment.english())
        return numbers


class Chapter:
    """Bölüm dosyası; bölüm bilgisi ({num, en, tr}) ilk sayfasının belgesinden gelir."""

    def __init__(self, file_name, info):
        self.file_name = file_name
        self.info = info
        self.flow = ChapterFlow()
        self.pages = []
        self.page_cards = []

    def add(self, page_document):
        page = page_document.number()
        self.pages.append(page)
        self.flow.add_page(page, EpubBlockVisitor(page_document).fragments())
        self.page_cards += [(page, card) for card in page_document.concepts()]

    def title(self):
        return self.info.get("tr") or self.info.get("en") or ""

    def toc_entries(self):
        cards = [(CARDS_TITLE, CARDS_ANCHOR)] if self.page_cards else []
        return self.flow.toc_entries() + cards

    def xhtml(self):
        parts = [self._heading(), self.flow.render(), cards_section(self.page_cards),
                 notes_section(self.flow.english())]
        return document(self.title(), "\n".join(part for part in parts if part))

    def _heading(self):
        number = self.info.get("num")
        label = f'<p class="chapter-num">Bölüm {number}</p>' if number else ""
        return f'<header class="chapter">{label}<h1 class="chapter-title">{escape(self.title())}</h1></header>'
