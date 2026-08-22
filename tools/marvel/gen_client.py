# -*- coding: utf-8 -*-
"""クライアントエンティティとアタッチャブル。

ここが「モデル・テクスチャ・アニメーション」を実際に結びつける層。
アニメーションの短縮名は、コントローラが参照する名前と一字一句合っている
必要があるので、マップは手書きせず、下の定数から機械的に組み立てる。
"""
from __future__ import annotations

import _path  # noqa: F401

import contract as K  # noqa: E402
from common import write_json  # noqa: E402

A = f"animation.{K.NS}."


def a(group, name):
    return K.anim(group, name)


LOOK = f"animation.{K.NS}.look_at_target"

#: 人型 NPC が要るアニメーションの短縮名 -> 実体
HUMANOID_ANIMS = {
    "look": LOOK,
    "idle": a("humanoid", "idle"),
    "walk": a("humanoid", "walk"),
    "run": a("humanoid", "run"),
    "air": a("humanoid", "air"),
    "attack": a("humanoid", "attack"),
    "hurt": a("humanoid", "hurt"),
    "death": a("humanoid", "death"),
    "general": K.ctrl("humanoid.general"),
    "action": K.ctrl("humanoid.action"),
}

MAGNETO_ANIMS = {
    "look": LOOK,
    "idle": a("magneto", "idle"),
    "walk": a("magneto", "walk"),
    "run": a("magneto", "run"),
    "air": a("magneto", "air"),
    "hover": a("magneto", "hover"),
    "cape_idle": a("magneto", "cape_idle"),
    "cape_move": a("magneto", "cape_move"),
    "cape": K.ctrl("cape"),
    "attack": a("humanoid", "attack"),
    "hurt": a("humanoid", "hurt"),
    "death": a("humanoid", "death"),
    "tech": a("tech", "repulse"),
    "ult": a("tech", "sphere"),
    "general": K.ctrl("magneto.general"),
    "action": K.ctrl("magneto.action"),
}

SENTINEL_ANIMS = {
    "look": LOOK,
    "idle": a("sentinel", "idle"),
    "walk": a("sentinel", "walk"),
    "beam": a("sentinel", "beam"),
    "stomp": a("sentinel", "stomp"),
    "scan": a("sentinel", "scan"),
    "hurt": a("sentinel", "hurt"),
    "death": a("sentinel", "death"),
    "general": K.ctrl("sentinel.general"),
    "action": K.ctrl("sentinel.action"),
}

#: 変身体アタッチャブルのベース（プレイヤーの動きに重ねる味付け）
FORM_ANIMS = {
    "idle": a("form", "idle"),
    "walk": a("form", "walk"),
    "run": a("form", "run"),
    "sprint": a("form", "sprint"),
    "crouch": a("form", "crouch"),
    "air": a("form", "air"),
    "swim": a("form", "swim"),
}

#: 各キャラの必殺級の技を、NPC の action コントローラに割り当てる
NPC_TECH = {
    "mystique": ("ally", "venom_strike"),
    "sabretooth": ("ally", "rend"),
    "toad": ("ally", "tongue_lash"),
    "juggernaut": ("ally", "unstoppable"),
    "quicksilver": ("ally", "blitz"),
    "pyro": ("ally", "flame_wave"),
    "avalanche": ("ally", "tremor"),
    "blob": ("ally", "body_slam"),
    "scarlet_witch": ("ally", "hex_bolt"),
    "mrd_trooper": ("humanoid", "attack"),
}

#: エンティティにぶら下げる常時パーティクル
ENTITY_PARTICLES = {
    "magneto": {"aura": K.part("mag_aura"), "field": K.part("mag_field"),
                "hit": K.part("hurt_spark")},
    "sentinel": {"spark": K.part("sentinel_spark"),
                 "smoke": K.part("sentinel_smoke"),
                 "scan": K.part("sentinel_scan")},
    "prime_sentinel": {"spark": K.part("sentinel_spark"),
                       "smoke": K.part("sentinel_smoke"),
                       "core": K.part("core_break")},
    "sentinel_drone": {"scan": K.part("sentinel_scan"),
                       "spark": K.part("sentinel_spark")},
    "mrd_trooper": {"muzzle": K.part("mrd_muzzle")},
    "sabretooth": {"slash": K.part("claw_slash"), "regen": K.part("regen_knit")},
    "mystique": {"shift": K.part("shift_shimmer")},
    "pyro": {"flame": K.part("flame_wave")},
    "scarlet_witch": {"hex": K.part("chaos_motes")},
    "quicksilver": {"blur": K.part("blur_after")},
    "avalanche": {"quake": K.part("quake_dust")},
    "juggernaut": {"quake": K.part("quake_dust")},
    "blob": {"slam": K.part("slam_ring")},
    "toad": {"slime": K.part("tongue_slime")},
}

#: 小物エンティティ — (ジオメトリ, アニメ, レンダーコントローラ, パーティクル)
PROP_CLIENTS = {
    "metal_shard": ("prop", "spin", "default", {"trail": K.part("shard_trail")}),
    "orbit_shard": ("prop", "orbit", "default", {"glint": K.part("metal_glint")}),
    "debris": ("prop", "spin", "default", {"dust": K.part("debris_dust")}),
    "hex_bolt": ("prop", "spin", "glow", {"trail": K.part("hex_bolt_trail")}),
    "fire_bolt": ("prop", "spin", "glow", {"trail": K.part("ember_rise")}),
    "sentinel_beam": ("prop", "spin", "glow",
                      {"trail": K.part("sentinel_beam_trail")}),
    "barrier_dome": ("prop", "drift", "hologram",
                     {"hex": K.part("barrier_hex")}),
    "ruin_sphere": ("prop", "pulse", "hologram",
                    {"orbit": K.part("sphere_orbit")}),
    "steel_platform": ("prop", "orbit", "default",
                       {"dust": K.part("throne_dust")}),
    "iron_cage": ("prop", "drift", "default", {"weld": K.part("bind_weld")}),
}


def client(identifier, texture, geometry, animations, animate, egg=None,
           material="entity_emissive_alpha",
           render=None, particles=None, extra=None):
    desc = {
        "identifier": identifier,
        "min_engine_version": "1.8.0",
        "materials": {"default": material},
        "textures": {"default": texture},
        "geometry": {"default": geometry},
        "animations": dict(animations),
        "scripts": {"animate": list(animate)},
        "render_controllers": [render or K.render_ctrl("default")],
    }
    if particles:
        desc["particle_effects"] = dict(particles)
    if egg:
        desc["spawn_egg"] = {"base_color": egg[0], "overlay_color": egg[1]}
    if extra:
        desc.update(extra)
    return {"format_version": "1.10.0",
            "minecraft:client_entity": {"description": desc}}


def attachable(identifier, texture, geometry, animations, animate,
               material="entity_emissive_alpha",
               render="controller.render.item_default", parent_setup=None):
    scripts = {"animate": list(animate)}
    if parent_setup:
        scripts["parent_setup"] = parent_setup
    return {"format_version": "1.10.0", "minecraft:attachable": {"description": {
        "identifier": identifier,
        "materials": {"default": material,
                      "enchanted": "entity_alphatest_glint"},
        "textures": {"default": texture,
                     "enchanted": "textures/misc/enchanted_item_glint"},
        "geometry": {"default": geometry},
        "animations": dict(animations),
        "scripts": scripts,
        "render_controllers": [render],
    }}}


def main() -> None:
    K.ensure_dirs()
    print("client entities:")

    # ---- マグニートー --------------------------------------------------
    write_json(f"{K.CLIENT_DIR}/magneto.entity.json", client(
        K.eid("magneto"), K.tex("magneto"), K.geo("magneto"),
        MAGNETO_ANIMS, ["general", "action"],
        egg=K.CHARACTERS["magneto"]["egg"],
        render=K.render_ctrl("glow"),
        particles=ENTITY_PARTICLES["magneto"]))

    # ---- ブラザーフッド + MRD -------------------------------------------
    for key in K.BROTHERHOOD + ["mrd_trooper"]:
        anims = dict(HUMANOID_ANIMS)
        group, clip_name = NPC_TECH[key]
        anims["tech"] = a(group, clip_name)
        render = (K.render_ctrl("phase") if key == "mystique"
                  else K.render_ctrl("glow"))
        write_json(f"{K.CLIENT_DIR}/{key}.entity.json", client(
            K.eid(key), K.tex(key), K.geo(key), anims, ["general", "action"],
            egg=K.CHARACTERS[key]["egg"], render=render,
            particles=ENTITY_PARTICLES.get(key)))

    # ---- センチネル ------------------------------------------------------
    for key in ("sentinel", "prime_sentinel", "sentinel_drone"):
        anims = dict(SENTINEL_ANIMS)
        write_json(f"{K.CLIENT_DIR}/{key}.entity.json", client(
            K.eid(key), K.tex(key), K.geo(key), anims, ["general", "action"],
            egg=K.CHARACTERS[key]["egg"], render=K.render_ctrl("glow"),
            particles=ENTITY_PARTICLES.get(key)))

    # ---- 小物 ------------------------------------------------------------
    for key, (group, clip_name, render, particles) in PROP_CLIENTS.items():
        write_json(f"{K.CLIENT_DIR}/{key}.entity.json", client(
            K.eid(key), K.tex(key), K.geo(key),
            {"spin": a(group, clip_name), "controller": K.ctrl("prop.spin")},
            ["controller"], render=K.render_ctrl(render),
            particles=particles))

    print(f"  {1 + len(K.BROTHERHOOD) + 4 + len(PROP_CLIENTS)} client entities")

    # ---- 変身体アタッチャブル（技ごと）------------------------------------
    print("attachables:")
    n = 0
    for character, tech, group, clip_name in K.form_variants():
        anims = dict(FORM_ANIMS)
        if tech:
            anims["pose"] = a(group, clip_name)
        anims["controller"] = K.ctrl(K.form_controller_name(character, tech))
        key = K.form_key(character, tech)
        write_json(f"{K.ATTACH_DIR}/{key}.attachable.json", attachable(
            K.eid(key), K.tex(character), K.geo(character), anims,
            ["controller"], render=K.render_ctrl("default"),
            parent_setup="variable.helmet_layer_visible = 0.0;"))
        n += 1

    # ---- 技アイテム（一人称の手元）----------------------------------------
    for key, spec in K.TECHNIQUES.items():
        anims = {
            "idle": a("fp", "idle"),
            "act": a("fp", spec["fp"]),
            "third": a("fp", "third"),
            "controller": K.ctrl("fp.tech"),
        }
        write_json(f"{K.ATTACH_DIR}/{spec['item']}.attachable.json", attachable(
            K.eid(spec["item"]), K.tex("fp_hand"), K.geo("fp_hand"), anims,
            [{"controller": "c.is_first_person"},
             {"third": "!c.is_first_person"}]))
        n += 1

    # ---- ヘルメット / セレブロ（手に持つ）---------------------------------
    #  変身アイテムが手の中で紫の玉に見えては話にならないので、
    #  兜には兜そのもののジオメトリを持たせる。
    for key, geo_key in (("magneto_helmet", "helmet_prop"),
                         ("cerebro", "tech_orb")):
        write_json(f"{K.ATTACH_DIR}/{key}.attachable.json", attachable(
            K.eid(key), K.tex(geo_key), K.geo(geo_key),
            {"third": a("prop", "pulse")}, ["third"]))
        n += 1

    print(f"  {n} attachables")


if __name__ == "__main__":
    main()
