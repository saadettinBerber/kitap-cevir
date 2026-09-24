# PDF Çıkarım Ayarları (`progress.json` → `extraction`)

`prepare_page.py`, sayfayı iki kaynaktan okur ve birleştirir (kod:
`scripts/extraction/`, giriş noktası `page_extractor.PageExtractor`):

PDF kütüphanelerine yalnız `extraction/pdf/` altındaki adaptörler dokunur;
akışlar düz veri nesnelerini (`Span`, `Drawing`, `LayoutElement`) ve iki arayüzü
(`PdfPage`, `LayoutReader`) görür. Çıkarım kodunun tamamı sol-üst orijinle
çalışır. Başka bir düzen okuyucusu (ör. LiteParse) `LayoutReader`'a bir adaptör
yazılıp `PageExtractor`'a verilerek eklenir.

1. **OpenDataLoader PDF** (Java; `LayoutReader` adaptörü `pdf/odl_adapter.py`):
   başlık, paragraf, liste, tablo, görsel, caption ve okuma sırası. ODL
   koordinatları sol-alt orijinlidir; adaptör sınırda sol-üst orijine çevirir.
2. **PyMuPDF metin katmanı** (`extraction/text_layer/`): tek aralıklı (monospace) fontla dizilmiş
   satırları girintili kod listelerine çevirir, satır içi kod parçalarını ters
   tırnakla işaretler, ODL'nin sildiği tireleri onarır.
3. **PyMuPDF çizim katmanı** (`extraction/tables/`): ODL yalnız
   kenarlık çizgili tabloları tanır; e-kitap kökenli PDF'lerde hücreler zebra
   dolgu dikdörtgenleriyle çizilir ve ODL bunları paragraf/heading yığını sanır.
   Bu modül sütunları dolgu dikdörtgenlerinden (soldan sağa döşeyerek, satır içi
   kod vurgularını eleyerek), satırları dolgu bantlarından ya da metin
   aralıklarından türetir; kalın ilk satırlar `header_rows` olur. Tablo bölgesine
   düşen ODL öğeleri ve kod blokları tek `table` bloğuyla değiştirilir.
   `Table N-M` deseni caption'ı `kind: "table"` yapar. Tablo **altındaki ilk yatay
   çizgide** biter (alt kenar); çizgi yoksa metin alanının sonunda — sayfa sonuna
   uzatmak altındaki caption'ı, yan kutuyu ve koşu başlığını tabloya katıyordu.
   Aynı sayfadaki iki tablo çoğu zaman aynı sol kenardan başlar; ortak kenar
   değil aradaki dikey boşluk ayırır. Bantsız gövdede satır eşiği
   `table_row_gap_ratio` ile kitaba göre ayarlanır.
4. **Denklemler** (`extraction/equations/`): MathML kökenli denklemler Type3 glif
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
5. **Kod satırı hazırlığı** (`text_layer/code_lines.py`, simgeler `script_marks.py`): PyMuPDF geniş boşlukta böldüğü
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
| `running_header`           | `"top"`               | Koşu başlığının yeri. `"top"`: `header_zone_bottom` üstündeki ilk öğe. `"bottom"`: sayfanın altında (O'Reilly dizgisi: `Kesit Adı \| 201`, çift sayfada `200 \| Chapter 14: ...`); kesit adı alt bilgi bölgesinden okunur. `"none"`: koşu başlığı yok (e-kitap kökenli PDF'ler); sayfanın en üstü gövdedir. Eski `header_at_bottom` anahtarı kaldırıldı, bulunursa çıkarım durur. |
| `header_zone_bottom`       | `610`                 | Yalnız `running_header: "top"`: alt kenarı sayfanın altından bu yükseklikten (`odlY`) yukarıda kalan ilk öğe koşu başlığıdır. |
| `footer_zone_top`          | `30`                  | Üst kenarı sayfanın altından bu yükseklikten (`odlY`) aşağıda kalan öğeler alt bilgidir, atılır. |
| `chapter_number_min_size`  | `40`                  | Bu boyut ve üstünde tek başına sayı = bölüm numarası. |
| `chapter_title_min_size`   | `20`                  | Bu boyut ve üstündeki başlık = bölüm başlığı (`chapter` bloğu). |
| `section_min_size`         | `13.5`                | Başlık seviyesi 1 eşiği. |
| `subsection_min_size`      | `11`                  | Başlık seviyesi 2 eşiği; altı seviye 3. |
| `footnote_max_size`        | `7.5`                 | Bu boyut ve altındaki paragraf = dipnot. |
| `bold_heading_font`        | `"Arial"`             | Bu font adı + "Bold" içeren paragraf küçük başlık (seviye 3) sayılır. |
| `listing_caption_pattern`  | `"^Listing \\d+-\\d+"`| Bu desene uyan başlık = kod listesi caption'ı (`kind: "listing"`). |
| `table_caption_pattern`    | `"^Table \\d+[-.]\\d+"`| Bu desene uyan paragraf = tablo caption'ı (`kind: "table"`). |
| `table_row_gap_ratio`      | `1.5`                 | Bantsız tablo gövdesinde satır arası boşluk / satır yüksekliği eşiği. Kitaba göre ölçülür: bir kitapta satır içi 1.2 / satırlar arası 1.6 (eşik 1.5), başkasında 0.93 / 1.26 (eşik 1.1). Yanlışsa bütün satırlar tek hücrede `<br>` ile birleşir. |
| `equation_caption_pattern` | `"^Equation \\d+[-.]\\d+"`| Bu desene uyan paragraf = denklem caption'ı (`kind: "equation"`); denklem bölgesine yutulmaz, ayrıca çevrilir. |
| `math_font_prefix`         | `"Type3"`             | Bu önekle başlayan font = denklem glifi (MathML kökenli PDF'ler). Kitapta denklem yoksa etkisizdir. |
| `math_geometry`            | `false`               | Denklemleri düz metinle dizen kitaplarda (Type3 fontu yok) denklemi kesir çizgisinden bul: dar, yatay, sütun kenarından başlamayan çizginin çevresindeki satırlar tek `math` bloğu (PNG) olur. |
| `chapter_header_prefix`    | `"Chapter "`          | Koşu başlığı bu önekle başlıyorsa bölüm sayfasıdır, kesit adı değildir. |
| `chapter_label_pattern`    | `""` (kapalı)         | Bölüm açılışındaki etiket satırı (`"^CHAPTER (\\d+)$"`); eşleşen satır paragraf değil bölüm numarası olur ve bölüm başlığıyla birleşir. |
| `code_image_link_pattern`  | `""` (kapalı)         | E-kitap kökenli PDF'lerde her kod listesinin üstündeki bağlantı satırı (`"Click here to view code image"`). Desen **satırın tamamıyla** eşleşir; eşleşen satır atılır, ODL'nin ona yapıştırdığı kod satırı kod listesine döner. Metin içinde bağlantıdan söz eden cümleye dokunulmaz. |
| `default_code_language`    | `"java"`              | Kod bloklarının vurgulama dili. |

## Ayarları ölçmek

```bash
python3 $SKILL/scripts/inspect_pdf.py book.pdf layout <PDF sayfası>
```

Her satır için `y` (üst orijin), `odlY` (sayfanın altından yükseklik; bölge ayarları bununla ölçülür), font ve
boyut basılır; sonunda font/boyut histogramı gelir. Kod içeren bir sayfa ile
bölüm açılış sayfasına bakmak yeterlidir:

- Koşu başlığının `odlY` değeri → `header_zone_bottom` bunun biraz altı olmalı.
  Sayfaların ilk satırı gövde metniyse (önceki sayfadan süren paragraf, kod,
  tablo satırı) kitapta koşu başlığı yoktur → `running_header: "none"`. Yoksa
  her sayfanın ilk öğesi koşu başlığı sanılıp atılır.
- Alt bilgi/sayfa numarası satırının `odlY` değeri → `footer_zone_top` bunun biraz üstü.
- Kod satırlarının font adı ve boyutu → `code_font_prefix`, `code_max_font_size`.
- Bölüm numarası / bölüm başlığı / kesit başlığı boyutları → ilgili `*_min_size`.

Ayarları değiştirdikten sonra `prepare_page.py <sayfa>` ile bir sayfayı yeniden
çıkarıp `_work/in/page-N.json` dosyasındaki blok tiplerini kontrol edin. Önceden
çevrilmiş sayfaları yeni ayarlara taşımak için: SKILL.md → D. Taşıma.

## Belirtiler ve çözümleri

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| "Sayfa N boş" ama boş değil | `pdf_offset` yanlış | `inspect_pdf.py book.pdf offset` ile yeniden tahmin |
| Kod listesi paragraf olarak geliyor | kod fontu tanınmıyor | `code_font_prefix` / `code_max_font_size` |
| Koşu başlığı gövdeye karışıyor | `header_zone_bottom` düşük | `layout` ile ölçüp yükselt |
| Sayfanın ilk paragrafı ya da madde başlığı çıkarımda yok | kitapta koşu başlığı yok ama `running_header` `"top"` | `running_header: "none"` |
| Kesit başlıkları paragraf oluyor | başlık boyut eşiği yüksek | `section_min_size` / `subsection_min_size` düşür |
| Dipnotlar paragraf oluyor | `footnote_max_size` düşük | dipnot font boyutunu ölçüp ayarla |
| Listing caption'ları başlık oluyor | desen uymuyor | `listing_caption_pattern` (örn. `"^Example \\d+\\.\\d+"`) |
| Her kod listesinin üstünde "Click here to view code image" başlığı ya da paragrafı var | e-kitabın kod görseli bağlantısı | `code_image_link_pattern: "Click here to view code image"` |
| Tablo düz paragraf/heading olarak geliyor | hücrelerde ne dolgu dikdörtgeni ne ODL'nin tanıdığı kenarlık çizgisi var | Çizgisiz tablolar sütun hizasından yakalanır: kalın başlık + hizalı satırlar (en az 4 satır; sayfanın son satırına uzanıyorsa başlık + 1 satır yeter) ve sayfayı açan başlıksız devam (`header_rows: 0`). Başlığı kalın olmayan, çok satırlı hücreli ya da sayfa ortasında başlıksız tablolar için otomatik yol yok: hücreleri `_work/in/page-N.json`'da elle `table` bloğuna çevir |
| Denklem kayboluyor ya da parçalanıyor | denklem fontu `Type3` değil | `inspect_pdf.py <pdf> layout N` ile denklem satırının fontunu bul, `math_font_prefix` ayarla |
| Formüldeki üst simge ayrı satır oluyor | üst simge kod fontunda değil (ör. italik serif) | Bilinen sınırlama: yalnız kod fontlu alt/üst simgeler bağlanır |
| Tablodaki uzun hücre sonrası metin ayrı paragraf oluyor | hücre içindeki boş satır satır sonu sanıldı (bantsız gövde) | Bilinen sınırlama; içerik kaybolmaz, `_work/in` JSON'unda hücreye elle taşı |
