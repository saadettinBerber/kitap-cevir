# PDF Çıkarım Ayarları (`progress.json` → `extraction`)

`prepare_page.py`, sayfayı iki kaynaktan okur ve birleştirir:

1. **OpenDataLoader PDF** (Java): başlık, paragraf, liste, tablo, görsel,
   caption ve okuma sırası. Koordinatları sol-alt orijinlidir.
2. **PyMuPDF** (`layout_scan.py`): tek aralıklı (monospace) fontla dizilmiş
   satırları girintili kod listelerine çevirir, satır içi kod parçalarını ters
   tırnakla işaretler, ODL'nin sildiği tireleri onarır.

Kitaba özgü eşikler `progress.json` içindeki `extraction` nesnesinden gelir.
Verilmeyen anahtar için varsayılan (`scripts/project.py` → `DEFAULT_EXTRACTION`)
kullanılır; varsayılanlar 6x9 inç teknik kitap dizgisi için ayarlanmıştır.

| Anahtar                    | Varsayılan            | Anlamı |
|----------------------------|-----------------------|--------|
| `code_font_prefix`         | `"Courier"`           | Bu önekle başlayan font = kod. Kitabınızda `Consolas`, `LucidaConsole`, `CourierNew` olabilir. |
| `code_max_font_size`       | `9.5`                 | Bu boyutun altındaki kod fontu gövde kodudur; daha büyüğü başlık/dosya adı sayılır. |
| `header_zone_bottom`       | `610`                 | ODL y (sol-alt orijin) bu değerin üstündeki ilk öğe koşu başlığıdır. |
| `footer_zone_top`          | `30`                  | ODL y bu değerin altındaki öğeler alt bilgidir, atılır. |
| `chapter_number_min_size`  | `40`                  | Bu boyut ve üstünde tek başına sayı = bölüm numarası. |
| `chapter_title_min_size`   | `20`                  | Bu boyut ve üstündeki başlık = bölüm başlığı (`chapter` bloğu). |
| `section_min_size`         | `13.5`                | Başlık seviyesi 1 eşiği. |
| `subsection_min_size`      | `11`                  | Başlık seviyesi 2 eşiği; altı seviye 3. |
| `footnote_max_size`        | `7.5`                 | Bu boyut ve altındaki paragraf = dipnot. |
| `bold_heading_font`        | `"Arial"`             | Bu font adı + "Bold" içeren paragraf küçük başlık (seviye 3) sayılır. |
| `listing_caption_pattern`  | `"^Listing \\d+-\\d+"`| Bu desene uyan başlık = kod listesi caption'ı (`kind: "listing"`). |
| `chapter_header_prefix`    | `"Chapter "`          | Koşu başlığı bu önekle başlıyorsa bölüm sayfasıdır, kesit adı değildir. |
| `default_code_language`    | `"java"`              | Kod bloklarının vurgulama dili. |

## Ayarları ölçmek

```bash
python3 ~/.claude/skills/kitap-cevir/scripts/inspect_pdf.py book.pdf layout <PDF sayfası>
```

Her satır için `y` (üst orijin), `odlY` (sol-alt orijin, ODL ile aynı), font ve
boyut basılır; sonunda font/boyut histogramı gelir. Kod içeren bir sayfa ile
bölüm açılış sayfasına bakmak yeterlidir:

- Koşu başlığının `odlY` değeri → `header_zone_bottom` bunun biraz altı olmalı.
- Alt bilgi/sayfa numarası satırının `odlY` değeri → `footer_zone_top` bunun biraz üstü.
- Kod satırlarının font adı ve boyutu → `code_font_prefix`, `code_max_font_size`.
- Bölüm numarası / bölüm başlığı / kesit başlığı boyutları → ilgili `*_min_size`.

Ayarları değiştirdikten sonra `prepare_page.py <sayfa>` ile bir sayfayı yeniden
çıkarıp `_work/in/page-N.json` dosyasındaki blok tiplerini kontrol edin.

## Belirtiler ve çözümleri

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| "Sayfa N boş" ama boş değil | `pdf_offset` yanlış | `inspect_pdf.py book.pdf offset` ile yeniden tahmin |
| Kod listesi paragraf olarak geliyor | kod fontu tanınmıyor | `code_font_prefix` / `code_max_font_size` |
| Koşu başlığı gövdeye karışıyor | `header_zone_bottom` düşük | `layout` ile ölçüp yükselt |
| Kesit başlıkları paragraf oluyor | başlık boyut eşiği yüksek | `section_min_size` / `subsection_min_size` düşür |
| Dipnotlar paragraf oluyor | `footnote_max_size` düşük | dipnot font boyutunu ölçüp ayarla |
| Listing caption'ları başlık oluyor | desen uymuyor | `listing_caption_pattern` (örn. `"^Example \\d+\\.\\d+"`) |
