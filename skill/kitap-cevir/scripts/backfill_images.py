"""Çevrilmiş sayfalara PDF'teki görselleri geriye dönük ekler.

Her çevrilmiş sayfa için PDF'ten görseller çıkarılır; her görsel, PDF'te hemen
önünde gelen metin bloğunun data/pages/page-N.js içindeki karşılığının ALTINA
`image` bloğu olarak eklenir. Metin bloklarına dokunulmaz; tekrar çalıştırmak
güvenlidir (aynı görsel iki kez eklenmez).

Kullanım (proje dizininde): python3 backfill_images.py [N ...]
(argümansız: progress.json'da kayıtlı tüm çevrilmiş sayfalar)
"""
import difflib
import re
import sys

from image_folder import ImageFolder
from page_blocks import Block
from page_input import PageInputBuilder
from project import Project
from translated_pages import TranslatedPages

MIN_IMAGE_SIDE_PX = 80          # daha küçükler süs/çizgi parçasıdır
MATCH_THRESHOLD = 0.55
ANCHOR_CHARS = 80
# Çevrilmiş blok, PDF'teki çapadan biraz uzun bir baş parçasıyla karşılaştırılır: araya giren birkaç harf
# (dipnot işareti, bağlantı metni) eşleşmeyi bozmasın.
CANDIDATE_SLACK_CHARS = 20
_TAG = re.compile(r"<[^>]+>")


def _plain(text):
    return re.sub(r"[^a-z0-9]+", " ", _TAG.sub(" ", text or "").lower()).strip()


def _similarity(anchor, candidate):
    return difflib.SequenceMatcher(None, anchor, candidate[:len(anchor) + CANDIDATE_SLACK_CHARS]).ratio()


class PageImages:
    """PDF'ten yeniden çıkarılan sayfanın görselleri ve PDF'te önlerindeki metin."""

    def __init__(self, blocks, folder):
        self._blocks = [Block.of(block) for block in blocks]
        self._folder = folder

    def anchored(self):
        """PDF sırasına göre (görsel src, önündeki metin) çiftleri; süs görseller atlanır."""
        found, previous_text = [], ""
        for block in self._blocks:
            sources = block.image_sources()
            if sources:
                found += [(src, previous_text) for src in sources if self._is_real(src)]
            else:
                previous_text = _plain(block.anchor_text())[:ANCHOR_CHARS] or previous_text
        return found

    def copy(self, sources, target_dir):
        """Eklenen görseller sayfanın görsel klasörüne kopyalanır; eklenen yoksa klasöre dokunulmaz."""
        if sources:
            self._folder.copy(sources, target_dir)

    def _is_real(self, src):
        return self._folder.has(src) and min(self._folder.size(src)) >= MIN_IMAGE_SIDE_PX


class ImagePlacement:
    """Çevrilmiş sayfaya görsel yerleştirir: görsel, PDF'te önündeki metnin karşılığının altına girer."""

    def __init__(self, document):
        self._document = document

    def missing(self, anchored):
        """(görsel src, çapa) çiftlerinden sayfada olmayanlar; PDF'te tekrar eden görsel bir kez."""
        present = set(self._document.image_sources())
        first_anchors = {}
        for src, anchor in anchored:
            first_anchors.setdefault(src, anchor)
        return [(src, anchor) for src, anchor in first_anchors.items() if src not in present]

    def add_all(self, anchored):
        for src, anchor in anchored:
            self.add(src, anchor)

    def add(self, src, anchor):
        self._document.insert_image(self._index_after(anchor), src)

    def _index_after(self, anchor):
        """Çapaya en çok benzeyen bloğun hemen sonrası; eşleşme yoksa sayfa başı
        başlıklarının sonrası."""
        score, index = self._best_match(anchor)
        if score >= MATCH_THRESHOLD:
            return index + 1
        return self._document.leading_block_count()

    def _best_match(self, anchor):
        """(benzerlik, blok sırası); çapa boşsa hiçbir blok eşleşmez."""
        if not anchor:
            return 0, -1
        scored = [(_similarity(anchor, _plain(text)), index)
                  for index, text in enumerate(self._document.anchor_texts())]
        return max(scored, default=(0, -1))


class ExtractedImages:
    """Sayfayı PDF'ten yeniden çıkarır; blokları ve görsel klasörünü PageImages olarak verir."""

    def __init__(self, builder, project):
        self._builder = builder
        self._project = project

    def of(self, page):
        image_dir = self._project.work_images(page)
        return PageImages(self._builder.build(page, image_dir)["blocks"], ImageFolder(image_dir))


class ImageBackfiller:
    """Çevrilmiş sayfalara PDF'teki görselleri ekler; metin bloklarına dokunmaz."""

    def __init__(self, pages, extracted):
        self._pages = pages
        self._extracted = extracted

    @classmethod
    def for_progress(cls, project, progress):
        builder = PageInputBuilder.for_progress(project, progress)
        return cls(TranslatedPages(project), ExtractedImages(builder, project))

    def backfill_page(self, page):
        """Eklenen görsel sayısı; sayfa yalnız görsel eklendiyse yeniden yazılır."""
        images = self._extracted.of(page)
        document = self._pages.get(page)
        placement = ImagePlacement(document)
        missing = placement.missing(images.anchored())
        placement.add_all(missing)
        images.copy([src for src, _ in missing], self._pages.images_dir(page))
        if missing:
            self._pages.save(document)
        return len(missing)


def main():
    project = Project.discover()
    progress = project.load_progress()
    pages = [int(a) for a in sys.argv[1:]] or progress.translated_pages()
    total = _backfill(ImageBackfiller.for_progress(project, progress), sorted(pages))
    print(f"Toplam {total} görsel, {len(pages)} sayfa tarandı.")


def _backfill(backfiller, pages):
    """Sayfaları sırayla tarar, görsel eklenenleri basar; toplam eklenen görsel."""
    total = 0
    for page in pages:
        added = backfiller.backfill_page(page)
        total += added
        if added:
            print(f"  sayfa {page}: {added} görsel eklendi")
    return total


if __name__ == "__main__":
    main()
