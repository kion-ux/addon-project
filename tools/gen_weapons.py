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
def combat_knife(bone, off=(0, 0, 0), s=1.0, sub=None):
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
def df_rifle(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    bolt = mk(sub("bolt", (0, 1.4, -6.0)) if sub else bone, off, s)
    bolt((1.5, 0.6, -8.6), (0.9, 1.4, 4.4), "steel", uv_scale=6)          # 槓桿
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
def twin_sw2033(bone, off=(0, 0, 0), s=1.0, twin=False, sub=None):
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
def axe_03ax(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    a((-0.95, -0.95, -17.0), (1.9, 1.9, 24.0), "axe_haft", uv_scale=4)     # 直線的な長柄
    a((-1.15, -1.15, 3.4), (2.3, 2.3, 2.6), "axe_cell", uv_scale=6,
      decals={"east": "powerline", "west": "powerline"})                   # 電池セル
    a((-1.2, -1.2, 0.4), (2.4, 2.4, 1.8), "axe_head", uv_scale=6,
      decals={"up": "core"})                                              # トリガー
    a((-1.25, -1.25, 6.2), (2.5, 2.5, 1.6), "axe_head", uv_scale=6)        # 石突
    a((-1.3, -1.3, -18.4), (2.6, 2.6, 3.4), "axe_head", uv_scale=5)        # 斧頭基部
    a((-1.05, 1.2, -19.6), (2.1, 7.0, 5.2), "axe_head", uv_scale=4)        # 片刃の刃身
    mk(sub("edge", (0, 4.7, -20.5)) if sub else bone, off, s)(
      (-1.15, 1.2, -21.6), (2.3, 7.0, 2.2), "axe_edge", uv_scale=5,
      decals={"north": "edge_glow", "east": "edge_glow"})                  # 前縁（放電）
    a((-0.95, 8.0, -18.2), (1.9, 2.6, 2.6), "axe_head", uv_scale=5,
      rotation=(-22, 0, 0))                                               # 上部スパイク
    a((-1.0, -0.4, -18.0), (2.0, 1.8, 2.6), "axe_cell", uv_scale=6)        # 通電カラー
    return 26.0 * s


# ===========================================================================
#  T-25101985 — 亜白ミナ専用大型火砲。肩当て式、全長2.2m
# ===========================================================================
def cannon_t25(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    b = mk(sub("barrel", (0, 1.0, -26.0)) if sub else bone, off, s)
    a((-2.2, -2.2, -13.0), (4.4, 5.6, 17.0), "gun_body", uv_scale=3)       # 機関部
    b((-1.9, -0.9, -32.0), (3.8, 3.8, 19.5), "gun_barrel", uv_scale=3)     # 砲身
    for i in range(3):                                                     # 冷却リブ
        b((-2.3, -1.3, -28.0 + i * 6.0), (4.6, 4.6, 1.6), "gun_body", uv_scale=5)
    b((-2.5, -1.5, -35.4), (5.0, 5.0, 3.6), "gun_body", uv_scale=4)        # 砲口
    b((-1.3, -0.3, -35.9), (2.6, 2.6, 1.0), "gun_bore", uv_scale=6,
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
def gunblade_gs3305(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    b = mk(sub("bolt", (0, 1.3, -18.0)) if sub else bone, off, s)
    a((-1.0, -1.0, 3.6), (2.0, 2.0, 4.6), "grip", uv_scale=5)              # グリップ
    a((-1.7, -1.9, -5.0), (3.4, 4.4, 9.0), "gs_body", uv_scale=4)          # 機関部
    a((-1.5, -5.6, -1.6), (3.0, 3.8, 3.0), "gs_body", uv_scale=5)          # トリガーグループ
    a((-1.25, -2.8, -25.0), (2.5, 5.6, 20.5), "gs_blade", uv_scale=3,
      decals={"east": "number"})                                          # 幅広の重刃
    a((-1.35, -3.3, -25.0), (2.7, 1.0, 20.5), "gs_edge", uv_scale=4,
      decals={"down": "edge_glow"})                                       # 刃先（焼灼）
    a((-1.15, -2.6, -28.4), (2.3, 5.2, 3.6), "gs_edge", uv_scale=4)        # 切先
    b((-0.6, 0.7, -27.0), (1.2, 1.2, 22.0), "gs_body", uv_scale=4)         # 内蔵銃身
    b((-0.9, 0.4, -29.0), (1.8, 1.8, 2.2), "gs_body", uv_scale=5)          # 銃口
    a((-1.8, 1.6, -8.0), (3.6, 1.0, 5.0), "accent", uv_scale=5,
      decals={"up": "powerline"})
    return 33.0 * s


# ===========================================================================
#  SW-1023 — 保科の予備。一刀型の長刀（兄・宗一郎の流儀）
# ===========================================================================
def blade_sw1023(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    a((-0.8, -0.8, 0.4), (1.6, 1.6, 4.4), "sw_wrap", uv_scale=5)
    a((-1.0, -1.0, 4.6), (2.0, 2.0, 0.9), "sw_blade", uv_scale=5)
    a((-1.9, -1.5, -0.9), (3.8, 3.0, 1.0), "sw_blade", uv_scale=5)
    a((-0.55, -0.9, -18.0), (1.1, 1.8, 17.2), "sw_blade", uv_scale=4,
      decals={"east": "number", "west": "number"})
    a((-0.25, -1.0, -18.0), (0.5, 2.0, 17.2), "sw_edge", uv_scale=4)
    a((-0.52, -0.85, -20.2), (1.04, 1.7, 2.4), "sw_edge", uv_scale=5)
    a((-0.7, -0.85, -2.2), (1.4, 1.7, 1.0), "accent", uv_scale=6,
      decals={"north": "core"})
    return 21.0 * s


# ===========================================================================
#  DF-STD バズーカ / 自動拳銃 — 一般隊員の支給装備
# ===========================================================================
def df_bazooka(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    v = mk(sub("vent", (0, 0, 8.2)) if sub else bone, off, s)
    a((-2.0, -2.0, -20.0), (4.0, 4.0, 30.0), "dark", uv_scale=3)          # 発射筒
    a((-2.3, -2.3, -21.0), (4.6, 4.6, 2.4), "steel", uv_scale=4)          # 銃口リング
    v((-2.3, -2.3, 7.0), (4.6, 4.6, 2.4), "steel", uv_scale=4)            # 後方噴出口
    a((-1.2, 2.0, -14.0), (2.4, 1.6, 8.0), "steel", uv_scale=4)           # 照準器
    a((-1.0, 3.3, -14.6), (2.0, 1.2, 0.8), "core", uv_scale=6,
      decals={"north": "core"})
    a((-1.3, -6.4, -4.0), (2.6, 4.6, 3.0), "grip", uv_scale=4,
      rotation=(12, 0, 0))
    a((-2.2, -2.6, -2.0), (4.4, 1.2, 6.0), "green", uv_scale=4,
      decals={"down": "panel_line"})                                      # 肩当て
    a((-2.4, 1.6, 0.0), (4.8, 1.0, 4.0), "decal", uv_scale=5,
      decals={"up": "logo"})
    return 31.0 * s


def df_pistol(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    d = mk(sub("slide", (0, 0.8, -4.0)) if sub else bone, off, s)
    d((-0.9, -0.5, -7.0), (1.8, 2.6, 8.0), "dark", uv_scale=6)            # スライド
    d((-0.7, -0.2, -9.2), (1.4, 1.4, 2.4), "steel", uv_scale=6)           # 銃口
    a((-0.85, -4.6, -0.8), (1.7, 4.4, 2.2), "grip", uv_scale=6,
      rotation=(14, 0, 0))                                                # 握把
    a((-0.75, -4.0, -0.4), (1.5, 3.2, 1.4), "green", uv_scale=6)          # ユニソケット
    a((-0.6, 2.2, -6.0), (1.2, 0.7, 3.0), "accent", uv_scale=6,
      decals={"up": "powerline"})
    return 10.0 * s


# ===========================================================================
#  怪獣探知機 / 怪獣8号の核
# ===========================================================================
def kaiju_detector(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    a((-3.0, -0.9, -5.0), (6.0, 1.8, 9.0), "dark", uv_scale=4)
    a((-2.6, 0.9, -4.4), (5.2, 0.5, 7.6), "core", uv_scale=6,
      decals={"up": "hex"})
    a((-3.2, -1.2, -5.4), (6.4, 2.4, 1.4), "steel", uv_scale=5)
    a((-0.6, 1.4, -1.0), (1.2, 2.6, 1.2), "accent", uv_scale=6)
    return 10.0 * s


def no8_core(bone, off=(0, 0, 0), s=1.0, sub=None):
    a = mk(bone, off, s)
    r = mk(sub("ring", (0, 0, 0)) if sub else bone, off, s)
    a((-2.2, -2.2, -2.2), (4.4, 4.4, 4.4), "no8", uv_scale=5,
      decals={"north": "core", "south": "core", "up": "core"})
    r((-3.0, -0.5, -3.0), (6.0, 1.0, 6.0), "accent", uv_scale=5,
      decals={"up": "hex"}, rotation=(0, 22, 0))
    r((-0.5, -3.0, -3.0), (1.0, 6.0, 6.0), "accent", uv_scale=5,
      decals={"east": "hex"}, rotation=(18, 0, 0))
    return 8.0 * s


BUILDERS = {
    "combat_knife": combat_knife,
    "df_pistol": df_pistol,
    "df_bazooka": df_bazooka,
    "blade_sw1023": blade_sw1023,
    "df_rifle": df_rifle,
    "twin_sw2033": twin_sw2033,
    "axe_03ax": axe_03ax,
    "cannon_t25": cannon_t25,
    "gunblade_gs3305": gunblade_gs3305,
    "kaiju_detector": kaiju_detector,
    "no8_power": no8_core,
}

# 手のボーンに対する見え方: (三人称 pos, 三人称 rot, 一人称 pos, 一人称 rot, 一人称 scale,
#                          振りの角度, 構えの角度)
WIELD = {
    "combat_knife":    ((0, 0, 0), (0, 0, 0), (0, 3, -3), (0, -18, 0), 0.85,
                        (-92, 24, 0), (-26, 12, 0)),
    "df_rifle":        ((0, 1, -2), (-6, 0, 0), (1, 3, -5), (0, -12, 0), 0.70,
                        (-24, 10, 0), (-46, 16, 0)),
    "twin_sw2033":     ((0, 0, 0), (0, 0, 0), (0, 3, -3), (0, -20, 0), 0.85,
                        (-104, 30, 0), (-34, 18, 0)),
    "axe_03ax":        ((0, 1, -1), (0, 0, 0), (1, 3, -5), (0, -16, 0), 0.55,
                        (-118, 18, 0), (-52, 10, 0)),
    "cannon_t25":      ((0, 2, -3), (-4, 0, 0), (2, 3, -7), (0, -10, 0), 0.45,
                        (-16, 6, 0), (-30, 12, 0)),
    "gunblade_gs3305": ((0, 1, -2), (0, 0, 0), (1, 3, -6), (0, -14, 0), 0.50,
                        (-110, 22, 0), (-44, 14, 0)),
    "df_pistol":       ((0, 0, 0), (0, 0, 0), (0, 3, -3), (0, -22, 0), 1.0,
                        (-22, 8, 0), (-40, 14, 0)),
    "df_bazooka":      ((0, 2, -3), (-4, 0, 0), (2, 3, -8), (0, -10, 0), 0.50,
                        (-14, 6, 0), (-28, 10, 0)),
    "blade_sw1023":    ((0, 0, 0), (0, 0, 0), (0, 3, -4), (0, -20, 0), 0.80,
                        (-112, 28, 0), (-38, 16, 0)),
    "kaiju_detector":  ((0, 0, -1), (0, 0, 0), (0, 3, -2), (0, -24, 0), 0.9,
                        (-30, 12, 0), (-16, 8, 0)),
    "no8_power":       ((0, 2, -2), (0, 0, 0), (0, 4, -3), (0, -20, 0), 0.9,
                        (-70, 16, 0), (-20, 10, 0)),
}


def build_model(name: str) -> Model:
    m = Model(f"geometry.kaiju8.weapon.{name}", uv_scale=4,
              visible_bounds=(3.5, 3.5), vb_offset=(0, 0, -1),
              max_atlas=(512, 512))
    # WITHOUT this binding the geometry is drawn at the holder's origin — i.e.
    # at their feet.  The binding attaches it to whichever hand bone holds the
    # item (rightitem / leftitem).
    root = m.bone("root", (0, 0, 0),
                  binding="q.item_slot_to_bone_name(c.item_slot)")

    def sub(bone_name, pivot=(0, 0, 0)):
        """可動部。反動でスライドが下がり、砲身が後退し、噴出口が開く。"""
        return m.bone(bone_name, pivot, parent="root")

    BUILDERS[name](root, sub=sub)
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
                    "swing": f"animation.kaiju8.swing.{name}",
                    "swing2": f"animation.kaiju8.swing2.{name}",
                    "swing3": f"animation.kaiju8.swing3.{name}",
                    "tech": f"animation.kaiju8.tech.{name}",
                    "tech2": f"animation.kaiju8.tech2.{name}",
                    "ready": f"animation.kaiju8.ready.{name}",
                    "ctrl": "controller.animation.kaiju8.wield",
                },
                "scripts": {
                    "pre_animation": list(WIELD_SCRIPTS),
                    "animate": ["ctrl"],
                },
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


# 振りの型。刀は袈裟／逆袈裟、斧と銃剣は溜めの長い大振り、銃は反動、
# 8号の核は素手の突き。
STYLE = {
    "combat_knife": "slash", "twin_sw2033": "slash", "blade_sw1023": "slash",
    "axe_03ax": "heavy", "gunblade_gs3305": "heavy",
    "df_rifle": "gun", "df_pistol": "gun", "cannon_t25": "gun",
    "df_bazooka": "gun",
    "kaiju_detector": "tool", "no8_power": "fist",
}

# 可動部: ボーン名 -> 反動チャンネル。position は [x, y, z]、+Z が後方。
PARTS = {
    "df_rifle":        ("bolt",   {"position": {"0.0": [0, 0, 0], "0.04": [0, 0, 2.2],
                                                "0.16": [0, 0, 0]}}),
    "df_pistol":       ("slide",  {"position": {"0.0": [0, 0, 0], "0.03": [0, 0, 2.8],
                                                "0.14": [0, 0, 0]}}),
    "cannon_t25":      ("barrel", {"position": {"0.0": [0, 0, 0], "0.05": [0, 0, 3.4],
                                                "0.26": [0, 0, 0]}}),
    "df_bazooka":      ("vent",   {"scale": {"0.0": [1, 1, 1], "0.05": [1.7, 1.7, 1.0],
                                             "0.24": [1, 1, 1]}}),
    "gunblade_gs3305": ("bolt",   {"position": {"0.0": [0, 0, 0], "0.18": [0, 0, 0],
                                                "0.24": [0, 0, 2.6],
                                                "0.44": [0, 0, 0]}}),
    "axe_03ax":        ("edge",   {"scale": {"0.0": [1, 1, 1], "0.14": [1.35, 1.1, 1.35],
                                             "0.40": [1, 1, 1]}}),
    "no8_power":       ("ring",   {"rotation": {"0.0": [0, 0, 0], "0.20": [0, 180, 0],
                                                "0.42": [0, 360, 0]}}),
}


def _slash(sx, sy, sz, v=0):
    """刀の三振り。0=袈裟斬り 1=逆袈裟 2=横薙ぎ。連撃すると順に出る。"""
    if v == 2:                                   # 横薙ぎ: 水平に払う
        return 0.40, {
            "rotation": {
                "0.0":  [0, 0, 0],
                "0.06": [sx * 0.10, -sy * 1.35, sz * 0.20],
                "0.15": [sx * 0.34, sy * 1.55, sz * 0.30],
                "0.24": [sx * 0.22, sy * 0.95, sz * 0.20],
                "0.40": [0, 0, 0],
            },
            "position": {
                "0.0":  [0, 0, 0],
                "0.06": [0, 0.4, 1.4],
                "0.15": [0, 0.2, -2.2],
                "0.40": [0, 0, 0],
            },
        }
    d = -1.0 if v == 1 else 1.0                  # 1 = 逆袈裟
    return 0.44, {
        "rotation": {
            "0.0":  [0, 0, 0],
            "0.07": [sx * -0.34, -sy * 0.95 * d, sz * 0.30 * d],
            "0.16": [sx * 1.10, sy * 1.18 * d, sz * d],
            "0.26": [sx * 0.66, sy * 0.52 * d, sz * 0.55 * d],
            "0.44": [0, 0, 0],
        },
        "position": {
            "0.0":  [0, 0, 0],
            "0.07": [0, 1.3, 1.9],
            "0.16": [0, -1.5, -2.9],
            "0.26": [0, -0.7, -1.2],
            "0.44": [0, 0, 0],
        },
    }


def _heavy(sx, sy, sz, v=0):
    """斧と銃剣。0=振り下ろし 1=切り返し 2=下段からの掬い上げ。"""
    if v == 2:                                   # 掬い上げ: 低く構えて跳ね上げる
        return 0.58, {
            "rotation": {
                "0.0":  [0, 0, 0],
                "0.14": [sx * 0.42, -sy * 0.7, -sz * 0.4],
                "0.30": [sx * -0.95, sy * 1.25, sz * 0.9],
                "0.40": [sx * -0.70, sy * 0.85, sz * 0.6],
                "0.58": [0, 0, 0],
            },
            "position": {
                "0.0":  [0, 0, 0],
                "0.14": [0, -2.4, 2.0],
                "0.30": [0, 2.8, -3.0],
                "0.58": [0, 0, 0],
            },
        }
    d = -1.0 if v == 1 else 1.0
    return 0.62, {
        "rotation": {
            "0.0":  [0, 0, 0],
            "0.14": [sx * -0.52, -sy * 1.15 * d, sz * 0.45 * d],
            "0.20": [sx * -0.55, -sy * 1.20 * d, sz * 0.50 * d],
            "0.32": [sx * 1.16, sy * 1.10 * d, sz * d],
            "0.42": [sx * 0.94, sy * 0.70 * d, sz * 0.7 * d],
            "0.62": [0, 0, 0],
        },
        "position": {
            "0.0":  [0, 0, 0],
            "0.18": [0, 2.6, 3.2],
            "0.32": [0, -2.4, -3.6],
            "0.44": [0, -1.0, -1.4],
            "0.62": [0, 0, 0],
        },
    }


def _gun(sx, sy, sz, v=0):
    """反動。0=単発 1=軽い二射目 2=二点射（跳ねが二度来る）。"""
    if v == 2:
        return 0.42, {
            "rotation": {
                "0.0":  [0, 0, 0],
                "0.03": [sx, sy * 0.5, sz],
                "0.10": [sx * 0.30, sy * 0.15, sz * 0.3],
                "0.15": [sx * 0.86, sy * 0.42, sz],
                "0.24": [sx * 0.22, sy * 0.10, sz * 0.2],
                "0.42": [0, 0, 0],
            },
            "position": {
                "0.0":  [0, 0, 0],
                "0.03": [0, 0.5, 2.1],
                "0.10": [0, 0.1, 0.5],
                "0.15": [0, 0.4, 1.8],
                "0.42": [0, 0, 0],
            },
        }
    k = 0.62 if v == 1 else 1.0
    return 0.32, {
        "rotation": {
            "0.0":  [0, 0, 0],
            "0.04": [sx * k, sy * 0.5 * k, sz],
            "0.12": [sx * 0.34 * k, sy * 0.16 * k, sz * 0.3],
            "0.32": [0, 0, 0],
        },
        "position": {
            "0.0":  [0, 0, 0],
            "0.04": [0, 0.5 * k, 2.1 * k],
            "0.14": [0, 0.1 * k, 0.5 * k],
            "0.32": [0, 0, 0],
        },
    }


def _fist(sx, sy, sz, v=0):
    """怪獣の腕。0=右の直突き 1=返しの裏拳 2=振り下ろし。"""
    if v == 2:
        return 0.50, {
            "rotation": {
                "0.0":  [0, 0, 0],
                "0.12": [sx * -0.70, sy * 0.3, 0],
                "0.24": [sx * 1.35, sy * 0.6, sz],
                "0.34": [sx * 0.80, sy * 0.3, sz * 0.5],
                "0.50": [0, 0, 0],
            },
            "position": {
                "0.0":  [0, 0, 0],
                "0.12": [0, 3.4, 1.6],
                "0.24": [0, -3.0, -2.6],
                "0.50": [0, 0, 0],
            },
        }
    d = -1.0 if v == 1 else 1.0
    return 0.46, {
        "rotation": {
            "0.0":  [0, 0, 0],
            "0.10": [sx * -0.40, -sy * 0.8 * d, 0],
            "0.20": [sx * 1.05, sy * 1.2 * d, sz],
            "0.30": [sx * 0.5, sy * 0.5 * d, sz * 0.5],
            "0.46": [0, 0, 0],
        },
        "position": {
            "0.0":  [0, 0, 0],
            "0.10": [0, 0.8, 3.0],
            "0.20": [0, -0.6, -4.4],
            "0.46": [0, 0, 0],
        },
    }


def _tool(sx, sy, sz, v=0):
    d = [1.0, -1.0, 0.4][v % 3]
    return 0.30, {
        "rotation": {"0.0": [0, 0, 0], "0.12": [sx * abs(d), sy * d, sz],
                     "0.30": [0, 0, 0]},
        "position": {"0.0": [0, 0, 0], "0.12": [0, -0.5, -0.8], "0.30": [0, 0, 0]},
    }


PROFILE = {"slash": _slash, "heavy": _heavy, "gun": _gun, "fist": _fist,
           "tool": _tool}


def _tech(style, sx, sy, sz, v=0):
    """技のモーション。深い溜め → 静止（撓め）→ 解放 → 残心。"""
    if style == "gun":
        return 0.86, {
            "rotation": {
                "0.0":  [0, 0, 0],
                "0.16": [sx * -0.8, sy * 0.3, sz],          # 構え直し
                "0.30": [sx * -0.9, sy * 0.3, sz],
                "0.38": [sx * 1.5, sy * 0.8, sz],           # 初弾
                "0.48": [sx * 0.6, sy * 0.4, sz],
                "0.56": [sx * 1.3, sy * 0.7, sz],           # 追撃
                "0.68": [sx * 0.4, sy * 0.2, sz],
                "0.86": [0, 0, 0],
            },
            "position": {
                "0.0":  [0, 0, 0],
                "0.16": [0, 0.6, -1.6],
                "0.38": [0, 0.9, 3.2],
                "0.48": [0, 0.2, 0.6],
                "0.56": [0, 0.8, 2.6],
                "0.86": [0, 0, 0],
            },
        }
    if v == 1:
        # 二の型。溜めを反対側に取り、抜けたあとに返しを一度入れる
        return 0.94, {
            "rotation": {
                "0.0":  [0, 0, 0],
                "0.18": [sx * 0.46, sy * 1.30, sz * 0.5],
                "0.36": [sx * 0.52, sy * 1.42, sz * 0.55],
                "0.46": [sx * -1.10, -sy * 1.20, -sz * 1.0],
                "0.58": [sx * 0.85, sy * 1.05, sz * 0.8],
                "0.70": [sx * 0.30, sy * 0.35, sz * 0.3],
                "0.94": [0, 0, 0],
            },
            "position": {
                "0.0":  [0, 0, 0],
                "0.18": [0, 2.0, 3.4],
                "0.36": [0, 2.2, 3.6],
                "0.46": [0, -2.6, -4.2],
                "0.58": [0, 1.0, 1.6],
                "0.70": [0, -1.4, -2.2],
                "0.94": [0, 0, 0],
            },
        }
    if style in ("heavy", "fist"):
        return 1.02, {
            "rotation": {
                "0.0":  [0, 0, 0],
                "0.20": [sx * -0.62, -sy * 1.3, -sz * 0.5],
                "0.42": [sx * -0.70, -sy * 1.4, -sz * 0.6],   # 溜め切り
                "0.52": [sx * 1.30, sy * 1.35, sz * 1.2],     # 解放
                "0.66": [sx * 1.00, sy * 0.80, sz * 0.8],
                "1.02": [0, 0, 0],
            },
            "position": {
                "0.0":  [0, 0, 0],
                "0.20": [0, 3.2, 4.0],
                "0.42": [0, 3.4, 4.2],
                "0.52": [0, -2.8, -4.6],
                "0.66": [0, -1.0, -1.6],
                "1.02": [0, 0, 0],
            },
        }
    return 0.90, {
        "rotation": {
            "0.0":  [0, 0, 0],
            "0.16": [sx * -0.50, -sy * 1.35, -sz * 0.45],
            "0.34": [sx * -0.56, -sy * 1.45, -sz * 0.50],
            "0.44": [sx * 1.24, sy * 1.30, sz * 1.15],
            "0.56": [sx * 0.30, -sy * 0.90, -sz * 0.6],       # 返し
            "0.66": [sx * 0.80, sy * 0.60, sz * 0.5],
            "0.90": [0, 0, 0],
        },
        "position": {
            "0.0":  [0, 0, 0],
            "0.16": [0, 2.4, 3.6],
            "0.34": [0, 2.6, 3.8],
            "0.44": [0, -2.2, -4.0],
            "0.56": [0, 0.6, 1.4],
            "0.66": [0, -1.2, -2.0],
            "0.90": [0, 0, 0],
        },
    }


def _round(channels):
    """浮動小数の尻尾を落とす。差分を見るときに読めなくなるので。"""
    for chan in channels.values():
        if isinstance(chan, dict):
            for t, v in chan.items():
                chan[t] = [round(float(x), 2) for x in v]
        elif isinstance(chan, list):
            channels[[k for k, v in channels.items() if v is chan][0]] = \
                [round(float(x), 2) for x in chan]
    return channels


def wield_animations() -> dict:
    """持ち位置・二種の振り・技・構えを武器ごとに書き出す。"""
    anims = {}
    for name, (tp, tr, fp, fr, fs, swing, ready) in WIELD.items():
        style = STYLE.get(name, "slash")
        sx, sy, sz = swing
        rx, ry, rz = ready
        part = PARTS.get(name)

        anims[f"animation.kaiju8.wield.{name}"] = {
            "loop": True,
            "bones": {"root": {"position": list(tp), "rotation": list(tr)}},
        }
        anims[f"animation.kaiju8.wield.{name}_fp"] = {
            "loop": True,
            "bones": {"root": {"position": list(fp), "rotation": list(fr),
                               "scale": fs}},
        }

        # 三振り。連撃すると順に出るので、同じ斬りが続かない。
        for suffix, variant in (("swing", 0), ("swing2", 1), ("swing3", 2)):
            length, root = PROFILE[style](sx, sy, sz, variant)
            bones = {"root": _round(root)}
            if part:
                bones[part[0]] = part[1]
            anims[f"animation.kaiju8.{suffix}.{name}"] = {
                "loop": False, "animation_length": length, "bones": bones,
            }

        # 技。右クリックを保持しているあいだ再生され、撃つたび一の型と二の型が入れ替わる。
        for suffix, variant in (("tech", 0), ("tech2", 1)):
            length, root = _tech(style, sx, sy, sz, variant)
            bones = {"root": _round(root)}
            if part:
                bones[part[0]] = part[1]
            anims[f"animation.kaiju8.{suffix}.{name}"] = {
                "loop": "hold_on_last_frame", "animation_length": length,
                "bones": bones,
            }

        # 構え。呼吸ぶんだけ揺れる。
        anims[f"animation.kaiju8.ready.{name}"] = {
            "loop": True,
            "animation_length": 2.4,
            "bones": {"root": {
                "rotation": {
                    "0.0": [rx, ry, rz],
                    "0.8": [rx - 1.6, ry + 1.2, rz],
                    "1.6": [rx + 1.4, ry - 0.9, rz],
                    "2.4": [rx, ry, rz],
                },
                "position": {
                    "0.0": [0, 1.0, -1.0],
                    "1.2": [0, 1.4, -1.3],
                    "2.4": [0, 1.0, -1.0],
                },
            }},
        }
    return anims


# v.alt は振るたび 0→1→2→0 と進み、v.talt は技を撃つたび 0/1 を往復する。
# どちらも「押した瞬間」だけ動かしたいので、直前の値と比べて立ち上がりを取る。
WIELD_SCRIPTS = [
    "v.main_hand = c.item_slot == 'main_hand';",
    "v.sw = math.max(v.attack_time ?? 0.0, 0.0);",
    "v.alt = (v.sw > 0.0 && (v.prev_sw ?? 0.0) <= 0.0) "
    "? math.mod((v.alt ?? 2.0) + 1.0, 3.0) : (v.alt ?? 2.0);",
    "v.prev_sw = v.sw;",
    "v.swing = v.sw;",
    "v.tech = q.is_using_item ? 1.0 : 0.0;",
    "v.talt = (v.tech > 0.5 && (v.prev_tech ?? 0.0) <= 0.0) "
    "? (1.0 - (v.talt ?? 1.0)) : (v.talt ?? 1.0);",
    "v.prev_tech = v.tech;",
]

_SW_A = "v.swing > 0.0 && v.alt < 0.5"
_SW_B = "v.swing > 0.0 && v.alt >= 0.5 && v.alt < 1.5"
_SW_C = "v.swing > 0.0 && v.alt >= 1.5"

_TP = [{"tech": "v.tech > 0.5 && v.talt < 0.5"},
       {"tech_b": "v.tech > 0.5"},
       {"swing_a": _SW_A}, {"swing_b": _SW_B}, {"swing_c": _SW_C}]
_FP = [{"fp_tech": "v.tech > 0.5 && v.talt < 0.5"},
       {"fp_tech_b": "v.tech > 0.5"},
       {"fp_swing_a": _SW_A}, {"fp_swing_b": _SW_B}, {"fp_swing_c": _SW_C}]

def _swing_state(clip, base):
    return {
        "animations": [base, clip],
        "blend_transition": 0.04,
        "transitions": ([{"fp": "c.is_first_person"}] if base == "third"
                        else [{"hold": "!c.is_first_person"}])
                       + [{"fp" if base == "first" else "hold":
                           "q.all_animations_finished"}],
    }


WIELD_CONTROLLER = {
    "controller.animation.kaiju8.wield": {
        "initial_state": "hold",
        "states": {
            "hold": {
                "animations": ["third"],
                "transitions": [{"fp": "c.is_first_person"}] + _TP
                               + [{"ready": "q.is_sneaking"}],
            },
            "ready": {
                "animations": ["third", "ready"],
                "blend_transition": 0.12,
                "transitions": [{"fp": "c.is_first_person"}] + _TP
                               + [{"hold": "!q.is_sneaking"}],
            },
            "swing_a": _swing_state("swing", "third"),
            "swing_b": _swing_state("swing2", "third"),
            "swing_c": _swing_state("swing3", "third"),
            "tech": {
                "animations": ["third", "tech"],
                "blend_transition": 0.08,
                "transitions": [{"fp": "c.is_first_person"},
                                {"hold": "v.tech <= 0.5"}],
            },
            "tech_b": {
                "animations": ["third", "tech2"],
                "blend_transition": 0.08,
                "transitions": [{"fp": "c.is_first_person"},
                                {"hold": "v.tech <= 0.5"}],
            },
            "fp": {
                "animations": ["first"],
                "transitions": [{"hold": "!c.is_first_person"}] + _FP,
            },
            "fp_swing_a": _swing_state("swing", "first"),
            "fp_swing_b": _swing_state("swing2", "first"),
            "fp_swing_c": _swing_state("swing3", "first"),
            "fp_tech": {
                "animations": ["first", "tech"],
                "blend_transition": 0.08,
                "transitions": [{"hold": "!c.is_first_person"},
                                {"fp": "v.tech <= 0.5"}],
            },
            "fp_tech_b": {
                "animations": ["first", "tech2"],
                "blend_transition": 0.08,
                "transitions": [{"hold": "!c.is_first_person"},
                                {"fp": "v.tech <= 0.5"}],
            },
        },
    }
}


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
