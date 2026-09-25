"""OpenDataLoader PDF adaptörü: `LayoutReader` arayüzünü ODL ile karşılar.

ODL iç içe bir ağaç (`kids`) üretir; burada düzleştirilir ve okuma sırasındaki
tipli öğeler `LayoutElement` olur. ODL kutuları sol-alt orijinlidir
([x0, bottom, x1, top]); sınırda sol-üst orijine çevrilir.
"""
import glob
import json
import os
import tempfile

import opendataloader_pdf

from extraction.pdf.geometry import Box
from extraction.pdf.model import LayoutElement, PageLayout

CONTENT_TYPES = ("heading", "paragraph", "table", "image", "caption", "list")
_NO_BBOX = (0, 0, 0, 0)


class OdlLayoutReader:
    def read(self, page, image_dir):
        with tempfile.TemporaryDirectory() as tmp:
            opendataloader_pdf.convert(input_path=[page.pdf_path], output_dir=tmp, format="json",
                                       pages=str(page.number), image_dir=image_dir, quiet=True)
            tree = _load_single_json(tmp)
        return OdlTree(tree, page.height).layout()


def layout_reader():
    return OdlLayoutReader()


def _load_single_json(out_dir):
    files = glob.glob(os.path.join(out_dir, "*.json"))
    if not files:
        raise RuntimeError("OpenDataLoader JSON çıktısı üretmedi")
    with open(files[0], encoding="utf-8") as fh:
        return json.load(fh)


class OdlTree:
    """ODL'nin tek sayfalık JSON ağacı; öğelerini `LayoutElement` olarak verir."""

    def __init__(self, tree, page_height):
        self._tree = tree
        self._page_height = page_height

    def layout(self):
        return PageLayout(self._page_height, self._elements(_flatten(self._tree.get("kids", []))))

    def _elements(self, nodes):
        return tuple(self._element(node) for node in nodes)

    def _element(self, node):
        return LayoutElement(
            kind=node.get("type") or "", box=self._box(node), text=node.get("content") or "",
            font=node.get("font") or "", font_size=node.get("font size") or 0,
            is_ordered=node.get("numbering style", "unordered") != "unordered",
            list_items=self._elements(node.get("list items") or []), children=self._elements(node.get("kids") or []),
            table_rows=_table_rows(node), image_file=os.path.basename(node.get("source") or ""))

    def _box(self, node):
        x0, bottom, x1, top = node.get("bounding box") or _NO_BBOX
        return Box(x0, self._page_height - top, x1, self._page_height - bottom)


def _flatten(node):
    """İç içe `kids` ağacındaki tipli öğeler, okuma sırasıyla (önce ebeveyn)."""
    if isinstance(node, list):
        return [element for child in node for element in _flatten(child)]
    if not isinstance(node, dict):
        return []
    own = [node] if node.get("type") in CONTENT_TYPES else []
    return own + _flatten(node.get("kids", []) or [])


def _table_rows(node):
    """Her hücrenin metni: hücredeki öğelerin metinleri boşlukla birleşir."""
    return tuple(tuple(" ".join(kid.get("content") or "" for kid in cell.get("kids", []))
                       for cell in row.get("cells", []))
                 for row in node.get("rows", []))
