# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — 形態ごとの色設計 (企画書 §04 / §06)。

企画書が求めている読み分けを、そのまま色の決まりにしたもの:

* 明部／基本色／陰の3段階を基礎に、関節としわだけ補助色を置く
* 覇気は「暗い基本色＋面方向のハイライト」。黒い筒に見せない
* ギア5の白は、暖色寄りの明部と薄い青紫の陰で髪・肌・服を読み分ける。
  全面純白にも、常時強発光にもしない
* 蒸気は柔らかい輪郭。効果が消えても形態が分かること

`mctexture.Painter` は style 名 → style 仕様の辞書しか見ないので、
ここは完全に色だけの層。`palettes.py`(怪獣8号) には一切触らない。
"""
from __future__ import annotations

from typing import Dict

# `S()` は怪獣8号側と同じ仕様ビルダ。共有して良い純粋関数。
from palettes import S

# ---------------------------------------------------------------------------
#  基本色
# ---------------------------------------------------------------------------
SKIN = "#E4A874"          # 日焼けした肌
SKIN_D = "#B87B4E"
SKIN_L = "#F6D2A8"
SKIN_HOT = "#E8795A"      # ギア2 — 血流が上がって赤みが差した肌
SKIN_HOT_D = "#B2472F"

HAIR = "#171210"          # 黒髪
HAIR_D = "#000000"
IRIS = "#3B2A22"

VEST = "#C33A2E"          # 赤いベスト
VEST_D = "#7E1D16"
SHORTS = "#2E62A8"        # デニムの短パン
SHORTS_D = "#1A3C6B"
SASH = "#E0B341"          # 黄色い帯
SASH_D = "#987221"
SANDAL = "#8A5A32"
SANDAL_D = "#553620"

STRAW = "#E6CB84"         # 麦わら
STRAW_D = "#A98F42"
HATBAND = "#B8302A"

SCAR = "#B4705A"

# 覇気: 暗い基本色に面方向のハイライト。真っ黒な筒にしない。
HAKI = "#15161B"
HAKI_HI = "#3E4350"

# 蒸気（ギア2）
STEAM = "#E7EEF2"
STEAM_D = "#A9BCC6"

# ギア5 — 白の設計。明部は暖色寄り、陰は薄い青紫。
G5_WHITE = "#F5F2EC"
G5_WHITE_D = "#C9C6D6"    # 薄い青紫の陰
G5_WARM = "#FFF6E4"       # 暖色寄りの明部
G5_HAIR = "#FBFAF6"
G5_HAIR_D = "#CFCBDA"
G5_CLOUD = "#FDFDFB"
G5_CLOUD_D = "#D5D8E6"
G5_GLOW = "#FFE9B0"       # 弱い暖色。常時強発光はしない


def _common(skin: str, skin_d: str, hair: str, hair_d: str,
            glow: str = G5_GLOW) -> Dict[str, dict]:
    """どの形態にも要る土台。

    HumanRig が既定で引く 8 キー (skin/suit/armor/accent/hair/steel/cloth/
    underlay) と、メソッド内で literal になっている green/decal/visor、
    そして paint_model のフォールバックである base を必ず埋める。
    """
    return {
        # フォールバック。未知の style 名はすべてここへ落ちる。
        "base": S(skin, skin_d, "skin", 3, skin=skin, iris=IRIS,
                  hair_col=hair, light=SKIN_L, dark="#2A1E18"),
        "skin": S(skin, skin_d, "skin", 3, skin=skin, iris=IRIS,
                  hair_col=hair, light=SKIN_L, dark="#2A1E18"),
        "hair": S(hair, hair_d, "hair", 5, light="#FFFFFF", dark="#080608"),
        # 素肌が主役なので suit も肌。服は個別の style で後から貼る。
        "suit": S(skin, skin_d, "skin", 3, skin=skin, iris=IRIS,
                  hair_col=hair, light=SKIN_L, dark="#2A1E18"),
        "underlay": S(skin_d, "#8E5A38", "skin", 3, light=SKIN_L, dark="#2A1E18"),
        "muscle": S(skin, skin_d, "muscle", 4, skin=skin, light=SKIN_L,
                    dark="#2A1E18"),
        # 服飾
        "vest": S(VEST, VEST_D, "cloth", 5, light="#F07A66", dark="#3E0C08"),
        "shorts": S(SHORTS, SHORTS_D, "cloth", 5, light="#6E9FDC", dark="#0E1F38"),
        "sash": S(SASH, SASH_D, "cloth", 5, light="#F6DA8C", dark="#4A3510"),
        "sandal": S(SANDAL, SANDAL_D, "leather", 5, light="#C2905E", dark="#2C1B0F"),
        "straw": S(STRAW, STRAW_D, "weave", 6, light="#F7E7B2", dark="#5A4818"),
        "hatband": S(HATBAND, "#6E1713", "cloth", 4, light="#E8685E", dark="#330906"),
        "scar": S(SCAR, "#8A4A38", "skin", 3, light="#DCA08C", dark="#3A1C14"),
        # 覇気 — 面方向のハイライトが出るよう brushed を使う
        "haki": S(HAKI, HAKI_HI, "brushed", 4, light="#7E8698", dark="#05060A",
                  glow=glow),
        "haki_line": S("#0B0C10", glow, "crack", 3, glow=glow),
        # 蒸気
        "steam": S(STEAM, STEAM_D, "cloth", 4, light="#FFFFFF", dark="#6E8492"),
        # 汎用（rig 内で literal になっているキーを必ず埋める）
        "cloth": S(VEST, VEST_D, "cloth", 5, light="#F07A66", dark="#3E0C08"),
        "armor": S("#9BA2AA", "#5E656D", "panel", 4, light="#E8ECF0", dark="#1A1D22"),
        "accent": S(glow, "#8A6A1E", "metal", 4, glow=glow, light="#FFF3CE"),
        "steel": S("#8E959C", "#565C64", "brushed", 5, light="#E2E6EA", dark="#1B1E24"),
        "green": S("#3B5A38", "#22331F", "cloth", 5, light="#8FAE86", dark="#111A0F"),
        "decal": S("#6E7680", "#3A4048", "panel", 3, light="#D8DCE2", dark="#14171C"),
        "visor": S("#EDEFF2", "#A8B0B8", "glass", 3, light="#FFFFFF"),
    }


def _dress(p: Dict[str, dict], **over) -> Dict[str, dict]:
    p = dict(p)
    p.update(over)
    return p


# ---------------------------------------------------------------------------
#  形態ごとのパレット
# ---------------------------------------------------------------------------

#  通常ルフィ — 基準。ここの色が読めなければ他も読めない。
NORMAL = _common(SKIN, SKIN_D, HAIR, HAIR_D)

#  ギア2 — 骨格は通常と共有し、肌の色味と蒸気だけを専用調整する。
GEAR2 = _dress(
    _common(SKIN_HOT, SKIN_HOT_D, HAIR, HAIR_D, glow="#FF9C6A"),
    # 蒸気は輪郭を柔らかく。白飛びさせない。
    steam=S(STEAM, STEAM_D, "cloth", 6, light="#FFFFFF", dark="#7F94A2"),
    # 汗と熱で光る縁
    haki_line=S("#3A1712", "#FF9C6A", "crack", 3, glow="#FF9C6A"),
)

#  ギア3 — 見た目は通常のまま。膨張部分だけ張りのある肌にする。
GEAR3 = _dress(
    _common(SKIN, SKIN_D, HAIR, HAIR_D),
    inflate=S("#EDB782", "#BE8350", "muscle", 4, skin="#EDB782",
              light="#FBDCB4", dark="#2E2018"),
)

#  ギア4・バウンドマン — 覇気の模様が主役。肌は残し、上半身と腕を覇気で覆う。
G4_BOUND = _dress(
    _common(SKIN, SKIN_D, HAIR, HAIR_D, glow="#C8A0FF"),
    haki=S(HAKI, HAKI_HI, "brushed", 4, light="#8790A4", dark="#05060A",
           glow="#C8A0FF"),
    haki_line=S("#0B0C10", "#C8A0FF", "crack", 3, glow="#C8A0FF"),
    # 圧縮された拳は艶を強める
    fist=S("#1B1D24", "#4A5160", "metal", 4, light="#9BA5BA", dark="#05060A",
           glow="#C8A0FF"),
)

#  ギア4・スネイクマン — バウンドマンと別の輪郭。覇気は同じ黒でも艶を落とす。
G4_SNAKE = _dress(
    _common(SKIN, SKIN_D, HAIR, HAIR_D, glow="#8FE0FF"),
    haki=S("#101218", "#333B4A", "brushed", 4, light="#6E7A8E", dark="#04050A",
           glow="#8FE0FF"),
    haki_line=S("#080A0E", "#8FE0FF", "crack", 3, glow="#8FE0FF"),
    fist=S("#141720", "#3A4252", "metal", 4, light="#8896AC", dark="#04050A",
           glow="#8FE0FF"),
)

#  ギア5・ニカ — 白の三段階。髪・肌・服を別の白で分ける。
GEAR5 = _dress(
    _common("#F0CFA8", "#C99C6E", G5_HAIR, G5_HAIR_D, glow=G5_GLOW),
    # 髪は一番明るく、陰に薄い青紫
    hair=S(G5_HAIR, G5_HAIR_D, "hair", 4, light=G5_WARM, dark="#9A96AC"),
    # 衣装は髪より一段落とし、布の質感を残す
    shirt=S(G5_WHITE, G5_WHITE_D, "cloth", 4, light=G5_WARM, dark="#8E8AA0"),
    shorts=S(G5_WHITE, "#BFBCD0", "cloth", 4, light=G5_WARM, dark="#86829A"),
    sash=S("#E9DFC4", "#B3A882", "cloth", 5, light="#FBF3DC", dark="#524A32"),
    # 雲は服よりさらに明るく、輪郭だけ青紫で締める
    cloud=S(G5_CLOUD, G5_CLOUD_D, "cloth", 3, light="#FFFFFF", dark="#9EA2B8"),
    # 弱い暖色の縁取り。常時強発光にはしない。
    rim=S("#E7DCC2", G5_GLOW, "crack", 3, glow=G5_GLOW),
    haki=S("#16171E", "#454C5C", "brushed", 4, light="#8A93A6", dark="#05060A",
           glow=G5_GLOW),
)

PALETTES: Dict[str, Dict[str, dict]] = {
    "normal": NORMAL,
    "gear2": GEAR2,
    "gear3": GEAR3,
    "gear4_bound": G4_BOUND,
    "gear4_snake": G4_SNAKE,
    "gear5": GEAR5,
}

# ---------------------------------------------------------------------------
#  その他のモデル
# ---------------------------------------------------------------------------

#  訓練用標的 — 藁と丸太。派手にせず、当たった場所が分かる色にする。
DUMMY = {
    "base": S("#C8A961", "#8E7436", "weave", 6, light="#EBD69C", dark="#4A3A18"),
    "straw": S("#C8A961", "#8E7436", "weave", 6, light="#EBD69C", dark="#4A3A18"),
    "wood": S("#7A5632", "#4C3520", "leather", 5, light="#B0895C", dark="#2A1C10"),
    "mark": S("#C4342C", "#7A1A15", "cloth", 4, light="#EE7A6C", dark="#3A0A07"),
    "rope": S("#A89068", "#6E5C40", "weave", 5, light="#D8C8A4", dark="#33291A"),
}

#  演出用の拳 — 覇気の黒とゴムの肌、2色だけ
VFX_FIST = {
    "base": S(SKIN, SKIN_D, "muscle", 4, light=SKIN_L, dark="#2A1E18"),
    "skin": S(SKIN, SKIN_D, "muscle", 4, light=SKIN_L, dark="#2A1E18"),
    "haki": S(HAKI, HAKI_HI, "brushed", 4, light="#7E8698", dark="#05060A"),
}

#  投げた雷 — 芯は白、縁は黄。crack の emissive を使う。
VFX_BOLT = {
    "base": S("#FFF4C4", "#FFFFFF", "crack", 3, glow="#FFFFFF"),
    "bolt": S("#FFF4C4", "#FFFFFF", "crack", 3, glow="#FFFFFF"),
    "edge": S("#F2C63C", "#FFE68A", "crack", 3, glow="#FFE68A"),
}

#  アイテムのアイコン用。64x64 の原画で輪郭を設計する (企画書 §06)。
ICON = {
    "base": S("#8A6A3C", "#5A431F", "weave", 4, light="#D8BE86", dark="#2A1E0E"),
    "straw": S(STRAW, STRAW_D, "weave", 4, light="#F7E7B2", dark="#5A4818"),
    "hatband": S(HATBAND, "#6E1713", "cloth", 3, light="#E8685E", dark="#330906"),
    "fruit": S("#6E3A8E", "#3E1E55", "scale", 4, light="#C08ADC", dark="#1A0A26"),
    "fruit_swirl": S("#2A0F3A", "#C08ADC", "crack", 3, glow="#C08ADC"),
    "stem": S("#4A7A32", "#2C4A1E", "leather", 4, light="#8ABE6C", dark="#16260E"),
    "wrap": S("#E8E2D2", "#B0A890", "cloth", 4, light="#FFFFFF", dark="#4E4838"),
    "wrap_tie": S("#C33A2E", "#7E1D16", "cloth", 3, light="#F07A66", dark="#3E0C08"),
    "glass": S("#D8ECF2", "#8CB4C4", "glass", 3, light="#FFFFFF", dark="#2A3A44"),
    "brass": S("#C8A24E", "#7E6224", "metal", 4, light="#F4DC9A", dark="#3A2C0E"),
    "needle": S("#C4342C", "#7A1A15", "metal", 3, light="#EE7A6C", dark="#3A0A07"),
}


def check() -> None:
    """rig が literal で引くキーが欠けていないかを起動時に潰しておく。"""
    required = ["base", "skin", "suit", "armor", "accent", "hair", "steel",
                "cloth", "underlay", "green", "decal", "visor"]
    for name, pal in PALETTES.items():
        missing = [k for k in required if k not in pal]
        if missing:
            raise SystemExit(f"palette {name}: 不足しているキー {missing}")
        for key, spec in pal.items():
            if spec.get("pattern") == "crack" and not spec.get("second"):
                raise SystemExit(
                    f"palette {name}.{key}: crack は second が発光色になるので必須")


if __name__ == "__main__":
    check()
    for name, pal in PALETTES.items():
        print(f"{name:12s} {len(pal):2d} styles")
    print("palette ok")
