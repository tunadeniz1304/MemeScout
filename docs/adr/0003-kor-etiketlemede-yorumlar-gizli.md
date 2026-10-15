# ADR-0003: Kör etiketleme yorumları da kapsar

- **Durum:** Önerildi
- **Tarih:** 2026-10-15
- **İlgili:** `annotation.md` §3.5, §4.3, `openapi.yaml` `GET /memes/{meme_id}/comments`

## Bağlam

`annotation.md` §4.3, çift etiketlenen meme'lerde iki kişinin göndermeden önce birbirinin etiketini göremeyeceğini söylüyor. Ancak §3.5'teki yorum ve işaret özelliği bu kuralı delebilir: biri meme'e "Bence bu politik sayılır" diye yorum bırakırsa, ikinci kişi göndermeden önce bunu görüp etkilenir ve uyum olduğundan yüksek çıkar.

## Karar

Çift etiketli bir meme'de, iki annotation da `gonderildi` durumuna geçene kadar bir annotator, diğer annotator'ın o meme'e bıraktığı yorumları göremez. Kural backend'de uygulanır; yorum listesi istek yapan kişiye göre filtrelenir. Admin ve reviewer tüm yorumları görür.

## Sonuçlar

- Uyum ölçümü gerçek bağımsız etiketlemeyi yansıtır.
- Etiketleme sırasında soru sormak isteyen annotator yanıtı geç alabilir. Genel sorular meme'e değil ekip kanalına sorulmalı ya da kılavuza ekleme önerisi olarak yazılmalı.
- `annotation.md` §4.3 buna göre güncellenmeli.
