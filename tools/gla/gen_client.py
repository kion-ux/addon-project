# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — 資源パックのクライアント側 (企画書 §05 / §06 / §07)。

ここが書くのは「何を、どの動きで、どう描くか」の結線だけ:

* エンティティ定義 — 訓練用の的2種と、内部表示体2種の描画設定
* 形態アタッチャブル 6枚 — 変身したプレイヤーの全身を差し替える本命
* 描画コントローラ — 既定と、被弾の明滅を持つ .glow
* アイテムのアイコン4枚と、それを登録する item_texture.json

形（geometry と png）は gen_models.py、動き（clip と controller）は
gen_anim.py が作る。このファイルはその2つを束ねるだけなので、形態や技が
増えても変わるのは spec.py の表だけで済む（企画書 §09 の狙い）。

アタッチャブルが要になる理由 (企画書 §17 QA-05 全身の可視性):
変身の見た目は「プレイヤーを隠して、頭スロットの装備として全身モデルを
着せる」方式で出す。だから アタッチャブルの identifier は BP 側の
形態表示体アイテムの id と1文字も違ってはいけない — 違うと装備しても
何も描かれず、プレイヤーだけが消える。ここでは spec.form_item() から
引いて、名前を二度書かない。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

from PIL import Image                                   # noqa: E402

from mctexture import hexc, shade                       # noqa: E402

import palette                                          # noqa: E402
import spec                                             # noqa: E402

NS = spec.NS
RP = os.path.join(ROOT, spec.RP_DIR)
ENT = os.path.join(RP, "entity")
ATT = os.path.join(RP, "attachables")
RC_DIR = os.path.join(RP, "render_controllers")
ITEM_DIR = os.path.join(RP, "textures", "items")

# 資産の種類ごとに format_version が違う。怪獣8号パックと同じ値に揃える。
CLIENT_FMT = "1.10.0"          # client_entity / attachable
RC_FMT = "1.8.0"               # render_controllers

# 識別子の接頭辞。企画書 §18「他パックとの競合」— 4種すべてを NS で括る。
A = f"animation.{NS}."
C = f"controller.animation.{NS}."
TEX = f"textures/entity/{NS}/"
RENDER = f"controller.render.{NS}.default"
RENDER_GLOW = f"controller.render.{NS}.glow"

#  光るテクセル (alpha 254) を持つモデルがあるので既定の材質はこれ。
#  投げた雷の芯は crack パターンで発光前提に塗ってある (palette.VFX_BOLT)。
MATERIAL = "entity_emissive_alpha"


def dump(path: str, doc: dict) -> None:
    """唯一の書き出し口。Painter.save() と違いディレクトリを自分で作る。

    ensure_ascii=False は必須 — 生成物を人が読んで直せる状態に保つ。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ===============================================================  ENTITIES
def client(identifier: str, texture: str, geometry: str,
           animations: dict, animate: list, egg=None,
           material: str = MATERIAL, render: str = RENDER,
           particles=None) -> dict:
    """client_entity 1件。怪獣8号パックの client() と同じ並びを保つ。

    怪獣8号版にある `extra` は落としてある — 呼び出し側から
    identifier や textures を後から上書きできる口で、使っていないのに
    事故だけ起こせるため（あちらも全呼び出しで未使用）。
    """
    desc = {
        "identifier": identifier,
        "materials": {"default": material},
        "textures": {"default": TEX + texture},
        "geometry": {"default": geometry},
        "animations": animations,
        "scripts": {"animate": animate},
        "render_controllers": [render],
    }
    if particles:
        desc["particle_effects"] = particles
    if egg:
        desc["spawn_egg"] = {"base_color": egg[0], "overlay_color": egg[1]}
    return {"format_version": CLIENT_FMT,
            "minecraft:client_entity": {"description": desc}}


#  モデルを塗ったパレットと同じものをここでも引く。スポーンエッグの色を
#  手で決めると、的の色を変えたときに卵だけ取り残される (企画書 §06)。
MOB_PALETTE = {
    "dummy": palette.DUMMY,
    "dummy_small": palette.DUMMY,
    "vfx_fist": palette.VFX_FIST,
    "vfx_bolt": palette.VFX_BOLT,
}


def egg_colours(m: spec.Mob):
    """スポーンエッグの2色。配布しない表示体には卵を出さない。

    spec.Mob.summonable が「配布してよいか＝卵を出すか」なので、
    内部表示体（拳・雷）はここで None になり spawn_egg 自体が消える。
    """
    if not m.summonable:
        return None
    pal = MOB_PALETTE[m.geo]
    accent = pal.get("mark") or pal.get("edge") or pal["base"]
    return (pal["base"]["base"], accent["base"])


def gen_entities() -> int:
    """spec.MOBS をそのまま client_entity にする。

    animations を空にしてあるのは手抜きではない: gen_anim.py が作るのは
    形態のクリップと技のクリップだけで、的や表示体の専用クリップは無い。
    無い id を書くと参照切れになり、実機では静かに描画が落ちる。
    的の「立っているだけ」はバニラの既定挙動で十分成立する。
    """
    for m in spec.MOBS:
        dump(os.path.join(ENT, m.slug + ".entity.json"),
             client(m.id, m.geo, m.geometry, {}, [], egg=egg_colours(m)))
    eggs = sum(1 for m in spec.MOBS if m.summonable)
    print(f"  client entities {len(spec.MOBS):2d}  (スポーンエッグ {eggs})")
    return len(spec.MOBS)


# ============================================================  ATTACHABLES
#  アタッチャブルに載せるクリップ。短いキーは
#  controller.animation.gla.form が状態名として引く側なので、
#  コントローラの状態と1対1で揃える (企画書 §07 コントローラの分離)。
#  idle / walk / run / air / land / crouch  … コントローラが出し分ける移動系
#  laugh / strafe / hurt                    … コントローラは出さない。
#      看板演出 (企画書 §08) と、左右移動・被弾 (企画書 §07 の必要な動作) を
#      スクリプトから直接鳴らすための口。組み込みのクエリだけでは
#      「横に動いている」「今殴られた」を出し分けられないため。
FORM_CLIPS = spec.FORM_CLIPS       # 一覧は spec.py 側が持つ

#  攻撃中かどうかを Molang 変数へ拾っておく。技の専用クリップは
#  スクリプトから再生する「best effort」なので、変数が未定義のまま
#  参照されても落ちないよう ?? で初期値を与える（怪獣8号側と同じ書き方）。
PRE_ANIMATION = "v.swing = math.max(v.attack_time ?? 0.0, 0.0);"


def form_attachable(form: spec.Form) -> dict:
    """形態1つ分の全身表示体。

    アタッチャブルは1つの識別子に1つの geometry しか持てないので、
    形態の数だけこの枚数が要る (spec.ITEMS の form_* と同じ数)。

    parent_setup の helmet_layer_visible = 0.0 は、頭スロットに装備した
    ことで出るバニラの兜レイヤーを消すためのもの。プレイヤー本体を隠す
    のはこれではなく BP 側のスクリプト — ここだけ直しても本体は消えない
    (企画書 §17 QA-04 変身・解除20往復で二重表示として現れる)。
    """
    anims = {k: f"{A}{form.key}.{k}" for k in FORM_CLIPS}
    anims["controller"] = C + "form"
    return {
        "format_version": CLIENT_FMT,
        "minecraft:attachable": {
            "description": {
                # BP の形態表示体アイテムと同じ id。ここが本体の接合点。
                "identifier": spec.form_item(form.key),
                "materials": {"default": MATERIAL,
                              "enchanted": "entity_alphatest_glint"},
                "textures": {"default": TEX + form.texture,
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": form.geometry},
                "animations": anims,
                "scripts": {
                    "parent_setup": "variable.helmet_layer_visible = 0.0;",
                    "pre_animation": [PRE_ANIMATION],
                    "animate": ["controller"],
                },
                "render_controllers": [RENDER],
            }
        }
    }


def gen_attachables() -> int:
    for f in spec.FORMS:
        dump(os.path.join(ATT, f"form_{f.key}.attachable.json"),
             form_attachable(f))
    print(f"  attachables     {len(spec.FORMS):2d}  "
          f"({len(FORM_CLIPS)} クリップ + コントローラ1)")
    return len(spec.FORMS)


# =======================================================  RENDER CONTROLLERS
def gen_render_controllers() -> int:
    """描画コントローラ。生成物の中で唯一「増えない」ファイル。

    既定は素通し。.glow は被弾の明滅用で、スクリプトが
    variable.hurt_flash を上げたときだけ白く乗る。上限 0.6 なのは
    暗い形態（覇気・ギア4）が真っ白に飛ぶのを避けるため (企画書 §04)。
    """
    dump(os.path.join(RC_DIR, f"{NS}.render_controllers.json"), {
        "format_version": RC_FMT,
        "render_controllers": {
            RENDER: {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
            },
            RENDER_GLOW: {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
                "overlay_color": {
                    "r": 1.0, "g": 1.0, "b": 1.0,
                    "a": "math.clamp(variable.hurt_flash, 0.0, 0.6)",
                },
            },
        },
    })
    print("  render ctrl      1  (default / glow の2本)")
    return 1


# ==================================================================  ICONS
#  アイコンの色は palette.ICON から引く。手に持った実物と同じ定義元に
#  しておけば、ホットバーの絵と実物の色がずれない (企画書 §06)。
_INK = shade(hexc(palette.ICON["base"]["dark"]), 0.70)


def _c(style: str, key: str = "base"):
    return hexc(palette.ICON[style][key])


#  1文字1色。大文字＝明部、小文字＝基本色か陰、という読み方で統一する。
COLS = {
    ".": None,
    "k": _INK,
    "s": _c("straw"), "S": _c("straw", "light"), "z": _c("straw", "second"),
    "b": _c("hatband"), "B": _c("hatband", "light"),
    "f": _c("fruit"), "F": _c("fruit", "light"), "v": _c("fruit", "second"),
    "c": _c("fruit_swirl"),
    "g": _c("stem"), "G": _c("stem", "light"),
    "w": _c("wrap"), "W": _c("wrap", "light"), "u": _c("wrap", "second"),
    "r": _c("wrap_tie"), "R": _c("wrap_tie", "light"),
    "l": _c("glass", "second"), "L": _c("glass"), "d": _c("glass", "dark"),
    "m": _c("brass"), "M": _c("brass", "light"), "n": _c("brass", "second"),
    "x": _c("needle"), "X": _c("needle", "light"),
}

#  企画書 §06「小さくても読める輪郭」— 16x16 では色より形が先に届く。
#  4つが一目で見分くよう、輪郭の性格を意図的にばらしてある:
#      麦わら帽子 … 横に広い楕円（つばが画面幅いっぱい）
#      悪魔の実   … 縦に丸い塊 ＋ 上に伸びる軸
#      拳の包帯   … 四角い巻きの塊 ＋ 斜めに垂れる端
#      ログポース … 丸い球 ＋ 下に開いた腕輪のコ字
#  どれも同じ濃い輪郭線 (k) で囲み、面の色が暗い場所でも形だけは残す。
ART = {}

#  つば → 山 → 帯 の3要素だけ。編み目を描くと 16px では灰色に潰れる。
#  山は上を1段すぼめ、帯は山より左右へ1マス出す。この2つを省くと
#  四角い箱に読めて、他の3つと同じ「塊」になってしまう。
ART["straw_hat"] = """
................
................
......kkkk......
.....kSSSSk.....
....kSSSSSSk....
....kssssssk....
...kbbBBBBbbk...
...kbBBBBBBbk...
.kssssssssssssk.
ksSSSSSSSSSSSSsk
kszzzzzzzzzzzzsk
.kzzzzzzzzzzzzk.
..kkkkkkkkkkkk..
................
................
................
"""

#  渦は太さの違う3本だけ入れる。左右対称にすると模様に見えず玉になる。
ART["devil_fruit"] = """
................
.......kgk......
......kgGGk.....
.....kkffkk.....
...kkfFFfffkk...
..kfFFffcfffvk..
.kfFFfccfccffvk.
.kfFffcffcffvvk.
.kffcffccffcvvk.
.kffcfcffffcvvk.
..kffccffccfvk..
...kkffvvvvkk...
.....kkvvkk.....
................
................
................
"""

#  巻きの段（明→基本→陰）を3段だけ繰り返し、赤い結びを縦に1本通す。
#  上下の角を1マスずつ落として「巻いた束」にし、垂れた端を左下へ流す。
#  角を残すと本や窓に読めるので、この面取りは飾りではなく識別のため。
ART["fist_wrap"] = """
................
................
................
..kkkkkkkkkk....
..kwwwrrwwwk....
.kWWWWrRWWWWk...
.kuuuurruuuuk...
.kwwwwrrwwwwk...
.kWWWWrRWWWWk...
.kuuuurruuuuk...
..kwwwrrwwwk....
..kkkkkkkkkk....
........kwWk....
.......kwWk.....
.......kkk......
................
"""

#  球＋台座＋腕輪。針は2マスの斜めに留める — 長くすると球の中で
#  折れ線に見えて、方位磁針ではなくヒビに読める。
ART["log_pose"] = """
................
......kkkk......
....kkLLLLkk....
...klLLLLLLlk...
..klLWWLLLLLlk..
..klLWLLxXLLlk..
..klLLLxxLLLlk..
...klLdLLLLlk...
....kklLLlkk....
...kmmmmmmmmk...
...kmMMMMMMmk...
....kmm..mmk....
....kmn..nmk....
....kmmmmmmk....
.....kkkkkk.....
................
"""


def draw_icon(name: str, art: str) -> None:
    """ASCII のドット絵 → 16x16 の RGBA PNG。怪獣8号側と同じ書き方。

    未知の文字は COLS.get() が None を返して透明のまま残る。ここは
    静かな事故になるので、check() 側で先に全文字を突き合わせてある。
    """
    rows = [r for r in art.strip("\n").split("\n") if r]
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows[:16]):
        for x, ch in enumerate(row[:16]):
            col = COLS.get(ch)
            if col:
                px[x, y] = (col[0], col[1], col[2], 255)
    os.makedirs(ITEM_DIR, exist_ok=True)
    img.save(os.path.join(ITEM_DIR, name + ".png"))


def gen_icons() -> int:
    """spec が「見える」と言ったアイテムの分だけ描く。

    形態表示体 (hidden) は麦わら帽子のアイコンを使い回すので、ここでは
    枚数が増えない — アイコンを増やすと、クリエイティブに出ない
    アイテムの絵だけが atlas に溜まる (企画書 §14 増やさない構造)。
    """
    names = sorted({it.icon for it in spec.ITEMS})
    for name in names:
        draw_icon(name, ART[name])
    visible = sum(1 for it in spec.ITEMS if not it.hidden)
    print(f"  item icons      {len(names):2d}  "
          f"(表示アイテム {visible} / 内部 {len(spec.ITEMS) - visible} は共用)")
    return len(names)


def gen_item_texture() -> int:
    """アイコンの atlas 登録。キーは Item.icon と1文字も違えられない。

    resource_pack_name は NS。他パックと同じ名前にすると、
    どちらか片方の atlas が丸ごと無視される (企画書 §18)。
    """
    names = sorted({it.icon for it in spec.ITEMS})
    dump(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": NS,
        "texture_name": "atlas.items",
        "texture_data": {n: {"textures": f"textures/items/{n}"} for n in names},
    })
    print(f"  item_texture     1  ({len(names)} キー)")
    return 1


# ===========================================================================
def check() -> None:
    """生成前に前提を潰す。ここで落ちるものは実機では静かに壊れる。"""
    #  絵の文字と大きさ。未定義の文字は透明の穴になるだけで警告が出ない。
    for name, art in ART.items():
        rows = [r for r in art.strip("\n").split("\n") if r]
        if len(rows) != 16:
            raise SystemExit(f"icon {name}: 16行のはず ({len(rows)}行)")
        for y, row in enumerate(rows):
            if len(row) != 16:
                raise SystemExit(f"icon {name}: {y}行目が {len(row)}文字")
            for ch in row:
                if ch not in COLS:
                    raise SystemExit(f"icon {name}: 未定義の文字 {ch!r}")
    #  spec が要求するアイコンと、手で描いた絵の突き合わせ。
    need = {it.icon for it in spec.ITEMS}
    if need - set(ART):
        raise SystemExit(f"アイコンの絵が無い: {sorted(need - set(ART))}")
    if set(ART) - need:
        raise SystemExit(f"spec が使わないアイコン: {sorted(set(ART) - need)}")
    #  アタッチャブルの id は BP のアイテム id と同一でなければならない。
    for f in spec.FORMS:
        if spec.form_item(f.key) not in {i.id for i in spec.ITEMS}:
            raise SystemExit(f"{f.key}: 形態表示体アイテムが spec.ITEMS に無い")
    #  モデルを塗ったパレットが全エンティティ分そろっているか。
    for m in spec.MOBS:
        if m.geo not in MOB_PALETTE:
            raise SystemExit(f"{m.id}: {m.geo} のパレットを知らない")


def cross_check() -> None:
    """gen_anim.py の生成物との突き合わせ。まだ走っていなければ黙る。

    警告に留めるのは、生成の順番 (models → anim → client) を
    このファイルが強制すべきではないから。build 側が順に呼ぶ。
    """
    anim_path = os.path.join(RP, "animations", f"{NS}.animation.json")
    ctrl_path = os.path.join(RP, "animation_controllers",
                             f"{NS}.animation_controllers.json")
    if not (os.path.exists(anim_path) and os.path.exists(ctrl_path)):
        print("  (アニメーション未生成 — 参照の突き合わせは省略)")
        return
    with open(anim_path, encoding="utf-8") as fh:
        clips = set(json.load(fh).get("animations", {}))
    with open(ctrl_path, encoding="utf-8") as fh:
        ctrls = json.load(fh).get("animation_controllers", {})

    missing = [f"{A}{f.key}.{k}" for f in spec.FORMS for k in FORM_CLIPS
               if f"{A}{f.key}.{k}" not in clips]
    if missing:
        print(f"  警告: 存在しないクリップを参照 {missing[:4]} 他{len(missing)}件")
    if C + "form" not in ctrls:
        print(f"  警告: {C}form が未生成")
        return
    plays = set()
    for st in ctrls[C + "form"].get("states", {}).values():
        for a in st.get("animations", []):
            plays.add(a if isinstance(a, str) else list(a)[0])
    unmapped = sorted(plays - set(FORM_CLIPS))
    if unmapped:
        print(f"  警告: コントローラが {unmapped} を再生するが割り当てが無い")


def main() -> None:
    print(f"client pack ({NS}):")
    n = {
        "entities": gen_entities(),
        "attachables": gen_attachables(),
        "render": gen_render_controllers(),
        "atlas": gen_item_texture(),
    }
    icons = gen_icons()
    cross_check()
    total = n["entities"] + n["attachables"] + n["render"] + n["atlas"]
    print(f"\n  {total} json + {icons} png  ->  {spec.RP_DIR}")
    print(f"  {len(spec.FORMS)} 形態ぶんの全身表示体 — "
          f"BP の {spec.form_item(spec.FORM_ORDER[0])} 系と id が一致")


if __name__ == "__main__":
    check()
    main()
