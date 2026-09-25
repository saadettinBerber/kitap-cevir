import unittest
from xml.etree import ElementTree

import _paths  # noqa: F401
from epub.xhtml import code_block, document, plain_inline, safe_inline, translated_html, unit_html, visible_text


class PlainInlineTest(unittest.TestCase):
    def test_escapes_markup_characters(self):
        self.assertEqual(plain_inline("List<int> & more"), "List&lt;int&gt; &amp; more")

    def test_backtick_parts_become_code(self):
        self.assertEqual(plain_inline("call `f(x)` now"), "call <code>f(x)</code> now")


class SafeInlineTest(unittest.TestCase):
    def test_allowed_tags_stay(self):
        self.assertEqual(safe_inline("<strong>a</strong> <em>b</em><sup>1</sup>"),
                         "<strong>a</strong> <em>b</em><sup>1</sup>")

    def test_line_break_becomes_self_closing(self):
        self.assertEqual(safe_inline("a<br>b"), "a<br/>b")

    def test_other_tags_leave_only_their_text(self):
        self.assertEqual(safe_inline('<span class="x">a</span>'), "a")

    def test_text_is_escaped_again(self):
        self.assertEqual(safe_inline("a &amp; b"), "a &amp; b")

    def test_unclosed_tag_is_closed_at_the_end(self):
        self.assertEqual(safe_inline("<em>a<code>b"), "<em>a<code>b</code></em>")

    def test_crossed_tags_close_the_inner_one_first(self):
        self.assertEqual(safe_inline("<em>a<code>b</em>c"), "<em>a<code>b</code></em>c")

    def test_stray_closing_tag_is_dropped(self):
        self.assertEqual(safe_inline("a</em>b"), "ab")


class UnitHtmlTest(unittest.TestCase):
    def test_html_unit_goes_through_safe_inline(self):
        self.assertEqual(unit_html({"en": "a<br>b", "html": True}, "en"), "a<br/>b")

    def test_plain_unit_is_escaped(self):
        self.assertEqual(unit_html({"en": "a<br>b"}, "en"), "a&lt;br&gt;b")

    def test_translated_html_prefers_turkish(self):
        self.assertEqual(translated_html({"en": "One", "tr": "Bir"}), "Bir")

    def test_untranslated_unit_falls_back_to_english(self):
        self.assertEqual(translated_html({"en": "One", "tr": ""}), "One")


class DocumentTest(unittest.TestCase):
    def test_document_is_well_formed_xml(self):
        root = ElementTree.fromstring(document("A & B", "<p>x</p>").encode("utf-8"))
        self.assertTrue(root.tag.endswith("html"))

    def test_visible_text_drops_tags(self):
        self.assertEqual(visible_text("<em>a</em> b<br/>"), "a b")

    def test_code_block_keeps_code_escaped(self):
        self.assertEqual(code_block("a < b\n  c"), '<pre class="code"><code>a &lt; b\n  c</code></pre>')


if __name__ == "__main__":
    unittest.main()
