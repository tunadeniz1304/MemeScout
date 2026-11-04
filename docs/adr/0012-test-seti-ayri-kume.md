# ADR-0012: Test seti etiketlemeden ayrı tutulur, sorgu yazan o meme'i etiketleyemez

- **Durum:** Kabul edildi
- **Tarih:** 2026-11-04
- **İlgili:** `annotation.md` §3.1, §3.7 ve §5, `openapi.yaml` `PATCH /memes/{meme_id}`, `POST /assignments`, `POST /assignments/auto`, `POST /test-queries`, [ADR-0002](0002-sizinti-kurali-reviewer-dahil.md)

## Bağlam

Ekip, değerlendirme seti için aynı fotoğrafları görüp her birine "bunu aratınca bu mem çıkmalı" dediği cümleler yazmak istiyor. ADR-0002'ye göre bir meme'in gold kaydına katkı veren kişi onun test sorgusunu yazamaz. 4 kişilik ekipte herkes etiketlemeye de katıldığı için her meme'e yalnızca 1-2 kişi sorgu yazabiliyor.

Kural ayrıca yalnızca sorgu yazılırken denetleniyor. Önce sorgu yazan kişi sonra o meme'e atanırsa örnek durumlara kendi test cümlelerini yazabilir ve sonuçlar olduğundan iyi görünür.

## Karar

- Admin bir meme'i test setine alabilir (`PATCH /memes/{meme_id}`, `test_seti: true`). Annotation'ı ya da gold kaydı olan meme alınamaz.
- Test setindeki meme elle ya da otomatik atanmaz; herkes ona test sorgusu yazar. Kartı AI taslağı olarak kalır.
- Sızıntı kuralı ters yönde de geçerlidir: bir meme'e test sorgusu yazmış kişi o meme'e annotator olarak atanamaz (elle, otomatik ya da yeniden atama) ve onun reviewer'ı olamaz. Platform ihlalde `SIZINTI` döner.
- Ekip dışında toplanmış sorgular (ör. bir belgedekiler) admin tarafından yazarları adına eklenir (`POST /test-queries`, `yazan_id`). Kurallar yazara uygulanır.

## Sonuçlar

- Herkes aynı test fotoğraflarına bağımsız cümle yazabilir ve ölçüm sızıntısız olur.
- Test setindeki meme'lerin kartı insan gözünden geçmez. Bu meme'lerde değerlendirme AI taslağı kartlarla yapılır.
- Bir meme'e herkes sorgu yazmışsa otomatik dağıtım onu kimseye atamaz.
- Canlı veritabanına `meme.test_seti` sütunu eklenir.
