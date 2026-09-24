import os
import tempfile
import unittest

import _paths  # noqa: F401
from backfill_images import ANCHOR_CHARS, MIN_IMAGE_SIDE_PX, ImageBackfiller, ImageFolder, ImagePlacement, PageImages
from page_document import PageDocument
from project import Project

ANCHOR = "layers separate concerns"
FIGURE = (MIN_IMAGE_SIDE_PX, MIN_IMAGE_SIDE_PX)
CODE = {"type": "code", "code": "x = 1"}


def _para(text):
    return {"type": "para", "sentences": [{"en": text, "tr": text}]}


def _image(src):
    return {"type": "image", "src": src}


class FakeImageFolder:
    """ImageFolder gibi; dosyalar {src: (genişlik, yükseklik)} olarak verilir."""

    def __init__(self, sizes):
        self.sizes = sizes
        self.copied = []

    def has(self, src):
        return src in self.sizes

    def size(self, src):
        return self.sizes[src]

    def copy(self, src, target_dir):
        self.copied.append((src, target_dir))


def _anchored(blocks, sizes):
    """sizes: klasördeki dosyalar, {src: (genişlik, yükseklik)}."""
    return PageImages(blocks, FakeImageFolder(sizes)).anchored()


class PageImagesTest(unittest.TestCase):
    """Görsel, PDF'te önündeki metne çapalanır; süs görseller ve eksik dosyalar atlanır."""

    def test_image_is_anchored_to_the_text_before_it(self):
        self.assertEqual(_anchored([_para("Layers separate concerns."), _image("fig.png")], {"fig.png": FIGURE}),
                         [("fig.png", ANCHOR)])

    def test_block_without_text_keeps_the_previous_anchor(self):
        blocks = [_para("Layers separate concerns."), CODE, _image("fig.png")]
        self.assertEqual(_anchored(blocks, {"fig.png": FIGURE}), [("fig.png", ANCHOR)])

    def test_image_before_any_text_has_an_empty_anchor(self):
        self.assertEqual(_anchored([_image("fig.png")], {"fig.png": FIGURE}), [("fig.png", "")])

    def test_missing_file_is_skipped(self):
        self.assertEqual(_anchored([_para("Layers separate concerns."), _image("missing.png")], {}), [])

    def test_image_whose_shorter_side_reaches_the_limit_is_kept(self):
        self.assertEqual(len(_anchored([_image("fig.png")], {"fig.png": (400, MIN_IMAGE_SIDE_PX)})), 1)

    def test_image_whose_shorter_side_is_below_the_limit_is_an_ornament(self):
        self.assertEqual(_anchored([_image("dot.png")], {"dot.png": (400, MIN_IMAGE_SIDE_PX - 1)}), [])

    def test_anchor_keeps_only_the_first_characters(self):
        [(_, anchor)] = _anchored([_para("x" * (ANCHOR_CHARS + 1)), _image("fig.png")], {"fig.png": FIGURE})
        self.assertEqual(anchor, "x" * ANCHOR_CHARS)


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


class ImagePlacementTest(unittest.TestCase):
    def setUp(self):
        self.blocks = [{"type": "heading", "en": "Styles", "tr": "Tarzlar"},
                       _para("Layers separate concerns."), _para("Microservices are small.")]
        self.placement = ImagePlacement(self.blocks)

    def test_image_goes_below_the_matching_block(self):
        self.placement.add("fig.png", "layers separate concerns")
        self.assertEqual(self.blocks[2], _image("fig.png"))

    def test_unmatched_image_goes_below_page_headings(self):
        self.placement.add("fig.png", "")
        self.assertEqual(self.blocks[1], _image("fig.png"))

    def test_has_sees_only_images_already_on_the_page(self):
        self.assertFalse(self.placement.has("fig.png"))
        self.placement.add("fig.png", "")
        self.assertTrue(self.placement.has("fig.png"))



class AnchorMatchTest(unittest.TestCase):
    """Çapa, blok metninin başıyla karşılaştırılır; etiket ve büyük harf sayılmaz."""

    def _placed_at(self, anchor, *texts):
        blocks = [{"type": "heading", "en": "Styles", "tr": "Tarzlar"}] + [_para(text) for text in texts]
        ImagePlacement(blocks).add("fig.png", anchor)
        return blocks.index(_image("fig.png"))

    def test_markup_is_ignored(self):
        text = '<a href="chapter-4.html#layered-architecture">Layers</a> separate concerns'
        self.assertEqual(self._placed_at(ANCHOR, text, "Other."), 2)

    def test_case_is_ignored(self):
        self.assertEqual(self._placed_at(ANCHOR, "LAYERS SEPARATE CONCERNS", "Other."), 2)

    def test_long_block_matches_by_its_beginning(self):
        """PDF'teki çapa önceki bloğun ilk ANCHOR_CHARS harfidir; çevrilmiş blok ise paragrafın tamamı."""
        text = "Layers separate concerns. " + "Each layer talks only to the one below it. " * 5
        self.assertEqual(self._placed_at(ANCHOR, "Other.", text), 3)

    def test_similarity_at_the_threshold_matches(self):
        """11 ortak harf / 40 harf: oran 2 × 11 / 40 = 0.55."""
        self.assertEqual(self._placed_at("a" * 11 + "b" * 9, "Other.", "a" * 11 + "c" * 9), 3)

    def test_similarity_below_the_threshold_does_not_match(self):
        """10 ortak harf / 40 harf: oran 0.5."""
        self.assertEqual(self._placed_at("a" * 10 + "b" * 10, "Other.", "a" * 10 + "c" * 10), 1)

    def test_unmatched_image_on_a_page_of_headings_goes_last(self):
        blocks = [{"type": "heading", "en": "Styles", "tr": "Tarzlar"}]
        ImagePlacement(blocks).add("fig.png", "")
        self.assertEqual(blocks[-1], _image("fig.png"))


class FakeExtractedImages:
    """ExtractedImages gibi; sayfayı PDF'ten çıkarmak yerine hazır blokları verir."""

    def __init__(self, blocks, folder):
        self.blocks = blocks
        self.folder = folder

    def of(self, page):
        return PageImages(self.blocks, self.folder)


class ImageBackfillerTest(unittest.TestCase):
    """PDF'ten çıkan görseller çevrilmiş sayfaya eklenir; tekrar çalıştırmak güvenlidir."""

    PAGE = 5

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project(self.tmp.name)
        self.folder = FakeImageFolder({"fig.png": FIGURE})
        extracted = FakeExtractedImages([_para("Layers separate concerns."), _image("fig.png")], self.folder)
        self.backfiller = ImageBackfiller(self.project, extracted)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_page(self, blocks):
        PageDocument({"page": self.PAGE, "blocks": blocks}).write(self.project.page_js(self.PAGE))

    def _page_blocks(self):
        return PageDocument.read(self.project.page_js(self.PAGE)).data["blocks"]

    def test_missing_image_goes_below_its_text(self):
        self._write_page([_para("Layers separate concerns."), _para("Microservices are small.")])
        self.assertEqual(self.backfiller.backfill_page(self.PAGE), 1)
        self.assertEqual(self._page_blocks()[1], _image("fig.png"))

    def test_added_image_is_copied_next_to_the_page(self):
        self._write_page([_para("Layers separate concerns.")])
        self.backfiller.backfill_page(self.PAGE)
        self.assertEqual(self.folder.copied, [("fig.png", self.project.page_images(self.PAGE))])

    def test_second_run_adds_nothing(self):
        self._write_page([_para("Layers separate concerns.")])
        self.backfiller.backfill_page(self.PAGE)
        self.assertEqual((self.backfiller.backfill_page(self.PAGE), len(self._page_blocks())), (0, 2))

    def test_page_without_new_images_is_not_rewritten(self):
        path = self.project.page_js(self.PAGE)
        self._write_page([_para("Layers separate concerns."), _image("fig.png")])
        with open(path, "a", encoding="utf-8") as page_js:
            page_js.write("// elle eklenmiş satır\n")
        self.backfiller.backfill_page(self.PAGE)
        with open(path, encoding="utf-8") as page_js:
            self.assertTrue(page_js.read().endswith("// elle eklenmiş satır\n"))

if __name__ == "__main__":
    unittest.main()
