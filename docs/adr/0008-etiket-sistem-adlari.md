# ADR-0008: Etiketlerin sistem adları

- **Durum:** Kabul edildi
- **Tarih:** 2026-10-15
- **İlgili:** `architecture.md` §3, §3.1, `annotation.md` §3.6

## Bağlam

Backend her etiketi değişmeyen bir sistem adıyla (`etiket`) ve ekranda gösterilen bir adla (`gorunen_ad`) saklar. `architecture.md`'de etiket listesi ile örnek kayıt uyuşmuyor:
- Liste: "tepki gösterme" — örnek kayıt: `niyet: [tepki]`
- Liste: "şüphe", "şaşkınlık" — örnek kayıt: `duygu: [suphe, saskinlik]`

Sistem adları sabitlenmeden etiketleme başlarsa, sonradan değiştirmek tüm kayıtların dönüştürülmesini gerektirir.

## Önerilen karar

- Sistem adı: küçük harf, Türkçe karaktersiz, boşluk yerine alt çizgi (`^[a-z0-9_]+$`). Türkçe karakter dönüşümü: ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u.
- Görünen ad: listedeki Türkçe ad.
- Eğik çizgili etiketlerde (ör. "sevinç/zafer") ad etiketleme kılavuzunda tek bir kavrama indirilir ya da iki etikete bölünür.

Örnek: `bikkinlik` → "Bıkkınlık", `tepki_gosterme` → "Tepki gösterme", `beklenti_gerceklik_zitligi` → "Beklenti–gerçeklik zıtlığı".

## Yapılması gerekenler

- Etiketleme kılavuzu yazılırken her etiketin sistem adı, görünen adı ve tanımı tek tabloda kesinleşmeli.
- `architecture.md` §3 örneği kesinleşen adlarla güncellenmeli.
- Bu karar, backend'de etiketleme ekranı endpoint'leri yazılmadan önce verilmeli.

## Karar (2026-10-18)

Önerilen karar kabul edildi. Eğik çizgili etiketler tek kavram olarak birleşik sistem adıyla tutulur: `sevinc_zafer`, `ustunluk_kibir`, `sikayet_isyan`, `kaba_argo`. `architecture.md` §3.1 ve §3'teki örnek kayıt bu adlarla güncellendi.
