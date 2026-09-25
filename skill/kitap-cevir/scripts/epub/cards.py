"""Kavram kartları bölüm sonunda düz XHTML olur (okuyucudaki karşılığı js/concepts.js).
Sayfanın kartlarını PageCards, bölüm sonu kesitini ChapterCards tutar. Kartın türe göre değişen
gövdesini EpubCardVisitor çizer (VISITOR, Bl.6); tür dallanması Card.of'ta kalır. Denetimi
concept_check'tedir.
"""
from concept_cards import Card
from concept_check import SIDES
from epub.fragments import Fragment
from epub.xhtml import code_block, translated_html

CARDS_ANCHOR = "kavram-kartlari"
CARDS_TITLE = "Kavram kartları"
CODE_LABELS = ("Önce", "Sonra")
CONTRAST_LABELS = ("Kaçın", "Tercih et")
TRADEOFF_TIP_LABEL = "Ne zaman hangisi"
DEFAULT_TIP_LABEL = "Pratik ipucu"
OPTION_LABELS = (("gains", "Kazandırır"), ("costs", "Bedeli"))
FIRST_CARD = 1
CARD_LINK_SEPARATOR = " · "


class PageCards:
    """Bir sayfanın çizilecek kartları: sayfa metninin sonundaki kart satırı ve bölüm sonundaki kartlar.
    Çapa kart kimliğinden değil sayfadan ve sayfa içindeki sıradan kurulur; kimlikler ASCII dışı harf
    taşıyabilir (G26)."""

    def __init__(self, page, cards):
        self._page = page
        self._cards = [card for card in cards if _is_drawable(card)]

    def has_cards(self):
        return bool(self._cards)

    def page_end(self):
        """Sayfanın metni bittiği yerde duran satır; her kart başlığı bölüm sonundaki kartına götürür."""
        return [Fragment(self._links())] if self._cards else []

    def html(self):
        return "\n".join(self._card_html(index, card) for index, card in self._numbered())

    def _links(self):
        links = CARD_LINK_SEPARATOR.join(f'<a href="#{self._anchor(index)}">{_text(card.get("title"))}</a>'
                                         for index, card in self._numbered())
        return f'<p class="card-links" id="{self._links_anchor()}">{CARDS_TITLE}: {links}</p>'

    def _numbered(self):
        return enumerate(self._cards, FIRST_CARD)

    def _anchor(self, index):
        return f"kart-{self._page}-{index}"

    def _links_anchor(self):
        """Kart okunduktan sonra dönülecek yer."""
        return f"kartlar-{self._page}"

    def _card_html(self, index, card):
        body = _paragraph(card.get("summary")) + Card.of(card).accept(EpubCardVisitor())
        return f'<div class="card" id="{self._anchor(index)}">{self._head(card)}{body}</div>'

    def _head(self, card):
        back = f'<p class="card-page"><a href="#{self._links_anchor()}">s. {self._page}</a></p>'
        return f'<h3>{_text(card.get("title"))}</h3>{back}'


class ChapterCards:
    """Bölüm sonundaki kart kesiti; sayfaların kartları sırayla eklenir."""

    def __init__(self):
        self._pages = []

    def add(self, page_cards):
        if page_cards.has_cards():
            self._pages.append(page_cards)

    def toc_entries(self):
        return [(CARDS_TITLE, CARDS_ANCHOR)] if self._pages else []

    def section(self):
        """Kart yoksa boş."""
        if not self._pages:
            return ""
        cards = "\n".join(page.html() for page in self._pages)
        return f'<section class="cards">\n<h2 id="{CARDS_ANCHOR}">{CARDS_TITLE}</h2>\n{cards}\n</section>'


class EpubCardVisitor:
    """Kartın özetten sonraki gövdesi: türe özgü kısım ve ipucu."""

    def visit_unknown(self, card):
        return self.visit_explain(card)

    def visit_explain(self, card):
        return self._tip(card, DEFAULT_TIP_LABEL)

    def visit_contrast(self, card):
        return self._sides(card, CONTRAST_LABELS) + self._tip(card, DEFAULT_TIP_LABEL)

    def visit_code(self, card):
        return self._sides(card, CODE_LABELS) + self._tip(card, DEFAULT_TIP_LABEL)

    def visit_tradeoff(self, card):
        return self._options(card) + self._tip(card, TRADEOFF_TIP_LABEL)

    def _sides(self, card, labels):
        return "".join(self._side(card.get(side) or {}, label) for side, label in zip(SIDES, labels))

    def _side(self, sample, label):
        return f'<p class="label">{label}</p>{self._sample_body(sample)}{_paragraph(sample.get("why"))}'

    @staticmethod
    def _sample_body(sample):
        if sample.get("code"):
            return code_block(sample["code"])
        return _paragraph(sample.get("text"))

    def _options(self, card):
        return "".join(self._option(option) for option in card.get("options", []))

    @staticmethod
    def _option(option):
        lines = "".join(f"<p><em>{label}:</em> {_text(option.get(field))}</p>" for field, label in OPTION_LABELS)
        return f'<div class="option"><p class="label">{_text(option.get("name"))}</p>{lines}</div>'

    @staticmethod
    def _tip(card, label):
        if not card.get("tip"):
            return ""
        return f'<p class="tip"><strong>{label}:</strong> {_text(card["tip"])}</p>'


def _is_drawable(card):
    """Özeti (FORMAT.md'de zorunlu) olmayan kart çizilmez; başlıktan ibaret kart kitapta gürültüdür."""
    return bool(card.get("summary"))


def _paragraph(unit):
    return f"<p>{_text(unit)}</p>" if unit else ""


def _text(unit):
    return translated_html(unit or {})

