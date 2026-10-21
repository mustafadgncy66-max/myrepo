# Total War: ATTILA Optimizer

Attila'nın 32-bit motorundan en iyi performansı almak için küçük bir Windows aracı.

## Neyi çözer, neyi çözemez

**Çözemez:** Attila.exe 32-bit bir programdır ve 64-bit sürümü hiç çıkmadı.
Large Address Aware bayrağıyla bile en fazla 4 GB adres alanı kullanabilir.
Bu sınır hiçbir araçla kaldırılamaz. Kaynak kodu olmadan oyunu 64-bit'e çevirmek mümkün değildir.

**Bu sınırın içinde yapabildikleri:**

| Sorun | Araç ne yapıyor |
|---|---|
| Oyun VRAM'i 3072 MB görüyor | `gfx_video_memory -1` ile tespit sınırını 4095 MB'a çeker |
| VRAM dolunca dokular bozuluyor | `gfx_unlimited_video_memory true` |
| Savaşlarda takılma | `number_of_threads` değerini işlemcinize göre ayarlar (en fazla 8) |
| Savaşlarda düşük GPU kullanımı, işlemci darboğazı | DirectX 11'i Vulkan'a çeviren **DXVK**'nın 32-bit sürümünü kurar |

## Kurulum ve kullanım

1. `AttilaOptimizer` klasörünü bilgisayarınıza indirin.
2. Oyunu kapatın.
3. `AttilaOptimizer.bat` dosyasına çift tıklayın.
4. Menüden sırayla seçin:
   - **1:** Durum raporu (oyunun 32-bit ve LAA durumu, mevcut ayarlar)
   - **2:** Ayar düzeltmesi (önce otomatik yedek alır)
   - **3:** DXVK kur (GitHub'dan son sürümü indirir)

Mod yapımı için:
- **6:** Oyunun ve Workshop modlarının `.pack` dosyalarından yalnızca gereken veritabanı
  tablolarını (birimler, efektler, zorluk bonusları...) çıkarır ve masaüstüne
  `AttilaModData.zip` olarak koyar. 1 GB'lık pack'ler de birkaç saniyede taranır, çünkü
  yalnızca dosya listesi okunur ve sadece istenen tablolar kopyalanır.
  Karakter portre tabloları, MK1212'nin başlangıç kaydı (`startpos.esf`) ve Attila.exe'deki
  karakterle ilgili betik fonksiyonu adları (`exe_names.txt`) da eklenir. Başlangıç kaydı
  `AttilaStartpos.zip`, Selçuklu portreleri ve portre listesi `AttilaPortraits.zip` olarak ayrı yazılır.

- **7:** Yeni indirdiğiniz tek bir Workshop modunu (pack dosyası ve içindeki tüm dosyalar) `AttilaSubmod.zip`
  olarak masaüstüne koyar. Son indirilen modlar listenin başındadır.

Geri almak için:
- **4:** DXVK'yı kaldırır, oyun DirectX 11'e döner.
- **5:** Ayar dosyasını son yedekten geri yükler.

## Test etme

1. Önce yalnızca **2** numaralı adımı yapın ve büyük bir savaşta FPS'e bakın.
2. Ardından **3** ile DXVK'yı kurun ve aynı savaşı tekrar oynayın.
3. Oyun klasöründe `Attila_d3d11.log` dosyası oluştuysa DXVK çalışıyor demektir.
4. Çökme veya görüntü hatası olursa **4** ile DXVK'yı kaldırın.

## Bilinen riskler

- `gfx_video_memory -1` topluluk tarafından öneriliyor. Bir Creative Assembly geliştiricisi bunun yalnızca
  gösterilen değeri değiştirdiğini söylemiş. Zararı yok, ama mucize beklemeyin.
- DXVK, Attila'da bazı sistemlerde çok iyi çalışırken bazılarında çöküyor. Bu yüzden kaldırma seçeneği var.
- İlk savaşlarda DXVK shader derlediği için kısa takılmalar normaldir.
- Oyun çıkışta `preferences.script.txt` dosyasını yeniden yazar. Araç yalnızca oyun kapalıyken çalışır.

## Dosyalar

- Ayar dosyası: `%APPDATA%\The Creative Assembly\Attila\scripts\preferences.script.txt`
- Yedekler: aynı klasörde `preferences.script.txt.backup_TARİH`
- DXVK: oyun klasöründe `d3d11.dll`, `dxgi.dll`, `dxvk.conf`
