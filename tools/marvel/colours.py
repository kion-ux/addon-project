# -*- coding: utf-8 -*-
"""配色 — キャラクターごとのスタイル辞書。

モデル側は ``Cube(style="helm")`` のように **キー名だけ** を渡す。
実際の色・模様・光り方はここで決まるので、モデルを触らずに見た目を
作り込める（テクスチャ担当の作業領域）。

明度の設計
----------
描画までに基準色へ掛かる係数は **三段重ね** になっている。

1. ``mctexture.FACE_LIGHT`` — down 面 0.64 倍 / east 面 0.84 倍
2. ``Painter.paint_face`` の ``ao``（既定 0.30）が面の縁を落とす
3. レンダラの拡散光（最悪 0.35 倍）

三つ掛かると 0.64 × 0.70 × 0.35 ≒ **0.16 倍**。基準色を中明度で置くと
どの素材も同じ「黒っぽい塊」に着地する。だから

* **素材の差は暗い側ではなく明るい側で作る。** 金属は迷わず上へ振る
* 金属の基準は ``docs/DIRECTION.md`` §2-2 の鋼 ``#B8C0CC``
* 布はその 4 割程度の明度に置き、差を 40% 以上取る
* 暗いキャラ（ミスティーク・センチネル・プライム）ほど ``ao`` を下げ、
  ``light`` を強くしてパターンのコントラストで形を読ませる

``metal()`` / ``fabric()`` / ``flesh()`` はこの規約を既定値として持つ
コンストラクタなので、新しいスタイルはこの三つのどれかで作ること。

参照する見た目
--------------
マグニートー: 画像のガンメタルの兜（M字クレスト）＋ 古典的な深紫の装甲と
深紅のマント。金属質は ``metal`` / ``brushed`` / ``panel`` パターンで、
磁力の発光は ``glow`` に紫を置いて emissive で拾わせる。
"""
from __future__ import annotations


# ---------------------------------------------------------------- 明度の段
#  金属はこの段の上二つ、布は下二つ。中間で迷わないための物差し。
STEEL_XL = "#E8ECF2"        # 稜線・擦り傷のハイライト
STEEL_L = "#CED5DE"
STEEL = "#B8C0CC"           # §2-2 の「鋼」。全ての金属の基準点
STEEL_M = "#98A0AC"
STEEL_D = "#6E7681"
STEEL_XD = "#454B54"

# ---------------------------------------------------------------- 基本色
VIOLET = "#6A38A0"          # マグニートーの装甲（旧 #5B2E86 から一段上げた）
VIOLET_D = "#452068"
VIOLET_L = "#C8A2F0"
CRIMSON = "#B01423"         # マント / ブーツ / 手袋
CRIMSON_D = "#6E0A16"
CRIMSON_L = "#E86A74"
GUNMETAL = "#ADB5C1"        # 兜（画像の色を鋼の段へ寄せた）
GUNMETAL_D = "#7C838F"
GUNMETAL_L = "#DCE2EA"
MAG_GLOW = "#B47CFF"        # 磁界の光
IRON = "#A0A8B2"
NIGHT = "#2A2E38"


# ---------------------------------------------------------------- 小道具
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(t):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in t)


def tone(colour: str, f: float) -> str:
    """明度を掛ける。1.0 超は白へ寄せるので、彩度を失わずに持ち上がる。"""
    r, g, b = _rgb(colour)
    if f <= 1.0:
        return _hex((r * f, g * f, b * f))
    t = min(1.0, f - 1.0)
    return _hex((r + (255 - r) * t, g + (255 - g) * t, b + (255 - b) * t))


def lum(colour: str) -> float:
    """0..1 の知覚明度。素材差が足りているかを機械で見るためだけに使う。"""
    r, g, b = _rgb(colour)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def S(base, second=None, pattern="flat", noise=6, **kw):
    """スタイル辞書を組み立てる小さなヘルパ。"""
    d = {"base": base, "pattern": pattern, "noise": noise}
    if second:
        d["second"] = second
    d.update(kw)
    return d


def metal(base, second=None, pattern="brushed", noise=4, **kw):
    """金属面。

    ``ao`` を既定の 0.30 から 0.14 へ落とす。金属は面の縁が暗く落ちるほど
    「濡れた布」に見えるので、影ではなく稜線のハイライトで丸みを出す。
    """
    kw.setdefault("ao", 0.14)
    kw.setdefault("grad", 0.22)
    kw.setdefault("light", tone(base, 1.45))
    kw.setdefault("dark", tone(base, 0.24))
    return S(base, second or tone(base, 0.70), pattern, noise, **kw)


def fabric(base, second=None, pattern="cloth", noise=6, **kw):
    """布・革。金属より暗く置くが、``ao`` は下げて縁だけが沈むのを防ぐ。"""
    kw.setdefault("ao", 0.22)
    kw.setdefault("grad", 0.16)
    kw.setdefault("light", tone(base, 1.40))
    kw.setdefault("dark", tone(base, 0.32))
    return S(base, second or tone(base, 0.62), pattern, noise, **kw)


def flesh(base, second=None, noise=3, **kw):
    """肌。AO を強く掛けると土気色になるので最小にする。"""
    kw.setdefault("ao", 0.16)
    kw.setdefault("grad", 0.12)
    kw.setdefault("light", tone(base, 1.35))
    kw.setdefault("dark", tone(base, 0.34))
    return S(base, second or tone(base, 0.80), "skin", noise, **kw)


def lit(base, second=None, pattern="flat", noise=2, **kw):
    """自ら光る面。AO も階調も掛けない。"""
    kw.setdefault("ao", 0.0)
    kw.setdefault("grad", 0.06)
    kw.setdefault("light", "#FFFFFF")
    kw.setdefault("dark", tone(base, 0.30))
    return S(base, second or tone(base, 0.42), pattern, noise, **kw)


def _common(glow=MAG_GLOW, skin="#E8C4A2", iris="#4A6B8E", hair="#2A2530"):
    """どのキャラでも rig が触る既定スタイル。個別 palette が上書きする。

    ここが全キャラの下敷きになるので、**既定値そのものを明るく持つ**。
    個別パレットで上書きし忘れた部位が黒い塊になるのを防ぐのが目的。
    """
    return {
        "base": metal(STEEL, STEEL_M, "brushed", 4, glow=glow),
        "skin": flesh(skin, "#C99A78", 3, skin=skin, iris=iris,
                      hair_col=hair, light="#FFF2E0", dark="#4A3730"),
        # weave は uv_scale ぶんの升目になるので、胴のような広い面では
        # 市松模様として読めてしまう。既定は leather（不規則な粒）にする。
        "suit": fabric(NIGHT, "#191C24", "leather", 5, glow=glow,
                       light="#6E7686"),
        "underlay": fabric("#21242C", "#141620", "weave", 4, glow=glow),
        "armor": metal(STEEL_L, STEEL_M, "panel", 4, glow=glow,
                       light="#FFFFFF", dark="#2A2E36"),
        "accent": metal(glow, "#5A3A9A", "metal", 4, glow=glow),
        "hair": S(hair, tone(hair, 0.42), "hair", 6, ao=0.18, grad=0.20,
                  light=tone(hair, 1.55), dark=tone(hair, 0.28)),
        "steel": metal(STEEL, STEEL_M, "brushed", 4, glow=glow),
        "cloth": fabric("#33373F", "#1E212A", "leather", 5, glow=glow),
        "decal": metal("#A6ADB8", "#6E757F", "panel", 3, glow=glow),
        "visor": lit("#D8E2EE", "#8E9AA8", "glass", 3, glow=glow),
        "glow": lit(glow, "#4A2A82", "flat", 2, glow=glow),
        # モデルが使うかもしれない汎用キー（未指定でも壊れないように）
        "helm": metal(GUNMETAL, GUNMETAL_D, "brushed", 4, glow=glow),
        "helm_dark": metal(GUNMETAL_D, "#565C66", "metal", 4, glow=glow),
        "helm_crest": metal(GUNMETAL_L, GUNMETAL, "brushed", 3, glow=glow),
        "cape": fabric(CRIMSON, CRIMSON_D, "cloth", 6, glow=glow),
        "cape_inner": fabric(CRIMSON_D, "#3A0710", "cloth", 5, glow=glow),
        "plate": metal(VIOLET, VIOLET_D, "panel", 4, glow=glow),
        "plate_dark": metal(VIOLET_D, "#2C1546", "panel", 4, glow=glow),
        "belt": metal("#97A0AC", "#6A7079", "metal", 4, glow=glow),
        "boot": fabric(CRIMSON, CRIMSON_D, "leather", 5, glow=glow),
        "glove": fabric(CRIMSON, CRIMSON_D, "leather", 5, glow=glow),
        "magnet": lit(MAG_GLOW, "#4A2A82", "metal", 3, glow=MAG_GLOW),
        "scale": S("#3E86CC", "#22568E", "scale", 5, glow=glow, ao=0.14,
                   grad=0.22, light="#B4E0FF", dark="#0E2038"),
        "fur": S("#C89C58", "#7E6234", "hair", 8, glow=glow, ao=0.18,
                 grad=0.22, light="#F4E2B0", dark="#3A2C14"),
        "claw": metal("#F2EEE0", "#A8A294", "brushed", 4, glow=glow),
        "flame": S("#F0862A", "#A04410", "muscle", 8, glow="#FFC24A",
                   ao=0.12, grad=0.24, light="#FFE0A0", dark="#5A2404"),
        "stone": S("#948672", "#5E5648", "crack", 7, glow="#C8A05A", ao=0.20,
                   grad=0.20, light="#D8CCB4", dark="#3A342A"),
        "hex": S("#C4183A", "#6E0C1E", "glass", 5, glow="#FF4A6E", ao=0.16,
                 grad=0.20, light="#FF8AA0", dark="#2A040A"),
        "gut": S("#A66E58", "#6E4030", "muscle", 6, glow=glow, ao=0.18,
                 grad=0.18, light="#E0AE92", dark="#3A2018"),
        "tongue": S("#D4788E", "#96455C", "sinew", 5, glow=glow, ao=0.16,
                    light="#F4B4C2", dark="#4A1C28"),
        "goggle": lit("#3A404E", "#1E222C", "glass", 3, glow="#FF6A2A"),
        "rune": lit(MAG_GLOW, "#3A1C58", "crack", 3, glow=MAG_GLOW),
        "robot": metal("#9E92C8", "#6E62A0", "panel", 4, glow="#FF5A2A"),
        "robot_dark": metal("#6E62A0", "#453C68", "panel", 4, glow="#FF5A2A"),
        "optic": lit("#E8823A", "#8E4A18", "glass", 3, glow="#FFB24A"),
        "cable": S("#3E4250", "#22252E", "rubber", 4, glow=glow, ao=0.20,
                   grad=0.18, light="#8A90A0", dark="#12141A"),
        "hazard": S("#E8C43A", "#96790E", "plate", 5, glow="#FFE24A", ao=0.14,
                    grad=0.20, light="#FFF2A0", dark="#3A2E06"),
        "shard": metal(IRON, "#5E6670", "metal", 5, glow=glow),
        "rock": S("#8A7E6C", "#544C40", "crack", 7, glow="#A88E5A", ao=0.20,
                  grad=0.20, light="#CEC2AC", dark="#332E26"),
        "energy": lit(glow, "#3A1C58", "glass", 2, glow=glow),
    }


# ===========================================================================
#  マグニートー  —  画像のガンメタル兜 ＋ 深紫の装甲 ＋ 深紅のマント
# ===========================================================================
MAGNETO = _common(glow=MAG_GLOW, skin="#E2BE9E", iris="#5E7A9E", hair="#B8BCC4")
MAGNETO.update({
    # 兜は三段の明度で組む。本体 → 陰 → 稜線の順に上がっていき、
    # 遠景ではこの「稜線だけが白い」ことで M 字が読める。
    "helm": metal(GUNMETAL, GUNMETAL_D, "brushed", 4, glow=MAG_GLOW,
                  light="#F0F4FA", dark="#22252B"),
    "helm_dark": metal(GUNMETAL_D, "#565C66", "metal", 4, glow=MAG_GLOW,
                       light="#C6CCD6", dark="#16181D"),
    "helm_crest": metal(GUNMETAL_L, GUNMETAL, "brushed", 3, glow=MAG_GLOW,
                        light="#FFFFFF", dark="#2A2E34"),
    "plate": metal(VIOLET, VIOLET_D, "panel", 5, glow=MAG_GLOW,
                   light=VIOLET_L, dark="#1A0C2A"),
    "plate_dark": metal(VIOLET_D, "#2C1546", "panel", 4, glow=MAG_GLOW,
                        light="#9E72CE", dark="#150826"),
    "cape": fabric(CRIMSON, CRIMSON_D, "cloth", 7, glow=MAG_GLOW,
                   light=CRIMSON_L, dark="#42060E"),
    "cape_inner": fabric(CRIMSON_D, "#3E0710", "cloth", 6, glow=MAG_GLOW,
                         light="#C4505C", dark="#2A040A"),
    "suit": fabric("#3A2258", "#241440", "weave", 5, glow=MAG_GLOW,
                   light="#8E6ABE"),
    "underlay": fabric("#2A1842", "#180E28", "weave", 4, glow=MAG_GLOW),
    "boot": fabric(CRIMSON, CRIMSON_D, "leather", 6, glow=MAG_GLOW,
                   light=CRIMSON_L, dark="#3A050C"),
    "glove": fabric(CRIMSON, CRIMSON_D, "leather", 6, glow=MAG_GLOW,
                    light=CRIMSON_L, dark="#3A050C"),
    "belt": metal("#A2ABB8", "#70777F", "metal", 4, glow=MAG_GLOW,
                  light="#E4EAF2", dark="#22252B"),
    "armor": metal(VIOLET, VIOLET_D, "panel", 5, glow=MAG_GLOW,
                   light=VIOLET_L, dark="#1A0C2A"),
    "accent": lit(MAG_GLOW, "#3A1C58", "metal", 3, glow=MAG_GLOW),
    "magnet": lit(MAG_GLOW, "#3A1C58", "glass", 2, glow=MAG_GLOW),
})

# ===========================================================================
#  ブラザーフッド
# ===========================================================================
# ミスティークは「暗いキャラ」の筆頭。青を沈めると輪郭ごと消えるので、
# 鱗を読ませるために base を上げ、light との差を最大まで開く。
MYSTIQUE = _common(glow="#3AA8E0", skin="#3E86CC", iris="#E8C42A", hair="#E04A22")
MYSTIQUE.update({
    # 素肌そのものは滑らかな青に留める。``scale`` パターンのセルは
    # uv_scale 倍で大きくなるので、顔（uv_scale 12）に敷くと鱗一枚が
    # 顔より大きくなり、頬を横切る一本の継ぎ目にしか見えない。
    # 鱗は ``scales`` デカール（面のテクセル数で刻む）が受け持つ。
    "skin": S("#3E86CC", "#2E6FAE", "skin", 4, skin="#3E86CC", iris="#E8C42A",
              hair_col="#E04A22", light="#C4E8FF", dark="#0E2038", ao=0.12,
              grad=0.24),
    "scale": S("#3E86CC", "#22568E", "scale", 5, glow="#3AA8E0", ao=0.12,
               grad=0.24, light="#C4E8FF", dark="#0E2038"),
    "hair": S("#E04A22", "#8E2008", "hair", 7, ao=0.16, grad=0.24,
              light="#FFA070", dark="#4A1004"),
    "suit": fabric("#1E4478", "#10263F", "weave", 5, glow="#3AA8E0",
                   light="#5E96D8"),
    "cloth": fabric("#24446E", "#122438", "leather", 4, glow="#3AA8E0"),
    "belt": metal("#8E96A2", "#5E656E", "metal", 4, glow="#3AA8E0"),
})

SABRETOOTH = _common(glow="#E8A02A", skin="#E4C0A0", iris="#D8B42A",
                     hair="#D0A662")
SABRETOOTH.update({
    "fur": S("#D0A662", "#8A6C38", "hair", 9, ao=0.18, grad=0.24,
             light="#F8E8BC", dark="#3A2C14"),
    "hair": S("#DCB874", "#8A6C38", "hair", 9, ao=0.18, grad=0.24,
              light="#FFF0C8", dark="#3A2C14"),
    "claw": metal("#F6F2E4", "#A8A294", "brushed", 3, glow="#FFF4D8",
                  light="#FFFFFF", dark="#4A4640"),
    "suit": fabric("#7A5A3E", "#4A3624", "leather", 6, glow="#E8A02A",
                   light="#C89E74"),
    "cloth": fabric("#5E4430", "#38281A", "leather", 5, glow="#E8A02A"),
})

TOAD = _common(glow="#8EC84B", skin="#92B462", iris="#D8C42A", hair="#5E7034")
TOAD.update({
    "skin": S("#92B462", "#6E8E48", "skin", 6, skin="#92B462", iris="#D8C42A",
              hair_col="#5E7034", light="#DCF0AE", dark="#1E2810", ao=0.14,
              grad=0.22),
    "tongue": S("#D4788E", "#96455C", "sinew", 5, glow="#E88AA0", ao=0.16,
                light="#F4B4C2", dark="#4A1C28"),
    "suit": fabric("#4E6030", "#2A3618", "cloth", 6, glow="#8EC84B",
                   light="#8EA867"),
    "cloth": fabric("#3A4622", "#1E2610", "leather", 5, glow="#8EC84B"),
})

# ジャガーノートは全身が赤黒くなりがちなので、兜だけを一段上げて
# 「赤いドームが先に見える」順序を作る。
JUGGERNAUT = _common(glow="#E8562A", skin="#D8A882", iris="#3A2A20",
                     hair="#A8502A")
JUGGERNAUT.update({
    "helm": metal("#B8342C", "#7A1414", "metal", 5, glow="#E8562A",
                  light="#F79280", dark="#2A0808"),
    "helm_dark": metal("#7A1414", "#4A0A0A", "metal", 4, glow="#E8562A",
                       light="#C86254", dark="#1E0404"),
    "helm_crest": metal("#D8564A", "#8E2018", "brushed", 4, glow="#E8562A",
                        light="#FFC0B0", dark="#2A0808"),
    "armor": metal("#B8342C", "#7A1414", "panel", 5, glow="#E8562A",
                   light="#F79280", dark="#2A0808"),
    "plate": metal("#9A8468", "#61513C", "metal", 5, glow="#E8562A",
                   light="#DCC8A6", dark="#2E261C"),
    # 胴は赤い兜の下敷きなので、赤より一段落として、しかし黒には落とさない。
    # 茶を暗くすると赤兜と溶けて「赤黒い塊」に戻る。
    "suit": fabric("#8A5A40", "#5E3E2A", "leather", 5, glow="#E8562A",
                   light="#D09A78"),
    "belt": metal("#D8B46A", "#8E7030", "metal", 4, glow="#FFD88A",
                  light="#FFEEB8", dark="#3A2C0C"),
    "cloth": fabric("#5E3C28", "#331F14", "leather", 5, glow="#E8562A",
                    light="#A87A58"),
})

QUICKSILVER = _common(glow="#8ED8FF", skin="#E8C8AC", iris="#4A8ABE",
                      hair="#EAF0F8")
QUICKSILVER.update({
    "hair": S("#EAF0F8", "#A2AAB6", "hair", 5, ao=0.14, grad=0.22,
              light="#FFFFFF", dark="#6E7680"),
    "suit": fabric("#3A78B4", "#2A5E92", "leather", 5, glow="#8ED8FF",
                   light="#8EC0EC"),
    "armor": metal("#D2D8E2", "#8E96A2", "brushed", 4, glow="#8ED8FF",
                   light="#FFFFFF", dark="#333941"),
    "accent": lit("#8ED8FF", "#2A5A8E", "metal", 3, glow="#8ED8FF"),
    "boot": fabric("#2E5E92", "#183A5E", "leather", 5, glow="#8ED8FF"),
})

PYRO = _common(glow="#FFA02A", skin="#E4C0A0", iris="#8E5A2A", hair="#C8A462")
PYRO.update({
    "suit": fabric("#4E535F", "#2E323C", "leather", 5, glow="#FFA02A",
                   light="#949AA8"),
    "armor": metal("#E8762A", "#96430E", "panel", 5, glow="#FFC24A",
                   light="#FFC48E", dark="#3A1A04"),
    "flame": S("#F0862A", "#A04410", "muscle", 9, glow="#FFD86A", ao=0.10,
               grad=0.26, light="#FFE8B4", dark="#5A2404"),
    "accent": lit("#FFA02A", "#8E4A0A", "metal", 4, glow="#FFC24A"),
    "steel": metal("#B0B8C4", "#787F89", "brushed", 4, glow="#FFA02A"),
})

AVALANCHE = _common(glow="#C8843A", skin="#D8AE86", iris="#4A3A28",
                    hair="#4A3A28")
AVALANCHE.update({
    "suit": fabric("#7E6C56", "#4A3E30", "leather", 6, glow="#C8843A",
                   light="#C4B096"),
    "armor": metal("#A2907A", "#6A5B48", "plate", 6, glow="#C8843A",
                   light="#E4D6C0", dark="#2A241C"),
    "stone": S("#948672", "#5E5648", "crack", 8, glow="#C8A05A", ao=0.20,
               grad=0.22, light="#D8CCB4", dark="#3A342A"),
    "goggle": lit("#3A404E", "#1E222C", "glass", 3, glow="#FF8A2A"),
})

BLOB = _common(glow="#E8C86A", skin="#E8C09A", iris="#3A2A1E", hair="#4A3628")
BLOB.update({
    "skin": flesh("#E8C09A", "#B4886A", 4, skin="#E8C09A", iris="#3A2A1E",
                  hair_col="#4A3628", light="#FFF4E2", dark="#4A3428"),
    "gut": S("#E8C09A", "#B4886A", "muscle", 5, glow="#E8C86A", ao=0.14,
             grad=0.20, light="#FFF4E2", dark="#4A3428"),
    "suit": fabric("#56683A", "#2E3A1E", "cloth", 6, glow="#E8C86A",
                   light="#94A874"),
    "cloth": fabric("#3E4A26", "#222A14", "leather", 5, glow="#E8C86A"),
})

# 深紅は emissive を使わずに強く見せる（§2-2 の三色を汚さないため）。
# だから布そのものを上げ、縁のハイライトで光っているように見せる。
SCARLET_WITCH = _common(glow="#FF4A6E", skin="#E8C4A8", iris="#4A8A6E",
                        hair="#5E3626")
SCARLET_WITCH.update({
    "suit": fabric("#A81830", "#5E0C18", "cloth", 6, glow="#FF4A6E",
                   light="#EE7E90", dark="#2A040A"),
    "cape": fabric("#C4183A", "#6E0C1E", "cloth", 7, glow="#FF4A6E",
                   light="#FF7E96", dark="#2E040C"),
    "cape_inner": fabric("#6E0C1E", "#3A0410", "cloth", 5, glow="#FF4A6E",
                         light="#C45068"),
    "armor": metal("#D8B46A", "#8E7030", "metal", 4, glow="#FFD88A",
                   light="#FFEEB8", dark="#3A2C0C"),
    "hex": S("#C4183A", "#6E0C1E", "glass", 5, glow="#FF4A6E", ao=0.14,
             grad=0.22, light="#FF8AA0", dark="#2A040A"),
    "accent": lit("#FF4A6E", "#6E0A1C", "metal", 3, glow="#FF4A6E"),
    "boot": fabric("#7A1024", "#420812", "leather", 5, glow="#FF4A6E"),
})

# ===========================================================================
#  敵
# ===========================================================================
# Mk-I は「明るい紫鋼 + 橙のオプティック」。プライムは「黒鉄 + 琥珀 + 金」。
# 同じ紫の濃淡で差を付けようとすると、暗い側は必ず黒へ潰れて見分けが消える。
# だから **色相ごと変える**。
SENTINEL = _common(glow="#FF5A2A", skin="#9E92C8", iris="#FF5A2A",
                   hair="#6E62A0")
SENTINEL.update({
    "robot": metal("#9E92C8", "#6E62A0", "panel", 4, glow="#FF5A2A",
                   light="#E6DEFF", dark="#2A2446"),
    "robot_dark": metal("#6E62A0", "#453C68", "panel", 4, glow="#FF5A2A",
                        light="#B4A8E0", dark="#1E1836"),
    "armor": metal("#9E92C8", "#6E62A0", "panel", 4, glow="#FF5A2A",
                   light="#E6DEFF", dark="#2A2446"),
    "plate": metal("#B08A5E", "#75593A", "plate", 5, glow="#FF5A2A",
                   light="#E8CCA8", dark="#332618"),
    # オプティックの下地。発光は暗い下地の上では効かないので、
    # 縁取りの金属自体を明るい橙鋼にしておく。
    "optic": lit("#E8823A", "#8E4A18", "glass", 2, glow="#FFB24A"),
    "cable": S("#3E4250", "#22252E", "rubber", 4, glow="#FF5A2A", ao=0.20,
               grad=0.18, light="#8A90A0", dark="#12141A"),
    "steel": metal("#B4BAC6", "#7A818C", "brushed", 4, glow="#FF5A2A"),
    "base": metal("#B4BAC6", "#7A818C", "brushed", 4, glow="#FF5A2A"),
    "hazard": S("#E8C43A", "#96790E", "plate", 5, glow="#FFE24A", ao=0.14,
                grad=0.20, light="#FFF2A0", dark="#3A2E06"),
})

PRIME_SENTINEL = dict(SENTINEL)
PRIME_SENTINEL.update({
    "robot": metal("#7E848E", "#4E545E", "panel", 4, glow="#E8621E",
                   light="#DCE2EC", dark="#1A1D22"),
    "robot_dark": metal("#4E545E", "#31363E", "panel", 4, glow="#E8621E",
                        light="#A2A8B4", dark="#101216"),
    "armor": metal("#7E848E", "#4E545E", "panel", 4, glow="#E8621E",
                   light="#DCE2EC", dark="#1A1D22"),
    "plate": metal("#A08A4E", "#665730", "plate", 5, glow="#E8621E",
                   light="#E0CC96", dark="#2E2614"),
    "optic": lit("#FFB024", "#9E6408", "glass", 2, glow="#FFF0C0"),
    "hazard": S("#E8C43A", "#96790E", "plate", 5, glow="#FFE24A", ao=0.14,
                grad=0.20, light="#FFF2A0", dark="#3A2E06"),
    "steel": metal("#C2C8D2", "#868D97", "brushed", 4, glow="#E8621E"),
    "base": metal("#C2C8D2", "#868D97", "brushed", 4, glow="#E8621E"),
})

MRD = _common(glow="#FF6A2A", skin="#DCB694", iris="#3A3A44", hair="#3A342C")
MRD.update({
    "suit": fabric("#545C6E", "#333947", "leather", 5, glow="#FF6A2A",
                   light="#9AA2B0"),
    "armor": metal("#8A919E", "#5C626C", "panel", 4, glow="#FF6A2A",
                   light="#DDE2EA", dark="#20232A"),
    "goggle": lit("#343A46", "#181C24", "glass", 3, glow="#FF6A2A"),
    "hazard": S("#B02828", "#6E1414", "plate", 5, glow="#FF6A2A", ao=0.16,
                grad=0.20, light="#F08272", dark="#2E0808"),
    "cloth": fabric("#2E323C", "#181B22", "leather", 5, glow="#FF6A2A"),
})

# ===========================================================================
#  小物
# ===========================================================================
# 小物は画面上で小さく、単体で浮くので、地の色は迷わず明るい側に置く。
SHARD = _common(glow=MAG_GLOW)
SHARD.update({
    "base": metal(IRON, "#5E6670", "metal", 5, glow=MAG_GLOW,
                  light="#E8ECF2", dark="#2A2E34"),
    "shard": metal(IRON, "#5E6670", "metal", 5, glow=MAG_GLOW,
                   light="#E8ECF2", dark="#2A2E34"),
})
DEBRIS = _common(glow="#A88E5A")
DEBRIS.update({"base": S("#8A7E6C", "#544C40", "crack", 8, glow="#A88E5A",
                         ao=0.20, grad=0.22, light="#CEC2AC", dark="#332E26")})
ENERGY_VIOLET = _common(glow=MAG_GLOW)
ENERGY_VIOLET.update({"base": lit(MAG_GLOW, "#3A1C58", "glass", 3,
                                  glow=MAG_GLOW)})
ENERGY_CRIMSON = _common(glow="#FF4A6E")
ENERGY_CRIMSON.update({"base": lit("#FF4A6E", "#6E0A1C", "glass", 3,
                                   glow="#FF4A6E")})
ENERGY_FIRE = _common(glow="#FFB24A")
ENERGY_FIRE.update({"base": lit("#FF9A3A", "#8E3A0A", "glass", 3,
                                glow="#FFD86A")})
ENERGY_ORANGE = _common(glow="#FF7A2A")
ENERGY_ORANGE.update({"base": lit("#FF8A3A", "#8E2A0A", "glass", 3,
                                  glow="#FFB24A")})

# ===========================================================================
ALL = {
    "magneto": MAGNETO,
    "mystique": MYSTIQUE,
    "sabretooth": SABRETOOTH,
    "toad": TOAD,
    "juggernaut": JUGGERNAUT,
    "quicksilver": QUICKSILVER,
    "pyro": PYRO,
    "avalanche": AVALANCHE,
    "blob": BLOB,
    "scarlet_witch": SCARLET_WITCH,
    "sentinel": SENTINEL,
    "prime_sentinel": PRIME_SENTINEL,
    "mrd": MRD,
    # 小物
    "shard": SHARD,
    "debris": DEBRIS,
    "energy_violet": ENERGY_VIOLET,
    "energy_crimson": ENERGY_CRIMSON,
    "energy_fire": ENERGY_FIRE,
    "energy_orange": ENERGY_ORANGE,
}


def for_character(key: str) -> dict:
    """contract.CHARACTERS[key]["pal"] を引いてスタイル辞書を返す。"""
    from contract import CHARACTERS
    return ALL[CHARACTERS[key]["pal"]]


def contrast_report() -> list:
    """素材差が足りているかを数値で点検する（目視の前の足切り）。

    「布と金属で最低 40% の明度差」を守れているかを見るためのもの。
    生成には関わらないので、気になったときに手で呼ぶ。
    """
    out = []
    for name, pal in ALL.items():
        m = [k for k in ("helm", "armor", "steel", "robot", "base")
             if k in pal]
        c = [k for k in ("cape", "suit", "cloth", "boot") if k in pal]
        if not m or not c:
            continue
        mv = max(lum(pal[k]["base"]) for k in m)
        cv = max(lum(pal[k]["base"]) for k in c)
        out.append((name, round(mv, 3), round(cv, 3),
                    round((mv - cv) / max(mv, 1e-6), 3)))
    return out
