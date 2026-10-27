// このファイルは生成物です（tools/nightrunner/gen_nr_data_js.py）。直接編集しないでください。
// BP（blocks/ items/）の JSON を走査した結果。core/components.js が system.beforeEvents.startup で全部を登録し、
// 各モジュールが onBlockComponent / onItemComponent で足したフックへ配る。UNTICKED_BLOCKS は minecraft:tick の無いブロック
// （そこで使う名前に onTick を登録すると実機はコンテンツエラー）
/** @type {string[]} */
export const BLOCK_COMPONENTS = ["nr:ambient_fx","nr:craft_bench","nr:fire_barrel","nr:knockable","nr:landing","nr:multiblock","nr:random_variant","nr:stash","nr:street_lamp","nr:trap","nr:uv_lamp","nr:zipline"];
/** @type {string[]} */
export const ITEM_COMPONENTS = ["nr:weapon"];
/** @type {Record<string, any>} */
export const BLOCK_COMPONENT_USERS = {"nr:ambient_fx":["nr:gore_remains","nr:uv_shroom_patch"],"nr:craft_bench":["nr:crafting_bench"],"nr:fire_barrel":["nr:fire_barrel"],"nr:knockable":["nr:traffic_cone"],"nr:landing":["nr:trash_bags"],"nr:multiblock":["nr:street_lamp_base","nr:street_lamp_head","nr:street_lamp_pole","nr:water_tower_leg"],"nr:random_variant":["nr:blood_pool","nr:debris_scatter","nr:gore_remains","nr:graffiti_panel","nr:road_sign","nr:rubble_pile","nr:street_lamp_pole"],"nr:stash":["nr:med_cabinet","nr:survivor_stash"],"nr:street_lamp":["nr:street_lamp_head"],"nr:trap":["nr:barbed_wire","nr:bear_trap","nr:electric_trap","nr:fuel_canister","nr:gas_pipe","nr:oil_puddle","nr:spike_trap","nr:tripwire_mine","nr:uv_trap"],"nr:uv_lamp":["nr:uv_lamp"],"nr:zipline":["nr:zipline_anchor"]};
/** @type {Record<string, any>} */
export const ITEM_COMPONENT_USERS = {"nr:weapon":["nr:w_buzzsaw_glaive","nr:w_claw_hammer","nr:w_cleaver","nr:w_combat_knife","nr:w_crowbar","nr:w_fire_axe","nr:w_hatchet","nr:w_kukri","nr:w_leaf_spring_greatsword","nr:w_machete","nr:w_nail_bat","nr:w_pipe_mace","nr:w_pipe_wrench","nr:w_police_baton","nr:w_scrap_katana","nr:w_scythe","nr:w_sickle"]};
/** @type {Record<string, any>} */
export const UNTICKED_BLOCKS = {"nr:craft_bench":["nr:crafting_bench"],"nr:knockable":["nr:traffic_cone"],"nr:landing":["nr:trash_bags"],"nr:multiblock":["nr:street_lamp_base","nr:street_lamp_pole","nr:water_tower_leg"],"nr:random_variant":["nr:blood_pool","nr:debris_scatter","nr:graffiti_panel","nr:road_sign","nr:rubble_pile","nr:street_lamp_pole"],"nr:stash":["nr:med_cabinet","nr:survivor_stash"],"nr:zipline":["nr:zipline_anchor"]};
