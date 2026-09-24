"""Çıkarım ayarları (progress.json -> extraction) ve varsayılanları.

Varsayılanlar 6x9 inç teknik kitap dizgisi içindir; anlamları
references/extraction.md'dedir. Ayar üst düzeyde bir kez birleştirilir
(project.extraction_settings) ve tarayıcılara hazır verilir.
"""
DEFAULT_EXTRACTION = {
    "code_font_prefix": "Courier",
    "code_max_font_size": 9.5,
    "header_zone_bottom": 610,
    "footer_zone_top": 30,
    "running_header": "top",
    "layout_reader": "odl",
    "chapter_number_min_size": 40,
    "chapter_title_min_size": 20,
    "section_min_size": 13.5,
    "subsection_min_size": 11,
    "footnote_max_size": 7.5,
    "bold_heading_font": "Arial",
    "listing_caption_pattern": "^Listing \\d+-\\d+",
    "table_row_gap_ratio": 1.5,
    "table_caption_pattern": "^Table \\d+[-.]\\d+",
    "equation_caption_pattern": "^Equation \\d+[-.]\\d+",
    "math_font_prefix": "Type3",
    "math_geometry": False,
    "chapter_header_prefix": "Chapter ",
    "chapter_label_pattern": "",
    "code_image_link_pattern": "",
    "default_code_language": "java",
}


def with_defaults(overrides):
    return {**DEFAULT_EXTRACTION, **overrides}
