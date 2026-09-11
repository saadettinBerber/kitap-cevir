import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from project import (DEFAULT_EXTRACTION, Project, ProjectNotFound, book_info,
                     extraction_settings, find_root)


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


class SettingsTest(unittest.TestCase):
    def test_extraction_merges_over_defaults(self):
        merged = extraction_settings({"extraction": {"code_font_prefix": "Consolas"}})
        self.assertEqual(merged["code_font_prefix"], "Consolas")
        self.assertEqual(merged["footnote_max_size"], DEFAULT_EXTRACTION["footnote_max_size"])

    def test_book_info_has_fallback_slug(self):
        self.assertEqual(book_info({})["slug"], "kitap")

    def test_pdf_path_absolute_is_kept(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, "progress.json"), "w").write(json.dumps({"book_pdf": "/x/y.pdf"}))
            project = Project(root)
            self.assertEqual(project.pdf_path(project.load_progress()), "/x/y.pdf")


if __name__ == "__main__":
    unittest.main()
