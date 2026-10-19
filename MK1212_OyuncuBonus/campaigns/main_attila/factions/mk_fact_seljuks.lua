-- MK1212 Oyuncu Bonusu: Selçuklu Ticaret Ağı.
-- MK1212, oyuncunun fraksiyonuna ait bu dosyayı (factions/<fraksiyon>.lua) otomatik yükler; bu yüzden
-- yalnızca Selçuklu oynanırken çalışır. Paket anahtarları build.py'deki tablolarla eşleşir.

-- MK1212'nin fraksiyon betiklerinde olduğu gibi, genel betik ortamına erişim için gerekli.
setfenv(1, _G.script_env);

local SELJUKS = "mk_fact_seljuks";

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

cm:add_listener(
	"FactionTurnStart_PB_Seljuk_Trade",
	"FactionTurnStart",
	function(context) return context:faction():name() == SELJUKS end,
	function(context) PB_Seljuk_Trade_Update(context:faction()) end,
	true
);

-- Kayıt yüklenince ya da kampanya başlayınca beklemeden uygula; olmazsa ilk tur başında uygulanır.
local ok, err = pcall(function()
	PB_Seljuk_Trade_Update(cm:model():world():faction_by_key(SELJUKS));
end);

if not ok then
	output("PB Seljuk trade: initial update failed: " .. tostring(err));
end
