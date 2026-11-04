# ADR-0011: Kullanılmayacak meme'ler için oy ve havuz

- **Durum:** Kabul edildi
- **Tarih:** 2026-11-04
- **İlgili:** `annotation.md` §2, §3.10, §4.1, §5; `openapi.yaml` `/memes/{meme_id}/exclusion-vote`, `/exclusion-pool`; ADR-0003

## Bağlam

Toplanan meme'lerin bir kısmı veri setine girmemeli: görseli kalitesiz olanlar, aslında meme olmayanlar, anlaşılmayanlar, uygunsuz olanlar ya da başka bir meme'in kopyası olanlar. Bunları bulmak için bütün meme'leri ayrıca taramak yerine, etiketleme sırasında fark eden kişinin işaretlemesi ve işaretlenenlerin ekipçe konuşulması isteniyor.

## Karar

- Etiketleme ekranında her kişi bir meme için "Bu meme kullanılmasın" oyu verebilir. Oyda sabit bir listeden sebep (kalitesiz görsel, meme değil, anlaşılmaz, uygunsuz / rahatsız edici, kopya, diğer) ve isteğe bağlı, en fazla 300 karakterlik not bulunur. Kişi başına meme başına tek oy vardır; oy güncellenebilir ve geri çekilebilir.
- Oy etiketlemeyi durdurmaz; annotation'ın durumu değişmez. Oy veren isterse işi ayrıca atlar.
- Tek oy meme'i havuza düşürür. Havuz sayfası admin'e açıktır; oy sayısı, sebepler, notlar ve oy verenlerin takma adları görünür.
- Ekip havuzu toplantıda konuşur; admin her meme için "kalsın" ya da "çıkarılsın" der.
  - **Kalsın:** meme havuzdan çıkar. Sonradan verilen ya da güncellenen bir oy onu yeniden havuza açar.
  - **Çıkarılsın:** meme kuyruklardan, atamalardan, incelemeden, uyum hesabından, dışa aktarımdan ve test sorgularının doğru cevaplarından düşer. Çıkarılmış meme'e oy verilmez; verilmiş oylar kararın dayanağı olduğu için güncellenmez ve geri çekilmez. Admin "kalsın" diyerek kararı geri alabilir; annotation'lar ve gold kaydı silinmediği için meme olduğu gibi geri döner.
- Kör etiketleme (ADR-0003 gibi): etiketleme ekranında kişi yalnızca kendi oyunu görür. Başkalarının oyları ve notları yalnızca admin'in havuz sayfasında görünür.

## Sonuçlar

- Sorunlu meme'ler etiketleme sürerken toplanır; ayrı bir tarama gerekmez.
- Tek oyun yeterli olması havuzu kalabalıklaştırabilir. Çıkarma kararı admin'de olduğu için tek bir oy meme'i kendiliğinden çıkarmaz.
- Havuz sayfası, denetim kaydı ve dışa aktarım gibi bir admin aracıdır ve kör kurala göre süzülmez. Meme'i etiketleyen admin de havuzdaki notları görür; havuz zaten ekip toplantısında açıkça konuşulur.
- Çıkarılan meme'lerin annotation'ları ve gold kayıtları silinmez; yalnızca kullanımdan düşer.
