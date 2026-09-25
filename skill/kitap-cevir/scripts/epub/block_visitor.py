"""Bir sayfanın bloklarını bölüm akışının parçalarına çevirir; Block.accept'in ziyaretçisi
(VISITOR, Bl.6). Okuyucudaki karşılığı js/blocks.js; burada JavaScript yok, Kindle'ın
anladığı XHTML var.
"""
import re
from html import escape
from itertools import count
from urllib.parse import quote

from epub.fragments import Fragment, Heading, ParaPassage, Passage, PassageList
from epub.xhtml import code_block, translated_html, unit_html

MIN_HEADING_LEVEL = 1
MAX_HEADING_LEVEL = 3
_INLINE_EQUATION = re.compile(r"⟦(eq-\d+)⟧")


def image_href(page, src):
    """Görselin EPUB içindeki yeri; paket manifestosu da bölüm dosyası da bunu kullanır."""
    return f"images/page-{page}/{src}"


class EpubBlockVisitor:
    """Tek sayfanın ziyaretçisi; her visit_* bloğun parça listesini döner."""

    def __init__(self, page_document):
        self._document = page_document
        self._page = page_document.number()
        self._inline_math = {item["id"]: item for item in page_document.inline_math()}
        self._heading_numbers = count(1)

    def fragments(self):
        return [fragment for block in self._document.blocks() for fragment in block.accept(self)]

    def visit_unknown(self, block):
        return []

    def visit_chapter(self, block):
        """Bölüm başlığını bölüm dosyası bir kez yazar."""
        return []

    def visit_heading(self, block):
        anchor = f"h-{self._page}-{next(self._heading_numbers)}"
        return [Heading(_heading_level(block.data), self._tr(block.data), anchor)]

    def visit_text_unit(self, block):
        return [Passage(block.kind, self._tr(block.data), self._en(block.data))]

    def visit_para(self, block):
        css_class = " ".join(filter(None, ("para", block.data.get("style"))))
        units = block.units()
        return [ParaPassage(css_class, self._joined(units, self._tr), self._joined(units, self._en))]

    def visit_list(self, block):
        items = [Passage("item", self._tr(unit), self._en(unit)) for unit in block.units()]
        return [PassageList(block.data.get("ordered", False), items)]

    def visit_table(self, block):
        rows, header_rows = block.data["rows"], block.data.get("header_rows", 0)
        head = "".join(self._row(row, "th") for row in rows[:header_rows])
        body = "".join(self._row(row, "td") for row in rows[header_rows:])
        thead = f"<thead>{head}</thead>" if head else ""
        return [Fragment(f'<table class="book-table">{thead}<tbody>{body}</tbody></table>')]

    def visit_code(self, block):
        caption = block.data.get("caption")
        heading = f'<p class="caption">{self._tr(caption)}</p>' if caption else ""
        return [Fragment(heading + code_block(block.data["code"]))]

    def visit_image(self, block):
        return [Fragment(f'<div class="figure"><img src="{self._src(block.data["src"])}" alt=""/></div>')]

    def visit_math(self, block):
        return [Fragment(f'<div class="math">{self._equation_img(block.data, "math-display")}</div>')]

    def _row(self, row, cell_tag):
        return "<tr>" + "".join(f"<{cell_tag}>{self._tr(cell)}</{cell_tag}>" for cell in row) + "</tr>"

    @staticmethod
    def _joined(units, unit_to_html):
        return " ".join(unit_to_html(unit) for unit in units)

    def _tr(self, unit):
        return self._with_equations(translated_html(unit))

    def _en(self, unit):
        return self._with_equations(unit_html(unit, "en"))

    def _with_equations(self, html):
        """⟦eq-K⟧ yer tutucusu sayfanın denklem PNG'si olur; karşılığı yoksa olduğu gibi kalır."""
        return _INLINE_EQUATION.sub(self._equation_or_placeholder, html)

    def _equation_or_placeholder(self, match):
        item = self._inline_math.get(match.group(1))
        return self._equation_img(item, "math-inline") if item else match.group(0)

    def _equation_img(self, item, css_class):
        return f'<img class="{css_class}" src="{self._src(item["src"])}" alt="{escape(item.get("text", ""))}"/>'

    def _src(self, src):
        return "../" + quote(image_href(self._page, src))


def _heading_level(data):
    return min(max(data.get("level", MIN_HEADING_LEVEL), MIN_HEADING_LEVEL), MAX_HEADING_LEVEL)
