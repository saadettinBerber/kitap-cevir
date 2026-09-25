"""Kavram kartları bölüm sonunda düz XHTML olur (okuyucudaki karşılığı js/concepts.js).
Kartın türe göre değişen gövdesini EpubCardVisitor çizer (VISITOR, Bl.6); tür dallanması
Card.of'ta kalır. Denetimi concept_check'tedir.
"""
from typing import NamedTuple

from concept_cards import Card
from concept_check import SIDES
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


class PageCard(NamedTuple):
    """Bölüm sonuna giden kart; çapası geldiği sayfadan ve o sayfadaki sırasından kurulur."""
    page: int
    index: int
    card: dict


def is_drawable(card):
    """Özeti (FORMAT.md'de zorunlu) olmayan kart çizilmez; başlıktan ibaret kart kitapta gürültüdür."""
    return bool(card.get("summary"))


def page_cards(page, cards):
    """Sayfanın çizilecek kartları, sayfa içinde 1'den numaralanmış."""
    drawable = [card for card in cards if is_drawable(card)]
    return [PageCard(page, index, card) for index, card in enumerate(drawable, FIRST_CARD)]


def card_anchor(page_card):
    """Kart kimliği değil sıra kullanılır: kimlikler ASCII dışı harf taşıyabilir (G26)."""
    return f"kart-{page_card.page}-{page_card.index}"


def links_anchor(page):
    """Sayfanın kart satırı; kart okunduktan sonra dönülecek yer."""
    return f"kartlar-{page}"


def card_links(page_cards):
    """Sayfanın metni bittiği yerde duran satır; her kart başlığı bölüm sonundaki kartına götürür."""
    links = CARD_LINK_SEPARATOR.join(f'<a href="#{card_anchor(page_card)}">{_text(page_card.card.get("title"))}</a>'
                                     for page_card in page_cards)
    return f'<p class="card-links" id="{links_anchor(page_cards[0].page)}">{CARDS_TITLE}: {links}</p>'


def cards_section(page_cards):
    """Bölüm sonu kesiti; kart yoksa boş."""
    if not page_cards:
        return ""
    cards = "\n".join(card_html(page_card) for page_card in page_cards)
    return f'<section class="cards">\n<h2 id="{CARDS_ANCHOR}">{CARDS_TITLE}</h2>\n{cards}\n</section>'


def card_html(page_card):
    card = page_card.card
    body = _paragraph(card.get("summary")) + Card.of(card).accept(EpubCardVisitor())
    return f'<div class="card" id="{card_anchor(page_card)}">{_card_head(page_card)}{body}</div>'


def _card_head(page_card):
    page = page_card.page
    return f'<h3>{_text(page_card.card.get("title"))}</h3><p class="card-page"><a href="#{links_anchor(page)}">s. {page}</a></p>'


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


def _paragraph(unit):
    return f"<p>{_text(unit)}</p>" if unit else ""


def _text(unit):
    return translated_html(unit or {})

