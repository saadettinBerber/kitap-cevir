import os
import tempfile
import unittest

import _paths  # noqa: F401
from image_folder import ImageFolder


class ImageFolderTest(unittest.TestCase):
    """Diskteki klasör; piksel boyutunu okuyan image_size'ın öğrenme testi test_pdf_boundary'dedir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.tmp.name, "work")
        os.makedirs(self.source)
        with open(os.path.join(self.source, "fig.png"), "wb") as png:
            png.write(b"png")

    def tearDown(self):
        self.tmp.cleanup()

    def test_has_only_files_in_the_folder(self):
        folder = ImageFolder(self.source)
        self.assertEqual((folder.has("fig.png"), folder.has("missing.png")), (True, False))

    def test_copy_creates_the_target_folder(self):
        target = os.path.join(self.tmp.name, "pages", "page-5_images")
        ImageFolder(self.source).copy("fig.png", target)
        self.assertEqual(os.listdir(target), ["fig.png"])


if __name__ == "__main__":
    unittest.main()
