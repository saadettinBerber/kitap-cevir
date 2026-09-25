import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from progress import Progress
from project import Project, ProjectNotFound, find_root


class FindRootTest(unittest.TestCase):
    def test_walks_up_to_progress_json(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, "progress.json"), "w").write("{}")
            nested = os.path.join(root, "a", "b")
            os.makedirs(nested)
            self.assertEqual(find_root(nested), os.path.realpath(root) if os.path.realpath(root) == root else root)

    def test_raises_when_missing(self):
        with tempfile.TemporaryDirectory() as root:
            os.environ.pop("KITAP_ROOT", None)
            with self.assertRaises(ProjectNotFound):
                find_root(root)

    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as root:
            os.environ["KITAP_ROOT"] = root
            try:
                self.assertEqual(find_root("/"), root)
            finally:
                del os.environ["KITAP_ROOT"]


class PdfPathTest(unittest.TestCase):
    def test_pdf_path_absolute_is_kept(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, "progress.json"), "w").write(json.dumps({"book_pdf": "/x/y.pdf"}))
            project = Project(root)
            self.assertEqual(project.pdf_path(), "/x/y.pdf")


class ProgressFileTest(unittest.TestCase):
    PAGE = 3
    RECORD = {"pages": {str(PAGE): {"pdf_page": 22, "section_en": "Shelf", "section_tr": "Kitaplık"}}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Project(self.tmp.name).save_progress(Progress(self.RECORD))

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_progress_reads_back(self):
        progress = Project(self.tmp.name).load_progress()
        self.assertEqual(progress.section_of(self.PAGE), {"en": "Shelf", "tr": "Kitaplık"})

    def test_saved_progress_keeps_turkish_letters_and_ends_with_a_newline(self):
        with open(os.path.join(self.tmp.name, "progress.json"), encoding="utf-8") as handle:
            self.assertTrue(handle.read().endswith('"Kitaplık"\n    }\n  }\n}\n'))


if __name__ == "__main__":
    unittest.main()
