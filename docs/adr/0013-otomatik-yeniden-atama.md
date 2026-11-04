# ADR-0013: Atlanan meme otomatik yeniden atanır, tanıdıklık 3'te ikinci kişi eklenir

- **Durum:** Kabul edildi
- **Tarih:** 2026-11-04
- **İlgili:** `annotation.md` §3.3, §3.10 ve §4.2, `openapi.yaml` `POST /annotations/{annotation_id}/skip` ve `POST /annotations/{annotation_id}/submit`, [ADR-0007](0007-ek-api-islemleri.md), [ADR-0009](0009-tek-etiketli-memelerde-ikinci-bakis.md), [ADR-0010](0010-tek-etiketli-memelerde-llm-taslagi.md), [ADR-0011](0011-kullanilmasin-oyu-ve-havuz.md), [ADR-0012](0012-test-seti-ayri-kume.md)

## Bağlam

Annotator tanımadığı ya da tanıdıklığına 1-2 verdiği meme'i atlar. Atlanan iş, admin onu elle başka birine atayana kadar bekliyordu. Platformda bunun için bir ekran yoktu; admin her atlamayı ayrıca takip etmek zorundaydı.

Tanıdıklık 3 ("anlamını biliyorum") orta güvendir. Bu puanla gönderilen etiket, 4 ya da 5 verilmiş gibi tek başına geçiyordu.

## Karar

- Ana turda atlanan meme sıradaki uygun kişiye otomatik atanır. Uygun kişi, ana turda işi olan, bu meme'e daha önce atanmamış (atlamış da sayılır) ve ona test sorgusu yazmamış (ADR-0012) kişilerden açık işi en az olandır; eşitlikte toplam işi az olan seçilir. Ana turda hiç işi olmayan hesaplar (ör. deneme hesabı) aday olmaz.
- Uygun kimse kalmazsa ve meme'in başka annotator'ı da yoksa meme havuza düşer: son atlayan kişi adına "Diğer" sebepli, "kimse kalmadı" notlu bir kullanılmasın oyu verilir (ADR-0011). Kişinin bu meme'de kararla sonuçlanmış eski bir oyu varsa o oy bu sebeple yeniden açılır.
- Çift etiketli meme'de bir annotator kaldıysa ve onun yanına atanacak kimse yoksa meme onunla tek etiketli sürer. Tek etiketli meme gibi reviewer'ın ikinci bakışına gider (ADR-0009).
- Tanıdıklık 3 ile ilk kez gönderilen tek etiketli annotation'ın meme'ine aynı kuralla ikinci bir kişi atanır ve meme çift etiketli olur. Reviewer iki etiketi birleştirir. 4 ve 5 tek başına yeterlidir.
- Revizyondan dönen annotation'a ikinci kişi eklenmez, çünkü reviewer onu zaten görmüştür. Bir meme'i en çok iki kişi etiketler; ikinci kişi de 3 verirse üçüncü kişi eklenmez.
- AI taslaklı meme'e ikinci kişi eklenmez. ADR-0010'daki gibi tek etiketli kalır, reviewer'ın ikinci bakışı yeterlidir.
- Kalibrasyon turundaki atlamalar ile test setindeki, gold kaydı olan ve havuz kararıyla çıkarılan meme'ler otomatik atamaya girmez. Admin'in elle yeniden atama işlemi (ADR-0007) kalibrasyon ve elle müdahale için kalır.
- Otomatik oluşan annotation'ın denetim kaydında `otomatik: true` bulunur. Kaydı yapan kişi, atlayan ya da gönderen kişidir.

## Sonuçlar

- Atlanan iş beklemeden başka birine gider; admin'in atlamaları takip etmesi gerekmez.
- Orta güvenle verilen etiketler ikinci bir bakışla birleştirilir. Çift etiketli meme sayısı artar, uyum ölçümüne daha çok örnek girer.
- Ekibin iş yükü artar; en az açık işi olan seçildiği için yük dengeli kalır.
- Havuzdaki "kimse kalmadı" oyunu kişi kendisi vermemiştir; notundan ayırt edilir.
- Tek etiketliye dönen çift etiketli meme uyum ölçümünden çıkar.
