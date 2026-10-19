"""MK1212 Oyuncu Bonusu alt modunu üretir.

Bonuslar oyunun zorluk tablosuna (campaign_difficulty_handicap_effects) human=true
olarak eklenir, bu yüzden yalnızca insan oyuncuyu etkiler; AI fraksiyonlarına dokunmaz.
MK1212'nin hiçbir satırı değiştirilmez: tüm efekt, birim seti ve metin anahtarları yenidir.

Kullanım:
    python3 build.py --data <TSV klasörü> --rpfm <rpfm_cli> --schema <schema_att.ron> --out <klasör>

--data, kurulu modların TSV'ye çevrilmiş tablolarını içeren klasördür (her pack bir alt klasör).
Bakım bandları, oyunda geçerli olan main_units değerlerinden hesaplanır.
"""

import argparse
import csv
import glob
import os
import shutil
import subprocess

PREFIX = 'pb'                      # player bonus
DIFFICULTIES = range(-3, 4)        # Legendary (-3) ... Easy/en kolay (3)

# Ayarlanabilir değerler.
INCOME_PCT = 15                    # tüm binalardan servet
RESEARCH_PCT = 100                 # araştırma hızı; +%100 = süre yarıya
PUBLIC_ORDER = 5                   # eyalet başına kamu düzeni
GROWTH = 4                         # eyalet başına büyüme (teknolojiler +1/+2 verir)
UPKEEP_FREE_UNTIL = 120            # bu bakıma kadar indirim yok
UPKEEP_ANCHOR = (460, 180)         # 460 bakımlı birim 180'e iner; aradakiler doğrusal

# (anahtar, bonus_value_id, kapsam, değer, simge, öncelik, açıklama)
SIMPLE_EFFECTS = [
    ('gdp_all', 'gdp_mod_all', 'faction_to_region_own', INCOME_PCT,
     'wealth', 162, 'Player bonus - Wealth: %+n% from all buildings'),
    ('research_rate', 'research_rate_mod', 'faction_to_faction_own', RESEARCH_PCT,
     'technology', 61, 'Player bonus - Research rate: %+n%'),
    ('public_order', 'province_public_order_happiness_building_positive_factor', 'faction_to_province_own', PUBLIC_ORDER,
     'public_order', 5, 'Player bonus - Public order: %+n'),
    ('growth', 'province_development_growth_added_faction', 'faction_to_province_own', GROWTH,
     'growth', 30, 'Player bonus - Growth: %+n'),
]


def target_upkeep(upkeep):
    """Hedef bakım: eşiğe kadar aynı, sonra (eşik -> çapa) doğrusu üzerinde."""
    if upkeep <= UPKEEP_FREE_UNTIL:
        return upkeep
    old, new = UPKEEP_ANCHOR
    slope = (new - UPKEEP_FREE_UNTIL) / (old - UPKEEP_FREE_UNTIL)
    return UPKEEP_FREE_UNTIL + (upkeep - UPKEEP_FREE_UNTIL) * slope


def read_tsv(path):
    with open(path, newline='', encoding='utf-8') as fh:
        rows = list(csv.reader(fh, delimiter='\t'))
    return rows[0], rows[2:]


def effective_land_upkeep(data_dir):
    """Oyun tabloları dosya adı sırasıyla okur ve bir anahtarı ilk okuyan dosya kazanır."""
    files = sorted(glob.glob(os.path.join(data_dir, '*', 'db', 'main_units_tables', '*.tsv')),
                   key=os.path.basename)
    units = {}
    for path in files:
        header, rows = read_tsv(path)
        unit, upkeep, naval = header.index('unit'), header.index('upkeep_cost'), header.index('is_naval')
        for row in rows:
            if row[unit] not in units:
                units[row[unit]] = (int(float(row[upkeep])), row[naval] == 'true')
    return {k: up for k, (up, naval) in units.items() if not naval}


def upkeep_bands(units):
    """Birimleri %1'lik indirim bandlarına ayırır: {indirim_yüzdesi: [birimler]}."""
    bands = {}
    for unit, upkeep in units.items():
        if upkeep <= UPKEEP_FREE_UNTIL:
            continue
        pct = round((1 - target_upkeep(upkeep) / upkeep) * 100)
        if pct > 0:
            bands.setdefault(pct, []).append(unit)
    return bands


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


def build_tables(units, out_dir):
    name = f'!{PREFIX}_player_bonus'
    effects, basic, unit_sets, set_units, set_bonus, handicap, loc = [], [], [], [], [], [], []

    for key, bonus, scope, value, icon, priority, text in SIMPLE_EFFECTS:
        effect = f'{PREFIX}_effect_{key}'
        effects.append([effect, f'{icon}_positive.png', priority, f'{icon}_negative.png'])
        basic.append([effect, bonus])
        loc.append([f'effects_description_{effect}', text, 'true'])
        handicap += [[d, 'true', effect, scope, f'{value:.4f}', ''] for d in DIFFICULTIES]

    bands = upkeep_bands(units)
    for pct in sorted(bands):
        effect = f'{PREFIX}_effect_upkeep_{pct:02d}'
        unit_set = f'{PREFIX}_unit_set_upkeep_{pct:02d}'
        effects.append([effect, 'military_spending_negative.png', 101, 'military_spending_positive.png'])
        loc.append([f'effects_description_{effect}', 'Player bonus - Upkeep cost: %+n% for expensive units', 'true'])
        unit_sets.append([unit_set])
        set_bonus.append(['upkeep_mod', effect, unit_set])
        set_units += [['', '', '', unit, unit_set, 'false'] for unit in sorted(bands[pct])]
        handicap += [[d, 'true', effect, 'faction_to_force_own_unseen', f'{-pct:.4f}', ''] for d in DIFFICULTIES]

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
    return bands


def report(units, bands):
    worst = 0.0
    for pct, members in bands.items():
        for unit in members:
            up = units[unit]
            worst = max(worst, abs(up * (1 - pct / 100) - target_upkeep(up)))
    print(f'{len(units)} kara birimi, {sum(map(len, bands.values()))} tanesine indirim, {len(bands)} band')
    print(f'Hedef bakımdan en büyük sapma: {worst:.1f}')
    for up in (120, 200, 300, 400, 460, 600, 1000):
        pct = round((1 - target_upkeep(up) / up) * 100) if up > UPKEEP_FREE_UNTIL else 0
        print(f'  {up:5} -> {up * (1 - pct / 100):6.0f}  (-%{pct})')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--rpfm', required=True)
    ap.add_argument('--schema', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    units = effective_land_upkeep(args.data)
    tsv_dir = os.path.join(args.out, 'tsv')
    shutil.rmtree(tsv_dir, ignore_errors=True)
    bands = build_tables(units, tsv_dir)
    report(units, bands)

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
