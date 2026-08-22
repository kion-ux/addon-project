# -*- coding: utf-8 -*-
"""3D weapon models, built to the researched canon designs.

Each weapon is a *builder* that adds cubes to a bone, so the same geometry is
used twice: as the held attachable for the player, and welded into an NPC's hand
so 亜白ミナ actually carries T-25101985 rather than a flat sprite.

Weapon space: origin at the grip, -Z forward, +Y up, 16 units = 1 m.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcmodel import Cube, Model  # noqa: E402
from mctexture import Painter  # noqa: E402
import palettes  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "packs", "kaiju8_RP")
GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "kaiju8", "weapons")
ATT_DIR = os.path.join(RP, "attachables")


def mk(bone, off, s):
    def add(origin, size, style, **kw):
        return bone.add(Cube(
            (origin[0] * s + off[0], origin[1] * s + off[1], origin[2] * s + off[2]),
            (size[0] * s, size[1] * s, size[2] * s), style, **kw))
    return add


# ===========================================================================
#  戦闘用ナイフ — 一般隊員の標準装備。刃長20cm、解体作業も兼ねる重厚な実用刃
# ===========================================================================
def combat_knife(bone, off=(0, 0, 0), s=1.0):
    a = mk(bone, off, s)
    a((-0.75, -0.75, 0.2), (1.5, 1.5, 3.2), "grip", uv_scale=6)
    a((-0.95, -0.95, 3.2), (1.9, 1.9, 0.8), "dark", uv_scale=6)
    a((-1.35, -1.05, -0.7), (2.7, 2.1, 0.7), "dark", uv_scale=6)
    a((-0.5, -0.95, -4.2), (1.0, 1.9, 3.6), "steel", uv_scale=6)
    a((-0.24, -1.05, -4.2), (0.48, 2.1, 3.6), "edge", uv_scale=6,
      decals={"east": "edge_glow"})
    a((-0.48, -0.9, -5.4), (0.96, 1.7, 1.3), "edge", uv_scale=6)
    return 7.0 * s


# ===========================================================================
#  DF-STD アサルトライフル — 現用小銃モチーフ。マガジンはユニソケット収納型
# ===========================================================================
def df_rifle(bone, off=(0, 0, 0), s=1.0):
    a = mk(bone, off, s)
    a((-1.5, -1.4, -10.0), (3.0, 4.0, 14.0), "dark", uv_scale=4)          # 機関部
    a((-1.7, 2.2, -11.0), (3.4, 0.9, 13.0), "steel", uv_scale=4)          # レール
    a((-0.9, -0.4, -19.0), (1.8, 1.8, 9.5), "steel", uv_scale=4)          # 銃身
    a((-1.35, -0.85, -25.0), (2.7, 2.7, 6.2), "dark", uv_scale=4)         # サプレッサー
    a((-1.4, -6.6, -6.5), (2.8, 5.4, 3.4), "green", uv_scale=4)           # ユニソケット
    a((-1.5, -5.0, -6.8), (3.0, 1.2, 3.8), "accent", uv_scale=5,
      decals={"north": "core"})                                          # ソケット表示灯
    a((-1.45, -1.7, 4.0), (2.9, 4.2, 7.0), "dark", uv_scale=4)            # 銃床
    a((-1.55, -0.6, 10.6), (3.1, 3.4, 1.6), "grip", uv_scale=5)
    a((-1.0, 2.9, -11.5), (2.0, 2.0, 6.5), "steel", uv_scale=5)           # 光学照準
    a((-0.8, 3.2, -12.0), (1.6, 1.4, 0.7), "core", uv_scale=6,
      decals={"north": "core"})
    a((-1.1, -5.6, -0.8), (2.2, 5.0, 2.6), "grip", uv_scale=5,
      rotation=(12, 0, 0))                                               # 握把
    return 28.0 * s


# ===========================================================================
#  SW-2033 — 保科宗四郎の二刀。黒染めの忍者刀型、発光部なし
# ===========================================================================
def twin_sw2033(bone, off=(0, 0, 0), s=1.0, twin=False):
    a = mk(bone, off, s)
    a((-0.7, -0.7, 0.3), (1.4, 1.4, 3.4), "sw_wrap", uv_scale=6)          # 柄巻
    a((-0.9, -0.9, 3.5), (1.8, 1.8, 0.7), "sw_blade", uv_scale=6)         # 柄頭
    a((-1.6, -1.2, -0.7), (3.2, 2.4, 0.8), "sw_blade", uv_scale=6)        # 角鍔
    a((-0.5, -0.8, -11.2), (1.0, 1.6, 10.5), "sw_blade", uv_scale=5,
      decals={"east": "number", "west": "number"})                       # 刀身＋刻印
    a((-0.22, -0.9, -11.2), (0.44, 1.8, 10.5), "sw_edge", uv_scale=5)     # 刃
    a((-0.48, -0.78, -12.4), (0.96, 1.56, 1.3), "sw_edge", uv_scale=6)    # 角ばった切先
    if twin:
        a((-0.7, 1.5, 0.6), (1.4, 1.4, 3.2), "sw_wrap", uv_scale=6,
          rotation=(0, 0, 24))
        a((-0.5, 1.6, 4.2), (1.0, 1.6, 10.0), "sw_blade", uv_scale=5,
          rotation=(0, 0, 24))
        a((-0.2, 1.5, 4.2), (0.4, 1.8, 10.0), "sw_edge", uv_scale=5,
          rotation=(0, 0, 24))
    return 12.0 * s


# ===========================================================================
#  03Ax-0112 — 四ノ宮キコルの大戦斧。片刃・全長1.6m・柄に電池セルと引き金
# ===========================================================================
def axe_03ax(bone, off=(0, 0, 0), s=1.0):
    a = mk(bone, off, s)
    a((-0.95, -0.95, -17.0), (1.9, 1.9, 24.0), "axe_haft", uv_scale=4)     # 直線的な長柄
    a((-1.15, -1.15, 3.4), (2.3, 2.3, 2.6), "axe_cell", uv_scale=6,
      decals={"east": "powerline", "west": "powerline"})                   # 電池セル
    a((-1.2, -1.2, 0.4), (2.4, 2.4, 1.8), "axe_head", uv_scale=6,
      decals={"up": "core"})                                              # トリガー
    a((-1.25, -1.25, 6.2), (2.5, 2.5, 1.6), "axe_head", uv_scale=6)        # 石突
    a((-1.3, -1.3, -18.4), (2.6, 2.6, 3.4), "axe_head", uv_scale=5)        # 斧頭基部
    a((-1.05, 1.2, -19.6), (2.1, 7.0, 5.2), "axe_head", uv_scale=4)        # 片刃の刃身
    a((-1.15, 1.2, -21.6), (2.3, 7.0, 2.2), "axe_edge", uv_scale=5,
      decals={"north": "edge_glow", "east": "edge_glow"})                  # 前縁（放電）
    a((-0.95, 8.0, -18.2), (1.9, 2.6, 2.6), "axe_head", uv_scale=5,
      rotation=(-22, 0, 0))                                               # 上部スパイク
    a((-1.0, -0.4, -18.0), (2.0, 1.8, 2.6), "axe_cell", uv_scale=6)        # 通電カラー
    return 26.0 * s


# ===========================================================================
#  T-25101985 — 亜白ミナ専用大型火砲。肩当て式、全長2.2m
# ===========================================================================
def cannon_t25(bone, off=(0, 0, 0), s=1.0):
    a = mk(bone, off, s)
    a((-2.2, -2.2, -13.0), (4.4, 5.6, 17.0), "gun_body", uv_scale=3)       # 機関部
    a((-1.9, -0.9, -32.0), (3.8, 3.8, 19.5), "gun_barrel", uv_scale=3)     # 砲身
    for i in range(3):                                                     # 冷却リブ
        a((-2.3, -1.3, -28.0 + i * 6.0), (4.6, 4.6, 1.6), "gun_body", uv_scale=5)
    a((-2.5, -1.5, -35.4), (5.0, 5.0, 3.6), "gun_body", uv_scale=4)        # 砲口
    a((-1.3, -0.3, -35.9), (2.6, 2.6, 1.0), "gun_bore", uv_scale=6,
      decals={"north": "core"})                                           # 銃口内
    a((-1.3, 3.4, -15.0), (2.6, 2.4, 11.0), "gun_barrel", uv_scale=4)      # 照準器
    a((-1.05, 3.7, -15.6), (2.1, 1.7, 0.8), "core", uv_scale=6,
      decals={"north": "core"})
    a((-2.3, -2.4, 4.0), (4.6, 5.2, 8.0), "gun_body", uv_scale=3)          # 肩当て
    a((-2.5, -1.0, 11.6), (5.0, 4.4, 2.2), "gun_body", uv_scale=4)         # 尾筒
    a((-1.5, -7.4, -2.4), (3.0, 5.2, 3.0), "grip", uv_scale=4,
      rotation=(14, 0, 0))                                                # 握把
    a((-1.9, 3.6, 1.0), (3.8, 1.2, 4.0), "decal", uv_scale=5,
      decals={"up": "logo"})
    return 36.0 * s


# ===========================================================================
#  GS-3305 — 鳴海弦の巨大銃剣。刺してから内部に撃ち込む
# ===========================================================================
def gunblade_gs3305(bone, off=(0, 0, 0), s=1.0):
    a = mk(bone, off, s)
    a((-1.0, -1.0, 3.6), (2.0, 2.0, 4.6), "grip", uv_scale=5)              # グリップ
    a((-1.7, -1.9, -5.0), (3.4, 4.4, 9.0), "gs_body", uv_scale=4)          # 機関部
    a((-1.5, -5.6, -1.6), (3.0, 3.8, 3.0), "gs_body", uv_scale=5)          # トリガーグループ
    a((-1.25, -2.8, -25.0), (2.5, 5.6, 20.5), "gs_blade", uv_scale=3,
      decals={"east": "number"})                                          # 幅広の重刃
    a((-1.35, -3.3, -25.0), (2.7, 1.0, 20.5), "gs_edge", uv_scale=4,
      decals={"down": "edge_glow"})                                       # 刃先（焼灼）
    a((-1.15, -2.6, -28.4), (2.3, 5.2, 3.6), "gs_edge", uv_scale=4)        # 切先
    a((-0.6, 0.7, -27.0), (1.2, 1.2, 22.0), "gs_body", uv_scale=4)         # 内蔵銃身
    a((-0.9, 0.4, -29.0), (1.8, 1.8, 2.2), "gs_body", uv_scale=5)          # 銃口
    a((-1.8, 1.6, -8.0), (3.6, 1.0, 5.0), "accent", uv_scale=5,
      decals={"up": "powerline"})
    return 33.0 * s


# ===========================================================================
#  怪獣探知機 / 怪獣8号の核
# ===========================================================================
def kaiju_detector(bone, off=(0, 0, 0), s=1.0):
    a = mk(bone, off, s)
    a((-3.0, -0.9, -5.0), (6.0, 1.8, 9.0), "dark", uv_scale=4)
    a((-2.6, 0.9, -4.4), (5.2, 0.5, 7.6), "core", uv_scale=6,
      decals={"up": "hex"})
    a((-3.2, -1.2, -5.4), (6.4, 2.4, 1.4), "steel", uv_scale=5)
    a((-0.6, 1.4, -1.0), (1.2, 2.6, 1.2), "accent", uv_scale=6)
    return 10.0 * s


def no8_core(bone, off=(0, 0, 0), s=1.0):
    a = mk(bone, off, s)
    a((-2.2, -2.2, -2.2), (4.4, 4.4, 4.4), "no8", uv_scale=5,
      decals={"north": "core", "south": "core", "up": "core"})
    a((-3.0, -0.5, -3.0), (6.0, 1.0, 6.0), "accent", uv_scale=5,
      decals={"up": "hex"}, rotation=(0, 22, 0))
    a((-0.5, -3.0, -3.0), (1.0, 6.0, 6.0), "accent", uv_scale=5,
      decals={"east": "hex"}, rotation=(18, 0, 0))
    return 8.0 * s


BUILDERS = {
    "combat_knife": combat_knife,
    "df_rifle": df_rifle,
    "twin_sw2033": twin_sw2033,
    "axe_03ax": axe_03ax,
    "cannon_t25": cannon_t25,
    "gunblade_gs3305": gunblade_gs3305,
    "kaiju_detector": kaiju_detector,
    "no8_power": no8_core,
}

# how the item sits in the hand: (third pos, third rot, first pos, first rot, fp scale)
WIELD = {
    "combat_knife": ((0, 1, -1), (0, 0, 0), (2, 6, -4), (8, -46, 4), 1.0),
    "df_rifle": ((0, 1, -1), (0, 0, 0), (3, 5, -6), (6, -40, 2), 0.85),
    "twin_sw2033": ((0, 1, -1), (0, 0, 0), (2, 6, -5), (8, -48, 4), 0.95),
    "axe_03ax": ((0, 2, -2), (0, 0, 0), (3, 5, -7), (6, -42, 2), 0.68),
    "cannon_t25": ((0, 2, -3), (0, 0, 0), (4, 4, -9), (4, -34, 0), 0.58),
    "gunblade_gs3305": ((0, 2, -2), (0, 0, 0), (3, 5, -8), (6, -40, 2), 0.62),
    "kaiju_detector": ((0, 1, -2), (0, 0, 0), (2, 5, -4), (12, -40, 0), 1.0),
    "no8_power": ((0, 3, -2), (0, 0, 0), (2, 6, -4), (0, -30, 0), 1.0),
}


def build_model(name: str) -> Model:
    m = Model(f"geometry.kaiju8.weapon.{name}", uv_scale=4,
              visible_bounds=(3.5, 3.5), vb_offset=(0, 0, -1),
              max_atlas=(512, 512))
    root = m.bone("root", (0, 0, 0))
    BUILDERS[name](root)
    m.pack()
    return m


def attachable(name: str) -> dict:
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": f"kaiju8:{name}",
                "materials": {"default": "entity_emissive_alpha",
                              "enchanted": "entity_alphatest_glint"},
                "textures": {
                    "default": f"textures/entity/kaiju8/weapons/{name}",
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {"default": f"geometry.kaiju8.weapon.{name}"},
                "animations": {
                    "third": f"animation.kaiju8.wield.{name}",
                    "first": f"animation.kaiju8.wield.{name}_fp",
                },
                "scripts": {
                    "animate": [
                        {"first": "c.is_first_person"},
                        {"third": "!c.is_first_person"},
                    ]
                },
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


def wield_animations() -> dict:
    anims = {}
    for name, (tp, tr, fp, fr, fs) in WIELD.items():
        anims[f"animation.kaiju8.wield.{name}"] = {
            "loop": True,
            "bones": {"root": {"position": list(tp), "rotation": list(tr)}},
        }
        anims[f"animation.kaiju8.wield.{name}_fp"] = {
            "loop": True,
            "bones": {"root": {"position": list(fp), "rotation": list(fr),
                               "scale": fs}},
        }
    return anims


def main() -> None:
    print("weapons:")
    for d in (GEO_DIR, TEX_DIR, ATT_DIR):
        os.makedirs(d, exist_ok=True)
    for stale in os.listdir(GEO_DIR):
        if stale.startswith("weapon_") and stale.endswith(".geo.json"):
            if stale[len("weapon_"):-len(".geo.json")] not in BUILDERS:
                os.remove(os.path.join(GEO_DIR, stale))
    for i, name in enumerate(BUILDERS):
        m = build_model(name)
        m.write(os.path.join(GEO_DIR, f"weapon_{name}.geo.json"))
        p = Painter(m.tex_w, m.tex_h, 100 + i)
        p.paint_model(m, palettes.WEAPON)
        p.save(os.path.join(TEX_DIR, f"{name}.png"))
        with open(os.path.join(ATT_DIR, f"{name}.attachable.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(attachable(name), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"  {name:18s} {m.stats()}")


if __name__ == "__main__":
    main()
