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
import re
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
CONSTRUCTION_COST_PCT = -50        # bina yapım ve yükseltme maliyeti
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

# Portreler: MK1212 her Selçuklu sultanına aynı "sultan" görünümünü (Alaeddin Keykubad'ın bilinen
# portresi) verir. Keykâvus'un portre setinde (başlangıç kaydından) sultan görünümü, kendi portresi olan
# yeni bir görünümle değiştirilir; 3B modeli sultanınkiyle aynıdır. Keykubad tahta geçince sultan
# görünümünü alır. Aynı seti kullanan başka bir karakter sultan olursa o da Keykâvus'un portresini taşır.
# Portre dosyaları ui/portraits altında, tools/portrait.py ile art/kaikaus.jpg'den üretilir.
KAYKAUS_ART_SET = 'mk_campaign_sel_t1_general_07'
SULTAN_UNIFORM = 'mk_campaign_sel_t1_general_01'
KAYKAUS_UNIFORM = 'pb_campaign_sel_kaikaus'

# Selçuklu Ticaret Ağı: campaigns/main_attila/factions/mk_fact_seljuks.lua, sahip olunan kervan
# şehri ve liman sayısına göre aşağıdaki paketleri uygular. Liste uzunlukları o dosyadan okunur.
TRADE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'campaigns', 'main_attila', 'factions', 'mk_fact_seljuks.lua')
CARAVAN_COMMERCE_PER_CITY = 5      # şehir başına karadan ticaret serveti (%)
CARAVAN_TARIFF_PER_CITY = 3        # şehir başına ticaret anlaşması geliri (%)
PORT_COMMERCE_PER_PORT = 10        # liman başına deniz ticareti serveti (%)
PORT_TARIFF_PER_PORT = 5           # liman başına ticaret anlaşması geliri (%)

COMMERCE_LAND = ('att_effect_economy_gdp_mod_commerce_land', 'faction_to_region_own_unseen')
COMMERCE_SEA = ('att_effect_economy_gdp_mod_commerce_sea', 'faction_to_region_own_unseen')
TARIFF = ('att_effect_economy_trade_tariff_mod', 'faction_to_faction_own')
PUBLIC_ORDER_EFFECT = ('att_effect_public_order_base', 'faction_to_province_own')

GDP_ALL = ('att_effect_economy_gdp_mod_all', 'faction_to_region_own')
GROWTH_EFFECT = ('att_effects_province_growth_faction', 'faction_to_province_own')
RESEARCH = ('att_effect_technology_research_points_mod', 'faction_to_faction_own')
REPLENISHMENT_EFFECT = ('att_effect_force_all_campaign_replenishment_rate', 'faction_to_force_own')
RECRUITMENT_COST = ('att_effect_force_all_campaign_recruitment_cost_all', 'faction_to_force_own_unseen')

LOYALTY = ('att_effect_character_loyalty_mod_faction', 'faction_to_character_own')
INTEGRITY = ('att_effect_force_all_campaign_military_morale_factor_faction', 'faction_to_force_own')
MORALE_VS_NOMADS = ('att_effect_morale_against_nomads', 'faction_to_force_own')
RECRUIT_XP = ('att_effect_force_all_campaign_experience_base_all', 'faction_to_province_own_unseen')

# Selçuklu hikâye zinciri. Her olay kendi turunun başında tetiklenir (MK1212'de yılda 2 tur, 1. tur
# 1212 ilkbaharı); takvim mk_fact_seljuks.lua'ya bu listeden yazılır. Görsel ui/eventpics altında yoksa
# 'fallback' görseli kullanılır.
# Ödül paketleri: (anahtar, simge, başlık, açıklama, [(efekt, kapsam, değer)])
STORY_BUNDLES = [
    ('pb_bundle_seljuk_sinope', 'faction_leader_positive.png', 'The Conquest of Sinope',
     'Sinope has fallen and its harbour now serves the Sultanate. Merchants from the Crimea and the Pontic '
     'coast pay their dues to Seljuk officials.',
     [(*PUBLIC_ORDER_EFFECT, 3), (*GDP_ALL, 10)]),
    ('pb_bundle_seljuk_refugees', 'tax_growth_2.png', 'Refugees from the East',
     'Scholars, craftsmen and whole families fleeing the horde have found shelter in the lands of Rum.',
     [(*GROWTH_EFFECT, 3), (*RESEARCH, 10)]),
    ('pb_bundle_seljuk_walls', 'faction_leader_positive.png', 'Walls of the Sultanate',
     'The walls of Konya, Kayseri and Sivas have been rebuilt in stone. The people sleep easier behind them.',
     [(*PUBLIC_ORDER_EFFECT, 3), (*REPLENISHMENT_EFFECT, 15)]),
    ('pb_bundle_seljuk_frontier', 'faction_leader_positive.png', 'Call of the Frontier',
     'The Turkmen of the frontier have answered the Sultan\'s call, and their riders fill the ranks.',
     [(*RECRUITMENT_COST, -20), (*REPLENISHMENT_EFFECT, 10)]),
    ('pb_bundle_seljuk_illness', 'faction_leader_negative.png', 'The Sultan\'s Illness',
     'The Sultan lies ill in his palace, and the emirs are already choosing sides.',
     [(*PUBLIC_ORDER_EFFECT, -1)]),
    ('pb_bundle_seljuk_iqta', 'faction_leader_positive.png', 'The Emirs\' Iqta',
     'The great emirs hold rich iqta estates from the new Sultan and have sworn their oaths to him.',
     [(*LOYALTY, 2), (*PUBLIC_ORDER_EFFECT, 2), (*GDP_ALL, -5)]),
    ('pb_bundle_seljuk_ghulams', 'faction_leader_positive.png', 'The Sultan\'s Ghulams',
     'Slave soldiers raised in the palace and loyal to the Sultan alone guard the throne.',
     [(*INTEGRITY, 2), (*RECRUIT_XP, 1)]),
    ('pb_bundle_seljuk_crimea', 'tax_growth_4.png', 'Lord of the Black Sea',
     'Seljuk governors sit in the trading ports of the Crimea, and the Black Sea trade flows through Sinope.',
     [(*COMMERCE_SEA, 20), (*TARIFF, 10)]),
    ('pb_bundle_seljuk_alaiye', 'tax_growth_3.png', 'The Shipyard of Alaiye',
     'From the shipyard beneath the cliffs of Alaiye, Seljuk ships sail to Cyprus, Egypt and Venice.',
     [(*COMMERCE_SEA, 10), (*TARIFF, 5)]),
    ('pb_bundle_seljuk_hans', 'tax_growth_4.png', 'The Sultan\'s Hans',
     'A chain of great caravanserais, a day\'s journey apart, shelters the caravans that cross Anatolia.',
     [(*TARIFF, 20), (*COMMERCE_LAND, 15)]),
    ('pb_bundle_seljuk_khwarazm_alliance', 'faction_leader_positive.png', 'Alliance with the Khwarazmshah',
     'Khwarazmian veterans who know the Mongol way of war share their hard-won lessons with Seljuk commanders.',
     [(*MORALE_VS_NOMADS, 4), (*INTEGRITY, 1)]),
    ('pb_bundle_seljuk_eastern_watch', 'faction_leader_positive.png', 'Watch on the East',
     'The eastern garrisons are reinforced and drilled against raiders from beyond the mountains.',
     [(*REPLENISHMENT_EFFECT, 10), (*RECRUIT_XP, 1)]),
    ('pb_bundle_seljuk_scholars', 'tax_growth_3.png', 'The Sultan of Scholars',
     'Preachers, poets and students gather in the madrasas of Konya around the family of Baha al-Din Walad.',
     [(*RESEARCH, 15), (*PUBLIC_ORDER_EFFECT, 2)]),
    ('pb_bundle_seljuk_sultan_han', 'tax_growth_5.png', 'The Sultan Han',
     'The greatest caravanserai of Anatolia stands on the road between Konya and Aksaray.',
     [(*TARIFF, 10), (*COMMERCE_LAND, 10)]),
    ('pb_bundle_seljuk_yassi_chemen', 'faction_leader_positive.png', 'Veterans of Yassi Chemen',
     'The soldiers who broke the Khwarazmians return home as veterans, and the recruits want to be like them.',
     [(*INTEGRITY, 2), (*RECRUIT_XP, 1)]),
    ('pb_bundle_seljuk_babai_crushed', 'faction_leader_negative.png', 'The Revolt Crushed',
     'The rebels have been broken, but the Turkmen of the frontier will not soon forget it.',
     [(*PUBLIC_ORDER_EFFECT, -3), (*INTEGRITY, 1)]),
    ('pb_bundle_seljuk_babai_pardon', 'faction_leader_negative.png', 'The Tribes Pardoned',
     'Taxes on the frontier have been lowered and the tribes have returned to their pastures. The emirs whose '
     'lands were plundered resent the Sultan\'s leniency, and the treasury feels the loss.',
     [(*PUBLIC_ORDER_EFFECT, 2), (*GDP_ALL, -10), (*LOYALTY, -2)]),
    ('pb_bundle_seljuk_kose_dag_field', 'faction_leader_positive.png', 'The Host of Rum',
     'Emirs, ghulams, Turkmen and Frankish and Georgian mercenaries stand together against the horde.',
     [(*MORALE_VS_NOMADS, 6), (*INTEGRITY, 3), (*REPLENISHMENT_EFFECT, 20)]),
    ('pb_bundle_seljuk_kose_dag_walls', 'faction_leader_positive.png', 'Behind the Walls',
     'The Sultanate waits for the horde behind the stone walls of its cities.',
     [(*PUBLIC_ORDER_EFFECT, 3), (*REPLENISHMENT_EFFECT, 15)]),
    ('pb_bundle_seljuk_tribute', 'faction_leader_negative.png', 'Tribute to the Khan',
     'A heavy tribute is sent east each year. The people grumble at the taxes but are glad to be spared.',
     [(*PUBLIC_ORDER_EFFECT, 4), (*GDP_ALL, -10)]),
]

STORY_MISSIONS = [{
    'turn': 2, 'key': 'pb_mission_seljuk_sinope', 'image': 'pb_seljuk_sinope', 'fallback': 'pb_seljuk_sinope',
    'region': 'att_reg_bithynia_amasea', 'turns': 12, 'title': 'The Conquest of Sinope',
    'description': 'Sinope, the jewel of the Black Sea coast, is held by the Greeks. Whoever holds it controls the '
                   'trade between Anatolia and the northern lands. Sultan Kaykaus has resolved to take it, so that '
                   'Seljuk caravans may reach the sea in the north as they already do at Attaleia in the south.',
    'payloads': [('TREASURY', 'AMOUNT[6000]'), ('pb_bundle_seljuk_sinope', 'DURATION[10];GLOBAL')],
}, {
    'turn': 19, 'key': 'pb_mission_seljuk_crimea', 'image': 'pb_seljuk_crimea', 'fallback': 'pb_seljuk_sinope',
    'region': 'att_reg_sarmatia_europaea_chersonessus', 'turns': 16, 'title': 'The Crimean Expedition',
    'description': 'Kipchak raiders and Rus princes trouble the merchants of the Crimea, and Seljuk goods sold at '
                   'Sinope must cross the sea to reach them. The Sultan orders an expedition across the Black Sea '
                   'to seize the trading ports of the Crimea, as his armies did at Sudak.',
    'payloads': [('TREASURY', 'AMOUNT[5000]'), ('pb_bundle_seljuk_crimea', 'DURATION[20];GLOBAL')],
}]

STORY_INCIDENTS = [{
    'turn': 12, 'key': 'pb_incident_seljuk_mongol_threat', 'image': 'pb_seljuk_mongol_threat',
    'fallback': 'pb_seljuk_mongol_threat', 'title': 'A Storm in the East',
    'description': 'Merchants and refugees pour in from Khwarazm with terrible news: a horde from the eastern '
                   'steppes, led by a khan called Chinggis, is burning the great cities of Transoxiana. Scholars, '
                   'craftsmen and whole families seek shelter in the lands of Rum.',
    'payloads': [('pb_bundle_seljuk_refugees', 'DURATION[10];GLOBAL')],
}, {
    'turn': 15, 'key': 'pb_incident_seljuk_illness', 'image': 'pb_seljuk_illness', 'fallback': 'pb_seljuk_divan',
    'title': 'The Sultan Falls Ill',
    'description': 'Since the failed march on Aleppo, Sultan Kaykaus has been wasting away with consumption, and '
                   'his physicians say he will not live to see many more seasons. The emirs whisper about who will '
                   'follow him. If Kayqubad is to rule, name him heir in the family tree before the Sultan dies.',
    'payloads': [('pb_bundle_seljuk_illness', 'DURATION[4];GLOBAL')],
}, {
    'turn': 20, 'key': 'pb_incident_seljuk_alaiye', 'image': 'pb_seljuk_alaiye', 'fallback': 'pb_seljuk_sinope',
    'title': 'Kalon Oros Becomes Alaiye',
    'description': 'The Greek lord of the coastal fortress of Kalon Oros has surrendered to Sultan Kayqubad, who '
                   'has renamed it Alaiye after himself. A shipyard is being built beneath the cliffs, and the '
                   'Sultanate now has a second window on the Mediterranean.',
    'payloads': [('pb_bundle_seljuk_alaiye', 'DURATION[0];GLOBAL')],
}, {
    'turn': 33, 'key': 'pb_incident_seljuk_scholars', 'image': 'pb_seljuk_scholars', 'fallback': 'pb_seljuk_divan',
    'title': 'The Sultan of Scholars',
    'description': 'Baha al-Din Walad, the great preacher called the Sultan of Scholars, has arrived in Konya with '
                   'his family at the Sultan\'s invitation. His young son Jalal al-Din, who will one day be known '
                   'as Rumi, already draws students of his own. Konya is becoming a city of learning.',
    'payloads': [('pb_bundle_seljuk_scholars', 'DURATION[30];GLOBAL')],
}, {
    'turn': 35, 'key': 'pb_incident_seljuk_sultan_han', 'image': 'pb_seljuk_sultan_han',
    'fallback': 'pb_seljuk_caravanserai', 'title': 'The Sultan Han',
    'description': 'On the road between Konya and Aksaray, the largest caravanserai in Anatolia has been '
                   'completed. Its great carved portal welcomes caravans travelling from Tabriz to Attaleia.',
    'payloads': [('pb_bundle_seljuk_sultan_han', 'DURATION[0];GLOBAL')],
}, {
    'turn': 38, 'key': 'pb_incident_seljuk_yassi_chemen', 'image': 'pb_seljuk_yassi_chemen',
    'fallback': 'pb_seljuk_sinope', 'title': 'Victory at Yassi Chemen',
    'description': 'Near Erzincan, the armies of the Sultanate have routed Jalal ad-Din and his Khwarazmians. The '
                   'spoils of his camp are rich, and the Sultan\'s soldiers return home as veterans.',
    'payloads': [('TREASURY', 'AMOUNT[5000]'), ('pb_bundle_seljuk_yassi_chemen', 'DURATION[15];GLOBAL')],
}]

STORY_DILEMMAS = [{
    'turn': 12, 'key': 'pb_dilemma_seljuk_divan', 'image': 'pb_seljuk_divan', 'fallback': 'pb_seljuk_divan',
    'title': 'The Sultan\'s Divan',
    'description': 'The emirs gather before the Sultan. The horde has not yet reached Anatolia, but none doubt that '
                   'it will. Some urge that the walls of Konya, Kayseri and Sivas be rebuilt in stone; others say '
                   'the Turkmen of the frontier should be summoned and armed.',
    'choices': [
        ('FIRST', 'Raise the walls', 'Stone by stone, the walls of the great cities rise again.',
         [('TREASURY', 'AMOUNT[-4000]'), ('pb_bundle_seljuk_walls', 'DURATION[30];GLOBAL')]),
        ('SECOND', 'Summon the Turkmen', 'Riders from the frontier answer the Sultan\'s call.',
         [('TREASURY', 'AMOUNT[-2000]'), ('pb_bundle_seljuk_frontier', 'DURATION[20];GLOBAL')]),
    ],
}, {
    'turn': 17, 'key': 'pb_dilemma_seljuk_succession', 'image': 'pb_seljuk_succession', 'fallback': 'pb_seljuk_divan',
    'action': 'succession',
    'title': 'The Death of Kaykaus',
    'description': 'Sultan Kaykaus has died of consumption at the height of his power. His brother Kayqubad, whom '
                   'Kaykaus long kept far from power, has been raised to the throne. The emirs who once '
                   'backed Kaykaus watch the new Sultan closely. How will he secure the throne?',
    'choices': [
        ('FIRST', 'Grant the emirs iqta lands', 'The emirs receive rich estates and swear their oaths.',
         [('pb_bundle_seljuk_iqta', 'DURATION[20];GLOBAL')]),
        ('SECOND', 'Rely on the ghulam guard', 'The Sultan surrounds himself with soldiers loyal to him alone.',
         [('TREASURY', 'AMOUNT[-3000]'), ('pb_bundle_seljuk_ghulams', 'DURATION[20];GLOBAL')]),
    ],
}, {
    'turn': 25, 'key': 'pb_dilemma_seljuk_caravanserais', 'image': 'pb_seljuk_caravanserai',
    'fallback': 'pb_seljuk_caravanserai', 'title': 'The Sultan\'s Hans',
    'description': 'Trade along the Anatolian roads grows, but merchants fear bandits and harsh winters. The vizier '
                   'proposes a chain of great caravanserais, a day\'s journey apart, built and guarded by the state.',
    'choices': [
        ('FIRST', 'Build them', 'The great hans rise along the roads, and the caravans follow.',
         [('TREASURY', 'AMOUNT[-5000]'), ('pb_bundle_seljuk_hans', 'DURATION[0];GLOBAL')]),
        ('SECOND', 'Leave it to the merchants', 'The merchants build their own inns and pay the Sultan for the privilege.',
         [('TREASURY', 'AMOUNT[3000]')]),
    ],
}, {
    'turn': 31, 'key': 'pb_dilemma_seljuk_khwarazm_envoy', 'image': 'pb_seljuk_khwarazm_envoy',
    'fallback': 'pb_seljuk_divan', 'title': 'The Envoy of the Khwarazmshah',
    'description': 'Jalal ad-Din, the last Khwarazmshah, has carved out a new realm in the east after fleeing the '
                   'Mongols. His envoy proposes an alliance against the horde, but many at court fear the '
                   'Khwarazmian more than the Mongols, for his armies plunder friend and foe alike.',
    'choices': [
        ('FIRST', 'Accept the alliance', 'Gifts are exchanged, and Khwarazmian officers visit the Sultan\'s camps.',
         [('TREASURY', 'AMOUNT[-2000]'), ('pb_bundle_seljuk_khwarazm_alliance', 'DURATION[10];GLOBAL')]),
        ('SECOND', 'Refuse and guard the east', 'The envoy leaves empty-handed, and the eastern garrisons are reinforced.',
         [('pb_bundle_seljuk_eastern_watch', 'DURATION[10];GLOBAL')]),
    ],
}, {
    'turn': 57, 'key': 'pb_dilemma_seljuk_babai', 'image': 'pb_seljuk_babai', 'fallback': 'pb_seljuk_divan',
    'title': 'The Babai Revolt',
    'description': 'Baba Ishak, a dervish preacher, has raised the Turkmen of the frontier in revolt against the '
                   'Sultan\'s governors and taxes. His followers have taken Amasya and defeated the first armies '
                   'sent against them.',
    'choices': [
        ('FIRST', 'Crush the revolt', 'The rebels gather in arms near Amasya. An army must march to break them.',
         [('pb_bundle_seljuk_babai_crushed', 'DURATION[10];GLOBAL')]),
        ('SECOND', 'Lower the taxes and pardon the tribes', 'The tribes lay down their arms, but the emirs and the treasury pay the price.',
         [('TREASURY', 'AMOUNT[-6000]'), ('pb_bundle_seljuk_babai_pardon', 'DURATION[15];GLOBAL')]),
    ],
}, {
    'turn': 63, 'key': 'pb_dilemma_seljuk_kose_dag', 'image': 'pb_seljuk_kose_dag', 'fallback': 'pb_seljuk_mongol_threat',
    'title': 'The Road to Kose Dag',
    'description': 'A Mongol army under the general Baiju has taken Erzurum and marches into the Sultanate. The '
                   'Sultan has gathered his emirs, his ghulams and Frankish and Georgian mercenaries. History '
                   'remembers what befell the Sultanate when it met the Mongols at Kose Dag; this time the choice '
                   'is yours.',
    'choices': [
        ('FIRST', 'Meet them in the field', 'The host of Rum rides out to face the horde.',
         [('pb_bundle_seljuk_kose_dag_field', 'DURATION[10];GLOBAL')]),
        ('SECOND', 'Hold the fortresses', 'The Sultanate shuts its gates and waits for the storm to break.',
         [('pb_bundle_seljuk_kose_dag_walls', 'DURATION[20];GLOBAL')]),
        ('THIRD', 'Send tribute to the Khan', 'A heavy tribute is sent east, and the people are spared, for now.',
         [('TREASURY', 'AMOUNT[-15000]'), ('pb_bundle_seljuk_tribute', 'DURATION[30];GLOBAL')]),
    ],
}]

STORY_FIRST_ID = 8800000           # MK1212'nin kimlikleri 440000'in altında

# (anahtar, bonus_value_id'ler, kapsam, değer, (simge, negatif simge), öncelik, açıklama)
# Simgeler oyundaki eşdeğer efektlerden alındı; maliyet efektlerinde ters çevrilidir.
SIMPLE_EFFECTS = [
    ('gdp_all', ('gdp_mod_all',), 'faction_to_region_own', INCOME_PCT,
     ('wealth_positive.png', 'wealth_negative.png'), 162, 'Player bonus - Wealth: %+n% from all buildings'),
    ('research_rate', ('research_rate_mod',), 'faction_to_faction_own', RESEARCH_PCT,
     ('technology_positive.png', 'technology_negative.png'), 61, 'Player bonus - Research rate: %+n%'),
    ('public_order', ('province_public_order_happiness_building_positive_factor',), 'faction_to_province_own', PUBLIC_ORDER,
     ('public_order_positive.png', 'public_order_negative.png'), 5, 'Player bonus - Public order: %+n'),
    ('growth', ('province_development_growth_added_faction',), 'faction_to_province_own', GROWTH,
     ('growth_positive.png', 'growth_negative.png'), 30, 'Player bonus - Growth: %+n'),
    ('replenishment', ('replenishment_percentage_bonus',), 'faction_to_force_own', REPLENISHMENT,
     ('replenishment_positive.png', 'replenishment_negative.png'), 101, 'Player bonus - Replenishment: %+n%'),
    ('construction_cost', ('building_cost_mod', 'building_conversion_cost_mod'), 'faction_to_region_own',
     CONSTRUCTION_COST_PCT, ('construction_negative.png', 'construction_positive.png'), 101,
     'Player bonus - Construction cost: %+n%'),
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


def lua_list_length(path, name):
    body = re.search(name + r'\s*=\s*\{(.*?)\}', open(path, encoding='utf-8').read(), re.S).group(1)
    return len(re.findall(r'"[^"]+"', body))


def trade_bundles():
    """[(anahtar, simge, başlık, açıklama, [(efekt, kapsam, değer)])]"""
    cities = lua_list_length(TRADE_SCRIPT, 'PB_CARAVAN_CITIES')
    ports = lua_list_length(TRADE_SCRIPT, 'PB_PORTS')
    bundles = []
    for n in range(1, cities + 1):
        bundles.append((
            f'pb_bundle_seljuk_caravan_{n}', f'tax_growth_{min(n, 5)}.png', f'Silk Road: Caravan Cities ({n}/{cities})',
            f'Your caravans reach {n} of the {cities} great trade cities of the Anatolian Silk Road: Iconion, '
            'Kayseri, Ancyra, Malatya, Sis, Diyarbakir, Dvin and Tabriz.',
            [(*COMMERCE_LAND, CARAVAN_COMMERCE_PER_CITY * n), (*TARIFF, CARAVAN_TARIFF_PER_CITY * n)]))
    for n in range(1, ports + 1):
        bundles.append((
            f'pb_bundle_seljuk_ports_{n}', f'tax_growth_{min(n, 5)}.png', f'Silk Road: Sea Gates ({n}/{ports})',
            f'You hold {n} of the {ports} sea gates of Anatolian trade: Sinope, Attaleia, Smyrna and Caffa.',
            [(*COMMERCE_SEA, PORT_COMMERCE_PER_PORT * n), (*TARIFF, PORT_TARIFF_PER_PORT * n)]))
    bundles.append((
        'pb_bundle_seljuk_caravanserai', 'tax_growth_3.png', 'Seljuk Caravanserais',
        'A chain of state caravanserais shelters merchants along the roads, and the Sultan repays the losses '
        'of those robbed on them.',
        [(*TARIFF, 10), (*PUBLIC_ORDER_EFFECT, 1)]))
    bundles.append((
        'pb_bundle_seljuk_two_seas', 'tax_growth_5.png', 'Between Two Seas',
        'With Sinope on the Black Sea and Attaleia on the Mediterranean, the goods of the north and the south '
        'cross Anatolia under Seljuk protection.',
        [(*TARIFF, 15), (*COMMERCE_LAND, 10)]))
    return bundles


def table_schema(data_dir, table):
    """Kurulu dosyalardaki en yeni (başlık, sürüm)."""
    return max((read_tsv(path)[:2] for path in table_files(data_dir, table)), key=lambda hv: hv[1])


EVENTPICS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui', 'eventpics')


def event_image(event):
    """Olayın görseli henüz yoksa yedek görsel."""
    if os.path.exists(os.path.join(EVENTPICS, event['image'] + '.png')):
        return event['image']
    return event['fallback']


def write_story_schedule():
    """mk_fact_seljuks.lua'daki takvim bloğunu olay listelerinden yeniden yazar."""
    events = ([(m['turn'], 'mission', m['key'], m['region']) for m in STORY_MISSIONS] +
              [(i['turn'], 'incident', i['key'], None) for i in STORY_INCIDENTS] +
              [(d['turn'], 'dilemma', d['key'], None) for d in STORY_DILEMMAS] +
              [(d['turn'], 'action', d['action'], None) for d in STORY_DILEMMAS if 'action' in d])
    # Aynı turda önce betik eylemi (ör. tahta geçiş), sonra görev, haber ve en son karar gelir.
    order = {'action': -1, 'mission': 0, 'incident': 1, 'dilemma': 2}
    lines = ['PB_STORY_EVENTS = {']
    for turn, kind, key, region in sorted(events, key=lambda e: (e[0], order[e[1]])):
        unless = f', unless_owned = "{region}"' if region else ''
        lines.append(f'\t{{ turn = {turn}, kind = "{kind}", key = "{key}"{unless} }},')
    lines.append('};')
    begin, finish = '-- BEGIN STORY SCHEDULE (build.py)\n', '-- END STORY SCHEDULE\n'
    lua = open(TRADE_SCRIPT, encoding='utf-8').read()
    head, rest = lua.split(begin)
    _, tail = rest.split(finish)
    with open(TRADE_SCRIPT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(head + begin + '\n'.join(lines) + '\n' + finish + tail)


def payload_key(payload):
    """Efekt paketleri cdir_events_payloads üzerinden bağlanır; TREASURY gibi hazır anahtarlar olduğu gibi kalır."""
    return payload.replace('pb_bundle_', 'pb_payload_') if payload.startswith('pb_bundle_') else payload


def write_story_tables(data_dir, out_dir, name, loc):
    ids = iter(range(STORY_FIRST_ID, STORY_FIRST_ID + 100000))
    tables = {}

    def add(table, row):
        tables.setdefault(table, []).append(row)

    for m in STORY_MISSIONS:
        add('missions_tables', {'key': m['key'], 'generate': 'false', 'localised_description': m['description'],
                                'localised_title': m['title'], 'mission_type': 'CAPTURE_REGIONS',
                                'ui_icon': 'rom_event_mission.png', 'ui_image': event_image(m), 'prioritised': 'true',
                                'event_category': 'Military'})
        options = [('CND_CAMPAIGN', 'main_attila'), ('GEN_TARGET_REGION', ''), ('GEN_CND_REGION', m['region']),
                   ('GEN_CND_NOT_OWNS', ''), ('VAR_CHANCE', '100'), ('VAR_MISSION_LENGTH_MIN', str(m['turns'])),
                   ('VAR_MISSION_LENGTH_MAX', str(m['turns']))]
        for option, value in options:
            add('cdir_events_mission_option_junctions_tables',
                {'id': str(next(ids)), 'mission_key': m['key'], 'option_key': option, 'value': value})
        for payload, value in m['payloads'] + [('TARGET', 'EVENT')]:
            add('cdir_events_mission_payloads_tables', {'id': str(next(ids)), 'mission_key': m['key'],
                                                         'payload_key': payload_key(payload),
                                                         'status_key': 'SUCCESS', 'value': value})
        add('cdir_events_mission_issuer_junctions_tables', {'issuer_key': 'CLAN_ELDERS', 'mission_key': m['key']})
        loc.append([f'missions_localised_title_{m["key"]}', m['title'], 'true'])
        loc.append([f'missions_localised_description_{m["key"]}', m['description'], 'true'])

    for i in STORY_INCIDENTS:
        add('incidents_tables', {'key': i['key'], 'generate': 'false', 'ui_icon': 'message_generic_news.png',
                                 'ui_image': event_image(i), 'prioritised': 'true', 'event_category': 'Historical'})
        for option, value in (('CND_CAMPAIGN', 'main_attila'), ('GEN_TARGET_NONE', ''), ('VAR_CHANCE', '100')):
            add('cdir_events_incident_option_junctions_tables',
                {'id': str(next(ids)), 'incident_key': i['key'], 'option_key': option, 'value': value})
        for payload, value in i['payloads']:
            add('cdir_events_incident_payloads_tables', {'id': str(next(ids)), 'incident_key': i['key'],
                                                          'payload_key': payload_key(payload), 'value': value})
        loc.append([f'incidents_localised_title_{i["key"]}', i['title'], 'true'])
        loc.append([f'incidents_localised_description_{i["key"]}', i['description'], 'true'])

    for d in STORY_DILEMMAS:
        add('dilemmas_tables', {'key': d['key'], 'generate': 'false', 'localised_description': d['description'],
                                'localised_title': d['title'], 'ui_icon': 'rom_event_document.png',
                                'ui_image': event_image(d), 'prioritized': 'true', 'event_category': 'Historical'})
        for option, value in (('CND_CAMPAIGN', 'main_attila'), ('GEN_TARGET_NONE', ''), ('VAR_CHANCE', '100')):
            add('cdir_events_dilemma_option_junctions_tables',
                {'id': str(next(ids)), 'dilemma_key': d['key'], 'option_key': option, 'value': value})
        for choice, label, outcome, payloads in d['choices']:
            add('cdir_events_dilemma_choice_details_tables', {'choice_key': choice, 'dilemma_key': d['key']})
            for payload, value in payloads:
                add('cdir_events_dilemma_payloads_tables', {'id': str(next(ids)), 'choice_key': choice,
                                                             'dilemma_key': d['key'],
                                                             'payload_key': payload_key(payload), 'value': value})
            prefix = 'cdir_events_dilemma_choice_details_localised_choice'
            loc.append([f'{prefix}_label_{d["key"]}{choice}', label, 'true'])
            loc.append([f'{prefix}_title_{d["key"]}{choice}', outcome, 'true'])
        loc.append([f'dilemmas_localised_title_{d["key"]}', d['title'], 'true'])
        loc.append([f'dilemmas_localised_description_{d["key"]}', d['description'], 'true'])

    for key, *_ in STORY_BUNDLES:
        add('cdir_events_payloads_tables', {'payload_key': payload_key(key), 'effect_bundle_key': key})

    for table, rows in tables.items():
        header, version = table_schema(data_dir, table)
        write_tsv(out_dir, table, name, version, header, [[row.get(c, '') for c in header] for row in rows])


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

    for key, bonuses, scope, value, icons, priority, text in SIMPLE_EFFECTS:
        effect = f'{PREFIX}_effect_{key}'
        add_effect(effect, icons, priority, text)
        basic.extend([effect, bonus] for bonus in bonuses)
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

    # Keykâvus'un portresi.
    arts_header, arts_version, arts = effective_rows(data_dir, 'campaign_character_arts_tables', ['id'])
    art_set_col, uniform_col = arts_header.index('art_set_id'), arts_header.index('uniform')
    art_rows = [row[:uniform_col] + [KAYKAUS_UNIFORM] + row[uniform_col + 1:] for row in arts.values()
                if row[art_set_col] == KAYKAUS_ART_SET and row[uniform_col] == SULTAN_UNIFORM]
    write_tsv(out_dir, 'campaign_character_arts_tables', name, arts_version, arts_header, art_rows)
    uniforms_header, uniforms_version, uniforms = effective_rows(data_dir, 'agent_uniforms_tables',
                                                                 ['uniform_name'])
    uniform = dict(zip(uniforms_header, uniforms[(SULTAN_UNIFORM,)]))
    uniform['uniform_name'] = uniform['campaign_porthole_filename'] = KAYKAUS_UNIFORM
    uniform['campaign_politician_filename'] = KAYKAUS_UNIFORM
    write_tsv(out_dir, 'agent_uniforms_tables', name, uniforms_version, uniforms_header,
              [[uniform[c] for c in uniforms_header]])

    # Selçuklu Ticaret Ağı ve hikâye ödül paketleri.
    bundles = trade_bundles() + STORY_BUNDLES
    write_story_tables(data_dir, out_dir, name, loc)
    write_story_schedule()
    write_tsv(out_dir, 'effect_bundles_tables', name, 1,
              ['key', 'localised_description', 'localised_title', 'ui_icon', 'bundle_target'],
              [[key, 'Placeholder', title, icon, 'faction'] for key, icon, title, _, _ in bundles])
    write_tsv(out_dir, 'effect_bundles_to_effects_junctions_tables', name, 2,
              ['effect_bundle_key', 'effect_key', 'effect_scope', 'value', 'advancement_stage'],
              [[key, effect, scope, f'{value:.4f}', 'start_turn_completed']
               for key, _, _, _, contents in bundles for effect, scope, value in contents])
    for key, _, title, description, _ in bundles:
        loc.append([f'effect_bundles_localised_title_{key}', title, 'true'])
        loc.append([f'effect_bundles_localised_description_{key}', description, 'true'])

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
    print(f'Keykâvus portre satırı: {len(art_rows)}')
    print(f'Ticaret ve hikâye paketleri: {len(bundles)}; görev {len(STORY_MISSIONS)}, haber {len(STORY_INCIDENTS)}, '
          f'karar {len(STORY_DILEMMAS)}')


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
    # TSV dosyaları pack içindeki yerlerini kendi başlık satırlarından alır; betik ve görsel klasörleri açıkça verilir.
    campaigns = os.path.dirname(os.path.dirname(os.path.dirname(TRADE_SCRIPT)))
    ui = os.path.join(os.path.dirname(campaigns), 'ui')
    for folder in (f'{os.path.join(tsv_dir, "db")};', f'{os.path.join(tsv_dir, "text")};', f'{campaigns};campaigns',
                   f'{ui};ui'):
        subprocess.run([args.rpfm, '-g', 'attila', 'pack', 'add', '-p', pack, '-t', args.schema, '-F', folder],
                       check=True)
    print(f'Pack: {pack}')


if __name__ == '__main__':
    main()
