"""Çevrilmiş sayfalara PDF'teki görselleri geriye dönük ekler.

Her çevrilmiş sayfa için PDF'ten görseller çıkarılır; her görsel, PDF'te hemen
önünde gelen metin bloğunun data/pages/page-N.js içindeki karşılığının ALTINA
`image` bloğu olarak eklenir. Metin bloklarına dokunulmaz; tekrar çalıştırmak
güvenlidir (aynı görsel iki kez eklenmez).

Kullanım (proje dizininde): python3 backfill_images.py [N ...]
(argümansız: tüm çevrilmiş sayfalar)
"""
import difflib
import os
import re
import shutil
import sys

import fitz

from page_blocks import Block
from page_document import PageDocument
from page_input import PageInputBuilder
from project import Project

MIN_IMAGE_SIDE_PX = 80          # daha küçükler süs/çizgi parçasıdır
MATCH_THRESHOLD = 0.55
ANCHOR_CHARS = 80
_TAG = re.compile(r"<[^>]+>")


def _plain(text):
    return re.sub(r"[^a-z0-9]+", " ", _TAG.sub(" ", text or "").lower()).strip()


def _similarity(anchor, candidate):
    return difflib.SequenceMatcher(None, anchor, candidate[:len(anchor) + 20]).ratio()


class PageImages:
    """PDF'ten yeniden çıkarılan sayfanın görselleri ve PDF'te önlerindeki metin."""

    def __init__(self, blocks, image_dir):
        self.blocks = [Block.of(block) for block in blocks]
        self.image_dir = image_dir

    def anchored(self):
        """PDF sırasına göre (görsel src, önündeki metin) çiftleri; süs görseller atlanır."""
        found, previous_text = [], ""
        for block in self.blocks:
            sources = block.image_sources()
            if sources:
                found += [(src, previous_text) for src in sources if self._is_real(src)]
            else:
                previous_text = _plain(block.anchor_text())[:ANCHOR_CHARS] or previous_text
        return found

    def _is_real(self, src):
        path = os.path.join(self.image_dir, src)
        if not os.path.isfile(path):
            return False
        pixmap = fitz.Pixmap(path)
        return min(pixmap.width, pixmap.height) >= MIN_IMAGE_SIDE_PX

    def copy(self, src, target_dir):
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(os.path.join(self.image_dir, src), os.path.join(target_dir, src))


class ImagePlacement:
    """Çevrilmiş sayfanın blokları; görsel, PDF'te önünde gelen metnin karşılığının altına girer."""

    def __init__(self, blocks):
        self.blocks = blocks

    def has(self, src):
        return any(src in block.image_sources() for block in self._views())

    def add(self, src, anchor):
        self.blocks.insert(self._index_after(anchor), {"type": "image", "src": src})

    def _views(self):
        return [Block.of(block) for block in self.blocks]

    def _index_after(self, anchor):
        """Çapaya en çok benzeyen bloğun hemen sonrası; eşleşme yoksa sayfa başı
        başlıklarının sonrası."""
        score, index = self._best_match(anchor)
        if score >= MATCH_THRESHOLD:
            return index + 1
        return next((i for i, block in enumerate(self._views()) if not block.leads_page()), len(self.blocks))

    def _best_match(self, anchor):
        """(benzerlik, blok sırası); çapa boşsa hiçbir blok eşleşmez."""
        if not anchor:
            return 0, -1
        scored = [(_similarity(anchor, _plain(block.anchor_text())), index)
                  for index, block in enumerate(self._views())]
        return max(scored, default=(0, -1))


class ImageBackfiller:
    """Çevrilmiş sayfalara PDF'teki görselleri ekler; metin bloklarına dokunmaz."""

    def __init__(self, project, builder):
        self.project = project
        self.builder = builder

    @classmethod
    def for_project(cls, project):
        return cls(project, PageInputBuilder.for_progress(project, project.load_progress()))

    def backfill_page(self, page):
        """Eklenen görsel sayısı; sayfa yalnız görsel eklendiyse yeniden yazılır."""
        images = PageImages(self.builder.build(page)["blocks"], self.builder.image_dir(page))
        page_document = PageDocument.read(self.project.page_js(page))
        added = self._place(images, ImagePlacement(page_document.data["blocks"]), page)
        if added:
            page_document.write(self.project.pages_dir)
        return added

    def _place(self, images, placement, page):
        target_dir = os.path.join(self.project.pages_dir, f"page-{page}_images")
        added = 0
        for src, anchor in images.anchored():
            if not placement.has(src):
                placement.add(src, anchor)
                images.copy(src, target_dir)
                added += 1
        return added


def main():
    project = Project()
    backfiller = ImageBackfiller.for_project(project)
    pages = [int(a) for a in sys.argv[1:]] or project.translated_pages()
    total = 0
    for page in sorted(pages):
        added = backfiller.backfill_page(page)
        total += added
        if added:
            print(f"  sayfa {page}: {added} görsel eklendi")
    print(f"Toplam {total} görsel, {len(pages)} sayfa tarandı.")


if __name__ == "__main__":
    main()
