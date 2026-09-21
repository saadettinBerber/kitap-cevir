# PDF Çıkarım Ayarları (`progress.json` → `extraction`)

`prepare_page.py`, sayfayı iki kaynaktan okur ve birleştirir:

1. **OpenDataLoader PDF** (Java): başlık, paragraf, liste, tablo, görsel,
   caption ve okuma sırası. Koordinatları sol-alt orijinlidir.
2. **PyMuPDF** (`layout_scan.py`): tek aralıklı (monospace) fontla dizilmiş
   satırları girintili kod listelerine çevirir, satır içi kod parçalarını ters
   tırnakla işaretler, ODL'nin sildiği tireleri onarır.
3. **PyMuPDF çizim katmanı** (`table_scan.py` + `table_grid.py`): ODL yalnız
   kenarlık çizgili tabloları tanır; e-kitap kökenli PDF'lerde hücreler zebra
   dolgu dikdörtgenleriyle çizilir ve ODL bunları paragraf/heading yığını sanır.
   Bu modül sütunları dolgu dikdörtgenlerinden (soldan sağa döşeyerek, satır içi
   kod vurgularını eleyerek), satırları dolgu bantlarından ya da metin
   aralıklarından türetir; kalın ilk satırlar `header_rows` olur. Tablo bölgesine
   düşen ODL öğeleri ve kod blokları tek `table` bloğuyla değiştirilir.
   Ayar gerektirmez; `Table N-M` deseni caption'ı `kind: "table"` yapar.
4. **Denklemler** (`math_scan.py`): MathML kökenli denklemler Type3 glif
   fontuyla dizilir (`math_font_prefix`); ODL bu glifleri düşürür. Denklemi düz
   metinle dizen kitaplarda font ipucu yoktur, tetikleyici geometridir
   (`math_geometry`): kesir çizgisi çizim katmanında dar bir yatay çizgidir,
   çevresindeki satırlar (pay, payda, denklemin sol yanı, toplam limitleri) tek
   bölge olur. Tablo kenarlığı ile alt bilgi kuralı sütun kenarından başlar ya
   da sütunun çoğunu kaplar; ayrım aynı hizadaki parçaların toplamına bakılarak
   yapılır (parçaya bakmak yetmez). Ayrı satır
   denklemi PNG olarak kırpılıp `math` bloğu olur, satır içi denklem cümleye
   `⟦eq-K⟧` yer tutucusu (basit sembol düz Unicode) olarak girer. LaTeX üretimi
   çevirmene bırakılır; bkz. FORMAT.md "Denklemler".
5. **Kod satırı hazırlığı** (`code_lines.py`): PyMuPDF geniş boşlukta böldüğü
   parçaları aynı taban çizgisinde birleştirir; Courier formüllerindeki alt/üst
   simgeleri (`10` üstünde `23`) taban çizgisi kaymasından tanıyıp `10^23`,
   `W_K` olarak bağlar; gövde metnindeki simgeleri (`mᵃ`, `cᵉ`, `UR²`) Unicode
   karşılığıyla onarır — yalnız kısa bir sembole yapışanları, çünkü sözcük
   sonundaki küçük işaret (`Photos.²²`) dipnot göndermesidir; satır başındaki tek harflik kod parçasını (`W be the
   key...`) kod bloğu yapmaz.

Kitaba özgü eşikler `progress.json` içindeki `extraction` nesnesinden gelir.
Verilmeyen anahtar için varsayılan (`scripts/project.py` → `DEFAULT_EXTRACTION`)
kullanılır; varsayılanlar 6x9 inç teknik kitap dizgisi için ayarlanmıştır.

| Anahtar                    | Varsayılan            | Anlamı |
|----------------------------|-----------------------|--------|
| `code_font_prefix`         | `"Courier"`           | Bu önekle başlayan font = kod. Kitabınızda `Consolas`, `LucidaConsole`, `CourierNew` olabilir. |
| `code_max_font_size`       | `9.5`                 | Bu boyutun altındaki kod fontu gövde kodudur; daha büyüğü başlık/dosya adı sayılır. |
| `header_zone_bottom`       | `610`                 | ODL y (sol-alt orijin) bu değerin üstündeki ilk öğe koşu başlığıdır. |
| `footer_zone_top`          | `30`                  | ODL y bu değerin altındaki öğeler alt bilgidir, atılır. |
| `header_at_bottom`         | `false`               | Koşu başlığı sayfanın ALTINDAysa (O'Reilly dizgisi: `Kesit Adı \| 201`, çift sayfada `200 \| Chapter 14: ...`) `true` yap; kesit adı alt bilgi bölgesinden okunur. |
| `chapter_number_min_size`  | `40`                  | Bu boyut ve üstünde tek başına sayı = bölüm numarası. |
| `chapter_title_min_size`   | `20`                  | Bu boyut ve üstündeki başlık = bölüm başlığı (`chapter` bloğu). |
| `section_min_size`         | `13.5`                | Başlık seviyesi 1 eşiği. |
| `subsection_min_size`      | `11`                  | Başlık seviyesi 2 eşiği; altı seviye 3. |
| `footnote_max_size`        | `7.5`                 | Bu boyut ve altındaki paragraf = dipnot. |
| `bold_heading_font`        | `"Arial"`             | Bu font adı + "Bold" içeren paragraf küçük başlık (seviye 3) sayılır. |
| `listing_caption_pattern`  | `"^Listing \\d+-\\d+"`| Bu desene uyan başlık = kod listesi caption'ı (`kind: "listing"`). |
| `table_caption_pattern`    | `"^Table \\d+[-.]\\d+"`| Bu desene uyan paragraf = tablo caption'ı (`kind: "table"`). |
| `equation_caption_pattern` | `"^Equation \\d+[-.]\\d+"`| Bu desene uyan paragraf = denklem caption'ı (`kind: "equation"`); denklem bölgesine yutulmaz, ayrıca çevrilir. |
| `math_font_prefix`         | `"Type3"`             | Bu önekle başlayan font = denklem glifi (MathML kökenli PDF'ler). Kitapta denklem yoksa etkisizdir. |
| `math_geometry`            | `false`               | Denklemleri düz metinle dizen kitaplarda (Type3 fontu yok) denklemi kesir çizgisinden bul: dar, yatay, sütun kenarından başlamayan çizginin çevresindeki satırlar tek `math` bloğu (PNG) olur. |
| `chapter_header_prefix`    | `"Chapter "`          | Koşu başlığı bu önekle başlıyorsa bölüm sayfasıdır, kesit adı değildir. |
| `chapter_label_pattern`    | `""` (kapalı)         | Bölüm açılışındaki etiket satırı (`"^CHAPTER (\\d+)$"`); eşleşen satır paragraf değil bölüm numarası olur ve bölüm başlığıyla birleşir. |
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
| Tablo düz paragraf/heading olarak geliyor | hücrelerin dolgu dikdörtgeni yok (yalnız çizgi ya da hiç) | `inspect_pdf.py <pdf> layout N` yerine `python3 -c "import fitz; print(len(fitz.open('book.pdf')[N-1].get_drawings()))"` ile dolgu var mı bak; yoksa PyMuPDF `find_tables(strategy="text")` yedeği henüz yok, hücreleri elle `table` bloğuna çevir |
| Denklem kayboluyor ya da parçalanıyor | denklem fontu `Type3` değil | `inspect_pdf.py <pdf> layout N` ile denklem satırının fontunu bul, `math_font_prefix` ayarla |
| Formüldeki üst simge ayrı satır oluyor | üst simge kod fontunda değil (ör. italik serif) | Bilinen sınırlama: yalnız kod fontlu alt/üst simgeler bağlanır |
| Tablodaki uzun hücre sonrası metin ayrı paragraf oluyor | hücre içindeki boş satır satır sonu sanıldı (bantsız gövde) | Bilinen sınırlama; içerik kaybolmaz, `_work/in` JSON'unda hücreye elle taşı |
