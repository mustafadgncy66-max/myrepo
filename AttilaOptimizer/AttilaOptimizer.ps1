<#
    Total War: ATTILA Optimizer
    ---------------------------
    Attila 32-bit bir oyundur ve Large Address Aware (LAA) bayrağıyla en fazla 4 GB
    adres alanı kullanır. Oyun içi VRAM tespiti 3072 MB ile sınırlıdır. Bu araç,
    bu sınırların içinde ulaşılabilecek en iyi durumu kurar:

      1. Durum raporu   : Attila.exe'nin 32/64-bit ve LAA durumunu, ayar dosyasını,
                          DXVK'nın kurulu olup olmadığını gösterir.
      2. Ayar düzeltmesi: preferences.script.txt içinde VRAM sınırını, sınırsız video
                          belleğini ve iş parçacığı sayısını ayarlar (önce yedek alır).
      3. DXVK kurulumu  : DirectX 11'i Vulkan'a çeviren DXVK'nın 32-bit sürümünü kurar.
                          Savaşlardaki işlemci (draw call) darboğazını azaltmayı hedefler.
      4. DXVK kaldırma  : DXVK dosyalarını siler, varsa eski dosyaları geri yükler.
      5. Ayar geri alma : preferences.script.txt dosyasını en son yedekten geri yükler.
      6. Mod verisi     : Oyunun ve Workshop modlarının .pack dosyalarından yalnızca mod
                          yapımı için gereken veritabanı tablolarını çıkarıp küçük bir
                          ZIP dosyası olarak masaüstüne koyar.

    Kullanım: AttilaOptimizer.bat dosyasına çift tıklayın.
    Ya da: powershell -ExecutionPolicy Bypass -File AttilaOptimizer.ps1 [-Action Status|Tweak|InstallDxvk|RemoveDxvk|RestorePrefs|ExportModData]
#>

[CmdletBinding()]
param(
    [ValidateSet('Menu', 'Status', 'Tweak', 'InstallDxvk', 'RemoveDxvk', 'RestorePrefs', 'ExportModData')]
    [string]$Action = 'Menu',

    # Elle oyun klasörü vermek için (otomatik bulunamazsa).
    [string]$GameDir,

    # Mod verisinin yazılacağı klasör (varsayılan: masaüstü).
    [string]$OutDir
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$PrefsDir   = Join-Path $env:APPDATA 'The Creative Assembly\Attila\scripts'
$PrefsFile  = Join-Path $PrefsDir 'preferences.script.txt'
$DxvkFiles  = @('d3d11.dll', 'dxgi.dll')
$DxvkMarker = 'attila_optimizer_dxvk.txt'
$AttilaAppId = '325610'

# Mod yapımı için gereken tablolar (db\<tablo>\ klasör adları).
$ModDataTablePattern = '^(main_units|land_units|campaign_difficulty_handicap_effects|effects|effect_bonus_value_.+|effect_bundles.*|campaign_effect_scopes|campaign_bonus_value_ids_.+|factions|faction_groups|units_to_.+|unit_set.*|building_units_allowed|building_effects_junction|building_levels|building_chains|building_culture_variants|technologies|technology_effects_junction)_tables$'

function Write-Title($text) {
    Write-Host ''
    Write-Host "=== $text ===" -ForegroundColor Cyan
}

function Write-Ok($text)   { Write-Host "  [OK]  $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  [!]   $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  [X]   $text" -ForegroundColor Red }
function Write-Info($text) { Write-Host "        $text" }

# --- Oyun klasörünü bulma -----------------------------------------------------

function Get-SteamLibraries {
    $roots = @()
    foreach ($key in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam') {
        $item = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
        if ($item) {
            if ($item.SteamPath)   { $roots += $item.SteamPath }
            if ($item.InstallPath) { $roots += $item.InstallPath }
        }
    }

    $libraries = @()
    foreach ($root in ($roots | Select-Object -Unique)) {
        $root = $root -replace '/', '\'
        $libraries += $root
        $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
        if (Test-Path $vdf) {
            foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
                $libraries += ($m.Groups[1].Value -replace '\\\\', '\')
            }
        }
    }
    return $libraries | Select-Object -Unique
}

function Find-GameDir {
    if ($GameDir) {
        if (Test-Path (Join-Path $GameDir 'Attila.exe')) { return (Resolve-Path $GameDir).Path }
        throw "Verilen klasörde Attila.exe yok: $GameDir"
    }

    foreach ($lib in Get-SteamLibraries) {
        $common = Join-Path $lib 'steamapps\common'
        if (-not (Test-Path $common)) { continue }
        foreach ($dir in Get-ChildItem $common -Directory -ErrorAction SilentlyContinue) {
            if (Test-Path (Join-Path $dir.FullName 'Attila.exe')) { return $dir.FullName }
        }
    }
    return $null
}

function Get-GameDirOrAsk {
    $dir = Find-GameDir
    if ($dir) { return $dir }

    Write-Warn 'Attila klasörü otomatik bulunamadı.'
    $answer = Read-Host '  Attila.exe dosyasının bulunduğu klasörü yapıştırın'
    $answer = $answer.Trim('"', ' ')
    if ($answer -and (Test-Path (Join-Path $answer 'Attila.exe'))) { return $answer }
    throw 'Attila.exe bulunamadı.'
}

# --- PE başlığı: 32/64-bit ve LAA -----------------------------------------------

function Get-ExeInfo($path) {
    $bytes = [IO.File]::ReadAllBytes($path)
    $pe = [BitConverter]::ToInt32($bytes, 0x3C)
    $machine = [BitConverter]::ToUInt16($bytes, $pe + 4)
    $characteristics = [BitConverter]::ToUInt16($bytes, $pe + 22)
    return [pscustomobject]@{
        Is32Bit = ($machine -eq 0x014C)
        Is64Bit = ($machine -eq 0x8664)
        LargeAddressAware = (($characteristics -band 0x0020) -ne 0)
    }
}

# --- preferences.script.txt ---------------------------------------------------

function Get-Pref($text, $key) {
    $m = [regex]::Match($text, "(?m)^\s*$key\s+([^;\r\n]*);")
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return $null
}

function Set-Pref([ref]$text, $key, $value) {
    $pattern = "(?m)^(\s*$key\s+)[^;\r\n]*;"
    if ([regex]::IsMatch($text.Value, $pattern)) {
        $text.Value = [regex]::Replace($text.Value, $pattern, "`${1}$value;")
        return $true
    }
    return $false
}

function Assert-GameClosed {
    if (Get-Process -Name 'Attila' -ErrorAction SilentlyContinue) {
        throw 'Attila şu an açık. Ayarları değiştirmeden önce oyunu kapatın (oyun çıkışta dosyanın üzerine yazar).'
    }
}

function Invoke-Tweak {
    Write-Title 'Ayar düzeltmesi (preferences.script.txt)'
    Assert-GameClosed

    if (-not (Test-Path $PrefsFile)) {
        throw "Ayar dosyası yok: $PrefsFile`nOyunu bir kez açıp kapatın, dosya oluşur."
    }

    $backup = "$PrefsFile.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $PrefsFile $backup
    Write-Ok "Yedek alındı: $backup"

    $text = [IO.File]::ReadAllText($PrefsFile)
    $threads = [Math]::Min([Environment]::ProcessorCount, 8)

    # Anahtar, değer, açıklama. Dosyada olmayan anahtar eklenmez; yalnızca uyarı verilir.
    $changes = @(
        @('gfx_unlimited_video_memory', 'true', 'Sınırsız video belleği açık (VRAM dolunca dokular bozulmaz).'),
        @('gfx_video_memory', '-1', 'Oyunun algıladığı VRAM, motorun üst sınırına çekildi (3072 MB yerine en fazla 4095 MB).'),
        @('number_of_threads', "$threads", "İş parçacığı sayısı $threads (motor 8'in üstünde verimsizleşiyor).")
    )

    foreach ($c in $changes) {
        $old = Get-Pref $text $c[0]
        if (Set-Pref ([ref]$text) $c[0] $c[1]) {
            Write-Ok "$($c[0]): $old -> $($c[1])"
            Write-Info $c[2]
        } else {
            Write-Warn "$($c[0]) dosyada bulunamadı, atlandı."
        }
    }

    [IO.File]::WriteAllText($PrefsFile, $text, (New-Object Text.UTF8Encoding($false)))
    Write-Ok 'Ayar dosyası kaydedildi.'
}

function Invoke-RestorePrefs {
    Write-Title 'Ayar dosyasını geri yükleme'
    Assert-GameClosed

    $latest = Get-ChildItem $PrefsDir -Filter 'preferences.script.txt.backup_*' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) {
        Write-Warn 'Yedek bulunamadı.'
        return
    }
    Copy-Item $latest.FullName $PrefsFile -Force
    Write-Ok "Geri yüklendi: $($latest.Name)"
}

# --- DXVK --------------------------------------------------------------------

function Invoke-InstallDxvk {
    Write-Title 'DXVK kurulumu (32-bit)'
    Assert-GameClosed
    $dir = Get-GameDirOrAsk
    $exe = Get-ExeInfo (Join-Path $dir 'Attila.exe')
    $arch = 'x32'
    if ($exe.Is64Bit) { $arch = 'x64' }
    Write-Info "Oyun klasörü: $dir ($arch)"

    Write-Info 'GitHub üzerinden son DXVK sürümü aranıyor...'
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/doitsujin/dxvk/releases/latest' -Headers @{ 'User-Agent' = 'AttilaOptimizer' }
    $asset = $release.assets | Where-Object { $_.name -match '^dxvk-[\d\.]+\.tar\.gz$' } | Select-Object -First 1
    if (-not $asset) { throw 'DXVK indirme dosyası bulunamadı.' }

    $work = Join-Path $env:TEMP "attila_dxvk_$(Get-Random)"
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        $archive = Join-Path $work $asset.name
        Write-Info "İndiriliyor: $($asset.name)"
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive -UseBasicParsing

        # Windows 10/11 ile gelen tar.exe .tar.gz açabiliyor.
        & tar.exe -xzf $archive -C $work
        if ($LASTEXITCODE -ne 0) { throw 'Arşiv açılamadı (tar.exe).' }

        $src = Get-ChildItem $work -Directory | Where-Object { $_.Name -like 'dxvk-*' } | Select-Object -First 1
        $srcArch = Join-Path $src.FullName $arch
        if (-not (Test-Path (Join-Path $srcArch 'd3d11.dll'))) { throw "DXVK paketinde $arch klasörü yok." }

        foreach ($f in $DxvkFiles) {
            $target = Join-Path $dir $f
            if ((Test-Path $target) -and -not (Test-Path "$target.pre_dxvk")) {
                Move-Item $target "$target.pre_dxvk"
                Write-Warn "Mevcut $f yedeklendi: $f.pre_dxvk"
            }
            Copy-Item (Join-Path $srcArch $f) $target -Force
            Write-Ok "$f kopyalandı."
        }
    } finally {
        Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
    }

    # 32-bit oyuna 16 GB VRAM bildirmek yerine 4095 MB bildir; tespit taşmasını önler.
    $conf = @(
        '# AttilaOptimizer tarafından oluşturuldu.',
        '# 32-bit oyuna bildirilen VRAM (MB).',
        'dxgi.maxDeviceMemory = 4095'
    )
    $confPath = Join-Path $dir 'dxvk.conf'
    if ((Test-Path $confPath) -and -not (Test-Path "$confPath.pre_dxvk")) {
        Move-Item $confPath "$confPath.pre_dxvk"
    }
    Set-Content -Path $confPath -Value $conf -Encoding ASCII
    Set-Content -Path (Join-Path $dir $DxvkMarker) -Value $release.tag_name -Encoding ASCII
    Write-Ok "dxvk.conf yazıldı. DXVK $($release.tag_name) kuruldu."

    Write-Host ''
    Write-Info 'Doğrulama: oyunu açıp kapatın. Oyun klasöründe Attila_d3d11.log oluştuysa DXVK çalışıyor.'
    Write-Info 'İlk savaşlarda shader derlendiği için kısa takılmalar normaldir.'
    Write-Info 'Çökme olursa menüden "DXVK kaldır" seçeneğiyle eski haline döner.'
}

function Invoke-RemoveDxvk {
    Write-Title 'DXVK kaldırma'
    Assert-GameClosed
    $dir = Get-GameDirOrAsk

    # Başka bir araçla kurulmuş d3d11.dll'e (ör. ReShade) dokunma.
    if (-not (Test-Path (Join-Path $dir $DxvkMarker))) {
        Write-Warn 'DXVK bu araçla kurulmamış, hiçbir dosyaya dokunulmadı.'
        return
    }

    foreach ($f in $DxvkFiles + @('dxvk.conf')) {
        $target = Join-Path $dir $f
        if (Test-Path $target) {
            Remove-Item $target -Force
            Write-Ok "$f silindi."
        }
        if (Test-Path "$target.pre_dxvk") {
            Move-Item "$target.pre_dxvk" $target
            Write-Ok "Eski $f geri yüklendi."
        }
    }
    Remove-Item (Join-Path $dir $DxvkMarker) -ErrorAction SilentlyContinue
    Get-ChildItem $dir -Filter 'Attila_*.log' -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Ok 'DXVK kaldırıldı, oyun DirectX 11 ile çalışacak.'
}

# --- Mod verisi: .pack dosyalarından tablo çıkarma -------------------------------

# PFH4 (Attila) pack dosyasının içindekiler listesini okur. Veri bölümüne dokunmaz,
# bu yüzden 1 GB'lık pack'ler de hızlıca taranır.
function Get-PackEntries($path) {
    $stream = [IO.File]::OpenRead($path)
    try {
        $reader = New-Object IO.BinaryReader($stream)
        $preamble = [Text.Encoding]::ASCII.GetString($reader.ReadBytes(4))
        if ($preamble -ne 'PFH4') { return $null }

        $flags = $reader.ReadUInt32()
        $packsCount = $reader.ReadUInt32()
        $packsIndexSize = $reader.ReadUInt32()
        $filesCount = $reader.ReadUInt32()
        $filesIndexSize = $reader.ReadUInt32()
        [void]$reader.ReadUInt32()   # zaman damgası

        # Şifreli pack'ler (ör. music.pack) bizi ilgilendirmiyor.
        if ($flags -band 0x90) { return $null }
        if ($flags -band 0x100) { [void]$reader.ReadBytes(20) }
        $hasTimestamps = ($flags -band 0x40) -ne 0

        [void]$reader.ReadBytes([int]$packsIndexSize)
        $index = $reader.ReadBytes([int]$filesIndexSize)
        $offset = [int64]$stream.Position

        $entries = New-Object Collections.Generic.List[object]
        $pos = 0
        for ($i = 0; $i -lt $filesCount; $i++) {
            $size = [BitConverter]::ToUInt32($index, $pos)
            $pos += 4
            if ($hasTimestamps) { $pos += 4 }
            $end = [Array]::IndexOf($index, [byte]0, $pos)
            $name = [Text.Encoding]::UTF8.GetString($index, $pos, $end - $pos).Replace('\', '/')
            $pos = $end + 1
            $entries.Add([pscustomobject]@{ Path = $name; Size = $size; Offset = $offset })
            $offset += $size
        }
        return $entries
    } finally {
        $stream.Dispose()
    }
}

function Test-ModDataEntry($entryPath, $includeLocs, $includeScripts) {
    $parts = $entryPath.Split('/')
    if ($parts.Count -eq 3 -and $parts[0] -eq 'db' -and $parts[1] -match $ModDataTablePattern) { return $true }
    # Betikler ve olay görselleri (boyut ve biçim örneği için) yalnızca Workshop modlarından alınır.
    if ($includeScripts -and ($entryPath.EndsWith('.lua') -or $entryPath.StartsWith('ui/eventpics/'))) { return $true }
    return ($includeLocs -and $entryPath.EndsWith('.loc'))
}

# Küçük pack'lerin tam içerik listesini, büyüklerin klasör özetini yazar.
function Write-PackIndex($entries, $destFile) {
    if ($entries.Count -le 3000) {
        $lines = $entries | ForEach-Object { "$($_.Path)`t$($_.Size)" }
    } else {
        $lines = $entries | Group-Object { ($_.Path -split '/')[0] } | ForEach-Object {
            $total = ($_.Group | Measure-Object Size -Sum).Sum
            "$($_.Name)/`t$($_.Count) dosya`t$total"
        }
    }
    New-Item -ItemType Directory -Path (Split-Path $destFile) -Force | Out-Null
    Set-Content -Path $destFile -Value $lines -Encoding UTF8
}

function Export-PackEntries($packPath, $entries, $destDir) {
    $stream = [IO.File]::OpenRead($packPath)
    try {
        foreach ($e in $entries) {
            $target = Join-Path $destDir $e.Path
            New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
            $buffer = New-Object byte[] $e.Size
            [void]$stream.Seek($e.Offset, 'Begin')
            $read = 0
            while ($read -lt $e.Size) {
                $n = $stream.Read($buffer, $read, $e.Size - $read)
                if ($n -le 0) { throw "Pack beklenenden kısa: $packPath" }
                $read += $n
            }
            [IO.File]::WriteAllBytes($target, $buffer)
        }
    } finally {
        $stream.Dispose()
    }
}

function Invoke-ExportModData {
    Write-Title 'Mod verisi dışa aktarma'
    $dir = Get-GameDirOrAsk

    # Oyun klasörü <kütüphane>\steamapps\common\<oyun> biçiminde; Workshop aynı kütüphanede.
    $steamapps = Split-Path (Split-Path $dir)
    $workshop = Join-Path $steamapps "workshop\content\$AttilaAppId"

    $packs = @(Get-ChildItem (Join-Path $dir 'data') -Filter '*.pack' -ErrorAction SilentlyContinue)
    if (Test-Path $workshop) {
        $packs += @(Get-ChildItem $workshop -Filter '*.pack' -Recurse -ErrorAction SilentlyContinue)
    } else {
        Write-Warn "Workshop klasörü bulunamadı: $workshop"
    }

    $base = $OutDir
    if (-not $base) { $base = [Environment]::GetFolderPath('Desktop') }
    $outRoot = Join-Path $base 'AttilaModData'
    if (Test-Path $outRoot) { Remove-Item $outRoot -Recurse -Force }
    New-Item -ItemType Directory -Path $outRoot | Out-Null

    $manifest = New-Object Collections.Generic.List[string]
    foreach ($pack in $packs) {
        try {
            $entries = Get-PackEntries $pack.FullName
        } catch {
            Write-Warn "$($pack.Name) okunamadı: $($_.Exception.Message)"
            continue
        }
        if (-not $entries) { continue }

        # Yerelleştirme dosyaları yalnızca MK1212 pack'lerinden alınır; oyununkiler çok büyük.
        # Betikler ve içerik listesi yalnızca Workshop modlarından alınır.
        $isWorkshop = $pack.FullName.StartsWith($workshop)
        $includeLocs = $pack.Name -match '1212'
        $wanted = @($entries | Where-Object { Test-ModDataEntry $_.Path $includeLocs $isWorkshop })

        $folder = $pack.Name
        if ($isWorkshop) {
            $folder = "workshop_$($pack.Directory.Name)_$($pack.Name)"
            Write-PackIndex $entries (Join-Path $outRoot "$folder\_index.tsv")
        }
        if ($wanted.Count -eq 0) { continue }
        Export-PackEntries $pack.FullName $wanted (Join-Path $outRoot $folder)
        $manifest.Add("$folder`t$($wanted.Count)")
        Write-Ok "$($pack.Name): $($wanted.Count) dosya"
    }

    # Mod yöneticisinin yükleme sırası, alt modun önceliğini ayarlamak için gerekli.
    $userScript = Join-Path $PrefsDir 'user.script.txt'
    if (Test-Path $userScript) { Copy-Item $userScript $outRoot }
    Set-Content -Path (Join-Path $outRoot 'manifest.tsv') -Value $manifest -Encoding UTF8

    $zip = "$outRoot.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $outRoot '*') -DestinationPath $zip
    $sizeMb = [Math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Ok "Hazır: $zip ($sizeMb MB)"
    if ($sizeMb -gt 29) {
        Write-Warn 'ZIP 30 MB sınırını aşıyor. Bu çıktının ekran görüntüsünü gönderin, listeyi daraltalım.'
    } else {
        Write-Info 'Bu ZIP dosyasını sohbete yükleyin.'
    }
}

# --- Durum raporu --------------------------------------------------------------

function Show-Status {
    Write-Title 'Durum raporu'

    $dir = Find-GameDir
    if ($dir) {
        Write-Ok "Oyun klasörü: $dir"
        $exe = Get-ExeInfo (Join-Path $dir 'Attila.exe')
        if ($exe.Is32Bit) { Write-Info 'Attila.exe: 32-bit (64-bit sürümü yok, değiştirilemez).' }
        if ($exe.Is64Bit) { Write-Info 'Attila.exe: 64-bit.' }
        if ($exe.LargeAddressAware) {
            Write-Ok 'Large Address Aware: açık (oyun 4 GB adres alanının tamamını kullanabiliyor).'
        } else {
            Write-Warn 'Large Address Aware: kapalı (oyun en fazla 2 GB kullanabiliyor).'
        }

        $marker = Join-Path $dir $DxvkMarker
        if (Test-Path $marker) {
            Write-Ok "DXVK kurulu: $((Get-Content $marker -Raw).Trim())"
            if (Test-Path (Join-Path $dir 'Attila_d3d11.log')) { Write-Ok 'DXVK günlüğü var: DXVK en az bir kez çalışmış.' }
        } elseif (Test-Path (Join-Path $dir 'd3d11.dll')) {
            Write-Warn 'Oyun klasöründe başka bir d3d11.dll var (ReShade veya elle kurulmuş DXVK olabilir).'
        } else {
            Write-Info 'DXVK kurulu değil.'
        }
    } else {
        Write-Warn 'Oyun klasörü otomatik bulunamadı.'
    }

    if (Test-Path $PrefsFile) {
        $text = [IO.File]::ReadAllText($PrefsFile)
        Write-Ok "Ayar dosyası: $PrefsFile"
        foreach ($k in 'gfx_video_memory', 'gfx_unlimited_video_memory', 'number_of_threads', 'gfx_unit_size') {
            $v = Get-Pref $text $k
            if ($null -eq $v) { $v = '(yok)' }
            Write-Info ("{0,-28} {1}" -f $k, $v)
        }
    } else {
        Write-Warn "Ayar dosyası yok: $PrefsFile"
    }

    Write-Info "Mantıksal işlemci sayısı: $([Environment]::ProcessorCount)"
}

# --- Menü ----------------------------------------------------------------------

function Invoke-Action($name) {
    try {
        switch ($name) {
            'Status'       { Show-Status }
            'Tweak'        { Invoke-Tweak }
            'InstallDxvk'  { Invoke-InstallDxvk }
            'RemoveDxvk'   { Invoke-RemoveDxvk }
            'RestorePrefs' { Invoke-RestorePrefs }
            'ExportModData' { Invoke-ExportModData }
        }
    } catch {
        Write-Err $_.Exception.Message
    }
}

if ($Action -ne 'Menu') {
    Invoke-Action $Action
    return
}

while ($true) {
    Write-Title 'Total War: ATTILA Optimizer'
    Write-Host '  1) Durum raporu'
    Write-Host '  2) Ayar düzeltmesi uygula (VRAM, sınırsız bellek, iş parçacığı)'
    Write-Host '  3) DXVK kur (Vulkan, işlemci darboğazı için)'
    Write-Host '  4) DXVK kaldır'
    Write-Host '  5) Ayar dosyasını son yedekten geri yükle'
    Write-Host '  6) Mod verisini dışa aktar (tablolar, ZIP olarak masaüstüne)'
    Write-Host '  0) Çıkış'
    switch (Read-Host 'Seçim') {
        '1' { Invoke-Action 'Status' }
        '2' { Invoke-Action 'Tweak' }
        '3' { Invoke-Action 'InstallDxvk' }
        '4' { Invoke-Action 'RemoveDxvk' }
        '5' { Invoke-Action 'RestorePrefs' }
        '6' { Invoke-Action 'ExportModData' }
        '0' { return }
        default { Write-Warn 'Geçersiz seçim.' }
    }
}
