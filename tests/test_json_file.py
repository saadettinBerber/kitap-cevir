import os
import tempfile
import unittest

import _paths  # noqa: F401
from json_file import read_json, write_json

PAYLOAD = {"başlık": "Kitaplık", "sayfalar": [1, 2]}


class JsonFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "yeni", "kayıt.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_written_payload_reads_back(self):
        write_json(self.path, PAYLOAD)
        self.assertEqual(read_json(self.path), PAYLOAD)

    def test_missing_folder_is_created(self):
        write_json(self.path, PAYLOAD)
        self.assertTrue(os.path.isfile(self.path))

    def test_written_path_is_returned(self):
        self.assertEqual(write_json(self.path, PAYLOAD), self.path)

    def test_file_is_readable_by_hand(self):
        write_json(self.path, PAYLOAD)
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{\n  "başlık": "Kitaplık",\n  "sayfalar": [\n    1,\n    2\n  ]\n}\n')


if __name__ == "__main__":
    unittest.main()
