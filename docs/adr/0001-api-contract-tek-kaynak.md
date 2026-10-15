# ADR-0001: API contract tek doğru kaynak

- **Durum:** Önerildi
- **Tarih:** 2026-10-15
- **İlgili:** `annotation-platform/openapi.yaml`, `annotation.md`

## Bağlam

Annotation platformunun frontend'i ve backend'i farklı kişiler tarafından paralel geliştiriliyor. İki tarafın hangi verileri hangi şekilde alıp vereceği önceden sabitlenmezse, sonunda parçalar birbirine uymaz.

## Karar

Frontend ile backend arasındaki tüm istek ve cevaplar `annotation-platform/openapi.yaml` (OpenAPI 3) dosyasında tanımlanır. İki taraf da bu dosyaya uyar. Değişiklik gerekirse önce bu dosya PR ile güncellenir, sonra kod.

Ek ilkeler:
- Alan adları `architecture.md` şemasıyla birebir aynıdır (snake_case, Türkçe karakter yok).
- Hatalar her zaman `{"hata": {"kod", "mesaj", "alanlar", "detay"}}` şeklinde döner.
- Form doğrulama kuralları `GET /schema/annotation` ile backend'den gelir; frontend kuralları kendi içine sabit yazmaz.
- Kör etiketleme, sızıntı ve reviewer kuralları frontend'e güvenilmeden backend'de uygulanır.

## Sonuçlar

- Frontend, backend hazır olmadan sahte verilerle geliştirilebilir.
- Doğrulama kuralları tek yerde tanımlı olduğu için iki yerde ayrı ayrı güncellenmez.
- Contract'ı değiştirmek ekip içi iletişim gerektirir; bu bilinçli bir yavaşlatmadır.
