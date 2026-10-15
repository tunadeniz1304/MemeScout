# ADR-0005: Annotation'a `kalibrasyon`, `surum` ve `revizyon_notu` alanları

- **Durum:** Önerildi
- **Tarih:** 2026-10-15
- **İlgili:** `annotation.md` §3.3, §4.1, §4.2, `openapi.yaml` `Annotation`

## Bağlam

`annotation.md`'deki süreç, şemada karşılığı olmayan üç ihtiyaç doğuruyor:
1. §4.1'e göre kalibrasyon turunun etiketleri uyum ölçümüne katılmamalı, ama bu annotation'ları ayırt edecek bir alan yok.
2. Taslak otomatik kaydedilirken aynı annotation iki sekmede açıksa, bir sekme diğerinin işini üzerine yazarak silebilir.
3. §4.2'de `revizyon_gerekli` durumu var, ama annotator'a neyin düzeltilmesi gerektiğini iletecek bir yer yok.

## Karar

Annotation kaydına üç alan eklenir:
- `kalibrasyon` (bool): Kalibrasyon turuna ait annotation. Uyum hesaplamalarına katılmaz.
- `surum` (int): Her taslak kaydında artar. İstemci son bildiği sürümü gönderir; eşleşmezse backend `409 SURUM_CAKISMASI` döner (iyimser kilitleme).
- `revizyon_notu` (metin): Reviewer veya admin revizyon isterken yazdığı not; annotator'ın kuyruğunda görünür.

## Sonuçlar

- Kalibrasyon verisi ayrı tutulur, uyum skorları kirlenmez.
- Kullanıcı aynı annotation'ı iki sekmede açarsa uyarı alır, veri kaybolmaz.
- `annotation.md` §3.3 tablosuna bu alanlar eklenmeli.
