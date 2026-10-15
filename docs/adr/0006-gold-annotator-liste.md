# ADR-0006: `gold.jsonl`'de `annotator` alanı liste

- **Durum:** Önerildi
- **Tarih:** 2026-10-15
- **İlgili:** `architecture.md` §3, `annotation.md` §3.4, §5, `openapi.yaml` `GoldExportRow`

## Bağlam

`architecture.md` §3 şemasında `annotator` tek bir isim (`annotator: "<etiketleyen>"`). Ancak `annotation.md`'ye göre meme'lerin yaklaşık %20'si iki kişi tarafından etiketlenir ve gold kayıt iki annotation'dan türetilir. Tek isim bu durumu ifade edemez.

## Karar

`gold.jsonl` satırlarında:
- `annotator`: Gold kaydın türetildiği annotation'ların sahipleri, takma adla bir liste (ör. `["a1", "a3"]`). Tek etiketli meme'de tek elemanlı liste.
- `reviewer`: Onaylayan kişinin takma adı; tek etiketli meme'de `null`.
- `sema_versiyonu`, `etiket_listesi_versiyonu`: Kaydın hangi şema ve etiket listesiyle oluşturulduğu.

## Sonuçlar

- Arama sistemi ve analizler, bir kaydın kaç kişiden geçtiğini görebilir.
- `gold.jsonl`'i okuyan kod `annotator`'ı liste olarak işlemeli.
- `architecture.md` §3 şeması buna göre güncellenmeli.
