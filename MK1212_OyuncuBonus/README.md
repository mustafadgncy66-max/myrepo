# MK1212 Oyuncu Bonusu

Medieval Kingdoms 1212 AD için küçük bir alt mod. Bonusların çoğu **yalnızca insan oyuncuya**
verilir, AI fraksiyonları etkilenmez. Tüm zorluk seviyelerinde çalışır.

| Bonus | Değer |
|---|---|
| Tüm binalardan servet | +%15 |
| Araştırma hızı | +%100 (teknoloji süresi yarıya iner) |
| Kamu düzeni | eyalet başına +5 |
| Büyüme | eyalet başına +8 |
| Bina bakım maliyeti | tüm binalarda yarıya (kartlarda görünür; ör. Ghulam Barracks 100 → 50) |
| İkmal | +10 |
| Bina yapım ve yükseltme maliyeti | −%50 (yalnızca oyuncu; ör. Small Mosque 6000 → 3000) |
| Eyalet başkenti mescitleri | sanitasyon I/II/III/IV: +1/+2/+3/+4 (önce 0/+1/+1/+1) |
| Birim bakımı | 120 ve altı değişmez; 460 → ~180; aradakiler doğrusal |

Bakım örnekleri:

| Şu anki bakım | Yeni bakım |
|---|---|
| 120 | 120 |
| 200 | ~134 |
| 300 | ~153 |
| 400 | ~168 |
| 460 | ~179 |
| 600 | ~204 |
| 1000 | ~280 |

Selçuklu general muhafızlarının bakımı sabit **250**'dir (askere alma ekranında ve orduda).
Bu birimler yukarıdaki ölçeğin dışındadır.

## Nasıl çalışır

- Bonuslar oyunun zorluk tablosuna (`campaign_difficulty_handicap_effects`) `human = true`
  olarak eklenir. Oyunun kendisi de insan oyuncuya bonusu bu tabloyla verir.
- Bakım indirimi, birimleri %1'lik indirim bandlarına ayıran 79 birim seti üzerinden uygulanır.
  Bandlar, kurulu modlarınızla (MK1212 + Earl'ün realistic modları) oyunda geçerli olan
  bakım değerlerinden hesaplanmıştır.
- Bonusların anahtarları yenidir (`pb_` önekli); MK1212'nin satırlarına dokunmazlar.
- Kartlarda görünmesi gereken değerler ise MK1212'nin satırlarını ezer. Ezmenin çalışması için mod,
  yükleme sırasında **MK1212'nin üstünde** olmalıdır:
  - **Bina bakımı:** 450 bina seviyesinin bakımı yarıya iner. Bina tanımı ortak olduğu için AI'ya
    zorluk seviyesine göre telafi eklenir (Normal'de +%45); AI'nın ödediği bakım değişmez.
  - **Selçuklu general muhafızları:** 6 birimin bakımı 250. Selçuklu fraksiyon özelliği profesyonel
    birimlere −%20 verdiği için oyuncuya bu birimlerde +%20 eklenir; orduda da 250 görünür.
  - **Mescitler:** Sünni, Şii ve İbadi başkent mescitlerinin sanitasyonu. AI'nın mescitlerini de etkiler.

## Kurulum

1. `mk1212_oyuncu_bonus.pack` dosyasını indirin.
2. Attila'nın `data` klasörüne kopyalayın:
   `C:\Program Files (x86)\Steam\steamapps\common\Total War Attila\data\`
3. Oyunun başlatıcısında **Mod Manager**'dan `mk1212_oyuncu_bonus` modunu işaretleyin ve
   listede **en üste** (MK1212 dosyalarının üstüne) taşıyın.
4. **"Seljuks Cheat Mod"u etkinleştirmeyin.** İkisi birlikte çalışır ama değerler üst üste biner.

## Doğrulama

Kampanyada:
- Eyalet ayrıntılarında kamu düzeninin **Buildings** satırı +5 artmış olmalı
  (bonus oyunun bina kaynaklı kamu düzeni kategorisini kullanır).
- Büyüme ipucunda **Faction** satırı +8 artmış olmalı. Bu satıra siyasi güç seviyesinin
  büyüme etkisi de eklenir, bu yüzden tam +8 görünmeyebilir.
- Askere alma panelinde, bakımı ~460 olan bir birim ~180 göstermeli
  (ör. Askeri Lancers: 409 → 172).
- Small Mosque (II) bilgi panelinde **Sanitation: +2** ve **Maintenance cost: −200** görünmeli;
  inşa maliyeti 6000 yerine **3000** olmalı.
- Kuvvet Topla ekranında ve orduda Selçuklu general muhafızı **250** göstermeli.

Zorluk bonusları mevcut bir kayıtta devreye girmeyebilir. Görünmüyorsa yeni bir kampanya başlatın.

## Kaldırma

Mod Manager'dan işareti kaldırın. Pack dosyasını `data` klasöründen silebilirsiniz.

## Yeniden üretme

Değerler `build.py` dosyasının başında. Değiştirip şu komutla yeniden üretilir:

```
python3 build.py --data <TSV klasörü> --rpfm <rpfm_cli> --schema <schema_att.ron> --out .
```

`--data`, AttilaOptimizer'ın 6. seçeneğiyle dışa aktarılan tabloların TSV'ye çevrilmiş halidir.
`tsv/` klasörü, pack'in içindeki tabloların okunabilir kopyasıdır.
