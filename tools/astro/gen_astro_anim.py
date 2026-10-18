# -*- coding: utf-8 -*-
"""アストロ・ナノギア — プレイヤーの全身モーション（playanimation）と scripts/anim_meta.js。

    python3 tools/astro/gen_astro_anim.py                     書き出し＋検査
    python3 tools/astro/gen_astro_anim.py --check             めり込みの一覧も出す（武器が体に入るコマ）
    python3 tools/astro/gen_astro_anim.py --preview <名前> [--planet <key>] [--frames 8] [--view q34]
        <名前> は共通の名前（henshin）か惑星の名前（earth.combo1）。キーの姿勢を描いて
        build_preview/astro/anim_<名前>.png に並べる（スーツがあれば着せ、武器を手に持たせる）

書き出す物:
  packs/astro_RP/animations/astro_player.animation.json
      animation.astro.p.<名前>          共通（astro_animlib.library()）。武器の向きは騎士剣（sword）で解く
      animation.astro.p.<key>.<名前>    惑星の body.py の BODY_ANIMS
      animation.astro.p.<key>.<名前>    共通のうち wield() を使う物を、その惑星の武器で解き直した版
                                        （惑星が同じ名前を BODY_ANIMS に書いていればそちらが勝つ）
      スクリプトは `${key}.${name}` が ANIM_META にあればそれを、無ければ `${name}` を再生する。
  packs/astro_BP/scripts/anim_meta.js   export const ANIM_META = {"<名前>": [長さ秒, ブレンド可否], ...}
"""
from __future__ import annotations

import importlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import astro_animlib as AL  # noqa: E402
import astro_common as AC  # noqa: E402
import astro_data as D  # noqa: E402

ANIM_PATH = os.path.join(AC.RP, "animations", "astro_player.animation.json")
META_PATH = os.path.join(AC.BP, "scripts", "anim_meta.js")
CANON = "sword"          # 共通モーションの武器の向きを解く種類（名前に惑星が付かない版）
PLAYER_BONES = set(AL.BONES.values())


# ===========================================================================
#  集める
# ===========================================================================
def body_module(key):
    if not os.path.exists(os.path.join(AC.PLANETS_DIR, key, "body.py")):
        return None
    return importlib.import_module(f"planets.{key}.body")


def planet_hold(key):
    import astro_weapon as W
    return W.planet_hold(key, "weapon")


def collect():
    """[(名前, spec, 武器の種類, 持ち方 or None, 惑星 or None)]。"""
    import astro_hold as AH
    lib = AL.library()
    out = []
    canon = AH.hold(CANON)
    for name, spec in lib.items():
        out.append((name, spec, CANON, canon, None))
    for key in D.PLANET_KEYS:
        mod = body_module(key)
        own = dict(getattr(mod, "BODY_ANIMS", {}) or {}) if mod else {}
        h = planet_hold(key)
        for name, spec in own.items():
            if "." in name:
                raise ValueError(f"planets/{key}/body.py: name {name!r} must not contain '.'")
            out.append((f"{key}.{name}", spec, h["kind"], h, key))
        for name, spec in lib.items():
            if name in own or not AL.uses_wield(spec):
                continue
            out.append((f"{key}.{name}", spec, h["kind"], h, key))
    return out


def build(clear=True):
    """clear=True なら、wield() の腕を武器（生成済みのジオメトリ）が体に入らない向きへ回す。"""
    anims, meta, res_all = {}, {}, {}
    clouds = {}

    def cloud_of(key, kind):
        if not clear:
            return None
        if key is None:          # 共通の版: 同じ種類の武器を持つ惑星の武器で
            key = next((k for k in D.PLANET_KEYS if planet_hold(k)["kind"] == kind
                        and weapon_cloud(k) is not None), None)
            if key is None:
                return None
        if key not in clouds:
            clouds[key] = weapon_cloud(key)
        return clouds[key]
    for name, spec, kind, hold, key in collect():
        # 惑星の版は必ず（その惑星の武器で直す）。共通の版は wield() を使う物だけ（騎士剣で）
        cl = cloud_of(key, kind) if (key is not None or AL.uses_wield(spec)) else None
        if spec["frames"] and name.split(".")[-1] == "henshin":
            cl = None            # 変身の前半はコアを持っている
        res = AL.resolve(spec, kind, name=name, hold=hold, cloud=cl)
        res.planet = key
        res_all[name] = res
        anims[AL.PREFIX + name] = AL.to_json(res)
        meta[name] = [round(res.length, 3), 1 if res.blend else 0]
    return anims, meta, res_all


# ===========================================================================
#  検査
# ===========================================================================
def _balanced(s):
    d = 0
    for ch in s:
        d += ch == "("
        d -= ch == ")"
        if d < 0:
            return False
    return d == 0


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def validate(anims, res_all) -> list:
    errors = []
    for name, a in anims.items():
        for bone, ch in a["bones"].items():
            if bone not in PLAYER_BONES:
                errors.append(f"{name}: unknown player bone {bone}")
            for c, tr in ch.items():
                for t in tr:
                    if float(t) < -1e-6 or float(t) > a["animation_length"] + 1e-6:
                        errors.append(f"{name}: {bone}.{c} key {t} outside the length")
        for s in _strings(a):
            if not _balanced(s):
                errors.append(f"{name}: unbalanced molang {s[:70]}")
    errors += _consistency(anims, res_all)
    return errors


def _consistency(anims, res_all, limit=0.05):
    """書き出した JSON を Molang の評価器で読み戻し、キーの時刻で「バニラの持ち姿勢 + 出力」が
    解いた姿勢（三人称）と一致するか、一人称で腕が 25% になっているかを確かめる。"""
    try:
        from astro_scene import eval_animation
    except Exception:  # noqa: BLE001  (スーツ担当のファイルがまだ無い時)
        return []
    errs = []
    env_tp = {"v.is_first_person": 0.0, "v.attack_time": 0.0, "v.tcos0": 0.0}
    for name, res in res_all.items():
        js = anims[AL.PREFIX + name]
        for part, tr in res.tracks.items():
            bone = "root" if part == "root_pos" else AL.BONES[part]
            chan = "position" if part == "root_pos" else "rotation"
            for t, val in tr.items():
                e = eval_animation(js, t, env_tp).get(bone, {}).get(chan, [0, 0, 0])
                rest = (0, 0, 0) if part == "root_pos" else AL.REST.get(part, (0, 0, 0))
                got = [rest[i] + e[i] for i in range(3)]
                if max(abs(got[i] - val[i]) for i in range(3)) > limit:
                    errs.append(f"{name}: {part} at {t}: json {np.round(got, 2)} != {np.round(val, 2)}")
                    break
    return errs


def weapon_cloud(key, what="weapon", step=1.0):
    """惑星の武器の表面の点（右手 rightItem の空間、4 x N）。生成済みのジオメトリから。"""
    from PIL import Image
    import astro_weapon as W
    import hd_scene as S
    from hd_pose import surface_points
    geo_path = W.paths(key, what)[0]
    if not os.path.exists(geo_path):
        return None
    geo = json.load(open(geo_path, encoding="utf-8"))["minecraft:geometry"][0]
    h = W.planet_hold(key, what)
    tex = Image.new("RGBA", (geo["description"]["texture_width"], geo["description"]["texture_height"]))
    a = {"hold": {"rotation": h["tp"]["rotation"], "position": h["tp"]["position"],
                  "scale": (h["tp"]["scale"],) * 3}}
    ident = {"rightItem": np.eye(4), "leftItem": np.eye(4)}
    q = S.weapon_quads(geo, tex, ident, a, tag=True)
    keep = [x for x in q if not x[3].startswith("fx_")]
    pts = surface_points(keep, step)
    return np.c_[pts, np.ones(len(pts))].T


def penetration(pose, cloud):
    return AL.clip_depth(pose, cloud)


def clip_report(res_all, step=0.04, limit=0.8):
    """武器（無ければ代役）が体に入り込むモーションの一覧。"""
    clouds = {}
    rows = []
    for name, res in sorted(res_all.items()):
        key = res.planet or "earth"
        if key not in clouds:
            clouds[key] = weapon_cloud(key)
        cloud = clouds[key]
        if cloud is None:
            continue
        worst = (0.0, None, 0.0)
        n = max(1, int(math.ceil(res.length / step)))
        for i in range(n + 1):
            t = res.length * i / n
            if name.split(".")[-1] == "henshin" and t < AL.TR["weapon_form"]:
                continue        # 武器はまだコア
            d, bone = penetration(AL.sample(res, t), cloud)
            if d > worst[0]:
                worst = (d, bone, t)
        if worst[0] > limit:
            rows.append((name, worst))
    return rows


# ===========================================================================
#  プレビュー
# ===========================================================================
def preview(name, planet=None, frames=8, view=None, out=None):
    from PIL import Image
    import astro_weapon as W
    _anims, _meta, res_all = build()
    if name not in res_all:
        raise SystemExit(f"no animation {name!r}. one of: {', '.join(sorted(res_all))}")
    res = res_all[name]
    key = planet or res.planet or "earth"
    if planet and f"{planet}.{name}" in res_all:
        res = res_all[f"{planet}.{name}"]
    keys = sorted(res.keys)
    while len(keys) < min(frames, 6):                 # 少ないキーは間を足して見る
        gaps = [(b - a, a, b) for a, b in zip(keys, keys[1:])]
        _g, a, b = max(gaps)
        keys = sorted(keys + [round((a + b) / 2, 3)])
    if len(keys) > frames:
        idx = np.linspace(0, len(keys) - 1, frames).round().astype(int)
        keys = [keys[i] for i in sorted(set(idx))]
    tiles = []
    views = [view] if view else ["q34", "left"]
    suit = None
    try:
        import astro_scene as AS
        if os.path.exists(os.path.join(AC.GEO_DIR, f"astro_suit_{key}.geo.json")):
            suit = AS.load_suit(key)
    except Exception:  # noqa: BLE001
        AS = None
    for t in keys:
        pose = AL.sample(res, t)
        holding_core = name.split(".")[-1] == "henshin" and t < AL.TR["weapon_form"]
        what = "core" if holding_core else "weapon"
        g, tx, _ = W.paths(key, what)
        h = W.planet_hold(key, what)
        item = None
        if os.path.exists(g):
            item = {"geo": g, "tex": tx, "bind": "hand",
                    "anim": {"hold": {"rotation": h["tp"]["rotation"], "position": h["tp"]["position"],
                                      "scale": (h["tp"]["scale"],) * 3}}}
        col = []
        for v in views:
            if suit is not None:
                anim_ = AS.suit_anim(suit, ["idle"], t)
                im = AS.render(suit, pose, anim_, view=v, size=(260, 340), weapon=item,
                               centre=(0, 14, 0), scale=7.0)
            else:
                import hd_scene as S
                yaw, pitch = {"q34": (-34, -10), "left": (90, -4), "front": (0, -4), "back": (180, -4),
                              "q34l": (34, -10), "right": (-90, -4)}.get(v, (-34, -10))
                a = item["anim"] if item else {}
                im = S.tp(item["geo"] if item else g, item["tex"] if item else tx, pose, a, yaw=yaw,
                          pitch=pitch, size=(260, 340), scale=7.0, centre=(0, 14, 0)) if item else None
            if im is not None:
                from PIL import ImageDraw
                ImageDraw.Draw(im).text((8, 6), f"{name}  t={t:.2f}", fill=(240, 240, 250))
                col.append(im)
        tile = Image.new("RGB", (260, 340 * len(col)), (14, 15, 20))
        for i, im in enumerate(col):
            tile.paste(im, (0, i * 340))
        tiles.append(tile)
    sheet = Image.new("RGB", (260 * len(tiles), tiles[0].size[1]), (14, 15, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 260, 0))
    os.makedirs(AC.SCRATCH, exist_ok=True)
    path = out or os.path.join(AC.SCRATCH, f"anim_{name.replace('.', '_')}.png")
    sheet.save(path)
    print(f"wrote {path}")
    return path


# ===========================================================================
def write(anims, meta):
    AC.write_json(ANIM_PATH, {"format_version": "1.10.0",
                              "animations": {k: anims[k] for k in sorted(anims)}})
    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
    with open(META_PATH, "w", encoding="utf-8") as fh:
        fh.write("// 自動生成（tools/astro/gen_astro_anim.py）。全身モーションの [長さ(秒), ブレンド可否]。\n")
        fh.write("// 名前は animation.astro.p. を除いた物。惑星の版 `${key}.${name}` があればそちらを優先して再生する。\n")
        fh.write("export const ANIM_META = ")
        json.dump({k: meta[k] for k in sorted(meta)}, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    def opt(name, default=None):
        if name in argv:
            i = argv.index(name)
            return argv[i + 1] if i + 1 < len(argv) else default
        return default
    if "--preview" in argv:
        preview(opt("--preview"), opt("--planet"), int(opt("--frames", 8)), opt("--view"))
        return 0
    anims, meta, res_all = build()
    write(anims, meta)
    errors = validate(anims, res_all)
    shared = sum(1 for k in meta if "." not in k)
    print(f"  player animations: {len(anims)} ({shared} shared, {len(anims) - shared} per planet)")
    if "--check" in argv:
        for name, (d, bone, t) in clip_report(res_all):
            print(f"  CLIP {name:24s} {d:4.1f}px into {bone} at {t:.2f}s")
    for e in errors:
        print(f"  ERROR {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
