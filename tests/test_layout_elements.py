"""Düzen öğeleri üzerindeki düzeltmeler (LayoutElements), düzeltme başına bir test sınıfı."""
import contextlib
import io
import unittest

from pdf_fakes import element
from extraction.layout_elements import LayoutElements
from extraction.pdf.geometry import Box

HOST_BOX = (70, 100, 400, 120)
INSIDE_HOST = Box(120, 104, 140, 116)
BELOW_HOST = Box(120, 204, 140, 216)


def _equation(before="", after="", kind="image", text="", box=INSIDE_HOST):
    return {"kind": kind, "id": "eq-1", "text": text, "bbox": box, "before": before, "after": after}


class FootnoteMarkerTest(unittest.TestCase):
    def test_footnote_marker_joins_text_on_same_line(self):
        items = [element("a", (70, 100, 75, 110)), element("Footnote text.", (80, 100, 400, 110))]
        merged = LayoutElements(items).merge_footnote_markers().items
        self.assertEqual([item.text for item in merged], ["a Footnote text."])

    def test_marker_on_another_line_stays_apart(self):
        items = [element("a", (70, 100, 75, 110)), element("Next line.", (80, 110, 400, 120))]
        self.assertEqual(LayoutElements(items).merge_footnote_markers().items, items)


class NestedFragmentTest(unittest.TestCase):
    def test_single_character_inside_another_box_is_dropped(self):
        host, fragment = element("x squared", (70, 100, 300, 120)), element("2", (120, 110, 125, 118))
        self.assertEqual(LayoutElements([host, fragment]).drop_nested_fragments().items, [host])


class NestedListTest(unittest.TestCase):
    """ODL caption'ı liste sanıp sonrasını maddenin altına (children) gömebilir."""

    BOX = (70, 100, 430, 120)

    def _list_with_kids(self):
        kids = (element("Term Definition Configurability", self.BOX, font_size=9.0),
                element("Cross-Cutting", self.BOX, "heading", font_size=15.8))
        item = element("Table 4-2. Structural characteristics", self.BOX, "list item", font_size=10.0, children=kids)
        return element("", self.BOX, "list", is_ordered=True, list_items=(item,))

    def test_nested_content_returns_to_the_stream(self):
        flat = LayoutElements([self._list_with_kids()]).flatten_nested_lists().items
        self.assertEqual([e.kind for e in flat], ["list item", "paragraph", "heading"])
        self.assertEqual(flat[0].text, "Table 4-2. Structural characteristics")
        self.assertTrue(all(e.is_nested for e in flat))

    def test_plain_list_is_untouched(self):
        items = (element("first", self.BOX, "list item"), element("second", self.BOX, "list item"))
        plain = element("", self.BOX, "list", list_items=items)
        self.assertEqual(LayoutElements([plain]).flatten_nested_lists().items, [plain])


class CodeImageLinkTest(unittest.TestCase):
    """E-kitap kökenli PDF'lerde her kod listesinin üstünde bir bağlantı satırı
    vardır; kitabın içeriği değildir. ODL onu komşu satırla tek öğede birleştirebilir."""

    LINK = "Click here to view code image"
    # Bağlantı satırı 60-70'te, şeridi komşu satırlara kadar 50-80.
    SLOT = {"text": LINK, "y0": 50, "y1": 80}

    def _without_links(self, *elements):
        return LayoutElements(list(elements)).without_code_image_links([self.SLOT]).items

    def test_element_that_is_only_the_link_is_dropped(self):
        self.assertEqual(self._without_links(element(self.LINK, (70, 60, 430, 70), "heading")), [])

    def test_code_glued_under_the_link_keeps_its_text_and_loses_the_slot(self):
        [kept] = self._without_links(element(f"{self.LINK} // Two classes", (70, 60, 430, 90)))
        self.assertEqual(kept.text, "// Two classes")
        self.assertEqual(kept.box, Box(70, 80, 430, 90))

    def test_prose_glued_above_the_link_is_kept_above_the_slot(self):
        [kept] = self._without_links(element(f"reduces the time to 9.2 seconds: {self.LINK}", (70, 20, 430, 70)))
        self.assertEqual(kept.text, "reduces the time to 9.2 seconds:")
        self.assertEqual(kept.box, Box(70, 20, 430, 50))

    def test_elements_away_from_the_link_are_untouched(self):
        body, image = element("Body text", (70, 280, 430, 300)), element("", (70, 500, 430, 700), "image")
        self.assertEqual(self._without_links(body, image), [body, image])


class InlineMathTest(unittest.TestCase):
    """Satır içi denklem, kutusunu dikeyde kapsayan öğenin metnine komşu kelimeleri arasında girer."""

    def _spliced(self, equation, text="find to minimize"):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            [host] = LayoutElements([element(text, HOST_BOX)]).with_inline_math([equation]).items
        return host.text, output.getvalue()

    def test_placeholder_goes_between_both_neighbours(self):
        self.assertEqual(self._spliced(_equation("find", "to"))[0], "find ⟦eq-1⟧ to minimize")

    def test_placeholder_goes_before_the_following_word(self):
        self.assertEqual(self._spliced(_equation(after="to"))[0], "find ⟦eq-1⟧ to minimize")

    def test_placeholder_goes_after_the_preceding_word(self):
        self.assertEqual(self._spliced(_equation(before="find"))[0], "find ⟦eq-1⟧ to minimize")

    def test_equation_without_neighbours_is_appended(self):
        self.assertEqual(self._spliced(_equation())[0], "find to minimize ⟦eq-1⟧")

    def test_equation_whose_neighbours_are_missing_is_reported_and_left_out(self):
        text, output = self._spliced(_equation("seek", "into"))
        self.assertEqual(text, "find to minimize")
        self.assertIn("atlandı", output)

    def test_simple_symbol_is_inserted_as_text(self):
        self.assertEqual(self._spliced(_equation("find", "to", kind="text", text="πr"))[0], "find πr to minimize")

    def test_equation_below_every_element_is_reported_and_left_out(self):
        text, output = self._spliced(_equation("find", "to", box=BELOW_HOST))
        self.assertEqual(text, "find to minimize")
        self.assertIn("öğe bulunamadı", output)


if __name__ == "__main__":
    unittest.main()
