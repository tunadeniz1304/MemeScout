# ADR-0004: `uyari` alanında `null` ve `[]` ayrımı

- **Durum:** Kabul edildi
- **Tarih:** 2026-10-15
- **İlgili:** `annotation.md` §3.2, `openapi.yaml` `AnnotationContent.uyari`

## Bağlam

`annotation.md` §3.2'ye göre `uyari` alanı boş olabilir ve boş bırakmak bilinçli bir seçimdir ("uyarı yok" onayı). Ancak boş bir liste, annotator'ın alanı bilinçli olarak mı boş bıraktığını yoksa hiç bakmadığını mı ayırt etmez.

## Karar

- `uyari: null` → Henüz cevaplanmadı. Bu durumdaki annotation gönderilemez.
- `uyari: []` → Annotator "uyarı yok" diye onayladı.
- `uyari: ["politik", ...]` → Seçilen uyarılar.

Arayüzde uyarı etiketlerinin yanında ayrı bir "Uyarı yok" onay kutusu bulunur.

## Sonuçlar

- Uyarı alanının atlanmış olması gönderimde yakalanır.
- Dışa aktarılan gold kayıtlarda `uyari` her zaman bir listedir (`null` olmaz).
