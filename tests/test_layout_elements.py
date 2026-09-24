import contextlib
import io
import unittest

from pdf_fakes import element
from extraction.odl_elements import OdlElements
from extraction.pdf.geometry import Box

HOST_BOX = (70, 100, 400, 120)
INSIDE_HOST = Box(120, 104, 140, 116)
BELOW_HOST = Box(120, 204, 140, 216)


def _equation(before="", after="", kind="image", text="", box=INSIDE_HOST):
    return {"kind": kind, "id": "eq-1", "text": text, "bbox": box, "before": before, "after": after}


class InlineMathTest(unittest.TestCase):
    """Satır içi denklem, kutusunu dikeyde kapsayan öğenin metnine komşu kelimeleri arasında girer."""

    def _spliced(self, equation, text="find to minimize"):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            [host] = OdlElements([element(text, HOST_BOX)]).with_inline_math([equation]).items
        return host.text, output.getvalue()

    def test_placeholder_goes_between_both_neighbours(self):
        self.assertEqual(self._spliced(_equation("find", "to"))[0], "find ⟦eq-1⟧ to minimize")

    def test_placeholder_goes_before_the_following_word(self):
        self.assertEqual(self._spliced(_equation(after="to"))[0], "find ⟦eq-1⟧ to minimize")

    def test_placeholder_goes_after_the_preceding_word(self):
        self.assertEqual(self._spliced(_equation(before="find"))[0], "find ⟦eq-1⟧ to minimize")

    def test_equation_without_neighbours_is_appended(self):
        self.assertEqual(self._spliced(_equation())[0], "find to minimize ⟦eq-1⟧")

    def test_simple_symbol_is_inserted_as_text(self):
        self.assertEqual(self._spliced(_equation("find", "to", kind="text", text="πr"))[0], "find πr to minimize")

    def test_equation_below_every_element_is_reported_and_left_out(self):
        text, output = self._spliced(_equation("find", "to", box=BELOW_HOST))
        self.assertEqual(text, "find to minimize")
        self.assertIn("öğe bulunamadı", output)


if __name__ == "__main__":
    unittest.main()
