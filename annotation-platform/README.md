# MemeScout — Annotation Platformu

Etiketleme platformu. Ne yaptığı ve kuralları için `docs/annotation.md`, içerik şeması için `docs/architecture.md`.

```
annotation-platform/
├── openapi.yaml   # API contract: frontend ile backend arasındaki tek doğru kaynak
├── frontend/      # Etiketleme arayüzü
└── backend/       # API sunucusu
```

## API contract

`openapi.yaml` iki taraf için de bağlayıcıdır. Değişiklik gerekirse önce bu dosya güncellenir (PR ile), sonra iki taraf ona uyar.

Görüntülemek için: https://editor.swagger.io adresine dosyayı yapıştırın, ya da backend FastAPI ile kurulduğunda `/docs` adresinden.

### Frontend için notlar

- Form ve anlık doğrulama `GET /schema/annotation` kurallarından üretilir; kuralları frontend'e sabit yazmayın.
- Etiket seçicilerdeki tanımlar `GET /label-lists` içindeki `tanim` alanından gelir.
- Otomatik kayıt: birkaç saniyede bir ve sayfa kapanırken `PATCH /annotations/{id}/draft`. Her yanıttaki `surum` bir sonraki istekte geri gönderilir; 409 `SURUM_CAKISMASI` gelirse kullanıcıya "başka sekmede açık" uyarısı gösterin.
- Aktif süre frontend'de ölçülür (sekme odakta ve kullanıcı etkileşimde) ve `aktif_sure_artis_sn` ile gönderilir.
- Doğrulama hataları `hata.alanlar[]` içinde alan yolu ile gelir (`ornek_durumlar[2]` gibi); ilgili inputun altında gösterin.
- `uyari` alanında `null` "cevaplanmadı", `[]` "uyarı yok onayı" demektir; arayüzde ayrı bir "Uyarı yok" onay kutusu olmalı.

### Backend için notlar

contract'ın başındaki "Sunucu tarafında uygulanması zorunlu kurallar" bölümü (kör etiketleme, reviewer kısıtı, sızıntı kuralı, kopya engeli, tanıdıklık, doğrulama) frontend'e güvenilmeden sunucuda uygulanmalı.

### Durum geçişleri

```
atandi → devam_ediyor → gonderildi ─┬─► onaylandi
              ▲                     │
              └── revizyon_gerekli ◄┘
atandi / devam_ediyor → atlandi
```

| Endpoint | Geçiş |
|---|---|
| `POST /annotations/{id}/start` | atandi → devam_ediyor |
| `POST /annotations/{id}/submit` | devam_ediyor, revizyon_gerekli → gonderildi |
| `POST /annotations/{id}/skip` | atandi, devam_ediyor → atlandi |
| `POST /annotations/{id}/request-revision` | gonderildi → revizyon_gerekli |
| `POST /reviews/{meme_id}/gold` | gonderildi → onaylandi |

Geçersiz geçişlerde 409 `GECERSIZ_DURUM_GECISI` döner.

Gönderilen annotation otomatik onaylanmaz. Meme'in annotation'larının hepsi gönderilince meme inceleme kuyruğuna (`GET /reviews`) düşer: çift etiketli meme'de reviewer anlaşmazlığı çözer, tek etiketli meme'de ikinci bakışı yapar ([ADR-0009](../docs/adr/0009-tek-etiketli-memelerde-ikinci-bakis.md)). Reviewer gold kaydını onaylar ya da revizyon ister.


## Gereksinimler ve Kurulum
Proje bağımlılıkları iki dosyada tutulur:
- **requirements.txt**: Uygulamanın çalışması için temel paketler
- **requirements-dev.txt**: Geliştirme ve test için ek paketler
### requirements.txt

fastapi uvicorn[standard] sqlmodel python-multipart pyjwt pwdlib[argon2] python-dotenv requests pytest httpx



### requirements-dev.txt

pytest pytest-asyncio httpx coverage



---
## Testler
Test komutları:
- Geliştirme bağımlılıkları yüklü ise testleri çalıştırmak için:
```bash
pytest tests/
Örtük asenkron testler için pytest-asyncio yüklü olmalıdır.
Not: Testler ve geliştirme ortamı için requirements-dev.txt dosyasındaki paketleri yüklemek önemlidir.



