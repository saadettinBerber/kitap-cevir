import unittest

import _paths  # noqa: F401
from epub.cards import CARDS_ANCHOR, ChapterCards, PageCards

PAGE = 7
NEXT_PAGE = 8
FIRST_NOTE = 1
EMPTY = {"id": "e", "title": {"en": "EMPTY", "tr": "boş"}}


def _pair(tr):
    return {"en": tr.upper(), "tr": tr}


def _card(kind=None, **fields):
    card = {"id": "c", "title": _pair("başlık"), "summary": _pair("özet"), "tip": _pair("ipucu"), **fields}
    return {**card, "kind": kind} if kind else card


def _html(card):
    return PageCards(PAGE, [card]).html()


def _line(page_cards):
    return "".join(fragment.render(FIRST_NOTE) for fragment in page_cards.page_end())


class CommonPartsTest(unittest.TestCase):
    def test_card_returns_to_its_card_line(self):
        self.assertIn(f'<a href="#kartlar-{PAGE}">s. {PAGE}</a>', _html(_card("explain")))

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

    def test_contrast_side_explains_why(self):
        card = _card("contrast", bad={"text": _pair("kötü"), "why": _pair("çünkü")}, good={"text": _pair("iyi")})
        html = _html(card)
        self.assertLess(html.index("kötü"), html.index("çünkü"))

    def test_every_kind_ends_with_its_tip(self):
        cards = [_card("explain"), _card("contrast", bad={}, good={}), _card("code", bad={}, good={}),
                 _card("tradeoff", options=[]), _card("quiz")]
        self.assertTrue(all(_html(card).endswith("ipucu</p></div>") for card in cards))

    def test_card_without_kind_is_inferred_from_its_content(self):
        card = _card(bad={"lang": "java", "code": "x"}, good={"lang": "java", "code": "y"})
        self.assertIn("Önce", _html(card))

    def test_card_without_tip_has_no_tip(self):
        card = {"id": "c", "kind": "explain", "title": _pair("t"), "summary": _pair("s")}
        self.assertNotIn('class="tip"', _html(card))


class PageCardsTest(unittest.TestCase):
    def test_cards_are_numbered_from_one_within_their_page(self):
        html = PageCards(PAGE, [_card("explain"), _card("explain")]).html()
        self.assertLess(html.index(f'id="kart-{PAGE}-1"'), html.index(f'id="kart-{PAGE}-2"'))

    def test_same_card_on_two_pages_gets_two_anchors(self):
        self.assertIn(f'id="kart-{NEXT_PAGE}-1"', PageCards(NEXT_PAGE, [_card("explain")]).html())

    def test_card_without_summary_is_left_out_and_not_counted(self):
        html = PageCards(PAGE, [EMPTY, _card("explain")]).html()
        self.assertEqual((html.count('<div class="card" '), f'id="kart-{PAGE}-1"' in html), (1, True))

    def test_page_of_cards_without_summary_has_no_cards(self):
        self.assertFalse(PageCards(PAGE, [EMPTY]).has_cards())


class CardLineTest(unittest.TestCase):
    def test_line_links_every_card(self):
        self.assertEqual(_line(PageCards(PAGE, [_card("explain"), _card("explain")])).count('href="#kart-'), 2)

    def test_link_reads_as_the_card_title(self):
        self.assertIn(f'<a href="#kart-{PAGE}-1">başlık</a>', _line(PageCards(PAGE, [_card("explain")])))

    def test_line_carries_the_anchor_cards_return_to(self):
        self.assertIn(f'id="kartlar-{PAGE}"', _line(PageCards(PAGE, [_card("explain")])))

    def test_page_without_drawable_cards_ends_with_nothing(self):
        self.assertEqual(PageCards(PAGE, [EMPTY]).page_end(), [])


class ChapterCardsTest(unittest.TestCase):
    def setUp(self):
        self.cards = ChapterCards()

    def test_no_cards_no_section(self):
        self.cards.add(PageCards(PAGE, [EMPTY]))
        self.assertEqual(self.cards.section(), "")

    def test_no_cards_no_toc_entry(self):
        self.cards.add(PageCards(PAGE, [EMPTY]))
        self.assertEqual(self.cards.toc_entries(), [])

    def test_section_has_its_anchor_and_every_page_of_cards(self):
        self.cards.add(PageCards(PAGE, [_card("explain")]))
        self.cards.add(PageCards(NEXT_PAGE, [_card("explain")]))
        section = self.cards.section()
        self.assertEqual((f'id="{CARDS_ANCHOR}"' in section, section.count('<div class="card" ')), (True, 2))


if __name__ == "__main__":
    unittest.main()
