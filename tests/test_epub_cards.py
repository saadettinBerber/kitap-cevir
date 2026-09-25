import unittest

import _paths  # noqa: F401
from epub.cards import CARDS_ANCHOR, PageCard, card_anchor, card_html, cards_section, is_drawable, page_cards

PAGE = 7
NEXT_PAGE = 8


def _pair(tr):
    return {"en": tr.upper(), "tr": tr}


def _card(kind=None, **fields):
    card = {"id": "c", "title": _pair("başlık"), "summary": _pair("özet"), "tip": _pair("ipucu"), **fields}
    return {**card, "kind": kind} if kind else card


def _html(card):
    return card_html(PageCard(1, 1, card))


class CommonPartsTest(unittest.TestCase):
    def test_card_links_back_to_its_page(self):
        self.assertIn(f'<a href="#page-{PAGE}">s. {PAGE}</a>', card_html(PageCard(PAGE, 1, _card("explain"))))

    def test_card_carries_its_anchor(self):
        self.assertIn(f'<div class="card" id="kart-{PAGE}-2">', card_html(PageCard(PAGE, 2, _card("explain"))))

    def test_explain_card_has_title_summary_and_tip(self):
        html = _html(_card("explain"))
        self.assertIn("<h3>başlık</h3>", html)
        self.assertIn("<p>özet</p>", html)
        self.assertIn("<strong>Pratik ipucu:</strong> ipucu", html)

    def test_card_is_turkish(self):
        self.assertNotIn("BAŞLIK", _html(_card("explain")))


class KindTest(unittest.TestCase):
    def test_contrast_card_has_avoid_and_prefer(self):
        card = _card("contrast", bad={"text": _pair("kötü"), "why": _pair("çünkü")}, good={"text": _pair("iyi")})
        html = _html(card)
        self.assertLess(html.index("Kaçın"), html.index("kötü"))
        self.assertLess(html.index("Tercih et"), html.index("iyi"))

    def test_code_card_has_before_and_after_code(self):
        card = _card("code", bad={"lang": "python", "code": "a<b"}, good={"lang": "python", "code": "c"})
        html = _html(card)
        self.assertIn('<p class="label">Önce</p><pre class="code"><code>a&lt;b</code></pre>', html)

    def test_tradeoff_card_lists_gains_and_costs(self):
        option = {"name": _pair("seçenek"), "gains": _pair("kazanç"), "costs": _pair("bedel")}
        html = _html(_card("tradeoff", options=[option]))
        self.assertIn("<em>Kazandırır:</em> kazanç", html)
        self.assertIn("<strong>Ne zaman hangisi:</strong>", html)

    def test_card_without_kind_is_inferred_from_its_content(self):
        card = _card(bad={"lang": "java", "code": "x"}, good={"lang": "java", "code": "y"})
        self.assertIn("Önce", _html(card))

    def test_card_without_tip_has_no_tip(self):
        card = {"id": "c", "kind": "explain", "title": _pair("t"), "summary": _pair("s")}
        self.assertNotIn('class="tip"', _html(card))


class DrawableTest(unittest.TestCase):
    def test_card_with_summary_is_drawable(self):
        self.assertTrue(is_drawable(_card("explain")))

    def test_card_without_summary_is_not_drawable(self):
        self.assertFalse(is_drawable({"id": "e", "title": _pair("boş"), "body_html": "<p/>"}))


class PageCardsTest(unittest.TestCase):
    def test_cards_are_numbered_from_one_within_their_page(self):
        cards = page_cards(PAGE, [_card("explain"), _card("explain")])
        self.assertEqual([card_anchor(card) for card in cards], [f"kart-{PAGE}-1", f"kart-{PAGE}-2"])

    def test_same_card_id_on_two_pages_gets_two_anchors(self):
        first, second = page_cards(PAGE, [_card("explain")]) + page_cards(NEXT_PAGE, [_card("explain")])
        self.assertNotEqual(card_anchor(first), card_anchor(second))

    def test_card_without_summary_is_left_out_and_not_counted(self):
        empty = {"id": "e", "title": _pair("boş")}
        cards = page_cards(PAGE, [empty, _card("explain")])
        self.assertEqual([card_anchor(card) for card in cards], [f"kart-{PAGE}-1"])


class SectionTest(unittest.TestCase):
    def test_no_cards_no_section(self):
        self.assertEqual(cards_section([]), "")

    def test_section_has_its_anchor_and_every_card(self):
        section = cards_section(page_cards(1, [_card("explain")]) + page_cards(2, [_card("explain")]))
        self.assertIn(f'id="{CARDS_ANCHOR}"', section)
        self.assertEqual(section.count('<div class="card" '), 2)


if __name__ == "__main__":
    unittest.main()
