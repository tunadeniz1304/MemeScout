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


## Backend

FastAPI + SQLModel. `openapi.yaml`'daki işlemlerin hepsini karşılar; çalışan sunucunun şeması `/docs` adresinde de görülebilir.

### Kurulum ve çalıştırma

```bash
cd annotation-platform/backend
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

| Ortam değişkeni | Açıklama |
|---|---|
| `DATABASE_URL` | Zorunlu. Yerelde `sqlite:///./memescout.db`, canlıda Supabase session pooler adresi |
| `SECRET_KEY` | Token imza anahtarı; canlıda en az 32 baytlık rastgele bir değer |
| `FRONTEND_URL` | CORS izni verilen frontend adresi |
| `REGISTRATION_OPEN` | `1` ise `POST /auth/register` açılır; varsayılan kapalı |
| `SQL_ECHO` | `1` ise SQL sorguları loglanır; varsayılan kapalı |

Değişkenler ortamdan ya da `annotation-platform/backend/.env` dosyasından okunur; `.env` repoya girmez.

Vercel önizleme sürümleri (`VERCEL_ENV=preview`) `DATABASE_URL` tanımlı olsa bile canlı veritabanına bağlanmaz; boş, bellek içi SQLite ile açılır. Böylece bir branch'in önizlemesi canlıda tablo oluşturamaz ve deneme verisi yazamaz.

Sunucu açılırken eksik tabloları oluşturur ve etiket listesinin ilk versiyonunu (v1) yazar. PostgreSQL'de RLS'i kapalı olan uygulama tablolarında RLS'i açar: Supabase'in herkese açık API'si politika olmadan bu tablolara erişemez, backend ise tablo sahibi rolüyle bağlandığı için etkilenmez. Bu adım var olan tabloya kolon eklemez; bir modelin kolonları değişirse canlı veritabanı için ayrıca migration gerekir.

Görseller `meme_image` tablosunda (PostgreSQL'de `bytea`) tutulur, çünkü Vercel'de disk kalıcı değildir.

### Admin hesabı

```bash
python -m app.create_admin
```

`DATABASE_URL`'nin gösterdiği veritabanına yazar.

### Meme içe aktarma

`app/import_memes.py`, zip arşivlerindeki (ör. WhatsApp sohbet dışa aktarımı) ya da klasördeki görselleri API üzerinden yükler. Kopyaları sha256 ile ayıklar ve görselleri Vercel'in 4.5 MB istek sınırının altında kalan parçalar halinde gönderir. Şifre çalışırken sorulur.

```bash
python -m app.import_memes --deneme KLASOR
python -m app.import_memes --api https://memescout-annotation-api.vercel.app/api/v1 --kullanici ADMIN_ADI KLASOR
```

`--deneme` yalnızca sayar. Betik tekrar çalıştırılabilir; daha önce yüklenen görseller kopya olarak reddedilir.

### AI taslakları

`app/import_ai_drafts.py`, bir LLM'in architecture.md §3 biçiminde hazırladığı kartları meme'lere taslak olarak bağlar ([ADR-0010](../docs/adr/0010-tek-etiketli-memelerde-llm-taslagi.md)). Kartlar YAML (kart listesi) ya da CSV (aynı sütunlar, liste alanları ` | ` ile ayrılmış) dosyasından okunur. Her kartın `gorsel` yolu kart dosyasının klasörüne, `--gorseller` verilirse o klasöre göre çözülür ve görselin sha256'sıyla meme bulunur. Eşleşen meme yoksa görsel yeni meme olarak yüklenir; `--yalniz-eslesenler` bu kartları atlar. Kurallara uymayan kartlar da alınır; ihlaller ve sabit listede olmayan etiketler raporda listelenir.

```bash
python -m app.import_ai_drafts --deneme memescout_gold.yaml
python -m app.import_ai_drafts --api https://memescout-annotation-api.vercel.app/api/v1 --kullanici ADMIN_ADI memescout_gold.yaml
```

Taslak gold olmaz. AI taslağı olan meme tek etiketli kalır: atanan annotator etiketlemeye başlarken formu taslakla dolu bulur, düzeltir ve gönderir; ardından reviewer ikinci bakışı yapar. Bu meme'ler kalibrasyona ve çift etiketlemeye alınmaz. Ham kart değiştirilmeden saklanır ve `GET /export/ai_drafts.jsonl` ile alınır.

PNG'ye dönüştürülmüş bir görsel, zip'teki orijinalle aynı sha256'yı taşımaz ve ayrı bir meme olarak yüklenir. Kartların görselleri zip'teki dosyaların birebir kopyası olmalıdır.

### Testler

```bash
cd annotation-platform/backend
pytest
```

Testler bellek içi SQLite kullanır, `DATABASE_URL` gerekmez.

### Kurallar nerede

| Kural | Dosya |
|---|---|
| Kör etiketleme, reviewer kısıtı, meme durumu | `app/kurallar.py` |
| Annotation şeması ve gönderim doğrulaması | `app/sema.py` |
| Versiyonlu etiket listeleri ve tohum etiketler | `app/etiketler.py` |
| Yeniden kontrol listesi | `app/yeniden_kontrol.py` |
| AI taslakları ve formun önceden doldurulması | `app/ai_taslak.py` |
| Uyum ölçüleri (Cohen's kappa, MASI ile Krippendorff's alpha) | `app/olcum.py` |
| Denetim kaydı | `app/denetim.py` |
