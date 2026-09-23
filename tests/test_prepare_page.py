import unittest

import fitz

import _paths  # noqa: F401
from prepare_page import context_snippets


def _document(page_count):
    document = fitz.open()
    for number in range(1, page_count + 1):
        document.new_page().insert_text((72, 72), f"Sayfa {number}")
    return document


class ContextSnippetsTest(unittest.TestCase):
    def test_middle_page_sees_both_neighbours(self):
        with _document(3) as document:
            self.assertEqual(context_snippets(document, 2), {"prev_tail": "Sayfa 1", "next_head": "Sayfa 3"})

    def test_first_page_has_no_previous_text(self):
        with _document(3) as document:
            self.assertEqual(context_snippets(document, 1)["prev_tail"], "")

    def test_last_page_has_no_following_text(self):
        with _document(3) as document:
            self.assertEqual(context_snippets(document, 3)["next_head"], "")

    def test_single_page_document_has_no_context(self):
        with _document(1) as document:
            self.assertEqual(context_snippets(document, 1), {"prev_tail": "", "next_head": ""})


if __name__ == "__main__":
    unittest.main()
