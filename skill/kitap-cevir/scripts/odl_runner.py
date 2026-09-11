"""OpenDataLoader PDF'i tek sayfa için çağırıp öğe listesini döndürür.

OpenDataLoader iç içe bir ağaç (`kids`) üretir; burada onu düzleştirip
okuma sırasında tipli öğelerin düz listesini veririz.
"""
import glob
import json
import os
import tempfile

import opendataloader_pdf

CONTENT_TYPES = ("heading", "paragraph", "table", "image", "caption", "list")


def _flatten(node, out):
    if isinstance(node, list):
        for child in node:
            _flatten(child, out)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") in CONTENT_TYPES:
        out.append(node)
    for child in node.get("kids", []) or []:
        _flatten(child, out)


def _load_single_json(out_dir):
    files = glob.glob(os.path.join(out_dir, "*.json"))
    if not files:
        raise RuntimeError("OpenDataLoader JSON çıktısı üretmedi")
    with open(files[0], encoding="utf-8") as fh:
        return json.load(fh)


def extract_odl_elements(pdf_path, pdf_page, image_dir):
    """Verilen PDF sayfasını işleyip tipli öğelerin düz listesini döndürür.

    image_dir: çıkarılan görsellerin yazılacağı klasör (page_id bazlı).
    """
    with tempfile.TemporaryDirectory() as tmp:
        opendataloader_pdf.convert(
            input_path=[pdf_path],
            output_dir=tmp,
            format="json",
            pages=str(pdf_page),
            image_dir=image_dir,
            quiet=True,
        )
        doc = _load_single_json(tmp)
    elements = []
    _flatten(doc.get("kids", []), elements)
    return elements
