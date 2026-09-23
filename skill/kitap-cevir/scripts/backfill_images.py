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

from extraction.page_extractor import PageExtractor
from page_blocks import Block
from page_document import PageDocument
from project import Project, extraction_settings

MIN_IMAGE_SIDE_PX = 80          # daha küçükler süs/çizgi parçasıdır
MATCH_THRESHOLD = 0.55
ANCHOR_CHARS = 80
_TAG = re.compile(r"<[^>]+>")


def _plain(text):
    return re.sub(r"[^a-z0-9]+", " ", _TAG.sub(" ", text or "").lower()).strip()


def _is_real_image(image_dir, src):
    path = os.path.join(image_dir, src)
    if not os.path.isfile(path):
        return False
    pixmap = fitz.Pixmap(path)
    return min(pixmap.width, pixmap.height) >= MIN_IMAGE_SIDE_PX


def images_with_anchors(blocks, image_dir):
    """PDF sırasına göre (görsel src, önündeki metin) çiftleri."""
    found, previous_text = [], ""
    for block in map(Block.of, blocks):
        if block.kind != "image":
            previous_text = _plain(block.anchor_text())[:ANCHOR_CHARS] or previous_text
        elif _is_real_image(image_dir, block.data["src"]):
            found.append((block.data["src"], previous_text))
    return found


def _similarity(anchor, candidate):
    return difflib.SequenceMatcher(None, anchor, candidate[:len(anchor) + 20]).ratio()


def insertion_index(blocks, anchor):
    """Anchor metnine en çok benzeyen bloğun hemen sonrası; eşleşme yoksa
    ilk başlık/bölüm bloğunun sonrası (sayfa başı görseli)."""
    if anchor:
        scored = [(_similarity(anchor, _plain(Block.of(b).anchor_text())), i) for i, b in enumerate(blocks)]
        best = max(scored, default=(0, -1))
        if best[0] >= MATCH_THRESHOLD:
            return best[1] + 1
    for index, block in enumerate(map(Block.of, blocks)):
        if not block.leads_page():
            return index
    return len(blocks)


def already_has(blocks, src):
    return any(b["type"] == "image" and b.get("src") == src for b in blocks)


def copy_image(project, page, image_dir, src):
    target_dir = os.path.join(project.pages_dir, f"page-{page}_images")
    os.makedirs(target_dir, exist_ok=True)
    shutil.copy2(os.path.join(image_dir, src), os.path.join(target_dir, src))


class ImageBackfiller:
    def __init__(self, project, progress, extractor):
        self.project = project
        self.progress = progress
        self.extractor = extractor

    @classmethod
    def for_project(cls, project):
        progress = project.load_progress()
        return cls(project, progress, PageExtractor(extraction_settings(progress)))

    def translated_pages(self):
        return [int(n) for n, info in self.progress["pages"].items() if not info.get("blank")]

    def backfill_page(self, page):
        image_dir = os.path.join(self.project.work_in, f"page-{page}_images")
        pdf_page = page + self.progress["pdf_offset"]
        extracted = self.extractor.extract(self.project.pdf_path(self.progress), pdf_page, image_dir)
        page_document = PageDocument.read(self.project.page_js(page))
        document = page_document.data
        added = 0
        for src, anchor in images_with_anchors(extracted["blocks"], image_dir):
            if already_has(document["blocks"], src):
                continue
            document["blocks"].insert(insertion_index(document["blocks"], anchor), {"type": "image", "src": src})
            copy_image(self.project, page, image_dir, src)
            added += 1
        if added:
            page_document.write(self.project.pages_dir)
        return added


def main():
    backfiller = ImageBackfiller.for_project(Project())
    pages = [int(a) for a in sys.argv[1:]] or backfiller.translated_pages()
    total = 0
    for page in sorted(pages):
        added = backfiller.backfill_page(page)
        total += added
        if added:
            print(f"  sayfa {page}: {added} görsel eklendi")
    print(f"Toplam {total} görsel, {len(pages)} sayfa tarandı.")


if __name__ == "__main__":
    main()
