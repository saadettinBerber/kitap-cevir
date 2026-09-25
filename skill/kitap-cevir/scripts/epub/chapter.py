"""Bir bölümün EPUB dosyası: sayfaların tek akışı, sonunda kavram kartları ve açılır notlar."""
from html import escape
from itertools import accumulate

from epub.block_visitor import EpubBlockVisitor
from epub.cards import ChapterCards, PageCards
from epub.fragments import Fragment, notes_section
from epub.xhtml import document

FIRST_NOTE = 1
PAGE_ANCHOR = "page-{n}"
PAGE_MARK = '<span epub:type="pagebreak" role="doc-pagebreak" id="' + PAGE_ANCHOR + '" title="{n}"/>'


def page_mark(page):
    """Basılı sayfanın yeri; Kindle'ın sayfa listesi (nav → page-list) buraya bağlanır."""
    return PAGE_MARK.format(n=page)


class ChapterFlow:
    """Sayfalar tek akışa dizilir; sayfa sonunda yarım kalan paragraf devamıyla birleşir.
    Sayfa sonu eki (kart satırı) bu birleşmeyi kırmasın diye sonraki sayfa gelene dek bekler."""

    def __init__(self):
        self._fragments = []
        self._page_end = []

    def add_page(self, page, fragments):
        self._place(page, fragments)
        self._page_end = []

    def end_page(self, fragments):
        self._page_end = fragments

    def english(self):
        return [en for fragment in self._flow() for en in fragment.english()]

    def render(self):
        first_notes = self._first_note_numbers()
        return "\n".join(fragment.render(first) for fragment, first in zip(self._flow(), first_notes))

    def toc_entries(self):
        return [entry for fragment in self._flow() for entry in fragment.toc_entries()]

    def _flow(self):
        return self._fragments + self._page_end

    def _place(self, page, fragments):
        if self._is_continued_by(fragments):
            self._continue_paragraph(page, fragments)
        else:
            self._start_page(page, fragments)

    def _is_continued_by(self, fragments):
        return bool(fragments and self._fragments) and self._fragments[-1].continues_into(fragments[0])

    def _continue_paragraph(self, page, fragments):
        self._fragments[-1] = self._fragments[-1].join(fragments[0], page_mark(page))
        self._fragments += self._page_end + fragments[1:]

    def _start_page(self, page, fragments):
        self._fragments += [*self._page_end, Fragment(page_mark(page)), *fragments]

    def _first_note_numbers(self):
        """Her parçanın ilk not numarası; numaralar bölüm boyunca sürer."""
        note_counts = [len(fragment.english()) for fragment in self._flow()]
        return list(accumulate(note_counts[:-1], initial=FIRST_NOTE))


class Chapter:
    """Bölüm dosyası; bölüm bilgisi ({num, en, tr}) ilk sayfasının belgesinden gelir."""

    def __init__(self, file_name, info):
        self._file_name = file_name
        self._info = info
        self._flow = ChapterFlow()
        self._pages = []
        self._cards = ChapterCards()

    def add(self, page_document):
        page = page_document.number()
        self._pages.append(page)
        self._flow.add_page(page, EpubBlockVisitor(page_document).fragments())
        self._add_cards(PageCards(page, page_document.concepts()))

    def _add_cards(self, cards):
        self._flow.end_page(cards.page_end())
        self._cards.add(cards)

    def href(self, anchor=""):
        """Bölüm dosyasına, çapa verilirse dosyadaki o yere bağlantı."""
        return f"{self._file_name}#{anchor}" if anchor else self._file_name

    def page_links(self):
        """(basılı sayfa, bağlantı) çiftleri; Kindle'ın sayfa listesi bunlardan kurulur."""
        return [(page, self.href(PAGE_ANCHOR.format(n=page))) for page in self._pages]

    def title(self):
        return self._info.get("tr") or self._info.get("en") or ""

    def toc_entries(self):
        return self._flow.toc_entries() + self._cards.toc_entries()

    def xhtml(self):
        parts = [self._heading(), self._flow.render(), self._cards.section(),
                 notes_section(self._flow.english())]
        return document(self.title(), "\n".join(part for part in parts if part))

    def _heading(self):
        number = self._info.get("num")
        label = f'<p class="chapter-num">Bölüm {number}</p>' if number else ""
        return f'<header class="chapter">{label}<h1 class="chapter-title">{escape(self.title())}</h1></header>'
