"""PDF kütüphanelerinin sınırı (Bl.8 · Boundaries).

Çıkarım akışları PyMuPDF'i ya da OpenDataLoader'ı tanımaz; yalnız `model`deki
düz veri nesnelerini ve `ports`taki arayüzleri görür. Yabancı koda yalnız
adaptörler dokunur (`pymupdf_adapter`, `odl_adapter`). Yeni bir düzen
okuyucusu (ör. LiteParse) aynı `LayoutReader` arayüzüne bir adaptör daha
yazılarak eklenir. Tüm koordinatlar sol-üst orijinli, birimleri PDF puntosudur.
"""
