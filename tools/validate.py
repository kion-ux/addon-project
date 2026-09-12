"""Cross-checks each add-on's two packs for dangling references.

This repository now ships two add-ons that share one toolchain, so every check
runs once per pack pair.  Add a new add-on by appending to PACKS — nothing else
in this file is add-on specific.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#  (表示名, BP フォルダ, RP フォルダ, namespace)
PACKS = [
    ("Kaiju No.8", "kaiju8_BP", "kaiju8_RP", "kaiju8"),
    ("GRAND LINE AWAKENING", "gla_BP", "gla_RP", "gla"),
]

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


def check(BP: str, RP: str, NS: str) -> int:
    errors.clear()
    warnings.clear()
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
    geo_bones: dict[str, set[str]] = {}
    for path in walk(os.path.join(RP, "models")):
        doc = load(path)
        for geo in doc.get("minecraft:geometry", []):
            ident = geo["description"]["identifier"]
            geometries.add(ident)
            geo_bones[ident] = {b["name"] for b in geo.get("bones", [])}
    # vanilla geometries the attachables lean on
    geometries |= {
        "geometry.humanoid.armor.helmet", "geometry.humanoid.armor.chestplate",
        "geometry.humanoid.armor.leggings", "geometry.humanoid.armor.boots",
    }

    animations = set()
    anim_bones: dict[str, set[str]] = {}
    controllers = set()
    for path in walk(os.path.join(RP, "animations")):
        for name, clip in load(path).get("animations", {}).items():
            animations.add(name)
            anim_bones[name] = set(clip.get("bones", {}))
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

    # every <ns>: particle the scripts spawn must actually exist.
    # NOTE: keep this list in step with effects.js — a helper missing from it
    # means typo'd particle ids in those calls ship silently.
    import re
    spawn_call = re.compile(
        r'(?:fx|fxRing|fxLine|fxScatter|fxArc|fxSpiral|fxColumn|fxCone|fxWall|'
        r'trail|arcFx|spawn|spawnParticle|playStage)\s*'
        r'\([^;]{0,200}?"(' + NS + r':[a-z0-9_]+)"')
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
    # a particle id can also be named in a table and spawned indirectly; count
    # any bare mention so the "never used" warning does not cry wolf
    if os.path.isdir(script_dir):
        bare = re.compile(r'"(' + NS + r':[a-z0-9_]+)"')
        for path in walk(script_dir, ".js"):
            with open(path, encoding="utf-8") as fh:
                for m in bare.finditer(fh.read()):
                    if m.group(1) in particles:
                        used.add(m.group(1))
    for name in sorted(particles - used):
        warnings.append(f"particle {name} is defined but never used")

    # two effects that differ only by name are a copy-paste, not variety
    seen_shapes = {}
    if os.path.isdir(part_dir):
        for path in walk(part_dir):
            doc = load(path)["particle_effect"]
            key = json.dumps(doc["components"], sort_keys=True)
            ident = doc["description"]["identifier"]
            if key in seen_shapes:
                warnings.append(
                    f"particle {ident} is identical to {seen_shapes[key]}")
            else:
                seen_shapes[key] = ident

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

    # ---- アニメの形そのものが壊れていないこと ---------------------------
    #  時刻のキーが数字でない、値が3要素でない、知らないチャンネル名 —
    #  どれも Bedrock 側は黙って無視するか、そのクリップごと読み飛ばす。
    time_key = re.compile(r"^\d+(\.\d+)?$")
    for path in walk(os.path.join(RP, "animations")):
        rel = os.path.relpath(path, ROOT)
        for name, clip in load(path).get("animations", {}).items():
            if not isinstance(clip.get("loop", False), (bool, str)):
                errors.append(f"{rel}: {name}: loop must be a bool or a string")
            length = clip.get("animation_length")
            if length is not None and not isinstance(length, (int, float)):
                errors.append(f"{rel}: {name}: animation_length is not a number")
            for bone, channels in clip.get("bones", {}).items():
                for chan, val in channels.items():
                    if chan not in ("rotation", "position", "scale"):
                        errors.append(f"{rel}: {name}.{bone}: unknown channel {chan}")

                    def ok_value(v):
                        # scale だけは一様倍率のスカラーも書ける
                        if chan == "scale" and isinstance(v, (int, float, str)):
                            return True
                        return isinstance(v, list) and len(v) == 3

                    if isinstance(val, dict):
                        for key, vec in val.items():
                            if not time_key.match(str(key)):
                                errors.append(f"{rel}: {name}.{bone}.{chan}: "
                                              f"bad keyframe time {key!r}")
                            if not ok_value(vec):
                                errors.append(f"{rel}: {name}.{bone}.{chan}[{key}]: "
                                              f"bad value")
                    elif not ok_value(val):
                        errors.append(f"{rel}: {name}.{bone}.{chan}: bad value")

    # ---- アニメが動かすボーンは、そのジオメトリに実在すること ------------
    #  存在しないボーン名を書いても Bedrock は黙って無視するので、
    #  「動かないけどエラーも出ない」になる。ただし、1つのアニメ集合を
    #  小さいジオメトリにも流用するのは正常な作り方なので（怪獣8号の
    #  ナンバーズがそう）、欠けているだけでは咎めない。
    #
    #    error : そのクリップのボーンが1つもジオメトリに無い
    #            → 貼り付け先を間違えている。確実に動かない。
    #    warn  : そのジオメトリ専用のクリップなのにボーンが欠けている
    #            → 名前を変えたときの取りこぼし。
    def check_bones(label, desc):
        geos = list(desc.get("geometry", {}).values())
        known = set()
        for g in geos:
            known |= geo_bones.get(g, set())
        if not known:
            return
        for key, value in desc.get("animations", {}).items():
            for name in ([value] if value.startswith("animation.") else
                         sorted(controller_anim_refs.get(value, ()))):
                target = name
                if not target.startswith("animation."):
                    target = desc.get("animations", {}).get(name, "")
                used = anim_bones.get(target, set())
                if not used:
                    continue
                missing = sorted(used - known)
                if len(missing) == len(used):
                    errors.append(
                        f"{label}: {target} animates only bones that do not "
                        f"exist in {geos} — wrong geometry?")
                elif missing and any(
                        g.rsplit(".", 1)[-1] in target for g in geos):
                    warnings.append(
                        f"{label}: {target} is specific to {geos} but animates "
                        f"missing bones: {', '.join(missing[:6])}")

    for path in walk(os.path.join(RP, "entity")):
        check_bones(os.path.relpath(path, ROOT),
                    load(path)["minecraft:client_entity"]["description"])
    for path in walk(os.path.join(RP, "attachables")):
        check_bones(os.path.relpath(path, ROOT),
                    load(path)["minecraft:attachable"]["description"])

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
                if name.startswith(NS + ":") and name not in known:
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
            if name.startswith(NS + ":") and name not in known:
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

    # スクリプトが翻訳キーを引いているのに .lang に無いと、ゲーム内では
    # 生の識別子がそのまま表示される。実機で気付くしかないので、ここで潰す。
    en = {}
    en_path = os.path.join(RP, "texts", "en_US.lang")
    if os.path.exists(en_path):
        with open(en_path, encoding="utf-8") as fh:
            for row in fh:
                if "=" in row:
                    k, v = row.split("=", 1)
                    en[k.strip()] = v.strip()
    # ja と en でキーの集合が違うと、片方の言語だけ生の識別子が出る。
    if en:
        only_ja = sorted(set(lang) - set(en))
        only_en = sorted(set(en) - set(lang))
        for k in only_ja[:8]:
            errors.append(f"texts: {k} is in ja_JP but not en_US")
        for k in only_en[:8]:
            errors.append(f"texts: {k} is in en_US but not ja_JP")

    key_ref = re.compile(r'"(' + NS + r'\.[a-z][a-z0-9_.]*)"')
    # `gla.tech.${x}` のように組み立てるキーは完全一致では拾えないので、
    # 「その前置きで始まるキーが1つも無い」ことだけを見る。
    key_tpl = re.compile(r'`(' + NS + r'\.[a-z][a-z0-9_.]*)\$\{')
    for path in walk(script_dir, ".js") if os.path.isdir(script_dir) else ():
        rel = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        for m in key_ref.finditer(body):
            key = m.group(1)
            if key not in lang:
                errors.append(f"scripts/{rel}: ja_JP has no key {key}")
            if en and key not in en:
                errors.append(f"scripts/{rel}: en_US has no key {key}")
        for m in key_tpl.finditer(body):
            prefix = m.group(1)
            if not any(k.startswith(prefix) for k in lang):
                errors.append(f"scripts/{rel}: no ja_JP key starts with {prefix}")
            if en and not any(k.startswith(prefix) for k in en):
                errors.append(f"scripts/{rel}: no en_US key starts with {prefix}")

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
    print(f"  {len(bp_ids)} entities, {len(item_ids)} items, "
          f"{len(geometries)} geometries, {len(animations)} animations, "
          f"{len(particles)} particles, {len(attachable_ids)} attachables")
    print(f"  {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


def main() -> int:
    bad = 0
    for label, bp, rp, ns in PACKS:
        bp_dir = os.path.join(ROOT, "packs", bp)
        rp_dir = os.path.join(ROOT, "packs", rp)
        if not os.path.isdir(bp_dir) or not os.path.isdir(rp_dir):
            # 黙って飛ばすと、パックが丸ごと消えていてもビルドが通ってしまう。
            print(f"\n-- {label}")
            print(f"ERROR packs/{bp} または packs/{rp} が見つからない")
            bad = 1
            continue
        print(f"\n-- {label}")
        bad |= check(bp_dir, rp_dir, ns)
    return bad


if __name__ == "__main__":
    sys.exit(main())
