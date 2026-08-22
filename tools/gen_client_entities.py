"""Writes resource-pack client entity definitions + attachables."""
from __future__ import annotations

import json
import os

RP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "packs", "kaiju8_RP")
ENT = os.path.join(RP, "entity")
ATT = os.path.join(RP, "attachables")

A = "animation.kaiju8."
C = "controller.animation.kaiju8."

KAIJU_ANIMS = {
    "look": A + "look_at_target",
    "idle": A + "kaiju.idle",
    "walk": A + "kaiju.walk",
    "tail": A + "tail",
    "attack": A + "kaiju.attack",
    "roar": A + "kaiju.roar",
    "death": A + "kaiju.death",
    "general": C + "kaiju.general",
    "atk": C + "kaiju.attack",
}
HUMAN_ANIMS = {
    "look": A + "look_at_target",
    "idle": A + "humanoid.idle",
    "walk": A + "humanoid.walk",
    "attack": A + "humanoid.attack",
    "death": A + "humanoid.death",
    "general": C + "humanoid.general",
    "atk": C + "humanoid.attack",
}
QUAD_ANIMS = {
    "look": A + "look_at_target",
    "idle": A + "quadruped.idle",
    "walk": A + "quadruped.walk",
    "tail": A + "tail",
    "attack": A + "quadruped.attack",
    "death": A + "quadruped.death",
    "general": C + "quadruped.general",
    "atk": C + "quadruped.attack",
}


def client_entity(identifier, texture, geometry, animations, animate,
                  egg=None, material="entity_emissive_alpha",
                  render="controller.render.kaiju8.default", extra_desc=None):
    desc = {
        "identifier": identifier,
        "materials": {"default": material},
        "textures": {"default": f"textures/entity/kaiju8/{texture}"},
        "geometry": {"default": geometry},
        "animations": animations,
        "scripts": {"animate": animate},
        "render_controllers": [render],
    }
    if egg:
        desc["spawn_egg"] = {"base_color": egg[0], "overlay_color": egg[1]}
    if extra_desc:
        desc.update(extra_desc)
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def write(name, doc, folder=ENT):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("  " + name)


def main():
    print("client entities:")

    # ---- kaiju --------------------------------------------------------
    write("kaiju_no8.entity.json", client_entity(
        "kaiju8:kaiju_no8", "kaiju_no8", "geometry.kaiju8.no8",
        dict(KAIJU_ANIMS), ["general", "atk"], ("#141824", "#7ed8ff")))

    no9 = dict(KAIJU_ANIMS)
    no9["tendrils"] = A + "tendrils"
    write("kaiju_no9.entity.json", client_entity(
        "kaiju8:kaiju_no9", "kaiju_no9", "geometry.kaiju8.no9",
        no9, ["general", "atk", "tendrils"], ("#bab8c4", "#ff3e94")))

    no10 = dict(KAIJU_ANIMS)
    no10.update({"wings_idle": A + "wings.idle", "wings_flap": A + "wings.flap",
                 "wings": C + "wings"})
    write("kaiju_no10.entity.json", client_entity(
        "kaiju8:kaiju_no10", "kaiju_no10", "geometry.kaiju8.no10",
        no10, ["general", "atk", "wings"], ("#4e325c", "#ff6038")))

    write("yoju.entity.json", client_entity(
        "kaiju8:yoju", "yoju", "geometry.kaiju8.yoju",
        dict(QUAD_ANIMS), ["general", "atk"], ("#627058", "#ffc442")))

    write("honju.entity.json", client_entity(
        "kaiju8:honju", "honju", "geometry.kaiju8.honju",
        dict(KAIJU_ANIMS), ["general", "atk"], ("#705e4c", "#ff8a30")))

    # ---- defense force ------------------------------------------------
    troops = [
        ("defense_force_officer", "soldier", "geometry.kaiju8.soldier", "rifle", ("#e0e4ea", "#4a9eec")),
        ("kafka_hibino", "kafka", "geometry.kaiju8.kafka", None, ("#e0e4ea", "#262a34")),
        ("reno_ichikawa", "reno", "geometry.kaiju8.reno", None, ("#e0e4ea", "#d6d2c4")),
        ("mina_ashiro", "mina", "geometry.kaiju8.mina", "rifle", ("#e0e4ea", "#c62a36")),
        ("soshiro_hoshina", "hoshina", "geometry.kaiju8.hoshina", "blades", ("#e0e4ea", "#46325c")),
        ("kikoru_shinomiya", "kikoru", "geometry.kaiju8.kikoru", "axe", ("#e0e4ea", "#5cace2")),
    ]
    for ident, tex, geo, pose, egg in troops:
        anims = dict(HUMAN_ANIMS)
        animate = ["general"]
        if pose:
            anims["pose"] = A + "pose." + pose
            animate.append("pose")
        animate.append("atk")
        write(f"{ident}.entity.json", client_entity(
            f"kaiju8:{ident}", tex, geo, anims, animate, egg))

    # ---- projectiles / props -------------------------------------------
    spin = {"spin": A + "projectile.spin"}
    write("rifle_beam.entity.json", client_entity(
        "kaiju8:rifle_beam", "beam", "geometry.kaiju8.beam", dict(spin), ["spin"]))
    write("kaiju_acid.entity.json", client_entity(
        "kaiju8:kaiju_acid", "acid", "geometry.kaiju8.acid", dict(spin), ["spin"]))
    write("df_bullet.entity.json", client_entity(
        "kaiju8:df_bullet", "bullet", "geometry.kaiju8.bullet", {}, []))
    write("parasite_kaiju.entity.json", client_entity(
        "kaiju8:parasite_kaiju", "parasite", "geometry.kaiju8.parasite",
        {"crawl": A + "parasite.crawl"}, ["crawl"], ("#967884", "#ff6078")))

    # ---- attachables ----------------------------------------------------
    print("attachables:")
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
                "scripts": {
                    "parent_setup": "variable.helmet_layer_visible = 0.0;",
                    "pre_animation": ["variable.no8 = 1.0;"]
                },
                "render_controllers": ["controller.render.kaiju8.default"]
            }
        }
    }, ATT)

    for piece, geo in [("helmet", "geometry.humanoid.armor.helmet"),
                       ("chestplate", "geometry.humanoid.armor.chestplate"),
                       ("leggings", "geometry.humanoid.armor.leggings"),
                       ("boots", "geometry.humanoid.armor.boots")]:
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
                    "render_controllers": ["controller.render.armor"]
                }
            }
        }, ATT)


if __name__ == "__main__":
    main()
