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
│   │   # proje ve akış
│   ├── init_book.py          yeni proje: iskelet + progress.json + glossary.md
│   ├── inspect_pdf.py        PDF tanıma: info / text / layout / offset
│   ├── prepare_page.py       PDF sayfası → _work/in/page-N.json (agent girdisi)
│   ├── finalize_page.py      _work/out/page-N.json → data/pages + progress + sözlük + toc
│   ├── regen_concepts.py     kavram kartlarını yeniden ürettirir (metne dokunmaz)
│   ├── concept_check.py      kart denetimi: tür, zorunlu alanlar, kod dili
│   ├── migrate_page.py       çevrilmiş sayfaları yeni çıkarıma taşır (yeniden çeviri yok)
│   ├── migrate_match.py      eski en→tr eşleşmelerini yeni birimlere bulur
│   ├── backfill_images.py    görselleri geriye dönük ekler
│   ├── toc_builder.py        data/toc.js ve data/glossary.js üretimi
│   ├── project.py            proje kökü, progress.json, varsayılan ayarlar
│   │   # PDF çıkarımı
│   ├── odl_extract.py        OpenDataLoader + PyMuPDF birleşimi (PageExtractor)
│   ├── odl_runner.py         OpenDataLoader çağrısı
│   ├── layout_scan.py        kod satırları, satır içi kod, tire onarımı
│   ├── code_lines.py         kod satırı birleştirme, alt/üst simgeler
│   ├── block_merge.py        dipnot işaretleri ve blok birleştirme düzeltmeleri
│   ├── table_scan.py         çizim katmanından dolgulu tabloları bulur
│   ├── table_grid.py         dolgu dikdörtgenlerinden tablo ızgarası
│   ├── math_scan.py          denklemler: Type3 fontu ya da kesir çizgisi geometrisi
│   └── text_fixer.py / text_utils.py   metin onarımı, cümle ayırma
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

Betikler `skill/kitap-cevir/scripts` altında; testler PDF gerektirmez (PyMuPDF
ile geçici PDF üretir). Okuyucu iskeletini değiştirince `templates/project/`
altını düzenleyin; mevcut kitap projelerine elle taşınır.
