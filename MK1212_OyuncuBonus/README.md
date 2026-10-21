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

## Selçuklu Ticaret Ağı (İpek Yolu)

Yalnızca Selçuklu oynarken çalışan bir betik (`campaigns/main_attila/factions/mk_fact_seljuks.lua`),
her tur başında sahip olunan bölgelere göre fraksiyon paketleri uygular. MK1212 bu dosyayı oyuncunun
fraksiyonuna göre kendisi yükler; MK1212'nin kendi İpek Yolu kodu kapalıdır, yalnızca baharat
limanları çalışır.

| Paket | Koşul | Etki |
|---|---|---|
| Silk Road: Caravan Cities (n/8) | Konya, Kayseri, Ankara, Malatya, Sis, Diyarbakır, Dvin, Tebriz'den n tanesi | karadan ticaret serveti +%5×n, ticaret anlaşması geliri +%3×n |
| Silk Road: Sea Gates (n/4) | Sinop, Antalya, İzmir, Kefe'den n tanesi | deniz ticareti serveti +%10×n, ticaret anlaşması geliri +%5×n |
| Seljuk Caravanserais | en az 4 kervan şehri | ticaret anlaşması geliri +%10, eyalet başına kamu düzeni +1 |
| Between Two Seas | Sinop ve Antalya birlikte | ticaret anlaşması geliri +%15, karadan ticaret serveti +%10 |

Başlangıçta 4/8 kervan şehri, 1/4 liman ve kervansaray paketi etkindir; Sinop alınınca
"Between Two Seas" eklenir.

## Selçuklu hikâye zinciri

Aynı betik, belirli turlarda tarihî olaylar tetikler (MK1212'de yılda 2 tur; 1. tur 1212 ilkbaharı).
Görseller `ui/eventpics` altındadır (380×214 PNG).

| Tur | Yıl | Olay | Tür | Sonuç |
|---|---|---|---|---|
| 2 | 1212 | The Conquest of Sinope | görev (12 tur) | Sinop'u al: 6000 altın + 10 tur kamu düzeni +3, servet +%10 |
| 12 | 1217 | A Storm in the East | haber | Harezm'den mülteciler: 10 tur büyüme +3, araştırma +%10 |
| 12 | 1217 | The Sultan's Divan | karar | Surlar (−4000; 30 tur kamu düzeni +3, ikmal +15) / Türkmenler (−2000; 20 tur askere alma −%20, ikmal +10) |
| 15 | 1219 | The Sultan Falls Ill | haber | 4 tur kamu düzeni −1. Keykubad'ı aile ağacından veliaht yapmanız için hatırlatma |
| 17 | 1220 | The Death of Kaykaus | tahta geçiş + karar | Keykâvus ölür ve aile ağacında ölü görünür, tahta veliaht geçer. Ardından karar: emirlere ikta (20 tur sadakat +2, kamu düzeni +2, servet −%5) / Gulam muhafızı (−3000; 20 tur bütünlük +2, yeni askerlere +1 deneyim) |
| 19 | 1221 | The Crimean Expedition | görev (16 tur) | Kırım limanını (oyunda Caffa) al: 5000 altın + 20 tur deniz ticareti +%20, ticaret anlaşması +%10 |
| 20 | 1221 | Kalon Oros Becomes Alaiye | haber | Kalıcı: deniz ticareti +%10, ticaret anlaşması +%5 |
| 25 | 1224 | The Sultan's Hans | karar | Hanları yaptır (−5000; kalıcı ticaret anlaşması +%20, karadan ticaret +%15) / tüccarlara bırak (+3000) |
| 31 | 1227 | The Envoy of the Khwarazmshah | karar | İttifak (−2000; 10 tur göçebelere karşı moral +4, bütünlük +1) / Doğu'yu koru (10 tur ikmal +10, deneyim +1) |
| 33 | 1228 | The Sultan of Scholars | haber | Bahaeddin Veled ve ailesi Konya'da: 30 tur araştırma +%15, kamu düzeni +2 |
| 35 | 1229 | The Sultan Han | haber | Kalıcı: ticaret anlaşması +%10, karadan ticaret +%10 |
| 38 | 1230 | Victory at Yassi Chemen | haber | 5000 altın + 15 tur bütünlük +2, deneyim +1 |
| 57 | 1240 | The Babai Revolt | karar | Bastır: Amasya (yoksa Ankara, Kayseri, Konya) yakınında 14 birimlik Türkmen isyancı ordusu çıkar ve savaş ilan eder; 10 tur kamu düzeni −3, bütünlük +1 / Affet: −6000; 15 tur kamu düzeni +2, servet −%10, sadakat −2 |
| 63 | 1243 | The Road to Kose Dag | karar | Sahada karşıla (10 tur göçebelere karşı moral +6, bütünlük +3, ikmal +20) / Kalelerde bekle (20 tur kamu düzeni +3, ikmal +15) / Haraç (−15000; 30 tur kamu düzeni +4, servet −%10) |

Haraç seçeneği yalnızca etki paketi verir; Moğollarla barışı zorlamaz.

Keykubad MK1212'de aile ağacında zaten vardır. Tahta onun geçmesi için 17. turdan önce aile ağacında
Keykubad'ı seçip veliaht yapın; yapmazsanız tahta oyunun veliahtı (başlangıçta İbrahim) geçer. Keykubad
ölmüşse 17. turda yeni bir Keykubad veliaht olarak eklenir.

MK1212 her Selçuklu sultanına aynı portreyi (Alaeddin Keykubad'ın bilinen portresi) verir. Aile ağacı portresi
MK1212'nin `portrait_settings.xml` dosyasından gelir; oyun bu dosyanın moddaki bir kopyasını kullanmaz, yalnızca
resim dosyaları ezilebilir. Keykâvus da tahta geçen Keykubad da aynı resim dosyasını gösterir. Bu yüzden:

- Keykâvus'un çizilmiş portresi (sarıklı, kırmızı kaftanlı) ayrı bir pack'tedir: `mk1212_keykavus_portresi.pack`.
  Bu pack MK1212'nin **üstünde** olmalı ve **17. turda Keykâvus ölünce kapatılmalıdır**; yoksa Keykubad da
  sultan olunca Keykâvus'un portresini taşır. Pack yalnızca bir resim içerir, kampanya ortasında kapatılabilir.
- Keykubad tahta geçince MK1212'nin Alaeddin portresini ve sultan görünümünü alır.
- Keykâvus sultanken 3B modeli sultanınki değil, kendi general görünümüdür (atlı harita modeli ve animasyonlarıyla).

Keykâvus'un portresi `art/kaikaus.jpg` dosyasından `tools/portrait.py` ile `keykavus_portresi/` altına üretilir
(yeşil arka plan şeffaf yapılır, 180×240 ve 64×152).

### Hızlı test

`mk1212_hizli_test.pack` yüklüyken hikâye olayları 14 tur erken gelir: hastalık haberi 1. turda, Keykâvus'un
ölümü 3. turda. Yeni bir kampanyada denemek içindir; normal oyunda kapatın. Erteleme miktarı
`hizli_test/campaigns/main_attila/factions/pb_seljuk_test.lua` dosyasındadır.

Keykubad'a betikle oyunun kendi özellikleri en yüksek seviyeleriyle verilir (Attila'da moddan eklenen yeni
özellikler oyun tarafından tanınmadı):

- **Oyunun başından:** Master Strategist, Superior Attacker, Superior Defender, Into the Breach!,
  Take No Prisoners!, Utterly Fearless, Vital, Military Secretary.
- **Tahta geçince:** Upright, mimar (3. seviye), karizmatik.

Özellikler tur başında eklenir; oyun onları bir sonraki tur geçişinde gösterir. MK1212'nin "Kaiqobad" adının
metni "Alaeddin Keykubad" olarak değiştirilir (Attila'da karakter adı betikle değiştirilemez).

Betik, oyun klasörüne `pb_seljuk_log.txt` adlı bir kayıt dosyası yazar.


Görevin hedef bölgesi o turda zaten sizdeyse görev verilmez. Henüz görseli olmayan olaylar mevcut
görsellerden birini kullanır (`build.py`'deki `fallback`); görsel `ui/eventpics` altına eklenince
pack yeniden üretilir. Olaylar yalnızca o turun başında tetiklenir; mevcut
kampanya bu turları geçmişse görülmezler.

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
- Fraksiyon etkilerinde "Silk Road: Caravan Cities (4/8)", "Silk Road: Sea Gates (1/4)" ve
  "Seljuk Caravanserais" görünmeli (ilk tur sonunda kesinleşir).

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
