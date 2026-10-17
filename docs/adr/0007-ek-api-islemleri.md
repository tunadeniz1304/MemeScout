# ADR-0007: Dokümanda olmayan ek API işlemleri

- **Durum:** Kabul edildi
- **Tarih:** 2026-10-15
- **İlgili:** `annotation.md` §4, §5, `openapi.yaml`

## Bağlam

`annotation.md` süreci tanımlıyor ama bazı adımların nasıl tetikleneceğini açıkça söylemiyor: revizyonu kimin istediği, 300 meme'in 4 kişiye ve 6 ikiliye nasıl dağıtılacağı, atlanan meme'in kime gideceği.

## Karar

Contract'a şu işlemler eklendi:
- `POST /annotations/{id}/request-revision`: Reviewer veya admin, gönderilmiş bir annotation için not ile revizyon ister (`gonderildi → revizyon_gerekli`).
- `POST /assignments/auto`: Admin, atanmamış meme'leri annotator'lara eşit böler ve belirtilen oranı (varsayılan %20) ikinci bir kişiye de atar; ikinci atamalar tüm ikililere dengeli dağıtılır. `dry_run: true` ile önce plan görülür.
- `POST /annotations/{id}/reassign`: Admin, atlanan ya da tanıdıklığı düşük annotation'ı başka birine atar.
- `POST /annotations/{id}/validate`: Annotator göndermeden önce eksiklerini görür.

## Sonuçlar

- `annotation.md` §4.1'deki "kişi başı ~75 meme, ikili başına ~10 çift etiket" dağılımı elle hesaplanmak zorunda kalmaz.
- Backend'de yazılacak iş biraz artar; otomatik dağıtım ve revizyon istemi zorunlu ilk sürüme girmeyebilir.
