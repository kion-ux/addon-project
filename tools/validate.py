"""Cross-checks the two packs for dangling references."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "packs", "kaiju8_BP")
RP = os.path.join(ROOT, "packs", "kaiju8_RP")

errors: list[str] = []
warnings: list[str] = []


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def walk(root, suffix=".json"):
    for base, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(suffix):
                yield os.path.join(base, f)


def main() -> int:
    # ---- every json parses -------------------------------------------
    for pack in (BP, RP):
        for path in walk(pack):
            try:
                load(path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"invalid json: {os.path.relpath(path, ROOT)}: {exc}")
    if errors:
        for e in errors:
            print("ERROR", e)
        return 1

    # ---- geometry inventory ------------------------------------------
    geometries = set()
    for path in walk(os.path.join(RP, "models")):
        doc = load(path)
        for geo in doc.get("minecraft:geometry", []):
            geometries.add(geo["description"]["identifier"])
    # vanilla geometries the attachables lean on
    geometries |= {
        "geometry.humanoid.armor.helmet", "geometry.humanoid.armor.chestplate",
        "geometry.humanoid.armor.leggings", "geometry.humanoid.armor.boots",
    }

    animations = set()
    controllers = set()
    for path in walk(os.path.join(RP, "animations")):
        animations |= set(load(path).get("animations", {}))
    for path in walk(os.path.join(RP, "animation_controllers")):
        controllers |= set(load(path).get("animation_controllers", {}))
    controller_anim_refs = {}
    for path in walk(os.path.join(RP, "animation_controllers")):
        for name, ctrl in load(path).get("animation_controllers", {}).items():
            refs = set()
            for state in ctrl.get("states", {}).values():
                for a in state.get("animations", []):
                    refs.add(a if isinstance(a, str) else list(a)[0])
            controller_anim_refs[name] = refs

    render_controllers = set()
    for path in walk(os.path.join(RP, "render_controllers")):
        render_controllers |= set(load(path).get("render_controllers", {}))
    render_controllers |= {"controller.render.armor", "controller.render.item_default"}

    # ---- particles ------------------------------------------------------
    particles = set()
    part_dir = os.path.join(RP, "particles")
    if os.path.isdir(part_dir):
        for path in walk(part_dir):
            doc = load(path)["particle_effect"]
            particles.add(doc["description"]["identifier"])
            tex = doc["description"]["basic_render_parameters"]["texture"]
            if not os.path.exists(os.path.join(RP, tex + ".png")):
                errors.append(f"{os.path.relpath(path, ROOT)}: missing {tex}.png")

    # every kaiju8: particle the scripts spawn must actually exist
    import re
    spawn_call = re.compile(
        r'(?:fx|fxRing|fxLine|fxScatter|arcFx|spawnParticle)\s*'
        r'\([^;]{0,160}?"(kaiju8:[a-z0-9_]+)"')
    used = set()
    script_dir = os.path.join(BP, "scripts")
    if os.path.isdir(script_dir):
        for path in walk(script_dir, ".js"):
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            for m in spawn_call.finditer(body):
                name = m.group(1)
                if name in particles:
                    used.add(name)
                else:
                    errors.append(f"scripts: unknown particle {name} "
                                  f"({os.path.basename(path)})")
    for path in walk(os.path.join(RP, "entity")):
        for value in load(path)["minecraft:client_entity"]["description"].get(
                "particle_effects", {}).values():
            if value in particles:
                used.add(value)
    for name in sorted(particles - used):
        warnings.append(f"particle {name} is defined but never used")

    # ---- client entities ---------------------------------------------
    client_ids = set()
    for path in walk(os.path.join(RP, "entity")):
        desc = load(path)["minecraft:client_entity"]["description"]
        rel = os.path.relpath(path, ROOT)
        client_ids.add(desc["identifier"])
        for geo in desc.get("geometry", {}).values():
            if geo not in geometries:
                errors.append(f"{rel}: unknown geometry {geo}")
        for tex in desc.get("textures", {}).values():
            if not os.path.exists(os.path.join(RP, tex + ".png")):
                errors.append(f"{rel}: missing texture {tex}.png")
        for rc in desc.get("render_controllers", []):
            name = rc if isinstance(rc, str) else list(rc)[0]
            if name not in render_controllers:
                errors.append(f"{rel}: unknown render controller {name}")
        anims = desc.get("animations", {})
        for key, value in anims.items():
            if value.startswith("controller.") and value not in controllers:
                errors.append(f"{rel}: unknown animation controller {value}")
            if value.startswith("animation.") and value not in animations:
                errors.append(f"{rel}: unknown animation {value}")
        for short in desc.get("scripts", {}).get("animate", []):
            key = short if isinstance(short, str) else list(short)[0]
            if key not in anims:
                errors.append(f"{rel}: animate entry '{key}' has no animations mapping")
        # every animation a referenced controller plays must be mapped too
        for value in anims.values():
            for ref in controller_anim_refs.get(value, ()):  # only controllers match
                if ref not in anims:
                    errors.append(
                        f"{rel}: controller {value} plays '{ref}' "
                        f"but the entity maps no such animation")

    attachable_ids = set()
    # attachables
    for path in walk(os.path.join(RP, "attachables")):
        desc = load(path)["minecraft:attachable"]["description"]
        rel = os.path.relpath(path, ROOT)
        for geo in desc.get("geometry", {}).values():
            if geo not in geometries:
                errors.append(f"{rel}: unknown geometry {geo}")
        for name, tex in desc.get("textures", {}).items():
            if tex.startswith("textures/misc/"):
                continue
            if not os.path.exists(os.path.join(RP, tex + ".png")):
                errors.append(f"{rel}: missing texture {tex}.png")
        for key, value in desc.get("animations", {}).items():
            if value.startswith("controller.") and value not in controllers:
                errors.append(f"{rel}: unknown animation controller {value}")
            if value.startswith("animation.") and value not in animations:
                errors.append(f"{rel}: unknown animation {value}")
        for short in desc.get("scripts", {}).get("animate", []):
            key = short if isinstance(short, str) else list(short)[0]
            if key not in desc.get("animations", {}):
                errors.append(f"{rel}: animate entry '{key}' is not mapped")
        for value in desc.get("animations", {}).values():
            for ref in controller_anim_refs.get(value, ()):
                if ref not in desc.get("animations", {}):
                    errors.append(f"{rel}: controller {value} plays '{ref}' "
                                  f"but the attachable maps no such animation")
        attachable_ids.add(desc["identifier"])

    # ---- behaviour entities -------------------------------------------
    bp_ids = set()
    for path in walk(os.path.join(BP, "entities")):
        desc = load(path)["minecraft:entity"]["description"]
        bp_ids.add(desc["identifier"])
    for ident in bp_ids:
        if ident not in client_ids:
            errors.append(f"behaviour entity {ident} has no client entity")
    for ident in client_ids:
        if ident not in bp_ids:
            errors.append(f"client entity {ident} has no behaviour entity")

    # ---- items and their icons ----------------------------------------
    atlas = load(os.path.join(RP, "textures", "item_texture.json"))["texture_data"]
    for key, entry in atlas.items():
        path = os.path.join(RP, entry["textures"] + ".png")
        if not os.path.exists(path):
            errors.append(f"item_texture.json: missing {entry['textures']}.png")

    item_ids = set()
    for path in walk(os.path.join(BP, "items")):
        doc = load(path)["minecraft:item"]
        ident = doc["description"]["identifier"]
        item_ids.add(ident)
        icon = doc["components"].get("minecraft:icon")
        key = icon.get("texture") if isinstance(icon, dict) else icon
        if key not in atlas:
            errors.append(f"item {ident}: icon '{key}' not in item_texture.json")

    # every attachable must belong to a real item
    for ident in attachable_ids:
        if ident not in item_ids:
            errors.append(f"attachable {ident} has no matching item")

    # client-entity particle_effects must resolve
    for path in walk(os.path.join(RP, "entity")):
        desc = load(path)["minecraft:client_entity"]["description"]
        rel = os.path.relpath(path, ROOT)
        for key, value in desc.get("particle_effects", {}).items():
            if value not in particles and not value.startswith("minecraft:"):
                errors.append(f"{rel}: unknown particle {value}")

    # ---- spawn rules / loot / recipes reference real things -------------
    for path in walk(os.path.join(BP, "spawn_rules")):
        ident = load(path)["minecraft:spawn_rules"]["description"]["identifier"]
        if ident not in bp_ids:
            errors.append(f"spawn rule for unknown entity {ident}")

    known = item_ids | {f"{i}_spawn_egg" for i in bp_ids}
    for path in walk(os.path.join(BP, "loot_tables")):
        doc = load(path)
        rel = os.path.relpath(path, ROOT)
        for pool in doc.get("pools", []):
            for e in pool.get("entries", []):
                name = e.get("name", "")
                if name.startswith("kaiju8:") and name not in known:
                    errors.append(f"{rel}: loot references unknown item {name}")

    for path in walk(os.path.join(BP, "recipes")):
        doc = load(path)
        rel = os.path.relpath(path, ROOT)
        recipe = doc.get("minecraft:recipe_shaped") or doc.get("minecraft:recipe_shapeless")
        refs = []
        if "key" in recipe:
            refs += [v["item"] for v in recipe["key"].values()]
        refs += [i["item"] for i in recipe.get("ingredients", [])]
        refs.append(recipe["result"]["item"])
        for name in refs:
            if name.startswith("kaiju8:") and name not in known:
                errors.append(f"{rel}: recipe references unknown item {name}")

    # ---- loot tables referenced by entities exist ----------------------
    for path in walk(os.path.join(BP, "entities")):
        doc = load(path)["minecraft:entity"]
        rel = os.path.relpath(path, ROOT)
        table = doc.get("components", {}).get("minecraft:loot", {}).get("table")
        if table and not os.path.exists(os.path.join(BP, table)):
            errors.append(f"{rel}: missing loot table {table}")
        shooter = doc.get("components", {}).get("minecraft:shooter", {}).get("def")
        if shooter and shooter not in bp_ids:
            errors.append(f"{rel}: shooter references unknown entity {shooter}")

    # ---- language coverage --------------------------------------------
    lang = {}
    with open(os.path.join(RP, "texts", "ja_JP.lang"), encoding="utf-8") as fh:
        for line in fh:
            if "=" in line:
                k, v = line.split("=", 1)
                lang[k.strip()] = v.strip()
    for ident in item_ids:
        if f"item.{ident}" not in lang:
            warnings.append(f"no ja_JP name for item {ident}")
    for ident in bp_ids:
        if f"entity.{ident}.name" not in lang:
            warnings.append(f"no ja_JP name for entity {ident}")

    # ---- manifests -----------------------------------------------------
    bp_manifest = load(os.path.join(BP, "manifest.json"))
    rp_manifest = load(os.path.join(RP, "manifest.json"))
    if bp_manifest["dependencies"][0]["uuid"] != rp_manifest["header"]["uuid"]:
        errors.append("behaviour pack does not depend on the resource pack uuid")
    if rp_manifest["dependencies"][0]["uuid"] != bp_manifest["header"]["uuid"]:
        errors.append("resource pack does not depend on the behaviour pack uuid")
    for pack, manifest in ((BP, bp_manifest), (RP, rp_manifest)):
        if not os.path.exists(os.path.join(pack, "pack_icon.png")):
            errors.append(f"{os.path.basename(pack)}: missing pack_icon.png")

    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"\n{len(bp_ids)} entities, {len(item_ids)} items, {len(geometries)} geometries, "
          f"{len(animations)} animations, {len(particles)} particles, "
          f"{len(attachable_ids)} attachables")
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
