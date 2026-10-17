# ADR-0014: Tek etiketli meme'lerde hafif ikinci bakış

- **Durum:** Kabul edildi
- **Tarih:** 2026-10-18
- **İlgili:** `annotation.md` §2, §3.4, §4.1, §5, §6, ADR-0002, ADR-0006, ADR-0007

## Bağlam

Meme'lerin ~%20'si iki kişi tarafından bağımsız etiketleniyor. Kalan ~240 meme'in gold kaydı tek bir annotation'dan oluşuyor ve ona ikinci kimse bakmıyor. Kültürel bilgi kişiden kişiye değiştiği için tek kişinin gözünden kaçan bir hata (eksik bağlam, yanlış uyarı etiketi gibi) doğrudan gold'a girebilir.

## Karar

- Tek etiketli her meme, gold olmadan önce bir reviewer'ın hafif kontrolünden geçer. Reviewer kaydı onaylar ya da `revizyon_notu` ile geri gönderir (`gonderildi → revizyon_gerekli`).
- Reviewer, meme'i etiketleyen kişi olamaz; görev dönüşümlü dağıtılır.
- Bu kontrol uyum ölçümüne katılmaz. Uyum yalnızca bağımsız çift etiketlemeden hesaplanır.
- Çift etiketli meme'lerin ilk yarısı (~30) bittiğinde ara uyum ölçümü yapılır. Kappa'sı 0,4'ün altında kalan alanlarda kılavuz netleştirilir ve reviewer'lar bu alanları tek etiketli meme'lerde özellikle kontrol eder. Kılavuz güncellemesinden sonra da düşük kalırsa kalan meme'lerde çift etiketleme oranı artırılır (ör. %20'den %40'a).
- ADR-0006'daki "tek etiketli meme'de `reviewer` `null`" kuralı değişir: her gold kaydında `reviewer` dolu olur.

## Sonuçlar

- Her meme en az iki kişiden geçer.
- Ek iş kabaca meme başına 1–2 dakika: toplam 4–8 saat, kişi başı 1–2 saat.
- Sızıntı kuralına (ADR-0002) göre her meme'in reviewer'ı da o meme için test sorgusu yazamaz. 4 kişilik ekipte tek etiketli meme'ler için 2, çift etiketli meme'ler için 1 kişi sorgu yazabilir.
- Platformda, reviewer'a düşen kayıtlar için bir ikinci bakış kuyruğu gerekir.
