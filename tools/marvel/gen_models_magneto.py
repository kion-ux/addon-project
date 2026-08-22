# -*- coding: utf-8 -*-
"""マグニートーのモデル。

本作の主役なので、ここだけは他のキャラと別モジュールにしてある。
兜・マント・装甲を専用パーツとして組み、``player_rig=True`` で
バニラのプレイヤー骨格に載るようにしておく（＝変身体としてそのまま着られる）。

寸法の根拠は ``docs/DIRECTION.md`` §3。遠景で読ませたいのは
**兜の M 字 / 広い肩 / 長いマント** の三つだけなので、
その三つに cube と texel を集中させ、それ以外は箱のままで済ませている。
"""
from __future__ import annotations

import math

import _path  # noqa: F401  (sys.path を整える。必ず最初に import する)

import contract as K  # noqa: E402
import colours  # noqa: E402
from common import emit  # noqa: E402
from mcmodel import Bone, Cube, Model  # noqa: E402
from rig import Build, HumanRig  # noqa: E402


# ===========================================================================
#  共有エンジンに触らずに済ませるための小道具
# ===========================================================================
def _enable_locators() -> None:
    """``Bone`` に ``locators`` を持たせる。

    パーティクルの ``"locator": "rightHand"`` は、geometry 側に locator が
    無いと **黙って無視されて原点（足元）から出る**。共有エンジンの
    ``mcmodel.py`` は他アドオンも使うので書き換えられないため、
    ここでは to_json を包んで「locators 属性があれば書き出す」だけを足す。
    属性を持たない既存のボーンには一切影響しない。
    """
    if getattr(Bone, "_marvel_locators", False):
        return
    inner = Bone.to_json

    def to_json(self):
        out = inner(self)
        loc = getattr(self, "locators", None)
        if loc:
            out["locators"] = {k: [round(float(c), 3) for c in p]
                               for k, p in loc.items()}
        return out

    Bone.to_json = to_json
    Bone._marvel_locators = True


_enable_locators()


def _loc(bone: Bone, name: str, pos) -> None:
    if getattr(bone, "locators", None) is None:
        bone.locators = {}
    bone.locators[name] = tuple(pos)


def _rescale(cube: Cube, scale: int) -> None:
    """既に生成済みの cube の texel 密度だけを差し替える。

    ``rig.flesh()` が置く胴・腕・脚は既定 uv_scale のままだと粗すぎるが、
    rig.py は共有なので触れない。生成後に密度だけ上書きしている。
    """
    cube.uv_scale = scale
    cube._scale = scale


def _rot(rx: float, ry: float, rz: float, v):
    """Bedrock（と preview.py）と同じ合成順・同じ符号で点を回す。

    フィンの先端は「主翼を回した先」に置きたいので、
    回転後の座標を Python 側で解いておく必要がある。
    """
    a, b, c = math.radians(-rx), math.radians(-ry), math.radians(rz)
    x, y, z = v
    x, y = x * math.cos(c) - y * math.sin(c), x * math.sin(c) + y * math.cos(c)
    x, z = x * math.cos(b) + z * math.sin(b), -x * math.sin(b) + z * math.cos(b)
    y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
    return (x, y, z)


def _span(a: float, b: float):
    """(origin, size) を昇順で返す。左右対称パーツを sgn 倍で書くため。"""
    return (min(a, b), abs(b - a))


# ===========================================================================
#  兜
# ===========================================================================
#  兜のパーツは **必ず頭の箱より外側** に置く。内側に入った面は一枚も
#  描画されないので、内側に置いた瞬間そのパーツは存在しないのと同じになる。
#  旧実装の「顔の板」はまさにこれで head cube と同一平面に重なり、
#  z-fighting を起こしていた。顔は head cube の north 面に一本化する。
#  この制約のせいで頭が大きいままだと天頂を細らせられないので、
#  `helmet()` の側で頭蓋を 0.90 / 0.95 に絞ってからドームを被せている。
FACE_TOP = 0.508        # 兜の開口の上端（顎からの hh 比）。頭の 5 割弱だけ開ける
FIN_SWEEP = 40.0        # フィンの跳ね上げ角。兜幅はこれで決まる
FIN_YAW = 24.0          # 真横から板に見えないための捻り
FIN_PITCH = -18.0       # 牛角化の防止。後ろへ寝かせて「刃」にする


def _helm_cubes(hw: float, hh: float, hd: float, y0: float):
    """兜 22 cube を組む。頭の寸法だけを引数に取るので、
    被り物（`helmet()`）と手持ちの小道具（`build_helmet_prop()`）で共用できる。"""
    out = []
    zc = -0.03 * hd                       # 兜はわずかに前傾させて被せる

    def box(x_a, x_b, y_a, y_b, z_a, z_b, style, **kw):
        ox, sx = _span(x_a, x_b)
        oy, sy = _span(y_a, y_b)
        oz, sz = _span(z_a, z_b)
        c = Cube((ox, oy, oz), (sx, sy, sz), style, **kw)
        out.append(c)
        return c

    # --- ドーム 3 段 -----------------------------------------------------
    # 段ごとに幅と奥行きを絞って丸みを出す。天頂は総身長ちょうどで止める
    # （ここを超えると他キャラと並べたときに等身が狂う）。跳ね上がるのは
    # フィンだけ、という切り分け。
    for w, d, ya, yb, dec in (
        (0.578, 0.600, FACE_TOP, 0.720, {"north": "helm_crest"}),
        (0.525, 0.545, 0.720, 0.890, {"up": "panel_seam"}),
        (0.462, 0.492, 0.890, 1.000, {"up": "panel_seam"}),
    ):
        box(-w * hw, w * hw, y0 + ya * hh, y0 + yb * hh,
            zc - d * hd, zc + d * hd, "helm", uv_scale=8, decals=dec)

    # --- 頬当て（2 段、傾きを 6° ずらす）----------------------------------
    # 平行に置くと必ず長方形に見えるので、上段 7° / 顎 13° と差をつける。
    # 顎段の下端は chin より 0.17 下げ、顎を「挟む」形にする。
    for sgn in (-1, 1):
        c = box(0.300 * hw * sgn, 0.566 * hw * sgn,
                y0 + 0.235 * hh, y0 + FACE_TOP * hh,
                -0.610 * hd, -0.487 * hd, "helm", uv_scale=10,
                decals={"north": "helm_face"},
                rotation=(0, -10 * sgn, -7 * sgn))
        c.pivot = [0.300 * hw * sgn, y0 + FACE_TOP * hh, -0.55 * hd]
        c = box(0.272 * hw * sgn, 0.524 * hw * sgn,
                y0 - 0.040 * hh, y0 + 0.255 * hh,
                -0.595 * hd, -0.481 * hd, "helm", uv_scale=10,
                decals={"north": "helm_face"},
                rotation=(0, -14 * sgn, -13 * sgn))
        c.pivot = [0.272 * hw * sgn, y0 + 0.255 * hh, -0.54 * hd]

    # --- 側頭（耳を覆う板）------------------------------------------------
    # 頬当てより 1 段外へ出して、顔まわりに段差を作る。
    for sgn in (-1, 1):
        box(0.492 * hw * sgn, 0.598 * hw * sgn,
            y0 + 0.320 * hh, y0 + 0.760 * hh,
            -0.560 * hd, 0.330 * hd, "helm_dark", uv_scale=8,
            decals={"east" if sgn > 0 else "west": "helm_side"})
        box(0.470 * hw * sgn, 0.556 * hw * sgn,
            y0 + 0.055 * hh, y0 + 0.330 * hh,
            -0.500 * hd, 0.430 * hd, "helm_dark", uv_scale=8,
            decals={"east" if sgn > 0 else "west": "helm_temple"})

    # --- 後頭部の襟 -------------------------------------------------------
    c = box(-0.540 * hw, 0.540 * hw, y0 + 0.130 * hh, y0 + 0.650 * hh,
            0.336 * hd, 0.659 * hd, "helm_dark", uv_scale=8,
            decals={"south": "helm_temple"}, rotation=(-8, 0, 0))
    c.pivot = [0, y0 + 0.130 * hh, 0.40 * hd]

    # --- 眉間リッジ -------------------------------------------------------
    # V を M に変える一個。左右フィンの間の谷には **他に何も置かない**。
    c = box(-0.112 * hw, 0.112 * hw, y0 + 0.352 * hh, y0 + 0.575 * hh,
            -0.672 * hd, -0.566 * hd, "helm_crest", uv_scale=10,
            decals={"north": "helm_crest"}, rotation=(16, 0, 0))
    c.pivot = [0, y0 + 0.575 * hh, -0.62 * hd]

    # --- 額の稜 -----------------------------------------------------------
    # 眉間から外上へ 30° で走る張り出し。M 字は天頂ではなく
    # **額の前面** で作る。天頂に稜を足すと山が四つ並んで W に見えた。
    for sgn in (-1, 1):
        c = box(0.075 * hw * sgn, 0.500 * hw * sgn,
                y0 + 0.510 * hh, y0 + 0.600 * hh,
                -0.640 * hd, -0.573 * hd, "helm_crest", uv_scale=10,
                rotation=(0, 0, 30 * sgn))
        c.pivot = [0.075 * hw * sgn, y0 + 0.510 * hh, -0.60 * hd]

    # --- フィン ------------------------------------------------------------
    # 一本の箱だと必ず「角」に見えるので、同じ角度の板を根元から先端へ
    # 幅と奥行きを落としながら重ね、テーパーの付いた「刃」にする。
    # 先端だけ更に寝かせて後ろへ反らせると、真横から見たときに
    # 直線の棒ではなく鎌の形になる。
    for sgn in (-1, 1):
        piv = (0.360 * hw * sgn, y0 + 0.640 * hh, -0.270 * hd)
        rot = (FIN_PITCH, -FIN_YAW * sgn, -FIN_SWEEP * sgn)
        for half, length, deep in ((0.145, 0.340, 0.310),
                                   (0.105, 0.300, 0.245)):
            half, length, deep = half * hw, length * hh, deep * hd
            c = box(piv[0] - half, piv[0] + half, piv[1], piv[1] + length,
                    piv[2] - deep, piv[2] + deep, "helm_crest", uv_scale=10,
                    decals={"east": "panel_seam", "west": "panel_seam"},
                    rotation=rot)
            c.pivot = list(piv)
            piv = tuple(piv[i] + _rot(*rot, (0, length, 0))[i] for i in range(3))
        rot2 = (FIN_PITCH - 24, -FIN_YAW * sgn, -(FIN_SWEEP + 10) * sgn)
        half2, len2, deep2 = 0.075 * hw, 0.150 * hh, 0.155 * hd
        c = box(piv[0] - half2, piv[0] + half2, piv[1], piv[1] + len2,
                piv[2] - deep2, piv[2] + deep2, "helm_crest", uv_scale=10,
                rotation=rot2)
        c.pivot = list(piv)

    # --- 露出した顎 -------------------------------------------------------
    # 顔の板は廃止したので、顎だけを肌のまま前へ出して面を割る。
    # 無精髭はここに乗る（テクスチャ担当）。
    box(-0.236 * hw, 0.236 * hw, y0 - 0.030 * hh, y0 + 0.170 * hh,
        -0.543 * hd, -0.413 * hd, "skin", uv_scale=12)
    return out


def helmet(rig: HumanRig) -> None:
    """ガンメタルの兜。ドーム / 頬当て / 襟 / 跳ね上がる二枚のフィン。"""
    L = rig.L
    head = rig.b("head")

    # 顔の板 cube は置かない。rig.flesh() の head cube 一枚に統一し、
    # そこへ texel を集中させる（22x26 → 39x53）。目は少し下げ、幅と間隔を
    # 兜の開口 x±1.05 に収まる値で渡す。ここを渡さないと目が頬当てに切られる。
    face = head.cubes[0]
    _rescale(face, 12)
    # 頭蓋そのものを一回り絞る。ドームは「頭の箱より必ず外側」でないと
    # 一枚も描画されないので、頭が大きいままだと兜の天頂を細らせられず、
    # バケツのような寸胴になる。顔は絞った前面へそのまま乗る。
    face.origin[0] = round(-L.head_w * 0.450, 3)
    face.size[0] = round(L.head_w * 0.900, 3)
    face.origin[2] = round(-L.head_d * 0.495, 3)
    face.size[2] = round(L.head_d * 0.950, 3)
    face.decals["north"] = {"name": "face", "eye_v": 0.62, "eye_w": 0.19,
                            "eye_h": 0.135, "eye_gap": 0.075, "brow_tilt": 1}
    # 耳 cube は頬当てとドームに完全に埋没して一枚も描画されない。落とす。
    del head.cubes[1:]

    for cube in _helm_cubes(L.head_w, L.head_h, L.head_d, L.chin):
        head.add(cube)

    # 白髪は cube では出さない。襟・後頭部・頬当てで頭部が完全に囲われるので、
    # どこへ置いても一枚も描画されない（試して確認済み）。
    # 白髪まじりと無精髭は `face` デカール側の仕事。

    # 兜の天頂 = オーラや磁力線の発生点
    _loc(head, "helm", (0, L.chin + L.head_h * 1.02, -L.head_d * 0.05))


# ===========================================================================
#  マント
# ===========================================================================
#  段数 6。0 段目を **肩幅より狭く** 始め、裾へ向かって緩く開く台形にする。
#  旧実装は 0 段目から肩幅 1.10 倍の長方形で、正面から胴が完全に隠れて
#  「赤い壁」になっていた（docs/REVIEW_BASELINE.md）。
#
#  幅倍率は DIRECTION §3-4 の 0.86〜1.66 ではなく 0.76〜1.28 に落とした。
#  裾 1.28（＝11.0）はパウルドロン幅 11.2 のすぐ内側。1.66（＝14.3）だと
#  布が肩より大きくなり、正面でも背面でも
#  布が体より大きくなり、REVIEW_BASELINE が指摘した「赤い壁」が戻る。
#  読ませたいのは「肩より狭く始まって裾で開く」という台形の輪郭なので、
#  絶対値ではなく **肩幅との大小関係** を守る側を採った。
#  静止角も同様に累積 4〜9°（§3-4 は 6/9/12）。段が 6 段に増えた分、
#  同じ累積角でも裾の後退量が倍になるため。
#
#  裾 3 段は cape<i>L / cape<i>R に割って左右を逆位相で振れるようにする。
#  親の cape3..5 は空ボーンとして残すので、
#  「cape3 を動かす」既存アニメも「cape3L だけ動かす」新アニメも通る。
CAPE_WIDTH = (0.76, 0.84, 0.94, 1.06, 1.18, 1.28)
CAPE_REST = (4, 1, 1, 1, 1, 1)          # 段ごとの追加角。累積 4/5/6/7/8/9°
CAPE_SPLIT = 3                          # ここから下は左右に割る


def cape(rig: HumanRig, segments: int = 6) -> None:
    """関節を持つマント。段ごとにボーンを切ってあるので、風になびかせられる。"""
    L = rig.L
    total = L.total * 0.78                # 足首（y=2.05）まで届かせる
    seg = total / segments
    y_top = L.chest_top + L.total * 0.010
    z_face = L.chest_d * 0.517            # 胸の背面 (0.5) をわずかに逃がす
    piv_z = L.chest_d * 0.550             # 背中に食い込ませない

    parent = "chest"
    for i in range(segments):
        name = f"cape{i}"
        y = y_top - seg * i
        b = rig.model.bone(name, (0, y, piv_z), parent,
                           rotation=(CAPE_REST[i], 0, 0))
        rig.bones[name] = b
        w = L.shoulder_w * CAPE_WIDTH[i]
        t = L.total * (0.010 + 0.012 * i / (segments - 1))
        if i == segments - 1:
            t = L.total * 0.0165          # 裾だけは薄く絞って翻りを軽くする
        if i < CAPE_SPLIT:
            b.add(Cube((-w / 2, y - seg, z_face), (w, seg, t), "cape",
                       uv_scale=4, decals={"north": "cape_fold",
                                           "south": "cape_fold"}))
        else:
            # 裾: 左右別ボーン。表 (cape) と裏地 (cape_inner) の二枚重ねで、
            # 翻ったときに暗い裏が見えるようにする。
            for side, sgn in (("L", 1), ("R", -1)):
                # 裾の左右を縦軸まわりに前へ巻き込む。板を並べただけだと
                # 背中に立てた一枚の看板にしか見えない。
                fan = -(7 + 5 * (i - CAPE_SPLIT)) * sgn
                sub = rig.model.bone(f"{name}{side}", (0, y, piv_z), name,
                                     rotation=(0, fan, 0))
                rig.bones[f"{name}{side}"] = sub
                ox = 0 if sgn > 0 else -w / 2
                sub.add(Cube((ox, y - seg, z_face + t * 0.45),
                             (w / 2, seg, t * 0.55), "cape", uv_scale=4,
                             decals={"south": "cape_fold"}))
                sub.add(Cube((ox + 0.10, y - seg, z_face),
                             (w / 2 - 0.20, seg, t * 0.45), "cape_inner",
                             uv_scale=4, decals={"north": "cape_fold"}))
        parent = name

    _loc(rig.b(f"cape{segments - 1}L"), "capeTip",
         (L.shoulder_w * 0.35, y_top - total, z_face))

    # --- 立ち襟 ----------------------------------------------------------
    # 首の後ろに立ち上がる襟。これが無いとただの布になる。
    chest = rig.b("chest")
    col = Cube((-L.head_w * 0.62, L.chest_top - L.total * 0.020,
                L.chest_d * 0.50),
               (L.head_w * 1.24, L.total * 0.108, L.chest_d * 0.24), "cape",
               uv_scale=6, decals={"south": "cape_fold"},
               rotation=(-16, 0, 0))
    col.pivot = [0, L.chest_top - L.total * 0.020, L.chest_d * 0.52]
    chest.add(col)
    for sgn in (-1, 1):                   # 襟の左右の羽。外へ開いて三角を作る
        ox, sx = _span(L.head_w * 0.50 * sgn, L.head_w * 0.96 * sgn)
        w = Cube((ox, L.chest_top - L.total * 0.014, L.chest_d * 0.42),
                 (sx, L.total * 0.086, L.chest_d * 0.22), "cape_inner",
                 uv_scale=6, rotation=(-14, 0, 24 * sgn))
        w.pivot = [L.head_w * 0.50 * sgn, L.chest_top - L.total * 0.014,
                   L.chest_d * 0.50]
        chest.add(w)

    # --- 留め具 ----------------------------------------------------------
    # 旧実装は z=-0.669（胴の内側）にデカール面を置いていて一度も見えなかった。
    # 前の留め具と背中のヨークに分けて、両方とも表面へ出す。
    chest.add(Cube((-L.shoulder_w * 0.22, L.chest_top - L.total * 0.048,
                    -L.chest_d * 0.72),
                   (L.shoulder_w * 0.44, L.total * 0.040, L.chest_d * 0.13),
                   "helm", uv_scale=8, decals={"north": "cape_clasp"}))
    chest.add(Cube((-L.shoulder_w * 0.36, L.chest_top - L.total * 0.052,
                    L.chest_d * 0.44),
                   (L.shoulder_w * 0.72, L.total * 0.044, L.chest_d * 0.16),
                   "helm", uv_scale=6, decals={"up": "panel_seam"}))


# ===========================================================================
#  装甲
# ===========================================================================
def armour(rig: HumanRig) -> None:
    """深紫の装甲板・帯・深紅のブーツと手甲。狙いは逆三角形。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    chest = rig.b("chest")
    body = rig.b("body")

    # 素体側の腰を絞る。ここを細くしないとパウルドロンを広げても
    # 逆三角に見えない（肩:腰 = 2.5:1 が読みの下限）。
    waist = body.cubes[1]
    waist.origin[0] = round(-L.waist_w * 0.450, 3)
    waist.size[0] = round(L.waist_w * 0.900, 3)
    # 胸の underlay は装甲の下に完全に隠れる。cube ごと落とす。
    chest.cubes = [c for c in chest.cubes if c.style != rig.s["underlay"]]

    # --- 胸当て（磁力紋章つき）-------------------------------------------
    chest.add(Cube((-L.chest_w * 0.62, L.chest_bot + ch * 0.02,
                    -L.chest_d * 0.68),
                   (L.chest_w * 1.24, ch * 0.94, L.chest_d * 0.36), "plate",
                   uv_scale=10, decals={"north": "mag_sigil"}))
    # 胸から肩へ斜めに渡す楔。**この斜線が「肩が広い」の実体**で、
    # 箱を横に伸ばすより効く。
    for sgn in (-1, 1):
        ox, sx = _span(L.chest_w * 0.42 * sgn, L.shoulder_w * 0.52 * sgn)
        w = Cube((ox, L.chest_top - ch * 0.40, -L.chest_d * 0.56),
                 (sx, ch * 0.26, L.chest_d * 1.02), "plate", uv_scale=6,
                 decals={"up": "panel_seam"}, rotation=(0, 0, 22 * sgn))
        w.pivot = [L.chest_w * 0.42 * sgn, L.chest_top - ch * 0.27, 0]
        chest.add(w)
    _loc(chest, "chest", (0, L.chest_bot + ch * 0.55, -L.chest_d * 0.80))

    # --- 腹・腰 ----------------------------------------------------------
    body.add(Cube((-L.waist_w * 0.46, L.abdomen_bot, -L.waist_d * 0.51),
                  (L.waist_w * 0.92, L.chest_bot - L.abdomen_bot,
                   L.waist_d * 1.02), "plate_dark", uv_scale=5))
    body.add(Cube((-L.hip_w * 0.51, L.pelvis_bot + L.total * 0.004,
                   -L.waist_d * 0.53),
                  (L.hip_w * 1.02, L.abdomen_bot - L.pelvis_bot - L.total * 0.010,
                   L.waist_d * 1.06), "plate_dark", uv_scale=5))
    # ベルトは広く薄く。腰の細さは「上下を薄く見せる」ことで出す。
    body.add(Cube((-L.hip_w * 0.60, L.abdomen_bot - L.total * 0.012,
                   -L.waist_d * 0.64),
                  (L.hip_w * 1.20, L.total * 0.034, L.waist_d * 1.28), "belt",
                  uv_scale=10, decals={"north": "mag_core"}))
    tongue = Cube((-L.hip_w * 0.15, L.abdomen_bot - L.total * 0.052,
                   -L.waist_d * 0.66),
                  (L.hip_w * 0.30, L.total * 0.044, L.waist_d * 0.14), "belt",
                  uv_scale=8, decals={"north": "rivets"}, rotation=(-6, 0, 0))
    tongue.pivot = [0, L.abdomen_bot - L.total * 0.012, -L.waist_d * 0.60]
    body.add(tongue)

    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        lx = sgn * L.stance
        out = 0.34 * sgn                  # パウルドロンを外へ逃がす量

        # --- パウルドロン（3 枚）-----------------------------------------
        # 胴と一体に見えないよう、上帽・本体・下リップで段差を作る。
        # 段差だけでは同じ紫のまま繋がって見えたので、上帽だけ `belt`
        # （鋼）にして色でも切っている。ここが肩幅を「読ませて」いる。
        sh = rig.b(f"{side}Shoulder")
        sh.add(Cube((cx + out - L.arm_t * 1.10, L.shoulder_y - L.arm_t * 1.02,
                     -L.arm_t * 0.92),
                    (L.arm_t * 2.14, L.arm_t * 1.20, L.arm_t * 1.88), "plate",
                    uv_scale=6, decals={"up": "panel_seam",
                                        "east" if sgn > 0 else "west": "rivets"}))
        cap = Cube((cx + out - L.arm_t * 0.92, L.shoulder_y + L.arm_t * 0.08,
                    -L.arm_t * 0.80),
                   (L.arm_t * 1.90, L.arm_t * 0.42, L.arm_t * 1.66), "belt",
                   uv_scale=6, decals={"up": "rivets"}, rotation=(0, 0, -16 * sgn))
        cap.pivot = [cx + out, L.shoulder_y, 0]
        sh.add(cap)
        lip = Cube((cx + out - L.arm_t * 1.12, L.shoulder_y - L.arm_t * 1.44,
                    -L.arm_t * 0.86),
                   (L.arm_t * 2.24, L.arm_t * 0.42, L.arm_t * 1.72),
                   "plate_dark", uv_scale=6, rotation=(0, 0, -10 * sgn))
        lip.pivot = [cx + out, L.shoulder_y - L.arm_t * 1.20, 0]
        sh.add(lip)

        # --- 手甲（磁力コア）--------------------------------------------
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.76, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.02,
             -L.forearm_t * 0.76),
            (L.forearm_t * 1.52, (L.elbow_y - L.wrist_y) * 0.68,
             L.forearm_t * 1.52), "glove", uv_scale=10,
            decals={"north": "mag_core"}))
        # --- 手袋 --------------------------------------------------------
        hand = rig.b(f"{side}Hand")
        hand.add(Cube((cx - L.forearm_t * 0.60, L.wrist_y - L.hand_l * 1.08,
                       -L.forearm_t * 0.50),
                      (L.forearm_t * 1.20, L.hand_l * 1.10, L.forearm_t * 1.02),
                      "glove", uv_scale=6))
        _loc(hand, f"{side}Hand",
             (cx, L.wrist_y - L.hand_l * 1.30, -L.forearm_t * 1.05))

        # --- ブーツ（膝カフ 3.48 → 足首 2.53 のテーパー）------------------
        shin = rig.b(f"{side}Shin")
        knee = (L.knee_y - L.ankle_y)
        shin.add(Cube((lx - L.shin_t * 0.81, L.knee_y - knee * 0.16,
                       -L.shin_t * 0.86),
                      (L.shin_t * 1.62, knee * 0.26, L.shin_t * 1.54), "boot",
                      uv_scale=6, decals={"north": "panel_seam"}))
        shin.add(Cube((lx - L.shin_t * 0.589, L.ankle_y,
                       -L.shin_t * 0.66),
                      (L.shin_t * 1.178, knee * 0.86, L.shin_t * 1.20), "boot",
                      uv_scale=6))
        rig.b(f"{side}Foot").add(Cube(
            (lx - L.shin_t * 0.62, 0, -L.foot_l * 0.70),
            (L.shin_t * 1.24, L.foot_h * 1.10, L.foot_l * 0.72), "boot",
            uv_scale=6))

    _loc(body, "feet", (0, L.total * 0.010, 0))


def build_magneto() -> Model:
    c = K.CHARACTERS[K.MAGNETO]
    m = Model(K.geo(K.MAGNETO), uv_scale=5, visible_bounds=(3.8, 4.4),
              vb_offset=(0, 1.4, 0), max_atlas=(512, 512))
    rig = HumanRig(m, Build(c["cm"], c["heads"], c["sh"], c["limb"],
                            female=c["female"], bulk=c["bulk"]),
                   player_rig=True)
    rig.flesh(hands_bare=False)
    # 素体は全部 5。顔だけ helmet() が 12 まで上げる。
    for bone in m.bones:
        for cube in bone.cubes:
            _rescale(cube, 5)
    armour(rig)
    cape(rig)
    helmet(rig)
    return m


# ===========================================================================
#  一人称の手元
# ===========================================================================
def build_fp_hand() -> Model:
    """技アイテムを持つと一人称で見える磁力ガントレット。

    ボーン構成は「手 → 甲 → 磁界リング → 浮遊する鉄片」。
    リングと鉄片が別ボーンなので、技ごとに違う動きをさせられる。

    寸法は「画面の隅に収まること」を最優先にした。旧実装は鉄片が
    半径 9.6 まで飛び出していて、一人称で視界の 1/3 を潰していた。
    ここでは全体を原点から半径 4 以内に畳み、**手前に伸ばす方向**
    （-z）だけへ長く取っている。視界を潰すのは横幅であって奥行きではない。
    """
    m = Model(K.geo("fp_hand"), uv_scale=8, visible_bounds=(1.2, 1.2),
              vb_offset=(0, 0, -0.2), max_atlas=(512, 512))
    root = m.bone("root", (0, 0, 0))
    hand = m.bone("hand", (0, 0, 0), "root")
    # 掌。指は下ではなく **前** へ向ける。一人称では前へ伸びた手でないと
    # 「掴んでいる」に見えない。
    hand.add(Cube((-1.9, -1.9, -1.7), (3.8, 4.0, 3.4), "glove", uv_scale=8))
    for i in range(3):
        u = (i - 1) * 1.24
        f = m.bone(f"finger{i}", (u, 0.4, -1.7), "hand", rotation=(-8, 0, 0))
        f.add(Cube((u - 0.56, -0.35, -4.0), (1.12, 1.3, 2.4), "glove",
                   uv_scale=8))
    thumb = m.bone("thumb", (1.7, -0.6, -1.2), "hand", rotation=(0, 22, -30))
    thumb.add(Cube((1.2, -1.2, -3.1), (1.0, 1.2, 2.0), "glove", uv_scale=8))
    # 甲（手首側のカフ）。磁力コアはここで光らせる
    gaunt = m.bone("gauntlet", (0, 0, 1.4), "hand")
    gaunt.add(Cube((-2.3, -2.3, 1.4), (4.6, 4.6, 2.6), "helm", uv_scale=8,
                   decals={"up": "mag_core", "east": "panel_seam",
                           "west": "panel_seam"}))
    gaunt.add(Cube((-2.6, -2.6, 3.9), (5.2, 5.2, 0.7), "belt", uv_scale=8,
                   decals={"up": "rivets"}))

    # 指先の先に浮く磁界リング。待機 55°/s → 溜め 900°/s → 撃発で急停止。
    # 八角にしてあるのは、六角だと回転が「カクついて」見えるため。
    field = m.bone("field", (0, 0.3, -5.6), "root")
    for i in range(8):
        a = i * math.pi / 4
        c = Cube((2.7 * math.cos(a) - 0.86, 0.3 + 2.7 * math.sin(a) - 0.30,
                  -5.9), (1.72, 0.60, 0.60), "magnet", uv_scale=8,
                 rotation=(0, 0, math.degrees(a) + 90))
        c.pivot = [2.7 * math.cos(a), 0.3 + 2.7 * math.sin(a), -5.6]
        field.add(c)
    core = m.bone("core", (0, 0.3, -5.6), "field")
    core.add(Cube((-1.05, -0.75, -6.1), (2.1, 2.1, 0.9), "magnet", uv_scale=10,
                  decals={"north": "mag_sigil"}))
    # 周囲を回る鉄片。位相は 0/104/248 に崩してある（担当 5 の指定）。
    for i, phase in enumerate((0, 104, 248)):
        b = m.bone(f"shard{i}", (0, 0.3, -5.6), "field",
                   rotation=(0, 0, phase))
        b.add(Cube((3.5, -0.05, -5.95), (1.7, 0.62, 0.62), "shard",
                   uv_scale=10))
    _loc(root, "muzzle", (0, 0.3, -6.4))
    _loc(root, "palm", (0, -0.4, -2.6))
    root.add(Cube((-0.01, -0.01, -0.01), (0.02, 0.02, 0.02), "magnet",
                  uv_scale=1))
    m.pack()
    return m


def build_helmet_prop() -> Model:
    """手に持ったとき / 頭に装備したときに見える兜そのもの。

    変身アイテムが紫の玉に見えていては話にならないので、
    兜のシルエットを単体のジオメトリとして持たせる。
    形は `helmet()` と **同じ関数** から起こしているので、
    本体の兜を直せばこちらも自動で追従する。
    """
    m = Model(K.geo("helmet_prop"), uv_scale=6, visible_bounds=(1.6, 1.6),
              vb_offset=(0, 0.2, 0), max_atlas=(512, 512))
    root = m.bone("root", (0, 0, 0))
    # 手持ちの小道具なので原点まわりに畳む。比率は頭と同じ。
    hw, hh, hd = 4.90, 5.98, 5.26
    for cube in _helm_cubes(hw, hh, hd, -hh * 0.62):
        if cube.style == "skin":
            continue                      # 中身（顎）は要らない
        root.add(cube)
    m.pack()
    return m


def build_tech_orb() -> Model:
    """技アイテムを持っている時に三人称で手元に浮く磁力球。

    立方体一個だと「紫の箱」にしかならないので、
    芯 / 赤道の鋼帯 / 周回する鉄片 の三層に分けてある。
    ``core`` と ``ring`` のボーン名はアニメ側が回している。
    """
    m = Model(K.geo("tech_orb"), uv_scale=6, visible_bounds=(0.8, 0.8),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    core = m.bone("core", (0, 0, 0))
    # 紋章は帯に切られない上下面へ。正面は磁力線で「流れている」ことを見せる
    core.add(Cube((-1.15, -1.15, -1.15), (2.3, 2.3, 2.3), "magnet", uv_scale=8,
                  decals={"north": "mag_lines", "south": "mag_lines",
                          "up": "mag_sigil", "down": "mag_sigil"}))
    # 赤道の鋼帯。紫の発光だけだと質量が乗らない
    core.add(Cube((-1.42, -0.22, -1.42), (2.84, 0.44, 2.84), "belt", uv_scale=6,
                  decals={"north": "panel_seam", "south": "panel_seam"}))
    # 上下の極。子午線の帯を回すと胸の紋章を隠すので、極だけを立てる
    for sgn in (-1, 1):
        core.add(Cube((-0.62, 1.15 if sgn > 0 else -1.55, -0.62),
                      (1.24, 0.40, 1.24), "belt", uv_scale=6,
                      decals={"up": "rivets"}))
    ring = m.bone("ring", (0, 0, 0), "core")
    for i in range(6):
        a = i * math.pi / 3
        c = Cube((2.9 * math.cos(a) - 0.62, 2.9 * math.sin(a) - 0.28, -0.28),
                 (1.24, 0.56, 0.56), "shard", uv_scale=6,
                 rotation=(0, 0, math.degrees(a) + 90))
        c.pivot = [2.9 * math.cos(a), 2.9 * math.sin(a), 0]
        ring.add(c)
    m.pack()
    return m


def main() -> None:
    print("magneto:")
    emit(build_magneto(), colours.MAGNETO, K.MAGNETO, seed=101)
    emit(build_fp_hand(), colours.MAGNETO, "fp_hand", seed=102)
    emit(build_tech_orb(), colours.MAGNETO, "tech_orb", seed=103)
    emit(build_helmet_prop(), colours.MAGNETO, "helmet_prop", seed=104)


if __name__ == "__main__":
    main()
