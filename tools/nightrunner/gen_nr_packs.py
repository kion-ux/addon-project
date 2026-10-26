# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — マニフェスト・共有の登録ファイル・言語ファイル・パックアイコン。

**ビルドの最後に走る**（DESIGN.md §1）。ほかの生成器が `tools/nightrunner/.frag/<登録名>/<生成器>.json` に
書いた断片を全部まとめて、RP / BP の共有ファイルを書き出す:

| 断片 | 書き出す先 |
|---|---|
| `item_texture` | RP `textures/item_texture.json`（resource_pack_name `nightrunner`、texture_name `atlas.items`） |
| `terrain_texture` | RP `textures/terrain_texture.json`（texture_name `atlas.terrain`、padding・mip 段数付き） |
| `sound_definitions` | RP `sounds/sound_definitions.json`（format_version `1.20.20`、`sound_definitions` で包む） |
| `blocks` | RP `blocks.json`（format_version `[1, 1, 0]`） |
| `flipbook` | RP `textures/flipbook_textures.json`（配列） |
| `sounds_json` | RP `sounds.json`（入れ子の辞書を深くまとめる） |
| `lang` | BP / RP `texts/{ja_JP,en_US}.lang` と `texts/languages.json` |

言語ファイルは 4 層で組み立てる（上ほど強い）:

1. **パック**（このファイル）: `pack.name` / `pack.description`
2. **spec**（`nr_spec.py` があれば）: ゾンビ 50 体・武器・アイテム・ブロック・小道具・飛び道具の名前。
   `item.<id>` の鍵には同じ値の `item.<id>.name` も足す（display_name を書かないアイテムでも名前が出るように）
3. **断片**（`lang`）: 生成器ごとの文言
4. **予備**: 上で埋まらなかった鍵だけ（gib の名前・ゾンビのスポーンエッグ名）

1〜3 の間で**同じ鍵に違う値**が来たら、全部を一覧にして**失敗する**（どちらが正しいか黙って選ばない）。
同じ値の重複は許す。断片どうしの辞書（item_texture など）も同じ規則。

パックアイコン: `gen_nr_ui.py` が RP `textures/nr/ui/pack_icon.png`（任意で BP 用の
`textures/nr/ui/pack_icon_bp.png`）を書いていればそれを 256×256 にして両パックの `pack_icon.png` に使う。
無ければ仮のアイコン（暗い赤と黒に「NR」）を描く（フォントに頼らず多角形で描くので、どの環境でも同じバイト列）。

使い方: `python3 tools/nightrunner/gen_nr_packs.py`（普通は build_nr.py から）。
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nr_common import (BP, FRAG, FRAG_KINDS, HERE, MIN_ENGINE, RP, SERVER_API,  # noqa: E402
                       SERVER_UI_API, VERSION_TUPLE, read_frags, write_json, write_text)

PRODUCER = "gen_nr_packs"

# 一度だけ uuid4 で作って固定した値（変えると既存のワールドから別のパック扱いになる）
UUID = {
    "bp": "904d60a3-5fc8-4f47-9dab-71d589c66052",
    "bp_data": "cdc18b79-c5dc-485c-984c-d8d278e8d00d",
    "bp_script": "7f788db9-e0dc-4934-a78e-e24d4be17361",
    "rp": "2a3572b2-1a5a-4813-b045-90cac0129fd5",
    "rp_res": "e3d12a44-42b8-424a-9c52-dcc3d183f2fe",
}
AUTHORS = ["Night Runner Project"]
LANGS = ("en_US", "ja_JP")          # languages.json の並び
RESOURCE_PACK_NAME = "nightrunner"
TERRAIN_PADDING = 8
TERRAIN_MIPS = 4
SOUND_DEFS_FORMAT = "1.20.20"
BLOCKS_FORMAT = [1, 1, 0]

# パックが持つ文言（層 1）
PACK_LANG = {
    "ja_JP": {
        "pack.name": "NIGHT RUNNER: 感染都市",
        "pack.description": "パルクール × ゾンビ × 部位破壊ゴア。屋上を走り、夜を生き延びろ。"
                            "ゴアレベル 0〜100（既定 100）",
    },
    "en_US": {
        "pack.name": "NIGHT RUNNER: Infected City",
        "pack.description": "Parkour x zombies x dismemberment gore. Run the rooftops, survive the night. "
                            "Gore level 0-100 (default 100)",
    },
}

# 予備の文言（層 4。ほかの層に無いときだけ使う）
FALLBACK_LANG = {
    "ja_JP": {"entity.nr:gib.name": "ちぎれた部位"},
    "en_US": {"entity.nr:gib.name": "Severed Body Part"},
}

UI_ICON = os.path.join(RP, "textures", "nr", "ui", "pack_icon.png")
UI_ICON_BP = os.path.join(RP, "textures", "nr", "ui", "pack_icon_bp.png")

_warnings: list = []
_conflicts: list = []


def warn(msg: str) -> None:
    _warnings.append(msg)
    print(f"  WARNING [packs] {msg}")


# ===========================================================================
#  マニフェスト
# ===========================================================================
def manifests() -> None:
    meta = {"authors": AUTHORS, "license": "MIT", "product_type": "addon"}
    write_json(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": UUID["bp"],
                   "version": VERSION_TUPLE, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUID["bp_data"], "version": VERSION_TUPLE},
            {"type": "script", "language": "javascript", "uuid": UUID["bp_script"],
             "version": VERSION_TUPLE, "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": UUID["rp"], "version": VERSION_TUPLE},
            {"module_name": "@minecraft/server", "version": SERVER_API},
            {"module_name": "@minecraft/server-ui", "version": SERVER_UI_API},
        ],
        "metadata": meta,
    })
    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": UUID["rp"],
                   "version": VERSION_TUPLE, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID["rp_res"], "version": VERSION_TUPLE}],
        "dependencies": [{"uuid": UUID["bp"], "version": VERSION_TUPLE}],
        "metadata": meta,
    })


# ===========================================================================
#  断片のまとめ
# ===========================================================================
def _short(v) -> str:
    s = json.dumps(v, ensure_ascii=False, sort_keys=True)
    return s if len(s) <= 140 else s[:137] + "..."


def merge_flat(kind: str, check=None, unwrap: str = None, drop=()) -> dict:
    """辞書の断片を 1 段でまとめる。同じ鍵に違う値なら衝突として記録。"""
    out: dict = {}
    owner: dict = {}
    for producer, doc in read_frags(kind):
        if not isinstance(doc, dict):
            _conflicts.append(f"{kind}/{producer}.json: 辞書でない（{type(doc).__name__}）")
            continue
        if unwrap and set(doc) - set(drop) == {unwrap} and isinstance(doc[unwrap], dict):
            warn(f"{kind}/{producer}.json が '{unwrap}' で包まれている（中身の辞書だけを書く約束）。剥がして使う")
            doc = doc[unwrap]
        for k in drop:
            if k in doc:
                warn(f"{kind}/{producer}.json の '{k}' は gen_nr_packs が書くので無視する")
                doc = {kk: vv for kk, vv in doc.items() if kk != k}
        for key, val in doc.items():
            if check:
                msg = check(key, val)
                if msg:
                    _conflicts.append(f"{kind}/{producer}.json: {key}: {msg}")
                    continue
            if key in out:
                if out[key] != val:
                    _conflicts.append(f"{kind}: 鍵 {key!r} が食い違う — {owner[key]}: {_short(out[key])} / "
                                      f"{producer}: {_short(val)}")
                continue
            out[key] = val
            owner[key] = producer
    return dict(sorted(out.items()))


def _check_texture_entry(key, val):
    if not isinstance(val, dict) or "textures" not in val:
        return "値は {\"textures\": ...} の辞書にする"
    return None


def _check_sound_def(key, val):
    if not isinstance(val, dict) or not isinstance(val.get("sounds"), list) or not val["sounds"]:
        return "値は {\"category\": ..., \"sounds\": [...]}（sounds は空でないリスト）にする"
    return None


def _check_block_entry(key, val):
    if ":" not in key:
        return "鍵はフル ID（nr:xxx）にする"
    if not isinstance(val, dict):
        return "値は辞書にする"
    return None


def deep_merge(dst: dict, src: dict, path: str, producer: str, owners: dict, kind: str) -> None:
    for k, v in src.items():
        p = f"{path}/{k}"
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            deep_merge(dst[k], v, p, producer, owners, kind)
        elif k in dst:
            if dst[k] != v:
                _conflicts.append(f"{kind}: {p} が食い違う — {owners.get(p, '?')}: {_short(dst[k])} / "
                                  f"{producer}: {_short(v)}")
        else:
            dst[k] = json.loads(json.dumps(v))
            owners[p] = producer
            if isinstance(v, dict):
                _own_tree(v, p, producer, owners)


def _own_tree(d: dict, path: str, producer: str, owners: dict) -> None:
    for k, v in d.items():
        owners[f"{path}/{k}"] = producer
        if isinstance(v, dict):
            _own_tree(v, f"{path}/{k}", producer, owners)


def _sorted_tree(d):
    if isinstance(d, dict):
        return {k: _sorted_tree(d[k]) for k in sorted(d)}
    return d


def merge_sounds_json() -> dict:
    out: dict = {}
    owners: dict = {}
    for producer, doc in read_frags("sounds_json"):
        if not isinstance(doc, dict):
            _conflicts.append(f"sounds_json/{producer}.json: 辞書でない")
            continue
        deep_merge(out, doc, "", producer, owners, "sounds_json")
    return _sorted_tree(out)


def merge_flipbook() -> list:
    out: list = []
    seen: dict = {}
    for producer, doc in read_frags("flipbook"):
        if isinstance(doc, dict):
            doc = [doc]
            warn(f"flipbook/{producer}.json がリストでない（1 件として扱う）")
        if not isinstance(doc, list):
            _conflicts.append(f"flipbook/{producer}.json: リストでない")
            continue
        for ent in doc:
            if not isinstance(ent, dict) or "atlas_tile" not in ent or "flipbook_texture" not in ent:
                _conflicts.append(f"flipbook/{producer}.json: atlas_tile と flipbook_texture が要る: {_short(ent)}")
                continue
            tile = ent["atlas_tile"]
            if tile in seen:
                if seen[tile][1] != ent:
                    _conflicts.append(f"flipbook: atlas_tile {tile!r} が食い違う — {seen[tile][0]} / {producer}")
                continue
            seen[tile] = (producer, ent)
            out.append(ent)
    return sorted(out, key=lambda e: e["atlas_tile"])


def write_registries() -> dict:
    counts = {}
    items = merge_flat("item_texture", _check_texture_entry, unwrap="texture_data",
                       drop=("resource_pack_name", "texture_name"))
    write_json(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": RESOURCE_PACK_NAME, "texture_name": "atlas.items", "texture_data": items})
    counts["item_texture"] = len(items)

    terrain = merge_flat("terrain_texture", _check_texture_entry, unwrap="texture_data",
                         drop=("resource_pack_name", "texture_name", "padding", "num_mip_levels"))
    write_json(os.path.join(RP, "textures", "terrain_texture.json"), {
        "resource_pack_name": RESOURCE_PACK_NAME, "texture_name": "atlas.terrain",
        "padding": TERRAIN_PADDING, "num_mip_levels": TERRAIN_MIPS, "texture_data": terrain})
    counts["terrain_texture"] = len(terrain)

    sdefs = merge_flat("sound_definitions", _check_sound_def, unwrap="sound_definitions",
                       drop=("format_version",))
    write_json(os.path.join(RP, "sounds", "sound_definitions.json"), {
        "format_version": SOUND_DEFS_FORMAT, "sound_definitions": sdefs})
    counts["sound_definitions"] = len(sdefs)

    blocks = merge_flat("blocks", _check_block_entry, drop=("format_version",))
    write_json(os.path.join(RP, "blocks.json"), {"format_version": BLOCKS_FORMAT, **blocks})
    counts["blocks"] = len(blocks)

    flip = merge_flipbook()
    write_json(os.path.join(RP, "textures", "flipbook_textures.json"), flip)
    counts["flipbook"] = len(flip)

    sj = merge_sounds_json()
    write_json(os.path.join(RP, "sounds.json"), sj)
    counts["sounds_json"] = sum(len(v) if isinstance(v, dict) else 1 for v in sj.values())
    return counts


# ===========================================================================
#  言語
# ===========================================================================
def spec_lang():
    """nr_spec.py から名前の鍵を集める。nr_spec.py がまだ無ければ None。"""
    if not os.path.exists(os.path.join(HERE, "nr_spec.py")):
        warn("tools/nightrunner/nr_spec.py がまだ無いので spec の名前（ゾンビ・武器・アイテム…）は入らない")
        return None, None
    import nr_spec  # 中で例外が出たらそのまま落とす（壊れた spec を黙って飛ばさない）
    spec = {c: {} for c in LANGS}
    extra = {c: {} for c in LANGS}       # 予備（スポーンエッグ）
    for z in getattr(nr_spec, "ZOMBIES", []):
        ident = f"nr:z_{z['key']}"
        spec["ja_JP"][f"entity.{ident}.name"] = z["ja"]
        spec["en_US"][f"entity.{ident}.name"] = z["en"]
        extra["ja_JP"][f"item.spawn_egg.entity.{ident}.name"] = f"{z['ja']}のスポーンエッグ"
        extra["en_US"][f"item.spawn_egg.entity.{ident}.name"] = f"Spawn {z['en']}"
    if hasattr(nr_spec, "lang_entries"):
        le = nr_spec.lang_entries()
        for code in LANGS:
            for k, v in le.get(code, {}).items():
                if k in spec[code] and spec[code][k] != v:
                    _conflicts.append(f"lang/spec: {code} {k} が spec の中で食い違う")
                spec[code][k] = v
                # item.<id> だけの鍵には .name 版も（display_name 無しのアイテムの既定の鍵）
                if k.startswith("item.") and not k.endswith(".name"):
                    spec[code].setdefault(k + ".name", v)
    else:
        warn("nr_spec に lang_entries() が無い（武器・アイテム・ブロックの名前が入らない）")
    return spec, extra


def build_lang():
    layers = []                                        # [(層の名前, {code: {k: v}})]
    layers.append(("gen_nr_packs", PACK_LANG))
    spec, spec_extra = spec_lang()
    if spec:
        layers.append(("nr_spec", spec))
    for producer, doc in read_frags("lang"):
        if not isinstance(doc, dict) or not set(doc) <= set(LANGS):
            _conflicts.append(f"lang/{producer}.json: 鍵は {list(LANGS)} だけ（{sorted(doc) if isinstance(doc, dict) else doc}）")
            continue
        layers.append((producer, doc))
    out = {c: {} for c in LANGS}
    owner = {c: {} for c in LANGS}
    for name, doc in layers:
        for code, kv in doc.items():
            for k, v in kv.items():
                if not isinstance(v, str):
                    _conflicts.append(f"lang/{name}: {code} {k} の値が文字列でない")
                    continue
                if "\n" in v or "\r" in v:
                    _conflicts.append(f"lang/{name}: {code} {k} に改行がある（.lang は 1 行 1 鍵。改行は %1 か ~LINEBREAK~ 等で）")
                    continue
                if "##" in v:
                    _conflicts.append(f"lang/{name}: {code} {k} に '##' がある（.lang ではそこからコメントになる）")
                    continue
                if "=" in k or not k or k != k.strip() or " " in k:
                    _conflicts.append(f"lang/{name}: {code} 鍵 {k!r} が不正（空白・'=' を含めない）")
                    continue
                if k in out[code]:
                    if out[code][k] != v:
                        _conflicts.append(f"lang: {code} {k} が食い違う — {owner[code][k]}: {out[code][k]!r} / "
                                          f"{name}: {v!r}")
                    continue
                out[code][k] = v
                owner[code][k] = name
    for extra in (spec_extra or {}, FALLBACK_LANG):
        for code, kv in extra.items():
            for k, v in kv.items():
                out[code].setdefault(k, v)
    # 片方の言語にしか無い鍵（validate_nr でも見るが、ここでも知らせる）
    only = sorted(set(out["ja_JP"]) ^ set(out["en_US"]))
    if only:
        warn(f"片方の言語にしか無い鍵 {len(only)} 件: {', '.join(only[:8])}{' …' if len(only) > 8 else ''}")
    return out


def write_lang(lang: dict) -> None:
    header = ["## NIGHT RUNNER: 感染都市 — 生成物（tools/nightrunner/gen_nr_packs.py）。直接編集しない",
              "## 名前は tools/nightrunner/nr_spec*.py、文言は各生成器の lang 断片が正"]

    def order(k):
        return (0 if k.startswith("pack.") else 1, k)
    for pack in (BP, RP):
        d = os.path.join(pack, "texts")
        write_json(os.path.join(d, "languages.json"), list(LANGS))
        for code in LANGS:
            lines = header + [f"{k}={lang[code][k]}" for k in sorted(lang[code], key=order)]
            write_text(os.path.join(d, f"{code}.lang"), "\n".join(lines) + "\n")


def name_coverage(lang: dict) -> None:
    """BP にあるもので名前が無いものを知らせる（エラーにするのは validate_nr）。"""
    missing = []
    for sub, prefix, suffix, key in (("entities", "entity.", ".name", "minecraft:entity"),
                                     ("blocks", "tile.", ".name", "minecraft:block")):
        folder = os.path.join(BP, sub)
        if not os.path.isdir(folder):
            continue
        for base, _d, files in os.walk(folder):
            for f in sorted(files):
                if not f.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(base, f), encoding="utf-8") as fh:
                        ident = json.load(fh)[key]["description"]["identifier"]
                except Exception:  # noqa: BLE001 — 壊れた JSON は validate_nr が報告する
                    continue
                for code in LANGS:
                    if f"{prefix}{ident}{suffix}" not in lang[code]:
                        missing.append(f"{code}:{prefix}{ident}{suffix}")
    if missing:
        warn(f"名前の無いエンティティ／ブロック {len(missing)} 件: {', '.join(missing[:6])}{' …' if len(missing) > 6 else ''}")


# ===========================================================================
#  パックアイコン
# ===========================================================================
def _letter_polys(ch: str, x0: float, y0: float, w: float, h: float, t: float):
    """'N' と 'R' を多角形の組で返す（フォントを使わない）。t は線の太さ。"""
    if ch == "N":
        return [
            [(x0, y0), (x0 + t, y0), (x0 + t, y0 + h), (x0, y0 + h)],
            [(x0 + w - t, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0 + w - t, y0 + h)],
            [(x0, y0), (x0 + t * 1.15, y0), (x0 + w, y0 + h), (x0 + w - t * 1.15, y0 + h)],
        ]
    if ch == "R":
        bowl_h = h * 0.54
        polys = [[(x0, y0), (x0 + t, y0), (x0 + t, y0 + h), (x0, y0 + h)]]
        # 上の弧（外側と内側の半楕円の間を多角形で）
        cx, cy = x0 + w - bowl_h / 2, y0 + bowl_h / 2
        ro_x, ro_y = bowl_h / 2, bowl_h / 2
        ri_x, ri_y = max(1.0, ro_x - t), max(1.0, ro_y - t)
        outer = [(cx + ro_x * math.cos(a), cy + ro_y * math.sin(a))
                 for a in np.linspace(-math.pi / 2, math.pi / 2, 24)]
        inner = [(cx + ri_x * math.cos(a), cy + ri_y * math.sin(a))
                 for a in np.linspace(math.pi / 2, -math.pi / 2, 24)]
        polys.append([(x0 + t * 0.5, y0)] + outer + [(x0 + t * 0.5, y0 + bowl_h)] +
                     [(x0 + t * 0.5, y0 + bowl_h - t)] + inner + [(x0 + t * 0.5, y0 + t)])
        # 脚
        polys.append([(x0 + w * 0.42, y0 + bowl_h - t * 0.3), (x0 + w * 0.42 + t * 1.1, y0 + bowl_h - t * 0.3),
                      (x0 + w, y0 + h), (x0 + w - t * 1.15, y0 + h)])
        return polys
    raise ValueError(ch)


def placeholder_icon(size: int = 256) -> Image.Image:
    """仮のパックアイコン（gen_nr_ui が本物を描くまで）。暗い赤と黒、血の飛沫、骨色の「NR」。"""
    S = size
    rng = random.Random(0x4E52)              # 'NR'
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    r = np.sqrt((x - 0.5) ** 2 + (y - 0.46) ** 2)
    inner = np.array([118, 10, 14], np.float32)
    outer = np.array([10, 4, 6], np.float32)
    t = np.clip(r / 0.62, 0, 1)[..., None] ** 1.4
    img = inner * (1 - t) + outer * t
    # 細かいざらつき（決まった種のノイズ）
    noise = np.random.default_rng(7).normal(0, 1, (S // 4, S // 4)).astype(np.float32)
    noise = np.array(Image.fromarray(noise).resize((S, S), Image.BICUBIC))
    img *= (1.0 + 0.07 * noise[..., None])
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    # 血の飛沫（にじんだ円と垂れ）
    splat = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(splat)
    for _ in range(46):
        cx, cy = rng.uniform(0.08, 0.92) * S, rng.uniform(0.05, 0.95) * S
        rr = rng.uniform(1.5, 9.0) * (S / 256)
        col = (rng.randint(70, 120), rng.randint(0, 10), rng.randint(0, 12), rng.randint(150, 235))
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
        if rng.random() < 0.35:
            ln = rng.uniform(8, 40) * (S / 256)
            d.rectangle([cx - rr * 0.35, cy, cx + rr * 0.35, cy + ln], fill=col)
            d.ellipse([cx - rr * 0.6, cy + ln - rr * 0.6, cx + rr * 0.6, cy + ln + rr * 0.6], fill=col)
    base.alpha_composite(splat.filter(ImageFilter.GaussianBlur(0.7)))

    # 文字「NR」（影 → 本体 → 垂れる血）
    letters = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(letters)
    lw, lh, th = S * 0.30, S * 0.42, S * 0.075
    gap = S * 0.07
    x0 = (S - (lw * 2 + gap)) / 2
    y0 = S * 0.26
    polys = _letter_polys("N", x0, y0, lw, lh, th) + _letter_polys("R", x0 + lw + gap, y0, lw, lh, th)
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for p in polys:
        sd.polygon([(px + S * 0.012, py + S * 0.016) for px, py in p], fill=(0, 0, 0, 200))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(S * 0.012)))
    for p in polys:
        ld.polygon(p, fill=(226, 214, 196, 255))
    # 文字の下端から垂れる血
    for i in range(7):
        dx = x0 + rng.uniform(0.05, 0.95) * (lw * 2 + gap)
        ln = rng.uniform(0.04, 0.14) * S
        wd = rng.uniform(0.010, 0.020) * S
        top = y0 + lh - S * 0.01
        ld.rectangle([dx - wd / 2, top, dx + wd / 2, top + ln], fill=(140, 8, 12, 255))
        ld.ellipse([dx - wd, top + ln - wd, dx + wd, top + ln + wd], fill=(140, 8, 12, 255))
    # 文字の上の汚れ（暗い斑点）
    for _ in range(60):
        px, py = x0 + rng.uniform(0, lw * 2 + gap), y0 + rng.uniform(0, lh)
        rr = rng.uniform(0.5, 2.2) * (S / 256)
        ld.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(120, 30, 26, 255))
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    for p in polys:
        md.polygon(p, fill=255)
    # 斑点は文字の中だけ・垂れは文字の外にも
    letters_a = np.array(letters)
    inside = np.array(mask) > 0
    blood = (letters_a[..., 0] == 140) & (letters_a[..., 1] == 8)
    keep = inside | blood
    letters_a[~keep] = 0
    base.alpha_composite(Image.fromarray(letters_a, "RGBA"))
    # 下の帯（街の地平線のシルエット）
    sky = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    kd = ImageDraw.Draw(sky)
    xx = 0.0
    while xx < S:
        bw = rng.uniform(0.05, 0.12) * S
        bh = rng.uniform(0.06, 0.20) * S
        kd.rectangle([xx, S - bh, xx + bw, S], fill=(6, 3, 4, 255))
        xx += bw + rng.uniform(0, 0.01) * S
    base.alpha_composite(sky)
    return base.convert("RGB")


def pack_icons() -> str:
    if os.path.exists(UI_ICON):
        rp_icon = Image.open(UI_ICON).convert("RGB")
        bp_icon = Image.open(UI_ICON_BP).convert("RGB") if os.path.exists(UI_ICON_BP) else rp_icon
        src = "gen_nr_ui"
    else:
        rp_icon = bp_icon = placeholder_icon()
        src = "placeholder"
    for pack, icon in ((BP, bp_icon), (RP, rp_icon)):
        if icon.size != (256, 256):
            icon = icon.resize((256, 256), Image.LANCZOS)
        os.makedirs(pack, exist_ok=True)
        icon.save(os.path.join(pack, "pack_icon.png"), optimize=True)
    return src


# ===========================================================================
def unknown_frag_kinds() -> None:
    if not os.path.isdir(FRAG):
        return
    for name in sorted(os.listdir(FRAG)):
        if os.path.isdir(os.path.join(FRAG, name)) and name not in FRAG_KINDS:
            warn(f".frag/{name}/ は知らない登録名（{', '.join(FRAG_KINDS)} のどれか）。まとめない")


def main() -> int:
    unknown_frag_kinds()
    manifests()
    counts = write_registries()
    lang = build_lang()
    icon = pack_icons()
    if _conflicts:
        print(f"\n  ERROR [packs] 断片の衝突・不正 {len(_conflicts)} 件（どちらが正しいか決めて片方を直すこと）:")
        for c in _conflicts:
            print("    - " + c)
        return 1
    write_lang(lang)
    name_coverage(lang)
    producers = sorted({p for k in FRAG_KINDS for p, _ in read_frags(k)})
    print(f"  packs: manifest / {', '.join(f'{k} {v}' for k, v in counts.items())} / "
          f"lang ja {len(lang['ja_JP'])} en {len(lang['en_US'])} / icon {icon}")
    print(f"  packs: 断片を書いた生成器: {', '.join(producers) if producers else '（まだ無い）'}")
    if _warnings:
        print(f"  packs: 警告 {len(_warnings)} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
