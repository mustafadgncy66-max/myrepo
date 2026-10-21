-- MK1212 Oyuncu Bonusu: Selçuklu Ticaret Ağı.
-- MK1212, oyuncunun fraksiyonuna ait bu dosyayı (factions/<fraksiyon>.lua) otomatik yükler; bu yüzden
-- yalnızca Selçuklu oynanırken çalışır. Paket anahtarları build.py'deki tablolarla eşleşir.

-- MK1212'nin fraksiyon betiklerinde olduğu gibi, genel betik ortamına erişim için gerekli.
setfenv(1, _G.script_env);

local SELJUKS = "mk_fact_seljuks";

-- Oyun klasöründeki pb_seljuk_log.txt dosyasına yazar; betiğin oyunda ne yaptığını görmek için.
local LOG_FILE = "pb_seljuk_log.txt";

-- Kampanya betik ortamında io görünmeyebilir; Lua'nın yüklü kütüphanelerinden alınır.
local iolib = io or (package and package.loaded and package.loaded.io);

local function pb_log(text)
	local _, turn = pcall(function() return cm:model():turn_number() end);

	pcall(function()
		local file = iolib.open(LOG_FILE, "a");
		file:write("[" .. tostring(turn) .. "] " .. tostring(text) .. "\n");
		file:close();
	end);
end

-- Bir adımı çalıştırır; hata olursa kaydeder ve sonraki adımlara devam edilir.
local function try_step(name, fn, ...)
	local ok, err = pcall(fn, ...);

	if not ok then
		pb_log(name .. " failed: " .. tostring(err));
	end
end

-- Anadolu İpek Yolu'nun kervan şehirleri: Konya, Kayseri, Ankara, Malatya, Sis (Ayas limanı),
-- Diyarbakır, Dvin (Erzurum yolu) ve Tebriz.
PB_CARAVAN_CITIES = {
	"att_reg_cilicia_iconium",
	"att_reg_cappadocia_caesarea_eusebia",
	"att_reg_bithynia_ancyra",
	"att_reg_cappadocia_melitene",
	"att_reg_cilicia_tarsus",
	"att_reg_osroene_amida",
	"att_reg_armenia_duin",
	"att_reg_media_atropatene_ganzaga"
};

-- Deniz kapıları: Sinop (Karadeniz), Antalya (Akdeniz), İzmir (Ege), Kefe (Kırım).
PB_PORTS = {
	"att_reg_bithynia_amasea",
	"att_reg_cilicia_myra",
	"att_reg_asia_ephesus",
	"att_reg_sarmatia_europaea_chersonessus"
};

local SINOPE = "att_reg_bithynia_amasea";
local ATTALEIA = "att_reg_cilicia_myra";
local CARAVANSERAI_MIN_CITIES = 4;

local function owned_regions(faction)
	local owned = {};
	local regions = faction:region_list();

	for i = 0, regions:num_items() - 1 do
		owned[regions:item_at(i):name()] = true;
	end

	return owned;
end

local function count_owned(owned, list)
	local n = 0;

	for i = 1, #list do
		if owned[list[i]] then
			n = n + 1;
		end
	end

	return n;
end

-- Kademeli paketlerden yalnızca n. olanı etkin bırakır.
local function set_tier(prefix, max, n, faction_name)
	for i = 1, max do
		cm:remove_effect_bundle(prefix .. i, faction_name);
	end

	if n > 0 then
		cm:apply_effect_bundle(prefix .. n, faction_name, 0);
	end
end

local function set_bundle(key, active, faction_name)
	cm:remove_effect_bundle(key, faction_name);

	if active then
		cm:apply_effect_bundle(key, faction_name, 0);
	end
end

function PB_Seljuk_Trade_Update(faction)
	local faction_name = faction:name();
	local owned = owned_regions(faction);
	local cities = count_owned(owned, PB_CARAVAN_CITIES);

	set_tier("pb_bundle_seljuk_caravan_", #PB_CARAVAN_CITIES, cities, faction_name);
	set_tier("pb_bundle_seljuk_ports_", #PB_PORTS, count_owned(owned, PB_PORTS), faction_name);
	set_bundle("pb_bundle_seljuk_caravanserai", cities >= CARAVANSERAI_MIN_CITIES, faction_name);
	set_bundle("pb_bundle_seljuk_two_seas", owned[SINOPE] == true and owned[ATTALEIA] == true, faction_name);
end

-- Selçuklu hikâye zinciri (MK1212'de yılda 2 tur, 1. tur 1212 ilkbaharı). Her olay kendi turunda bir kez
-- tetiklenir; FactionTurnStart her tur bir kez geldiği için ayrıca kayıt tutmaya gerek yoktur.
-- Aşağıdaki takvim build.py tarafından olay listelerinden yazılır; elle düzenlemeyin.
-- BEGIN STORY SCHEDULE (build.py)
PB_STORY_EVENTS = {
	{ turn = 2, kind = "mission", key = "pb_mission_seljuk_sinope", unless_owned = "att_reg_bithynia_amasea" },
	{ turn = 12, kind = "incident", key = "pb_incident_seljuk_mongol_threat" },
	{ turn = 12, kind = "dilemma", key = "pb_dilemma_seljuk_divan" },
	{ turn = 15, kind = "incident", key = "pb_incident_seljuk_illness" },
	{ turn = 17, kind = "action", key = "succession" },
	{ turn = 17, kind = "dilemma", key = "pb_dilemma_seljuk_succession" },
	{ turn = 19, kind = "mission", key = "pb_mission_seljuk_crimea", unless_owned = "att_reg_sarmatia_europaea_chersonessus" },
	{ turn = 20, kind = "incident", key = "pb_incident_seljuk_alaiye" },
	{ turn = 25, kind = "dilemma", key = "pb_dilemma_seljuk_caravanserais" },
	{ turn = 31, kind = "dilemma", key = "pb_dilemma_seljuk_khwarazm_envoy" },
	{ turn = 33, kind = "incident", key = "pb_incident_seljuk_scholars" },
	{ turn = 35, kind = "incident", key = "pb_incident_seljuk_sultan_han" },
	{ turn = 38, kind = "incident", key = "pb_incident_seljuk_yassi_chemen" },
	{ turn = 57, kind = "dilemma", key = "pb_dilemma_seljuk_babai" },
	{ turn = 63, kind = "dilemma", key = "pb_dilemma_seljuk_kose_dag" },
};
-- END STORY SCHEDULE

-- Keykâvus'un ölümü (1220): MK1212'de Keykubad aile ağacında zaten vardır. Keykâvus ölür (aile ağacında
-- ölü görünür) ve tahta veliaht geçer. Oyuncu Keykubad'ı daha önce veliaht yapmış olmalıdır.
-- Keykubad ölmüşse MK1212'nin papa değişiminde yaptığı gibi yeni bir Keykubad veliaht olarak eklenir.
local KAYKAUS_NAME = "names_name_2147363192";    -- "Kaikaus"
local KAYQUBAD_NAME = "names_name_2147363203";   -- "Kaiqobad"
local KAYQUBAD_AGE = 32;
local KAYQUBAD_ART_SET = "mk_campaign_sel_t1_general_06";
-- Keykubad'ın özellikleri: oyunun kendi özellikleri, en yüksek seviyeleri için gereken puanla
-- (character_trait_levels: 3. seviye 6 puan, tek seviyeliler 2 puan). force_add_trait her çağrıda 1 puan verir.
-- Komutan seti oyunun başından, sultan seti tahta geçince verilir.
local KAYQUBAD_COMMANDER_TRAITS = {
	{"att_trait_general_military_all_strategist", 6},          -- Master Strategist: kurnazlık +3
	{"att_trait_general_military_army_all_attacker_good", 6},  -- Superior Attacker: saldırıda moral +15
	{"att_trait_general_military_army_all_defender_good", 6},  -- Superior Defender: savunmada moral +15
	{"att_trait_general_military_army_all_besieger_good", 6},  -- Into the Breach!: kuşatmada moral +15
	{"att_trait_general_military_all_high_casualties", 6},     -- Take No Prisoners!: hasar +%15
	{"att_trait_general_personality_all_bravery", 6},          -- Utterly Fearless: gayret +3, moral +4
	{"att_trait_all_personality_all_energetic", 6},            -- Vital: yetki +2, kurnazlık +1, gayret +3
	{"att_trait_general_government_all_military_admin", 6},    -- Military Secretary: askere alma -%15
};
local KAYQUBAD_SULTAN_TRAITS = {
	{"att_trait_general_personality_all_honest", 6},           -- Upright: yolsuzluk -%15, sadakat +2
	{"att_trait_general_government_all_architect", 6},         -- inşa maliyeti -%15 (valisi olduğu eyalet)
	{"att_trait_all_personality_all_innate_charismatic", 2},   -- yetki +1
};

local function find_character(faction, forename)
	local characters = faction:character_list();

	for i = 0, characters:num_items() - 1 do
		local character = characters:item_at(i);

		if not character:is_null_interface() and character:get_forename() == forename then
			return character;
		end
	end
end

-- Bir özellik setini hedef puanlara tamamlar; hepsi bir tur başında hedefte görülünce bir daha bakılmaz.
local function give_traits(character, traits, flag)
	if cm:get_saved_value(flag) then
		return;
	end

	local lookup = "character_cqi:" .. character:command_queue_index();
	local missing = 0;

	for i = 1, #traits do
		local trait, target = traits[i][1], traits[i][2];
		local points = math.max(character:trait_points(trait) or 0, 0);

		if points < target then
			pb_log("traits: " .. trait .. " " .. points .. " -> " .. target .. " for " .. lookup);
			for _ = points + 1, target do
				cm:force_add_trait(lookup, trait, false);
			end
			missing = missing + 1;
		end
	end

	if missing == 0 then
		pb_log("traits: " .. flag .. " complete");
		cm:set_saved_value(flag, true);
	end
end

local function give_kayqubad_traits(faction)
	local kayqubad = find_character(faction, KAYQUBAD_NAME);

	if not kayqubad then
		return;
	end

	give_traits(kayqubad, KAYQUBAD_COMMANDER_TRAITS, "pb_seljuk_kayqubad_commander_traits");

	if faction:has_faction_leader() and faction:faction_leader():get_forename() == KAYQUBAD_NAME then
		give_traits(kayqubad, KAYQUBAD_SULTAN_TRAITS, "pb_seljuk_kayqubad_sultan_traits");
	end
end

local function succession(faction)
	if cm:get_saved_value("pb_seljuk_succession_done") then
		return;
	end

	cm:set_saved_value("pb_seljuk_succession_done", true);

	-- Keykâvus daha önce öldüyse tarih zaten ilerlemiştir.
	if not faction:has_faction_leader() or faction:faction_leader():get_forename() ~= KAYKAUS_NAME then
		give_kayqubad_traits(faction);
		return;
	end

	if not find_character(faction, KAYQUBAD_NAME) then
		cm:spawn_character_into_family_tree(
			SELJUKS,			-- Faction Key
			KAYQUBAD_NAME,		-- Forename Key
			"",					-- Family Name Key
			"",					-- Clan Name Key
			"",					-- Other Name Key
			KAYQUBAD_AGE,		-- Age
			true,				-- Is Male?
			"",					-- Father Lookup
			"",					-- Mother Lookup
			false,				-- Is Immortal?
			KAYQUBAD_ART_SET,	-- Art Set ID
			true,				-- Make Heir?
			false				-- Is Attila?
		);
	end

	local kaykaus_cqi = faction:faction_leader():command_queue_index();
	cm:set_character_immortality("character_cqi:" .. kaykaus_cqi, false);
	cm:kill_character("character_cqi:" .. kaykaus_cqi, false, false);

	give_kayqubad_traits(cm:model():world():faction_by_key(SELJUKS));
end

-- Babai İsyanı (1240): "Bastır" seçilirse Amasya çevresinde Türkmen isyancılarından bir ordu çıkar.
local SEPARATISTS = "mk_fact_separatists_seljuks";
local BABAI_DILEMMA = "pb_dilemma_seljuk_babai";
local BABAI_REGIONS = {
	"att_reg_bithynia_amasea",				-- Amasya (oyunda Sinop bölgesi)
	"att_reg_bithynia_ancyra",
	"att_reg_cappadocia_caesarea_eusebia",
	"att_reg_cilicia_iconium"
};
local BABAI_UNITS = "mk_rum_t1_uc_turkleri,mk_rum_t1_uc_turkleri,mk_rum_t1_uc_turkleri,"
	.. "mk_rum_t1_ghazi_horse_archers,mk_rum_t1_ghazi_horse_archers,mk_rum_t1_ghazi_horse_archers,"
	.. "mk_rum_t1_ghazi_archers,mk_rum_t1_ghazi_archers,mk_rum_t1_ghazi_spearmen,mk_rum_t1_ghazi_spearmen,"
	.. "mk_rum_t1_ghazi_swordsmen,mk_rum_t1_ghazi_swordsmen,mk_rum_t1_hasher,mk_rum_t1_hasher";
-- Yerleşimin üstüne ordu çıkarılamaz; sırayla yakındaki karelerde denenir.
local BABAI_OFFSETS = { {4, 0}, {-4, 0}, {0, 4}, {0, -4}, {6, 6}, {-6, -6}, {6, -6}, {-6, 6} };

local function babai_army()
	if cm:get_saved_value("pb_seljuk_babai_army") then
		return;
	end

	cm:set_saved_value("pb_seljuk_babai_army", true);

	local owned = owned_regions(cm:model():world():faction_by_key(SELJUKS));
	local region_key = nil;

	for i = 1, #BABAI_REGIONS do
		if owned[BABAI_REGIONS[i]] then
			region_key = BABAI_REGIONS[i];
			break;
		end
	end

	if not region_key then
		region_key = next(owned);
	end

	if not region_key then
		return;
	end

	local settlement = cm:model():world():region_manager():region_by_key(region_key):settlement();
	local x, y = settlement:logical_position_x(), settlement:logical_position_y();
	local spawned = false;

	local function try_spawn(i)
		if spawned or i > #BABAI_OFFSETS then
			return;
		end

		cm:create_force(SEPARATISTS, BABAI_UNITS, region_key, x + BABAI_OFFSETS[i][1], y + BABAI_OFFSETS[i][2],
			"pb_babai_rebels_" .. i, true,
			function(cqi)
				spawned = true;
				cm:force_declare_war(SEPARATISTS, SELJUKS);
			end
		);

		cm:callback(function() try_spawn(i + 1) end, 0.5);
	end

	try_spawn(1);
end

local STORY_ACTIONS = { succession = succession };

-- Hızlı test: mk1212_hizli_test.pack yüklüyse olaylar o pack'teki pb_seljuk_test.lua'nın verdiği kadar
-- tur erken gelir. Pack yoksa require başarısız olur ve takvim değişmez.
local test_ok, test_settings = pcall(require, "pb_seljuk_test");
local STORY_TURN_OFFSET = test_ok and type(test_settings) == "table" and test_settings.turn_offset or 0;

function PB_Seljuk_Story(faction)
	local turn = cm:model():turn_number() + STORY_TURN_OFFSET;
	local owned = nil;

	for i = 1, #PB_STORY_EVENTS do
		local event = PB_STORY_EVENTS[i];

		if event.turn == turn then
			owned = owned or owned_regions(faction);

			-- Hedef bölge zaten bizdeyse görev verilmez.
			if not (event.unless_owned and owned[event.unless_owned]) then
				pb_log("story: " .. event.kind .. " " .. event.key);

				if event.kind == "action" then
					STORY_ACTIONS[event.key](faction);
				elseif event.kind == "mission" then
					cm:trigger_mission(SELJUKS, event.key);
				elseif event.kind == "incident" then
					cm:trigger_incident(SELJUKS, event.key);
				else
					cm:trigger_dilemma(SELJUKS, event.key);
				end
			end
		end
	end
end

cm:add_listener(
	"DilemmaChoiceMadeEvent_PB_Seljuk_Babai",
	"DilemmaChoiceMadeEvent",
	function(context) return context:dilemma() == BABAI_DILEMMA and context:choice() == 0 end,
	function(context) babai_army() end,
	true
);

cm:add_listener(
	"FactionTurnStart_PB_Seljuk_Trade",
	"FactionTurnStart",
	function(context) return context:faction():name() == SELJUKS end,
	function(context)
		local faction = context:faction();
		pb_log("turn start");
		try_step("trade", PB_Seljuk_Trade_Update, faction);
		try_step("story", PB_Seljuk_Story, faction);
		try_step("traits", give_kayqubad_traits, faction);
	end,
	true
);

-- Kayıt yüklenince ya da kampanya başlayınca beklemeden uygula; olmazsa ilk tur başında uygulanır.
-- Özellikler arayüz kurulurken eklenemez, bu yüzden biraz sonra denenir.
pb_log("loaded, story turn offset " .. STORY_TURN_OFFSET);
try_step("initial trade", function() PB_Seljuk_Trade_Update(cm:model():world():faction_by_key(SELJUKS)) end);
cm:callback(function()
	try_step("initial traits", function() give_kayqubad_traits(cm:model():world():faction_by_key(SELJUKS)) end);
end, 1);
