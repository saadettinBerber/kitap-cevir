"""Düzen öğeleri üzerindeki düzeltmeler (LayoutFixer), düzeltme başına bir test sınıfı."""
import contextlib
import io
import unittest

from pdf_fakes import element
from extraction.layout_elements import LayoutFixer
from extraction.pdf.geometry import Box

HOST_BOX = (70, 100, 400, 120)
INSIDE_HOST = Box(120, 104, 140, 116)
BELOW_HOST = Box(120, 204, 140, 216)


def _equation(**fields):
    """Metin katmanının satır içi denklemi; verilmeyen alanlar komşusuz, metinsiz bir görsel denkleminkidir."""
    return {"kind": "image", "id": "eq-1", "text": "", "bbox": INSIDE_HOST, "before": "", "after": "", **fields}


def _fixed(elements):
    """Yalnız yapı düzeltmeleri: sayfada satır içi denklem ya da kod görseli bağlantısı yok."""
    return LayoutFixer([], []).fixed(elements)


def _spliced(equation, text="find to minimize"):
    """(ev sahibinin denklemli metni, bildirilen uyarılar)."""
    with contextlib.redirect_stdout(io.StringIO()) as output:
        [host] = LayoutFixer([equation], []).fixed([element(text, HOST_BOX)])
    return host.text, output.getvalue()


class FootnoteMarkerTest(unittest.TestCase):
    def test_footnote_marker_joins_text_on_same_line(self):
        items = [element("a", (70, 100, 75, 110)), element("Footnote text.", (80, 100, 400, 110))]
        merged = _fixed(items)
        self.assertEqual([item.text for item in merged], ["a Footnote text."])

    def test_marker_on_another_line_stays_apart(self):
        items = [element("a", (70, 100, 75, 110)), element("Next line.", (80, 110, 400, 120))]
        self.assertEqual(_fixed(items), items)


class NestedFragmentTest(unittest.TestCase):
    def test_single_character_inside_another_box_is_dropped(self):
        host, fragment = element("x squared", (70, 100, 300, 120)), element("2", (120, 110, 125, 118))
        self.assertEqual(_fixed([host, fragment]), [host])


class NestedListTest(unittest.TestCase):
    """ODL caption'ı liste sanıp sonrasını maddenin altına (children) gömebilir."""

    BOX = (70, 100, 430, 120)

    def _list_with_kids(self):
        kids = (element("Term Definition Configurability", self.BOX, font_size=9.0),
                element("Cross-Cutting", self.BOX, "heading", font_size=15.8))
        item = element("Table 4-2. Structural characteristics", self.BOX, "list item", font_size=10.0, children=kids)
        return element("", self.BOX, "list", is_ordered=True, list_items=(item,))

    def test_nested_content_returns_to_the_stream(self):
        self.assertEqual([flat.kind for flat in _fixed([self._list_with_kids()])], ["list item", "paragraph", "heading"])

    def test_list_item_keeps_its_text(self):
        self.assertEqual(_fixed([self._list_with_kids()])[0].text, "Table 4-2. Structural characteristics")

    def test_returned_content_is_marked_nested(self):
        self.assertTrue(all(flat.is_nested for flat in _fixed([self._list_with_kids()])))

    def test_plain_list_is_untouched(self):
        items = (element("first", self.BOX, "list item"), element("second", self.BOX, "list item"))
        plain = element("", self.BOX, "list", list_items=items)
        self.assertEqual(_fixed([plain]), [plain])


class CodeImageLinkTest(unittest.TestCase):
    """E-kitap kökenli PDF'lerde her kod listesinin üstünde bir bağlantı satırı
    vardır; kitabın içeriği değildir. ODL onu komşu satırla tek öğede birleştirebilir."""

    LINK = "Click here to view code image"
    # Bağlantı satırı 60-70'te, şeridi komşu satırlara kadar 50-80.
    SLOT = {"text": LINK, "y0": 50, "y1": 80}

    def _without_links(self, *elements):
        return LayoutFixer([], [self.SLOT]).fixed(list(elements))

    def test_element_that_is_only_the_link_is_dropped(self):
        self.assertEqual(self._without_links(element(self.LINK, (70, 60, 430, 70), "heading")), [])

    def test_code_glued_under_the_link_keeps_its_text_and_loses_the_slot(self):
        kept = self._without_links(element(f"{self.LINK} // Two classes", (70, 60, 430, 90)))
        self.assertEqual(kept, [element("// Two classes", (70, 80, 430, 90))])

    def test_prose_glued_above_the_link_is_kept_above_the_slot(self):
        kept = self._without_links(element(f"reduces the time to 9.2 seconds: {self.LINK}", (70, 20, 430, 70)))
        self.assertEqual(kept, [element("reduces the time to 9.2 seconds:", (70, 20, 430, 50))])

    def test_elements_away_from_the_link_are_untouched(self):
        body, image = element("Body text", (70, 280, 430, 300)), element("", (70, 500, 430, 700), "image")
        self.assertEqual(self._without_links(body, image), [body, image])


class InlineMathTest(unittest.TestCase):
    """Satır içi denklem, kutusunu dikeyde kapsayan öğenin metnine komşu kelimeleri arasında girer."""

    def test_placeholder_goes_between_both_neighbours(self):
        self.assertEqual(_spliced(_equation(before="find", after="to"))[0], "find ⟦eq-1⟧ to minimize")

    def test_placeholder_goes_before_the_following_word(self):
        self.assertEqual(_spliced(_equation(after="to"))[0], "find ⟦eq-1⟧ to minimize")

    def test_placeholder_goes_after_the_preceding_word(self):
        self.assertEqual(_spliced(_equation(before="find"))[0], "find ⟦eq-1⟧ to minimize")

    def test_equation_without_neighbours_is_appended(self):
        self.assertEqual(_spliced(_equation())[0], "find to minimize ⟦eq-1⟧")

    def test_equation_whose_neighbours_are_missing_is_left_out(self):
        self.assertEqual(_spliced(_equation(before="seek", after="into"))[0], "find to minimize")

    def test_equation_whose_neighbours_are_missing_is_reported(self):
        self.assertIn("atlandı", _spliced(_equation(before="seek", after="into"))[1])

    def test_simple_symbol_is_inserted_as_text(self):
        self.assertEqual(_spliced(_equation(before="find", after="to", kind="text", text="πr"))[0], "find πr to minimize")

    def test_equation_goes_into_the_first_host_only(self):
        hosts = [element("find to minimize", HOST_BOX), element("find to maximize", HOST_BOX)]
        with contextlib.redirect_stdout(io.StringIO()):
            spliced = LayoutFixer([_equation(before="find", after="to")], []).fixed(hosts)
        self.assertEqual([host.text for host in spliced], ["find ⟦eq-1⟧ to minimize", "find to maximize"])

    def test_equation_below_every_element_is_left_out(self):
        self.assertEqual(_spliced(_equation(before="find", after="to", bbox=BELOW_HOST))[0], "find to minimize")

    def test_equation_below_every_element_is_reported(self):
        self.assertIn("öğe bulunamadı", _spliced(_equation(before="find", after="to", bbox=BELOW_HOST))[1])



class FlattenedInlineMathTest(unittest.TestCase):
    """LiteParse denklem glifini metinden düşürmez, düzleşmiş metin olarak bırakır ve bağlı
    harfleri ayırır; ODL düşürür. Denklemin düz metni komşuların arasındaysa yerini
    denklem alır."""

    ABC = _equation(before="the", after="grows", text="abc")

    def test_flattened_text_between_neighbours_gives_way_to_the_placeholder(self):
        equation = _equation(before="sequence", after="given", text="x1, . . . , xn")
        self.assertEqual(_spliced(equation, "the sequence x 1, , xn given"), ("the sequence ⟦eq-1⟧ given", ""))

    def test_simple_symbol_already_in_the_text_is_not_repeated(self):
        equation = _equation(before="want", after="to", kind="text", text="α")
        self.assertEqual(_spliced(equation, "you might want α to be larger"), ("you might want α to be larger", ""))

    def test_gap_as_long_as_the_equation_text_is_taken(self):
        self.assertEqual(_spliced(self.ABC, "the xyz grows"), ("the ⟦eq-1⟧ grows", ""))

    def test_gap_longer_than_the_equation_text_is_left_alone(self):
        self.assertEqual(_spliced(self.ABC, "the wxyz grows")[0], "the wxyz grows")

    def test_gap_longer_than_the_equation_text_is_reported(self):
        self.assertIn("atlandı", _spliced(self.ABC, "the wxyz grows")[1])

    def test_following_word_inside_the_equation_does_not_cut_it(self):
        equation = _equation(before="sample", after=",", text="(x, yw, yl)")
        self.assertEqual(_spliced(equation, "each sample (x, yw, yl), the loss"), ("each sample ⟦eq-1⟧ , the loss", ""))

    def test_ligature_in_a_neighbour_matches_its_letters(self):
        equation = _equation(before="\ufb01nd", after="to", text="θ")
        self.assertEqual(_spliced(equation, "find θ to minimize"), ("find ⟦eq-1⟧ to minimize", ""))

    def test_adjacent_neighbours_come_before_a_gap(self):
        """ODL metninde denklem yoktur; bitişik komşular bulunursa öncelik onlarındır."""
        equation = _equation(before="find", after="to", kind="text", text="θ")
        self.assertEqual(_spliced(equation, "find α to go, then find to stop")[0],
                         "find α to go, then find θ to stop")


class NeighbourWordBoundaryTest(unittest.TestCase):
    """Komşu kelime tam kelime olarak aranır: harfle başlayan ya da biten yanı başka bir harfe
    yapışık olamaz ('for', 'perform'un içinde değildir)."""

    GLUED = _equation(before="Let", after="be", text="t1, t2, . . . , tq")
    GLUED_TEXT = "Let t 1,t2, ,tqbe the terms"

    def test_following_word_is_not_found_inside_another_word(self):
        equation = _equation(after="for", text="e ∑j exj")
        self.assertEqual(_spliced(equation, "one to perform for each value")[0], "one to perform ⟦eq-1⟧ for each value")

    def test_preceding_word_is_not_found_inside_another_word(self):
        equation = _equation(before="in", text="S")
        self.assertEqual(_spliced(equation, "a point within reach lies in")[0], "a point within reach lies in ⟦eq-1⟧")

    def test_preceding_word_is_not_the_start_of_another_word(self):
        self.assertEqual(_spliced(_equation(before="u", text="u = W + α"), "for your use case")[0], "for your use case")

    def test_preceding_word_that_only_starts_another_word_is_reported(self):
        self.assertIn("atlandı", _spliced(_equation(before="u", text="u = W + α"), "for your use case")[1])

    def test_neighbours_around_flattened_text_are_whole_words(self):
        equation = _equation(before="is", after="The", text="[x1, x2, . . . , xN]")
        self.assertEqual(_spliced(equation, "so this is [x1, x2, The next")[0], "so this is ⟦eq-1⟧ The next")

    def test_flattened_text_glued_to_a_neighbour_is_left_alone(self):
        self.assertEqual(_spliced(self.GLUED, self.GLUED_TEXT)[0], self.GLUED_TEXT)

    def test_flattened_text_glued_to_a_neighbour_is_reported(self):
        self.assertIn("atlandı", _spliced(self.GLUED, self.GLUED_TEXT)[1])

    def test_following_punctuation_may_touch_the_flattened_text(self):
        equation = _equation(before="sum", after=",", text="∑j exj")
        self.assertEqual(_spliced(equation, "the sum ∑j xj, and one")[0], "the sum ⟦eq-1⟧ , and one")

    def test_preceding_punctuation_may_touch_the_flattened_text(self):
        equation = _equation(before="merging:", after="is", kind="text", text="W")
        self.assertEqual(_spliced(equation, "during merging:W is new")[0], "during merging: W is new")

if __name__ == "__main__":
    unittest.main()
