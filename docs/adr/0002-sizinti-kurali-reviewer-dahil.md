# ADR-0002: Sızıntı kuralı gold kayda katkı veren herkesi kapsar

- **Durum:** Önerildi
- **Tarih:** 2026-10-15
- **İlgili:** `annotation.md` §3.7, `architecture.md` §3.2, `openapi.yaml` `POST /test-queries`

## Bağlam

`annotation.md`'ye göre bir kişi, `ornek_durumlar` alanını kendisinin yazdığı meme'leri doğru cevap olarak gösteren test sorgusu yazamaz. Kural yalnızca annotator'a bakıyor. Ancak çift etiketli meme'lerde gold kaydı reviewer oluşturur ve iki annotation'ı birleştirirken `ornek_durumlar`'ı düzenleyebilir ya da yeniden yazabilir. Bu durumda reviewer da o meme'in örnek durumlarını bilir ve yazdığı test sorgusu sonuçları olduğundan iyi gösterebilir.

## Karar

Test sorgusunu yazan kişi, doğru cevap olarak gösterdiği meme'lerin gold kaydına katkı veren hiç kimse olamaz: `kaynak_annotationlar`'ın sahipleri ve `reviewer`. Backend ihlalde `422` ve `hata.kod = SIZINTI` döner; `hata.detay.ihlal_eden_memeler` sorunlu meme'leri listeler.

## Sonuçlar

- Değerlendirme sonuçları daha güvenilir olur.
- Sorgu yazabilecek kişi sayısı biraz azalır; 4 kişilik ekipte her meme için en az bir kişi uygun kalır.
- `architecture.md` §6 test setinin annotator olmayan kişilerce işaretlenmesini öneriyor; mümkünse ekip dışından sorgu yazarı kullanmak bu kuraldan daha güçlü bir korumadır. Kural, ekip içinden yazılan sorgular için alt sınırdır.
- `annotation.md` §3.7 buna göre güncellenmeli.
