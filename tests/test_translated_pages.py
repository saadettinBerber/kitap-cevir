import os
import tempfile
import unittest

import _paths  # noqa: F401
from page_document import PageDocument
from project import Project
from translated_pages import TranslatedPages

PAGE_NUMBER = 7
MISSING_PAGE = 8
PAGE = {"id": f"page-{PAGE_NUMBER}", "page": PAGE_NUMBER, "blocks": [{"type": "heading", "en": "H", "tr": "B"}]}


class TranslatedPagesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Project(tmp.name)
        self.pages = TranslatedPages(self.project)

    def test_saved_page_is_read_back_by_its_number(self):
        self.pages.save(PageDocument(PAGE))
        self.assertEqual(self.pages.get(PAGE_NUMBER), PageDocument(PAGE))

    def test_page_number_comes_from_the_document(self):
        self.pages.save(PageDocument(PAGE))
        self.assertTrue(os.path.isfile(self.project.page_js(PAGE_NUMBER)))

    def test_missing_page_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            self.pages.get(MISSING_PAGE)

    def test_agent_only_fields_do_not_reach_the_reader(self):
        self.pages.save(PageDocument({**PAGE, "context": {"prev_tail": "gizli"}}))
        self.assertEqual(self.pages.get(PAGE_NUMBER), PageDocument(PAGE))

    def test_page_file_is_a_reader_callback(self):
        self.pages.save(PageDocument(PAGE))
        with open(self.project.page_js(PAGE_NUMBER), encoding="utf-8") as page_js:
            self.assertTrue(page_js.read().startswith("window.PAGE({"))

    def test_replacing_cards_changes_only_the_cards(self):
        self.pages.save(PageDocument(PAGE))
        self.pages.replace_concepts(PAGE_NUMBER, [{"id": "yeni"}])
        self.assertEqual(self.pages.get(PAGE_NUMBER), PageDocument({**PAGE, "concepts": [{"id": "yeni"}]}))

    def test_images_sit_next_to_the_page_file(self):
        self.assertEqual(os.path.dirname(self.pages.images_dir(PAGE_NUMBER)),
                         os.path.dirname(self.project.page_js(PAGE_NUMBER)))


if __name__ == "__main__":
    unittest.main()
