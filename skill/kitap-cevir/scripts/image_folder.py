"""Diskteki bir görsel klasörü: çevirmen girdisinin (_work/in/page-N_images) ya da çevrilmiş sayfanın
(data/pages/page-N_images) PNG'leri. Görseller klasör içindeki adlarıyla (src) anılır."""
import os
import shutil

from extraction.pdf.pymupdf_adapter import image_size


class ImageFolder:
    """Görselin klasörde olup olmadığı, piksel boyutu ve başka klasöre kopyası."""

    def __init__(self, path):
        self.path = path

    def has(self, src):
        return os.path.isfile(self._file(src))

    def size(self, src):
        """(genişlik, yükseklik) piksel."""
        return image_size(self._file(src))

    def copy(self, src, target_dir):
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(self._file(src), os.path.join(target_dir, src))

    def _file(self, src):
        return os.path.join(self.path, src)
