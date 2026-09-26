import contextlib
import io
import os
import tempfile
import unittest

import _paths  # noqa: F401
from backfill_images import (ANCHOR_CHARS, MIN_IMAGE_SIDE_PX, ExtractedImages, ImageBackfiller, ImagePlacement,
                             PageImages)
from image_folder import ImageFolder
from page_document import PageDocument
from page_input import BuiltInput
from project import Project
from translated_pages import TranslatedPages

ANCHOR = "layers separate concerns"
FIGURE = (MIN_IMAGE_SIDE_PX, MIN_IMAGE_SIDE_PX)
WIDE_SIDE_PX = 400
CODE = {"type": "code", "code": "x = 1"}


def _para(text):
    return {"type": "para", "sentences": [{"en": text, "tr": text}]}


def _image(src):
    return {"type": "image", "src": src}


class FakeImageFolder:
    """ImageFolder gibi; dosyalar {src: (genişlik, yükseklik)} olarak verilir, kopyalar kaydedilir."""

    def __init__(self, sizes):
        self._sizes = sizes
        self._copies = []

    def has(self, src):
        return src in self._sizes

    def size(self, src):
        return self._sizes[src]

    def copy(self, sources, target_dir):
        """Gerçek klasör gibi, klasörde olmayan görseli kopyalayamaz."""
        missing = [src for src in sources if not self.has(src)]
        if missing:
            raise FileNotFoundError(missing)
        self._copies += [(src, target_dir) for src in sources]

    def copied(self):
        return list(self._copies)


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
        self.assertEqual(len(_anchored([_image("fig.png")], {"fig.png": (WIDE_SIDE_PX, MIN_IMAGE_SIDE_PX)})), 1)

    def test_image_whose_shorter_side_is_below_the_limit_is_an_ornament(self):
        self.assertEqual(_anchored([_image("dot.png")], {"dot.png": (WIDE_SIDE_PX, MIN_IMAGE_SIDE_PX - 1)}), [])

    def test_anchor_keeps_only_the_first_characters(self):
        [(_, anchor)] = _anchored([_para("x" * (ANCHOR_CHARS + 1)), _image("fig.png")], {"fig.png": FIGURE})
        self.assertEqual(anchor, "x" * ANCHOR_CHARS)


class PageImagesCopyTest(unittest.TestCase):
    def test_nothing_to_add_leaves_the_page_without_an_image_folder(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "page-5_images")
            PageImages([], ImageFolder(root)).copy([], target)
            self.assertFalse(os.path.exists(target))


HEADING = {"type": "heading", "en": "Styles", "tr": "Tarzlar"}
LAYERS = _para("Layers separate concerns.")
SMALL = _para("Microservices are small.")


def _page(*blocks):
    return PageDocument({"blocks": list(blocks)})


class ImagePlacementTest(unittest.TestCase):
    def setUp(self):
        self.page = _page(HEADING, LAYERS, SMALL)
        self.placement = ImagePlacement(self.page)

    def test_image_goes_below_the_matching_block(self):
        self.placement.add("fig.png", "layers separate concerns")
        self.assertEqual(self.page, _page(HEADING, LAYERS, _image("fig.png"), SMALL))

    def test_unmatched_image_goes_below_page_headings(self):
        self.placement.add("fig.png", "")
        self.assertEqual(self.page, _page(HEADING, _image("fig.png"), LAYERS, SMALL))

    def test_image_not_on_the_page_is_missing(self):
        self.assertEqual(self.placement.missing([("fig.png", ANCHOR)]), [("fig.png", ANCHOR)])

    def test_image_on_the_page_is_not_missing(self):
        placement = ImagePlacement(_page(HEADING, LAYERS, _image("fig.png")))
        self.assertEqual(placement.missing([("fig.png", ANCHOR)]), [])

    def test_repeated_image_keeps_its_first_anchor(self):
        self.assertEqual(self.placement.missing([("fig.png", ANCHOR), ("fig.png", "")]), [("fig.png", ANCHOR)])

    def test_unanchored_images_each_go_right_below_the_headings(self):
        self.placement.add_all([("fig.png", ""), ("fig-2.png", "")])
        self.assertEqual(self.page, _page(HEADING, _image("fig-2.png"), _image("fig.png"), LAYERS, SMALL))


class AnchorMatchTest(unittest.TestCase):
    """Çapa, blok metninin başıyla karşılaştırılır; etiket ve büyük harf sayılmaz."""

    @staticmethod
    def _placed_at(anchor, *texts):
        """Görselin başlık ve metin paragraflarından oluşan sayfada girdiği sıra."""
        blocks = [HEADING] + [_para(text) for text in texts]
        page = _page(*blocks)
        ImagePlacement(page).add("fig.png", anchor)
        return next(index for index in range(len(blocks) + 1)
                    if page == _page(*blocks[:index], _image("fig.png"), *blocks[index:]))

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

    def test_characters_inserted_before_the_text_still_match(self):
        """10 harflik çapa; blok başındaki 5 fazla harf karşılaştırılan paya sığar:
        oran 2 × 10 / 25 = 0.8."""
        self.assertEqual(self._placed_at("a" * 10, "Other.", "b" * 5 + "a" * 10), 3)

    def test_unmatched_image_on_a_page_of_headings_goes_last(self):
        self.assertEqual(self._placed_at(""), 1)


class FakeExtractedImages:
    """ExtractedImages gibi; sayfayı PDF'ten çıkarmak yerine hazır blokları verir."""

    def __init__(self, blocks, folder):
        self._blocks = blocks
        self._folder = folder

    def of(self, page):
        return PageImages(self._blocks, self._folder)


class FakePageInputBuilder:
    """PageInputBuilder gibi; boş bir girdi ve verilen denklem uyarılarını verir."""

    def __init__(self, skipped_equations):
        self._skipped_equations = skipped_equations

    def build(self, page, image_dir):
        return BuiltInput({"blocks": []}, self._skipped_equations)


class ExtractedImagesTest(unittest.TestCase):
    def test_skipped_equations_are_printed_while_extracting(self):
        with tempfile.TemporaryDirectory() as root:
            extracted = ExtractedImages(FakePageInputBuilder(["denklem atlandı"]), Project(root))
            with contextlib.redirect_stdout(io.StringIO()) as output:
                extracted.of(1)
        self.assertEqual(output.getvalue(), "  ! denklem atlandı\n")


class ImageBackfillerTest(unittest.TestCase):
    """PDF'ten çıkan görseller çevrilmiş sayfaya eklenir; tekrar çalıştırmak güvenlidir."""

    PAGE = 5
    EXTRACTED = [_para("Layers separate concerns."), _image("fig.png")]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project(self.tmp.name)
        self.folder = FakeImageFolder({"fig.png": FIGURE})
        self.pages = TranslatedPages(self.project)
        self.backfiller = self._backfiller(self.EXTRACTED)

    def tearDown(self):
        self.tmp.cleanup()

    def _backfiller(self, extracted_blocks):
        return ImageBackfiller(self.pages, FakeExtractedImages(extracted_blocks, self.folder))

    def _page(self, blocks):
        return PageDocument({"page": self.PAGE, "blocks": blocks})

    def _write_page(self, blocks):
        self.pages.save(self._page(blocks))

    def _saved_page(self):
        return self.pages.get(self.PAGE)

    def test_missing_image_is_counted(self):
        self._write_page([_para("Layers separate concerns."), _para("Microservices are small.")])
        self.assertEqual(self.backfiller.backfill_page(self.PAGE), 1)

    def test_missing_image_goes_below_its_text(self):
        self._write_page([_para("Layers separate concerns."), _para("Microservices are small.")])
        self.backfiller.backfill_page(self.PAGE)
        self.assertEqual(self._saved_page(), self._page([_para("Layers separate concerns."), _image("fig.png"),
                                                         _para("Microservices are small.")]))

    def test_added_image_is_copied_next_to_the_page(self):
        self._write_page([_para("Layers separate concerns.")])
        self.backfiller.backfill_page(self.PAGE)
        self.assertEqual(self.folder.copied(), [("fig.png", self.pages.images_dir(self.PAGE))])

    def test_image_repeated_in_the_pdf_is_added_once(self):
        self._write_page([_para("Layers separate concerns.")])
        self.assertEqual(self._backfiller(self.EXTRACTED + [_image("fig.png")]).backfill_page(self.PAGE), 1)

    def test_second_run_adds_nothing(self):
        self._write_page([_para("Layers separate concerns.")])
        self.backfiller.backfill_page(self.PAGE)
        self.assertEqual(self.backfiller.backfill_page(self.PAGE), 0)

    def test_second_run_leaves_the_page(self):
        self._write_page([_para("Layers separate concerns.")])
        self.backfiller.backfill_page(self.PAGE)
        self.backfiller.backfill_page(self.PAGE)
        self.assertEqual(self._saved_page(), self._page([_para("Layers separate concerns."), _image("fig.png")]))

    def test_image_already_on_the_page_is_not_copied(self):
        self._write_page([_para("Layers separate concerns."), _image("fig.png")])
        self.backfiller.backfill_page(self.PAGE)
        self.assertEqual(self.folder.copied(), [])

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
