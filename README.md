# kitap-cevir

İngilizce bir PDF kitabı sayfa sayfa Türkçeye çevirip iki dilli, kitap görünümlü
interaktif bir okuyucuda sunan **Claude Code skill'i**. (A Claude Code skill that
turns an English PDF book into a page-by-page EN/TR bilingual web reader.)

Bir kitap projesi üç parçadan oluşur: PDF'ten yapılı bloklar çıkaran Python
betikleri, her sayfayı paralel çeviren Claude agent'ları ve statik bir okuyucu
(`index.html` + `js/` + `css/`). İlerleme, bölüm tablosu ve kitaba özel çıkarım
ayarları projenin `progress.json` dosyasında tutulur; terimler `glossary.md`'de
birikir.

## Kurulum

```bash
git clone https://github.com/saadettinBerber/kitap-cevir ~/Desktop/kitap-cevir
ln -s ~/Desktop/kitap-cevir/skill/kitap-cevir ~/.claude/skills/kitap-cevir
python3 -m pip install -U opendataloader-pdf pymupdf   # Java 11+ gerekir
```

Claude Code'u yeniden başlatınca `/kitap-cevir` görünür.

## Kullanım

```
/kitap-cevir init          yeni kitap projesi kur (PDF yolu ve hedef dizin sorulur)
/kitap-cevir 55            kitap sayfası 55'i çevir
/kitap-cevir next          sıradaki sayfa(lar)ı çevir (progress.json → pages_per_run)
/kitap-cevir next --count 3
/kitap-cevir cards all     çevrilmiş sayfaların kavram kartlarını yeniden üret
/kitap-cevir migrate all   çevrilmiş sayfaları yeni çıkarıma taşı (yeniden çeviri yok)
/kitap-cevir backfill      çevrilmiş sayfalara PDF görsellerini geriye dönük ekle
```

"sıradaki sayfa", "devam et" gibi doğal ifadeler de aynı akışı tetikler.
Okuyucuyu açmak için proje dizininde `python3 -m http.server 8000`.

## Depo düzeni

```
skill/kitap-cevir/            ~/.claude/skills/kitap-cevir buraya bağlanır
├── SKILL.md                  akış: A kurulum / B çeviri / C kart yenileme / D taşıma
├── scripts/
│   │   # SKILL.md'nin çağırdığı betikler
│   ├── init_book.py          yeni proje: iskelet + progress.json + glossary.md
│   ├── inspect_pdf.py        PDF tanıma: info / text / layout / offset
│   ├── prepare_page.py       sıradaki sayfalar → _work/in/page-N.json; boş sayfaları işaretler
│   ├── finalize_page.py      _work/out/page-N.json → data/pages + progress + sözlük + toc
│   ├── regen_concepts.py     kavram kartlarını yeniden ürettirir (metne dokunmaz)
│   ├── migrate_page.py       çevrilmiş sayfaları yeni çıkarıma taşır (yeniden çeviri yok)
│   ├── backfill_images.py    görselleri geriye dönük ekler
│   │   # proje durumu
│   ├── project.py            proje kökü, progress.json, varsayılan ayarlar
│   ├── page_document.py      PageDocument: page-N.js okuma/yazma, çevrilecek metin birimleri
│   ├── page_blocks.py        Block.of: blok türüne göre davranış (birimler, kart girdisi, çapa)
│   ├── page_input.py         PageInputBuilder: sayfanın çevirmen girdisi (bloklar, bölüm, bağlam)
│   ├── json_file.py          JSON okuma/yazma (UTF-8, kaçışsız, girintili)
│   ├── reader_data.py        TableOfContents (data/toc.js), Glossary (glossary.md + data/glossary.js)
│   ├── concept_check.py      kart denetimi: tür, zorunlu alanlar, kod dili
│   ├── migrate_match.py      eski en→tr eşleşmelerini yeni birimlere bulur
│   └── extraction/           PDF sayfası → blok şeması
│       ├── page_extractor.py PageExtractor: ODL + PyMuPDF orkestrasyonu
│       ├── odl_runner.py     OpenDataLoader çağrısı, öğe kutusu
│       ├── page_zones.py     koşu başlığı ve alt bilgi
│       ├── block_builder.py  ODL öğesi → blok; ChapterOpener bölüm açılışını birleştirir
│       ├── page_regions.py   kod/tablo/denklem bölgelerinin okuma sırasına yerleşimi
│       ├── odl_elements.py   OdlElements: gömülü liste, simge parçası, dipnot işareti, satır içi denklem
│       ├── text_fixer.py / text_utils.py   metin onarımı, cümle ayırma
│       ├── text_layer/       PyMuPDF metin katmanı
│       │   ├── layout_scan.py    kod blokları, satır içi kod, tire onarımı
│       │   ├── code_lines.py     satır kurma (PageLineReader)
│       │   ├── text_line.py      TextLine: bir taban çizgisinin parçaları
│       │   └── script_marks.py   alt/üst simge bağlama ve düzeltmeleri
│       ├── tables/           çizgisiz (dolgulu) tablolar: table_scan.py, table_grid.py
│       └── equations/        math_scan.py (Type3 font), math_geometry.py (kesir çizgisi)
├── references/
│   ├── FORMAT.md             sayfa veri formatı, kavram kartları, agent sözleşmesi
│   ├── translation-style.md  çeviri kuralları
│   └── extraction.md         çıkarım ayarları ve akort rehberi
└── templates/project/        init ile kopyalanan okuyucu iskeleti
    ├── index.html, css/, js/, data/pages/
    ├── CLAUDE.md, glossary.md, .gitignore, .claude/launch.json
tests/                        birim testleri (PDF gerektirmez)
```

## Yeni bir kitap için akış

1. `inspect_pdf.py book.pdf offset` → PDF sayfası − kitap sayfası ofseti.
2. İçindekileri okuyup `chapters.json` yaz (`num`, `en`, `tr`, `start`).
3. `init_book.py --pdf ... --title ... --author ... --offset ... --total ... --chapters chapters.json --target <dizin>`
4. `inspect_pdf.py book.pdf layout <sayfa>` ile kod fontu ve başlık boyutlarını
   ölçüp gerekirse `progress.json → extraction` ayarla (bkz. `references/extraction.md`).
5. `/kitap-cevir 1` ve devamı.

## Geliştirme

```bash
python3 -m unittest discover -s tests -v
```

Betikler `skill/kitap-cevir/scripts` altında, çıkarım kütüphanesi `scripts/extraction/`; testler PDF gerektirmez (PyMuPDF
ile geçici PDF üretir). Okuyucu iskeletini değiştirince `templates/project/`
altını düzenleyin; mevcut kitap projelerine elle taşınır.
