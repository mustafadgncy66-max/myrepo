"""MK1212 Oyuncu Bonusu alt modunu üretir.

Bonusların çoğu oyunun zorluk tablosuna (campaign_difficulty_handicap_effects) human=true
olarak eklenir, bu yüzden yalnızca insan oyuncuyu etkiler; AI fraksiyonlarına dokunmaz.
Oyun içi kartlarda görünmesi istenen değerler (bina bakımı, Selçuklu general muhafızları,
mescit sanitasyonu) ise doğrudan tablo satırları ezilerek değiştirilir.

Kullanım:
    python3 build.py --data <TSV klasörü> --rpfm <rpfm_cli> --schema <schema_att.ron> --out <klasör>

--data, kurulu modların TSV'ye çevrilmiş tablolarını içeren klasördür (her pack bir alt klasör).
Bakım bandları ve ezilen satırlar, oyunda geçerli olan tablo değerlerinden hesaplanır.
"""

import argparse
import csv
import glob
import os
import shutil
import subprocess

PREFIX = 'pb'                      # player bonus
DIFFICULTIES = range(-3, 4)        # tüm zorluk seviyeleri

# Ayarlanabilir değerler.
INCOME_PCT = 15                    # tüm binalardan servet
RESEARCH_PCT = 100                 # araştırma hızı; +%100 = süre yarıya
PUBLIC_ORDER = 5                   # eyalet başına kamu düzeni
GROWTH = 8                         # eyalet başına büyüme (teknolojiler +1/+2 verir)
REPLENISHMENT = 10                 # ikmal hızı (AI zorluğa göre +2...+9 alır)
UPKEEP_FREE_UNTIL = 120            # bu bakıma kadar indirim yok
UPKEEP_ANCHOR = (460, 180)         # 460 bakımlı birim 180'e iner; aradakiler doğrusal

# Selçuklu general muhafızlarının sabit bakımı. Bu birimler bandların dışında tutulur ve
# Selçuklu fraksiyon özelliğinin (-%20, profesyonel birimler) oyuncuda dengelenmesi için
# +%20 alır; böylece hem askere alma ekranında hem orduda 250 görünür.
GENERAL_UNIT_PREFIX = 'mk_rum_'
GENERAL_UPKEEP = 250
GENERAL_TRAIT_COMPENSATION = 20

# Bina bakımı tablo değerinin bu katına iner (kartlarda görünür). Bina tanımı ortak olduğu için
# AI fraksiyonlarına zorluk seviyelerine göre telafi eklenir; AI'nın ödediği bakım değişmez.
BUILDING_UPKEEP_FACTOR = 0.5
BUILDING_UPKEEP_EFFECT = 'att_effect_building_upkeep_mod'

# Eyalet başkenti mescitlerinin sanitasyonu: {seviye: değer}. MK1212'de I. seviye 0, diğerleri +1.
# Bina tanımı değiştiği için bu, AI'nın mescitlerini de etkiler.
MOSQUE_SANITATION = {1: 1, 2: 2, 3: 3, 4: 4}
MOSQUE_RELIGIONS = ('sunni', 'shia', 'ibadi')

# (anahtar, bonus_value_id, kapsam, değer, (simge, negatif simge), öncelik, açıklama)
# Simgeler oyundaki eşdeğer efektlerden alındı; maliyet efektlerinde ters çevrilidir.
SIMPLE_EFFECTS = [
    ('gdp_all', 'gdp_mod_all', 'faction_to_region_own', INCOME_PCT,
     ('wealth_positive.png', 'wealth_negative.png'), 162, 'Player bonus - Wealth: %+n% from all buildings'),
    ('research_rate', 'research_rate_mod', 'faction_to_faction_own', RESEARCH_PCT,
     ('technology_positive.png', 'technology_negative.png'), 61, 'Player bonus - Research rate: %+n%'),
    ('public_order', 'province_public_order_happiness_building_positive_factor', 'faction_to_province_own', PUBLIC_ORDER,
     ('public_order_positive.png', 'public_order_negative.png'), 5, 'Player bonus - Public order: %+n'),
    ('growth', 'province_development_growth_added_faction', 'faction_to_province_own', GROWTH,
     ('growth_positive.png', 'growth_negative.png'), 30, 'Player bonus - Growth: %+n'),
    ('replenishment', 'replenishment_percentage_bonus', 'faction_to_force_own', REPLENISHMENT,
     ('replenishment_positive.png', 'replenishment_negative.png'), 101, 'Player bonus - Replenishment: %+n%'),
]


def target_upkeep(upkeep):
    """Hedef bakım: eşiğe kadar aynı, sonra (eşik -> çapa) doğrusu üzerinde."""
    if upkeep <= UPKEEP_FREE_UNTIL:
        return upkeep
    old, new = UPKEEP_ANCHOR
    slope = (new - UPKEEP_FREE_UNTIL) / (old - UPKEEP_FREE_UNTIL)
    return UPKEEP_FREE_UNTIL + (upkeep - UPKEEP_FREE_UNTIL) * slope


def discount_pct(upkeep):
    return round((1 - target_upkeep(upkeep) / upkeep) * 100) if upkeep > 0 else 0


def read_tsv(path):
    """(başlık, sürüm, satırlar)"""
    with open(path, newline='', encoding='utf-8') as fh:
        rows = list(csv.reader(fh, delimiter='\t'))
    return rows[0], int(rows[1][0].split(';')[1]), rows[2:]


def table_files(data_dir, table):
    """Bir tablonun dosyaları, oyunun okuma sırasıyla.

    Oyun tabloları dosya adı sırasıyla okur ve bir anahtarı ilk okuyan dosya kazanır.
    Bir mod, oyunun kendi dosyasıyla aynı adı taşıyan dosya getirirse oyununkinin yerine geçer.
    """
    paths = glob.glob(os.path.join(data_dir, '*', 'db', table, '*.tsv'))
    modded = {os.path.basename(p) for p in paths if not p.split(os.sep)[-4].startswith('data.pack')}
    paths = [p for p in paths if not (p.split(os.sep)[-4].startswith('data.pack') and os.path.basename(p) in modded)]
    return sorted(paths, key=os.path.basename)


def effective_rows(data_dir, table, key_columns):
    """(başlık, sürüm, {anahtar: satır}); her anahtar için oyunda geçerli olan satır.

    Dosyalar farklı tablo sürümlerinde olabilir; satırlar en yeni sürümün sütunlarına çevrilir.
    """
    files = [(path, *read_tsv(path)) for path in table_files(data_dir, table)]
    _, header, version, _ = max(files, key=lambda f: f[2])
    result = {}
    for _, h, _, rows in files:
        idx = [h.index(c) for c in key_columns]
        for row in rows:
            row = row + [''] * (len(h) - len(row))
            key = tuple(row[i] for i in idx)
            if key not in result:
                result[key] = [row[h.index(c)] if c in h else '' for c in header]
    return header, version, result


def effective_land_units(data_dir):
    """main_units başlığı, sürümü ve {birim: (satır, general_mi)}; deniz birimleri hariç."""
    land_header, _, land = effective_rows(data_dir, 'land_units_tables', ['key'])
    cls = land_header.index('class')
    classes = {key[0]: row[cls] for key, row in land.items()}

    header, version, mains = effective_rows(data_dir, 'main_units_tables', ['unit'])
    naval, land_unit = header.index('is_naval'), header.index('land_unit')
    units = {}
    for (unit,), row in mains.items():
        if row[naval] == 'true':
            continue
        general = unit.startswith(GENERAL_UNIT_PREFIX) and classes.get(row[land_unit]) == 'com'
        units[unit] = (row, general)
    return header, version, units


def upkeep_bands(units, upkeep_col):
    """General olmayan birimleri %1'lik indirim bandlarına ayırır: {indirim_yüzdesi: [birimler]}."""
    bands = {}
    for unit, (row, general) in units.items():
        if general:
            continue
        pct = discount_pct(int(float(row[upkeep_col])))
        if pct > 0:
            bands.setdefault(pct, []).append(unit)
    return bands


def ai_building_upkeep_compensation(data_dir):
    """{zorluk: AI telafi yüzdesi}. Taban yarıya inince AI'nın ödediği bakım aynı kalsın diye.

    AI'nın ödediği: taban * (1 + m). Yeni taban f * taban ile aynı tutar için gereken ek:
    k = (1 + m) * (1/f - 1). Teknoloji gibi diğer indirimler yok sayılır.
    """
    header, _, rows = effective_rows(data_dir, 'campaign_difficulty_handicap_effects_tables',
                                     ['campaign_difficulty_handicap', 'human', 'effect'])
    value = header.index('effect_value')
    result = {}
    for d in DIFFICULTIES:
        row = rows.get((str(d), 'false', BUILDING_UPKEEP_EFFECT))
        m = float(row[value]) / 100 if row else 0.0
        result[d] = round((1 + m) * (1 / BUILDING_UPKEEP_FACTOR - 1) * 100)
    return result


def write_tsv(out_dir, table, file_name, version, header, rows):
    path = os.path.join(out_dir, 'db', table, file_name + '.tsv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh, delimiter='\t', lineterminator='\n')
        w.writerow(header)
        w.writerow([f'#{table};{version};db/{table}/{file_name}'] + [''] * (len(header) - 1))
        w.writerows(rows)


def write_loc(out_dir, file_name, rows):
    path = os.path.join(out_dir, 'text', 'db', file_name + '.loc.tsv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh, delimiter='\t', lineterminator='\n')
        w.writerow(['key', 'text', 'tooltip'])
        w.writerow([f'#Loc;1;text/db/{file_name}.loc', '', ''])
        w.writerows(rows)


def build_tables(data_dir, out_dir):
    # Dosya adındaki '!', oyunun bu dosyayı MK1212'ninkilerden önce okumasını sağlar.
    name = f'!{PREFIX}_player_bonus'
    effects, basic, unit_sets, set_units, set_bonus, handicap, loc = [], [], [], [], [], [], []

    def add_effect(effect, icons, priority, text):
        effects.append([effect, icons[0], priority, icons[1]])
        loc.append([f'effects_description_{effect}', text, 'true'])

    def add_unit_set_effect(effect, unit_set, units, value, text):
        add_effect(effect, ('military_spending_negative.png', 'military_spending_positive.png'), 101, text)
        unit_sets.append([unit_set])
        set_bonus.append(['upkeep_mod', effect, unit_set])
        set_units.extend(['', '', '', unit, unit_set, 'false'] for unit in sorted(units))
        handicap.extend([d, 'true', effect, 'faction_to_force_own_unseen', f'{value:.4f}', ''] for d in DIFFICULTIES)

    for key, bonus, scope, value, icons, priority, text in SIMPLE_EFFECTS:
        effect = f'{PREFIX}_effect_{key}'
        add_effect(effect, icons, priority, text)
        basic.append([effect, bonus])
        handicap.extend([d, 'true', effect, scope, f'{value:.4f}', ''] for d in DIFFICULTIES)

    # Birim bakımı.
    units_header, units_version, units = effective_land_units(data_dir)
    upkeep_col = units_header.index('upkeep_cost')
    bands = upkeep_bands(units, upkeep_col)
    for pct in sorted(bands):
        add_unit_set_effect(f'{PREFIX}_effect_upkeep_{pct:02d}', f'{PREFIX}_unit_set_upkeep_{pct:02d}', bands[pct],
                            -pct, 'Player bonus - Upkeep cost: %+n% for expensive units')

    # Selçuklu general muhafızları: sabit bakım + fraksiyon özelliği telafisi.
    generals = sorted(unit for unit, (_, general) in units.items() if general)
    general_rows = []
    for unit in generals:
        row = list(units[unit][0])
        row[upkeep_col] = str(GENERAL_UPKEEP)
        general_rows.append(row)
    write_tsv(out_dir, 'main_units_tables', name, units_version, units_header, general_rows)
    add_unit_set_effect(f'{PREFIX}_effect_upkeep_generals', f'{PREFIX}_unit_set_generals', generals,
                        GENERAL_TRAIT_COMPENSATION, 'Player bonus - Upkeep cost: %+n% for generals (balance)')

    # Bina bakımı: taban yarıya, AI'ya telafi.
    levels_header, levels_version, levels = effective_rows(data_dir, 'building_levels_tables', ['level_name'])
    upkeep_col = levels_header.index('upkeep_cost')
    level_rows = []
    for row in levels.values():
        upkeep = float(row[upkeep_col])
        if upkeep > 0:
            row = list(row)
            row[upkeep_col] = str(int(upkeep * BUILDING_UPKEEP_FACTOR + 0.5))
            level_rows.append(row)
    write_tsv(out_dir, 'building_levels_tables', name, levels_version, levels_header, level_rows)
    compensation = ai_building_upkeep_compensation(data_dir)
    ai_effect = f'{PREFIX}_effect_building_upkeep_ai'
    add_effect(ai_effect, ('wealth_negative.png', 'wealth_positive.png'), 101, 'Maintenance cost: %+n%')
    basic.append([ai_effect, 'building_upkeep_mod'])
    handicap.extend([d, 'false', ai_effect, 'faction_to_region_own_unseen', f'{compensation[d]:.4f}', '']
                    for d in DIFFICULTIES if compensation[d])

    # Mescit sanitasyonu.
    building_effects = [[f'mk_bld_religion_{religion}_major_{level}', 'att_effect_sanitation_buildings',
                         'region_to_region_own', f'{value:.4f}', '0.0000', '0.0000']
                        for religion in MOSQUE_RELIGIONS for level, value in MOSQUE_SANITATION.items()]
    write_tsv(out_dir, 'building_effects_junction_tables', name, 3,
              ['building', 'effect', 'effect_scope', 'value', 'value_damaged', 'value_ruined'], building_effects)

    write_tsv(out_dir, 'effects_tables', name, 1, ['effect', 'icon', 'priority', 'icon_negative'], effects)
    write_tsv(out_dir, 'effect_bonus_value_basic_junction_tables', name, 0, ['effect', 'bonus_value_id'], basic)
    write_tsv(out_dir, 'unit_sets_tables', name, 0, ['key'], unit_sets)
    write_tsv(out_dir, 'unit_set_to_unit_junctions_tables', name, 0,
              ['unit_caste', 'unit_category', 'unit_class', 'unit_record', 'unit_set', 'exclude'], set_units)
    write_tsv(out_dir, 'effect_bonus_value_ids_unit_sets_tables', name, 0,
              ['bonus_value_id', 'effect', 'unit_set'], set_bonus)
    write_tsv(out_dir, 'campaign_difficulty_handicap_effects_tables', name, 0,
              ['campaign_difficulty_handicap', 'human', 'effect', 'effect_scope', 'effect_value',
               'optional_campaign_key'], handicap)
    write_loc(out_dir, name, loc)

    print(f'{len(units)} kara birimi, {sum(map(len, bands.values()))} tanesine indirim, {len(bands)} band')
    for up in (120, 200, 300, 400, 460, 600, 1000):
        pct = discount_pct(up)
        print(f'  {up:5} -> {up * (1 - pct / 100):6.0f}  (-%{pct})')
    print(f'General muhafızları ({GENERAL_UPKEEP}): {", ".join(generals)}')
    print(f'Bakımı yarıya inen bina seviyesi: {len(level_rows)}')
    print(f'AI bina bakımı telafisi (zorluk: %): {compensation}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--rpfm', required=True)
    ap.add_argument('--schema', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    tsv_dir = os.path.join(args.out, 'tsv')
    shutil.rmtree(tsv_dir, ignore_errors=True)
    build_tables(args.data, tsv_dir)

    pack = os.path.join(args.out, 'mk1212_oyuncu_bonus.pack')
    if os.path.exists(pack):
        os.remove(pack)
    subprocess.run([args.rpfm, '-g', 'attila', 'pack', 'create', '-p', pack], check=True)
    for folder in ('db', 'text'):
        subprocess.run([args.rpfm, '-g', 'attila', 'pack', 'add', '-p', pack, '-t', args.schema,
                        '-F', f'{os.path.join(tsv_dir, folder)};'], check=True)
    print(f'Pack: {pack}')


if __name__ == '__main__':
    main()
