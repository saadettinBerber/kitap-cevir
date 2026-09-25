import os
import tempfile
import unittest

import _paths  # noqa: F401
from page_document import PageDocument
from project import Project
from translated_pages import TranslatedPages

PAGE = {"id": "page-7", "page": 7, "blocks": [{"type": "heading", "en": "H", "tr": "B"}]}


class TranslatedPagesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Project(tmp.name)
        self.pages = TranslatedPages(self.project)

    def test_saved_page_is_read_back_by_its_number(self):
        self.pages.save(PageDocument(PAGE))
        self.assertEqual(self.pages.get(7).data, PAGE)

    def test_page_number_comes_from_the_document(self):
        self.assertEqual(self.pages.save(PageDocument(PAGE)), self.project.page_js(7))

    def test_missing_page_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            self.pages.get(8)

    def test_agent_only_fields_do_not_reach_the_reader(self):
        self.pages.save(PageDocument({**PAGE, "context": {"prev_tail": "gizli"}}))
        self.assertNotIn("context", self.pages.get(7).data)

    def test_page_file_is_a_reader_callback(self):
        with open(self.pages.save(PageDocument(PAGE)), encoding="utf-8") as page_js:
            self.assertTrue(page_js.read().startswith("window.PAGE({"))

    def test_images_sit_next_to_the_page_file(self):
        self.assertEqual(os.path.dirname(self.pages.images_dir(7)), os.path.dirname(self.project.page_js(7)))


if __name__ == "__main__":
    unittest.main()
