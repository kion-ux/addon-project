# -*- coding: utf-8 -*-
"""Resource-pack client entities + the 怪獣8号 body attachable."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "packs", "kaiju8_RP")
ENT = os.path.join(RP, "entity")
ATT = os.path.join(RP, "attachables")

A = "animation.kaiju8."
C = "controller.animation.kaiju8."

HUMAN = {
    "look": A + "look_at_target",
    "idle": A + "humanoid.idle",
    "walk": A + "humanoid.walk",
    "run": A + "humanoid.run",
    "attack": A + "humanoid.attack",
    "hurt": A + "humanoid.hurt",
    "death": A + "humanoid.death",
    "general": C + "humanoid.general",
    "action": C + "humanoid.action",
}
KAIJU = {
    "look": A + "look_at_target",
    "idle": A + "kaiju.idle",
    "walk": A + "kaiju.walk",
    "attack": A + "kaiju.attack",
    "roar": A + "kaiju.roar",
    "hurt": A + "kaiju.hurt",
    "death": A + "kaiju.death",
    "extras": A + "tail",
    "general": C + "kaiju.general",
    "action": C + "kaiju.action",
}
BEAST = {
    "look": A + "look_at_target",
    "idle": A + "beast.idle",
    "walk": A + "beast.walk",
    "attack": A + "beast.attack",
    "hurt": A + "beast.hurt",
    "death": A + "beast.death",
    "general": C + "beast.general",
    "action": C + "beast.action",
}


def client(identifier, texture, geometry, animations, animate, egg=None,
           material="entity_emissive_alpha",
           render="controller.render.kaiju8.default", particles=None, extra=None):
    desc = {
        "identifier": identifier,
        "materials": {"default": material},
        "textures": {"default": f"textures/entity/kaiju8/{texture}"},
        "geometry": {"default": geometry},
        "animations": animations,
        "scripts": {"animate": animate},
        "render_controllers": [render],
    }
    if particles:
        desc["particle_effects"] = particles
    if egg:
        desc["spawn_egg"] = {"base_color": egg[0], "overlay_color": egg[1]}
    if extra:
        desc.update(extra)
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def write(name, doc, folder=ENT):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# character -> (texture/geometry key, pose animation, spawn egg colours)
TROOPS = [
    ("defense_force_officer", "soldier", "rifle", ("#12141a", "#d2d6d9")),
    ("kafka_hibino", "kafka", "knife", ("#12141a", "#1e1a19")),
    ("reno_ichikawa", "reno", "rifle", ("#12141a", "#c9cdd4")),
    ("mina_ashiro", "mina", "cannon", ("#12141a", "#c8712a")),
    ("soshiro_hoshina", "hoshina", "twin", ("#12141a", "#3b2e5a")),
    ("kikoru_shinomiya", "kikoru", "axe", ("#12141a", "#f0d480")),
    ("gen_narumi", "narumi", "gunblade", ("#12141a", "#d3357f")),
]

# character -> the 技 clip its action controller plays
TECH = {
    "defense_force_officer": "tech.snipe",
    "kafka_hibino": "tech.slash",
    "reno_ichikawa": "tech.snipe",
    "mina_ashiro": "tech.snipe",
    "soshiro_hoshina": "tech.twin_slash",
    "kikoru_shinomiya": "tech.axe_smash",
    "gen_narumi": "tech.storm",
}


def main() -> None:
    print("client entities:")

    # ---- 識別怪獣 -----------------------------------------------------
    no8 = dict(KAIJU)
    no8["extras"] = A + "horns_idle"
    write("kaiju_no8.entity.json", client(
        "kaiju8:kaiju_no8", "kaiju_no8", "geometry.kaiju8.no8", no8,
        ["general", "action"], ("#1a1f2e", "#7ed8ff"),
        particles={"aura": "kaiju8:no8_aura", "seam": "kaiju8:seam_glow",
                   "blood": "kaiju8:kaiju_blood", "roar": "kaiju8:roar_wave"}))

    no9 = dict(KAIJU)
    no9["extras"] = A + "tendrils"
    write("kaiju_no9.entity.json", client(
        "kaiju8:kaiju_no9", "kaiju_no9", "geometry.kaiju8.no9", no9,
        ["general", "action"], ("#b8b6c4", "#ff3e94"),
        particles={"regen": "kaiju8:regen_knit", "molt": "kaiju8:molt",
                   "blood": "kaiju8:kaiju_blood"}))

    no10 = dict(KAIJU)
    write("kaiju_no10.entity.json", client(
        "kaiju8:kaiju_no10", "kaiju_no10", "geometry.kaiju8.no10", no10,
        ["general", "action"], ("#c4202a", "#e0329b"),
        particles={"blood": "kaiju8:kaiju_blood", "roar": "kaiju8:roar_wave",
                   "seam": "kaiju8:kaiju10_seam", "steam": "kaiju8:steam_vent"}))

    write("honju.entity.json", client(
        "kaiju8:honju", "honju", "geometry.kaiju8.honju", dict(KAIJU),
        ["general", "action"], ("#6f5c4a", "#ff8a30"),
        particles={"blood": "kaiju8:kaiju_blood", "roar": "kaiju8:roar_wave",
                   "aura": "kaiju8:kaiju_aura"}))

    write("yoju.entity.json", client(
        "kaiju8:yoju", "yoju", "geometry.kaiju8.yoju", dict(BEAST),
        ["general", "action"], ("#627058", "#ffc442"),
        particles={"blood": "kaiju8:kaiju_blood"}))

    write("parasite_kaiju.entity.json", client(
        "kaiju8:parasite_kaiju", "parasite", "geometry.kaiju8.parasite", dict(BEAST),
        ["general", "action"], ("#9c7884", "#ff6078")))

    # ---- 日本防衛隊 ----------------------------------------------------
    for ident, key, pose, egg in TROOPS:
        anims = dict(HUMAN)
        anims["pose"] = A + "pose." + pose
        anims["tech"] = A + TECH[ident]
        anims["hair"] = A + "hair_sway"
        write(f"{ident}.entity.json", client(
            f"kaiju8:{ident}", key, f"geometry.kaiju8.{key}", anims,
            ["general", "hair", "pose", "action"], egg,
            particles={"muzzle": "kaiju8:muzzle_flash", "slash": "kaiju8:slash_air",
                       "release": "kaiju8:release_aura"}))

    # ---- projectiles ---------------------------------------------------
    for ident, tex, geo, particles in (
        ("rifle_beam", "beam", "geometry.kaiju8.beam",
         {"trail": "kaiju8:beam_trail"}),
        ("kaiju_acid", "acid", "geometry.kaiju8.acid",
         {"trail": "kaiju8:acid_splash"}),
        ("df_bullet", "bullet", "geometry.kaiju8.bullet", None),
    ):
        write(f"{ident}.entity.json", client(
            f"kaiju8:{ident}", tex, geo, {}, [], particles=particles))

    # ---- attachables ----------------------------------------------------
    write("no8_form.attachable.json", {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": "kaiju8:no8_form",
                "materials": {"default": "entity_emissive_alpha",
                              "enchanted": "entity_alphatest_glint"},
                "textures": {"default": "textures/entity/kaiju8/kaiju_no8",
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": "geometry.kaiju8.no8"},
                "animations": {
                    "form_idle": A + "no8.form_idle",
                    "crouch": A + "no8.crouch",
                    "air": A + "no8.air",
                    "charge": A + "no8.charge",
                    "controller": C + "no8_form",
                },
                "scripts": {
                    "parent_setup": "variable.helmet_layer_visible = 0.0;",
                    "animate": ["controller"],
                },
                "render_controllers": ["controller.render.kaiju8.default"],
            }
        }
    }, ATT)

    for piece, geo in (("helmet", "geometry.humanoid.armor.helmet"),
                       ("chestplate", "geometry.humanoid.armor.chestplate"),
                       ("leggings", "geometry.humanoid.armor.leggings"),
                       ("boots", "geometry.humanoid.armor.boots")):
        layer = "kaiju8_suit_layer_2" if piece == "leggings" else "kaiju8_suit_layer_1"
        write(f"combat_suit_{piece}.attachable.json", {
            "format_version": "1.10.0",
            "minecraft:attachable": {
                "description": {
                    "identifier": f"kaiju8:combat_suit_{piece}",
                    "materials": {"default": "armor", "enchanted": "armor_enchanted"},
                    "textures": {"default": f"textures/models/armor/{layer}",
                                 "enchanted": "textures/misc/enchanted_item_glint"},
                    "geometry": {"default": geo},
                    "scripts": {"parent_setup": "variable.helmet_layer_visible = 0.0;"},
                    "render_controllers": ["controller.render.armor"],
                }
            }
        }, ATT)
    print(f"  {len(TROOPS) + 6} entities, {len(TROOPS)} 技 clips wired")


if __name__ == "__main__":
    main()
