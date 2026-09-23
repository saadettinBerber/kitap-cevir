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
_NO_BBOX = (0, 0, 0, 0)


def bbox_of(element):
    """ODL öğesinin kutusu [x0, bottom, x1, top]; sol-alt orijinlidir."""
    return element.get("bounding box") or _NO_BBOX


def _flatten(node):
    """İç içe `kids` ağacındaki tipli öğeler, okuma sırasıyla (önce ebeveyn)."""
    if isinstance(node, list):
        return [element for child in node for element in _flatten(child)]
    if not isinstance(node, dict):
        return []
    own = [node] if node.get("type") in CONTENT_TYPES else []
    return own + _flatten(node.get("kids", []) or [])


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
        opendataloader_pdf.convert(input_path=[pdf_path], output_dir=tmp, format="json",
                                   pages=str(pdf_page), image_dir=image_dir, quiet=True)
        doc = _load_single_json(tmp)
    return _flatten(doc.get("kids", []))
