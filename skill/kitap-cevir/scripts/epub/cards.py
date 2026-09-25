"""Kavram kartları bölüm sonunda düz XHTML olur (okuyucudaki karşılığı js/concepts.js).
Kart bir veri yapısıdır ve türleri sabittir; aynı veriye yeni bir işlem eklendiği için
çizim fonksiyonlarla yazılır (Bl.6). Denetimi concept_check'tedir.
"""
from concept_check import SIDES, card_kind
from epub.xhtml import code_block, translated_html

CARDS_ANCHOR = "kavram-kartlari"
CARDS_TITLE = "Kavram kartları"
SIDE_LABELS = {"code": ("Önce", "Sonra"), "contrast": ("Kaçın", "Tercih et")}
TIP_LABELS = {"tradeoff": "Ne zaman hangisi"}
DEFAULT_TIP_LABEL = "Pratik ipucu"
OPTION_LABELS = (("gains", "Kazandırır"), ("costs", "Bedeli"))


def is_drawable(card):
    """Özeti (FORMAT.md'de zorunlu) olmayan kart çizilmez; başlıktan ibaret kart kitapta gürültüdür."""
    return bool(card.get("summary"))


def cards_section(page_cards):
    """(sayfa, kart) çiftlerinden bölüm sonu kesiti; kart yoksa boş."""
    if not page_cards:
        return ""
    cards = "\n".join(card_html(page, card) for page, card in page_cards)
    return f'<section class="cards">\n<h2 id="{CARDS_ANCHOR}">{CARDS_TITLE}</h2>\n{cards}\n</section>'


def card_html(page, card):
    kind = card_kind(card)
    middle = _MIDDLE_PARTS.get(kind, _no_middle)(card, kind)
    return (f'<div class="card"><h3>{_text(card.get("title"))}</h3>'
            f'<p class="card-page"><a href="#page-{page}">s. {page}</a></p>'
            f'{_paragraph(card.get("summary"))}{middle}{_tip(card, kind)}</div>')


def _no_middle(card, kind):
    return ""


def _sides(card, kind):
    return "".join(_side(card.get(side) or {}, label) for side, label in zip(SIDES, SIDE_LABELS[kind]))


def _side(sample, label):
    return f'<p class="label">{label}</p>{_sample_body(sample)}{_paragraph(sample.get("why"))}'


def _sample_body(sample):
    if sample.get("code"):
        return code_block(sample["code"])
    return _paragraph(sample.get("text"))


def _options(card, kind):
    return "".join(_option(option) for option in card.get("options", []))


def _option(option):
    lines = "".join(f"<p><em>{label}:</em> {_text(option.get(field))}</p>" for field, label in OPTION_LABELS)
    return f'<div class="option"><p class="label">{_text(option.get("name"))}</p>{lines}</div>'


def _tip(card, kind):
    if not card.get("tip"):
        return ""
    return f'<p class="tip"><strong>{TIP_LABELS.get(kind, DEFAULT_TIP_LABEL)}:</strong> {_text(card["tip"])}</p>'


def _paragraph(unit):
    return f"<p>{_text(unit)}</p>" if unit else ""


def _text(unit):
    return translated_html(unit or {})


_MIDDLE_PARTS = {"contrast": _sides, "code": _sides, "tradeoff": _options}
