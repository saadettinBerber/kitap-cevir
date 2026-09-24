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
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project(self.tmp.name)
        self.pages = TranslatedPages(self.project)

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_page_is_read_back_by_its_number(self):
        self.pages.save(PageDocument(PAGE))
        self.assertEqual(self.pages.get(7).data, PAGE)

    def test_page_number_comes_from_the_document(self):
        self.assertEqual(self.pages.save(PageDocument(PAGE)), self.project.page_js(7))

    def test_missing_page_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            self.pages.get(8)

    def test_images_sit_next_to_the_page_file(self):
        self.assertEqual(os.path.dirname(self.pages.images_dir(7)), os.path.dirname(self.project.page_js(7)))


if __name__ == "__main__":
    unittest.main()
