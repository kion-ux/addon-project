# -*- coding: utf-8 -*-
"""ブラザーフッド9人のモデル。

体格は contract.CHARACTERS の cm / heads / sh / limb / bulk から導く。
同じ ``HumanRig`` を使いつつ、キャラごとの装飾を ``DRESS`` の関数で足す。

9人が並んだとき **遠景のシルエットだけで誰か判る** ことを、このファイルの
最優先事項に置いている。体格の数値だけでは「同じ人形の色違い」にしかならないので、
一人につき「その人にしか無い外形」をひとつ決め、cube をそこへ集中させた。

    ミスティーク    鱗の隆起と、後ろへ広がる赤い髪
    セイバートゥース 肩から胸を覆う鬣、前傾した胸、伸びた爪
    トード          猫背・膝まで届く腕・膨れた喉袋・大きな脚
    ジャガーノート  顔を完全に覆うドーム兜と、頭を小さく見せる肩幅
    クイックシルバー 前へ流れた髪と、後ろへ流れる衣装
    パイロ          背中の燃料タンクと腕の噴射装置
    アバランチ      面を覆うゴーグルと厚い前腕アーマー
    ブロブ          全てを飲み込む腹
    スカーレット・ウィッチ 二本角の頭飾りと短いマント

回転を惜しまないこと。箱を積むだけでは 40 ブロック先で全員同じ長方形になる。
"""
from __future__ import annotations

import _path  # noqa: F401

import colours  # noqa: E402
import contract as K  # noqa: E402
from common import emit  # noqa: E402
from mcmodel import Cube, Model  # noqa: E402
from rig import Build, HumanRig  # noqa: E402


# ---------------------------------------------------------------- 体格の補正
# contract.py は正典なので触らない。``Build`` が持っていて contract が
# 渡していない自由度（腕の長さ・脚の比率）だけを、ここで補う。
SHAPE = {
    # 膝まで垂れる腕。トードの「異様に長い腕」の実体はこれ一行
    "toad": dict(arm_len=1.34),
    # 獣は腕が長い。爪の位置が下がるほど前傾して見える
    "sabretooth": dict(arm_len=1.12),
    # 脚を短く、胴を長く。腹を置く縦の場所を稼ぐため
    "blob": dict(leg_ratio=0.455),
    # 逆に脚を長く取る。細く長い脚が速さの記号になる
    "quicksilver": dict(leg_ratio=0.545),
}

# 巨体は cube 一つが大きいので、そのままの密度ではアトラスに入らない。
# 遠くから見る相手なので密度を落として構わない（DIRECTION §3-6 の考え方）。
UV_SCALE = {"juggernaut": 2, "blob": 2}


# ---------------------------------------------------------------- 髪型
# 顔の輪郭ではなく **頭のシルエット** を分ける。9人の髪が似ていると、
# 兜組以外の6人が遠景で全部同じ頭になる。
HAIR = {
    # ミスティーク: 後頭部で大きく膨らみ、肩まで落ちる赤い塊
    "mystique": [((-0.56, 0.58, -0.50), (1.12, 0.50, 1.06)),
                 ((-0.58, 0.16, 0.30), (1.16, 0.58, 0.46)),
                 ((-0.60, 0.40, -0.46), (0.16, 0.50, 0.92)),
                 ((0.44, 0.40, -0.46), (0.16, 0.50, 0.92))],
    # セイバートゥース: 頭は低く抑える。高さを出すのは胸の鬣の役目で、
    # 髪まで盛ると頭と鬣が一つの塊になって顔が消える
    "sabretooth": [((-0.60, 0.62, -0.54), (1.20, 0.40, 1.16)),
                   ((-0.62, 0.14, 0.30), (1.24, 0.62, 0.40)),
                   ((-0.64, 0.30, -0.50), (0.22, 0.44, 1.10)),
                   ((0.42, 0.30, -0.50), (0.22, 0.44, 1.10))],
    # トード: 脂ぎった薄い数房。頭頂が平らで、後ろに数本だけ垂れる
    "toad": [((-0.50, 0.66, -0.44), (1.00, 0.24, 0.92)),
             ((-0.46, 0.34, 0.34), (0.34, 0.44, 0.22)),
             ((0.10, 0.44, 0.34), (0.30, 0.34, 0.22))],
    # クイックシルバー: 地の髪は後頭部を刈り上げて短く。
    # 前へ流れる庇は角度が要るので dress 側で回転付きの cube にする
    "quicksilver": [((-0.52, 0.62, -0.40), (1.04, 0.44, 0.86)),
                    ((-0.50, 0.50, 0.30), (1.00, 0.34, 0.16))],
    # パイロ: 額を出したオールバック。襟足だけ長い
    "pyro": [((-0.52, 0.70, -0.46), (1.04, 0.34, 1.00)),
             ((-0.52, 0.34, 0.36), (1.04, 0.42, 0.22)),
             ((-0.54, 0.64, -0.54), (1.08, 0.20, 0.12))],
    # アバランチ: 短く刈った剛毛と、太いもみあげ
    "avalanche": [((-0.52, 0.68, -0.50), (1.04, 0.34, 1.04)),
                  ((-0.52, 0.40, 0.38), (1.04, 0.32, 0.18)),
                  ((-0.56, 0.30, -0.30), (0.14, 0.42, 0.66)),
                  ((0.42, 0.30, -0.30), (0.14, 0.42, 0.66))],
    # ブロブ: ほとんど無い。頭頂に薄い一枚だけ
    "blob": [((-0.44, 0.72, -0.36), (0.88, 0.20, 0.76))],
    # スカーレット・ウィッチ: 頭飾りの下から肩へ落ちる長い髪
    "scarlet_witch": [((-0.54, 0.58, -0.52), (1.08, 0.46, 1.08)),
                      ((-0.58, -0.34, 0.26), (1.16, 1.00, 0.44)),
                      ((-0.60, -0.10, -0.48), (0.18, 0.82, 0.98)),
                      ((0.42, -0.10, -0.48), (0.18, 0.82, 0.98))],
    # ジャガーノートは兜の中なので髪を持たない
}


# ---------------------------------------------------------------- 共通の下ごしらえ
def _locators(bone, spots):
    """``mcmodel.Bone`` にまだ locators フィールドが無いので、書き出し時に差し込む。

    担当7の ally 技 VFX は locator が無いと全部足元（原点）に湧く。
    担当1が Bone 本体へ locators を入れたら、この包みは消してよい。
    """
    plain = bone.to_json

    def to_json():
        doc = plain()
        doc["locators"] = {name: [round(float(v), 3) for v in pos]
                           for name, pos in spots.items()}
        return doc

    bone.to_json = to_json


def _trim(rig, limb_style):
    """flesh() が置く「見えない cube」と「真っ黒な下敷き」を片づける。

    耳は髪に、胸の underlay は衣装に完全に埋もれて一度も画面に出ない。
    前腕と脛の underlay(#0B0D12) は見えるが、**9人が揃って手足だけ黒くなる**
    原因がこれなので、キャラの色へ差し替える。
    """
    del rig.b("head").cubes[1:]                     # 耳
    for bone in rig.model.bones:
        for cube in list(bone.cubes):
            if cube.style != "underlay":
                continue
            if bone.name == "chest":
                bone.cubes.remove(cube)             # 服の内側。永久に見えない
            else:
                cube.style = limb_style


def _face(rig, decal="face", uv=8):
    """顔の cube を貼り直す。flesh() 固定の uv_scale=6 では目が 2 テクセルになる。"""
    L = rig.L
    head = rig.b("head")
    head.cubes[0] = Cube((-L.head_w / 2, L.chin, -L.head_d * 0.52),
                         (L.head_w, L.head_h, L.head_d), head.cubes[0].style,
                         uv_scale=uv, decals={"north": decal})


def _restyle(rig, bones, style):
    """既に置かれた cube の色だけ差し替える（手袋・袖のように形が同じもの）。"""
    for name in bones:
        for cube in rig.b(name).cubes:
            cube.style = style


def _bodysuit(rig, style="suit", chest_decal=None, uv=4, top=0.94, hem=0.02):
    L = rig.L
    ch = L.chest_top - L.chest_bot
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.55, L.chest_bot + ch * hem, -L.chest_d * 0.60),
        (L.chest_w * 1.10, ch * top, L.chest_d * 1.20), style, uv_scale=uv,
        decals={"north": chest_decal} if chest_decal else None))


def _belt(rig, style="belt", mark="brotherhood_mark", uv=5):
    L = rig.L
    rig.b("body").add(Cube(
        (-L.hip_w * 0.60, L.abdomen_bot - L.total * 0.018, -L.waist_d * 0.64),
        (L.hip_w * 1.20, L.total * 0.038, L.waist_d * 1.28), style, uv_scale=uv,
        decals={"north": mark} if mark else None))


def _boots(rig, style="boot", top=0.68, uv=4, cuff=0.0):
    """脛を包む筒と足。cuff>0 で膝の折り返しが付き、脚が太く見える。"""
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        lx = sgn * L.stance
        shin = rig.b(f"{side}Shin")
        shin.add(Cube((lx - L.shin_t * 0.70, L.ankle_y, -L.shin_t * 0.76),
                      (L.shin_t * 1.40, (L.knee_y - L.ankle_y) * top,
                       L.shin_t * 1.32), style, uv_scale=uv))
        if cuff:
            h = (L.knee_y - L.ankle_y) * 0.16
            shin.add(Cube(
                (lx - L.shin_t * (0.70 + cuff), L.ankle_y +
                 (L.knee_y - L.ankle_y) * top - h, -L.shin_t * (0.76 + cuff)),
                (L.shin_t * (1.40 + cuff * 2), h, L.shin_t * (1.32 + cuff * 2)),
                style, uv_scale=uv))
        rig.b(f"{side}Foot").add(Cube(
            (lx - L.shin_t * 0.68, 0, -L.foot_l * 0.66),
            (L.shin_t * 1.36, L.foot_h * 1.18, L.foot_l * 0.66), style,
            uv_scale=uv))


def _pauldrons(rig, style, span=1.6, drop=1.2, tilt=16, decal=None, uv=4,
               lip=0.0, out=1.0):
    """肩の張り出し。Z 回転で外側の縁を落とすと、初めて「肩」に見える。

    span は arm_t 倍の幅。tilt を 0 にすると、ただの箱に戻ってしまう。
    out は肩の中心を外へずらす倍率。大きい肩当ては外へ逃がさないと胸を覆う。
    """
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2) * out
        bone = rig.b(f"{side}Shoulder")
        bone.add(Cube(
            (cx - L.arm_t * span * 0.5, L.shoulder_y - L.arm_t * drop * 0.72,
             -L.arm_t * span * 0.48),
            (L.arm_t * span, L.arm_t * drop, L.arm_t * span * 0.96), style,
            uv_scale=uv, rotation=(0, 0, -tilt * sgn),
            decals={"up": decal} if decal else None))
        if lip:
            bone.add(Cube(
                (cx - L.arm_t * span * 0.46, L.shoulder_y - L.arm_t * (drop + lip),
                 -L.arm_t * span * 0.42),
                (L.arm_t * span * 0.92, L.arm_t * lip, L.arm_t * span * 0.84),
                style, uv_scale=uv, rotation=(0, 0, -(tilt + 10) * sgn)))


def _wedges(rig, style, angle=22, uv=4):
    """胸から肩へ斜めに架ける楔。この斜線が「肩が広い」の実体（DIRECTION §3-5）。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    for sgn in (-1, 1):
        w = (L.shoulder_w - L.chest_w) * 0.52
        x = sgn * L.chest_w * 0.48 if sgn > 0 else -L.chest_w * 0.48 - w
        rig.b("chest").add(Cube(
            (x, L.chest_top - ch * 0.34, -L.chest_d * 0.44),
            (w, ch * 0.34, L.chest_d * 0.88), style, uv_scale=uv,
            rotation=(0, 0, -angle * sgn)))


def _claws(rig, style="claw", count=3, length=1.5, uv=5):
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        hand = rig.b(f"{side}Hand")
        for i in range(count):
            u = (i - (count - 1) / 2) * 0.36
            t = L.forearm_t * 0.20
            hand.add(Cube(
                (cx + u * L.forearm_t - t / 2, L.wrist_y - L.hand_l * (1 + length),
                 -L.forearm_t * 0.30),
                (t, L.hand_l * length, t * 1.3), style, uv_scale=uv,
                rotation=(18 + 6 * i, 0, 0)))


# ---------------------------------------------------------------- 9人の衣装
def dress_mystique(rig):
    """鱗の隆起。服を着せるほど青が沈むので、素肌の上に鱗板だけを重ねる。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    chest = rig.b("chest")
    # 背骨に沿って 3 枚。上ほど大きく、上ほど後ろへ倒す
    for i in range(3):
        w = L.chest_w * (0.66 - 0.13 * i)
        y = L.chest_bot + ch * (0.18 + 0.27 * i)
        chest.add(Cube((-w / 2, y, L.chest_d * 0.34),
                       (w, ch * 0.22, L.chest_d * 0.26), "scale", uv_scale=5,
                       rotation=(-20 + 8 * i, 0, 0),
                       decals={"south": "scales", "up": "scales"}))
    # 胸のヨーク。板を大きくすると看板になるので、鎖骨の幅だけに絞る
    chest.add(Cube((-L.chest_w * 0.34, L.chest_top - ch * 0.30, -L.chest_d * 0.62),
                   (L.chest_w * 0.68, ch * 0.30, L.chest_d * 0.28), "armor",
                   uv_scale=7, decals={"north": "brotherhood_mark"}))
    # 肩より高く出る背びれ 2 本。輪郭の頂点を肩の外に作らないと、
    # 何を足しても「肩幅のある長方形」から抜けられない
    for sgn in (-1, 1):
        chest.add(Cube((sgn * L.chest_w * 0.10 - (L.chest_w * 0.20 if sgn < 0 else 0),
                        L.chest_top - ch * 0.10, L.chest_d * 0.10),
                       (L.chest_w * 0.20, ch * 0.52, L.chest_d * 0.30), "scale",
                       uv_scale=5, rotation=(-30, 0, -18 * sgn)))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        # 肩の鱗冠。外へ 42 度倒して、遠景の輪郭にギザギザを作る
        for i, (h_f, rot, dz) in enumerate(((1.95, 42, 1.20), (1.25, 26, 0.70))):
            rig.b(f"{side}Shoulder").add(Cube(
                (cx - L.arm_t * 0.18, L.shoulder_y - L.arm_t * 0.30,
                 -L.arm_t * (0.62 - 0.72 * i)),
                (L.arm_t * 0.34, L.arm_t * h_f, L.arm_t * dz), "scale",
                uv_scale=5, rotation=(0, 0, -rot * sgn),
                decals={"east": "scales", "west": "scales"}))
        # 前腕と脛の鰭
        rig.b(f"{side}Forearm").add(Cube(
            (cx + sgn * L.forearm_t * 0.40, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.10,
             -L.forearm_t * 0.34),
            (L.forearm_t * 0.28, (L.elbow_y - L.wrist_y) * 0.76, L.forearm_t * 0.68),
            "scale", uv_scale=5, rotation=(0, 0, -14 * sgn)))
        rig.b(f"{side}Shin").add(Cube(
            (sgn * L.stance + sgn * L.shin_t * 0.44,
             L.ankle_y + (L.knee_y - L.ankle_y) * 0.18, -L.shin_t * 0.34),
            (L.shin_t * 0.26, (L.knee_y - L.ankle_y) * 0.60, L.shin_t * 0.70),
            "scale", uv_scale=5, rotation=(0, 0, -12 * sgn)))
    _belt(rig, "armor", "brotherhood_mark")
    # 赤い髪の塊。後ろへ 26 度流して、頭より一回り大きい輪郭にする
    hair = rig.b("hair")
    for sgn in (-1, 1):
        hair.add(Cube(((sgn * 0.36 - 0.18) * L.head_w, L.chin - L.head_h * 0.12,
                       L.head_d * 0.18),
                      (L.head_w * 0.36, L.head_h * 0.86, L.head_d * 0.42),
                      "hair", uv_scale=4, rotation=(-26, 0, -10 * sgn)))
    hair.add(Cube((-L.head_w * 0.44, L.chin + L.head_h * 0.86, -L.head_d * 0.10),
                  (L.head_w * 0.88, L.head_h * 0.30, L.head_d * 0.70), "hair",
                  uv_scale=4, rotation=(-24, 0, 0)))


def dress_sabretooth(rig):
    """鬣。肩幅より広い毛の輪で、頭と肩の境目を消して獣に見せる。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    # 胸を 8 度前へ倒す。獣の前傾。腕は root なので付いてこないが、
    # その継ぎ目はこの後の鬣が全部覆う
    rig.b("chest").rotation = [8, 0, 0]
    _bodysuit(rig, "suit", top=0.86)
    _belt(rig, "belt")
    _boots(rig, "cloth", top=0.52)
    _claws(rig, "claw", 3, 1.7)
    chest = rig.b("chest")
    # 鬣の土台。首の後ろで立ち上がり、頭の耳の高さまで来る
    chest.add(Cube((-L.head_w * 0.62, L.chest_top - ch * 0.16, L.chest_d * 0.02),
                   (L.head_w * 1.24, ch * 0.54, L.chest_d * 0.52), "fur",
                   uv_scale=3, rotation=(-16, 0, 0)))
    # 毛束 9 本。長さと角度を不揃いにする。揃えると毛皮ではなく肩当てに見える
    tuft = [(-0.62, 1.00, 0.20, (-4, 0, 52)), (-0.44, 1.34, 0.34, (-12, 0, 36)),
            (-0.24, 1.58, 0.42, (-20, 0, 18)), (0.00, 1.70, 0.44, (-26, 0, 0)),
            (0.24, 1.58, 0.42, (-20, 0, -18)), (0.44, 1.34, 0.34, (-12, 0, -36)),
            (0.62, 1.00, 0.20, (-4, 0, -52)),
            (-0.30, 1.10, -0.52, (26, 0, 14)), (0.30, 1.10, -0.52, (26, 0, -14))]
    for ox, hf, oz, rot in tuft:
        w = L.shoulder_w * 0.15
        chest.add(Cube(
            (ox * L.shoulder_w - w / 2, L.chest_top - ch * 0.24,
             oz * L.chest_d - L.chest_d * 0.22),
            (w, ch * 0.46 * hf, L.chest_d * 0.46), "fur", uv_scale=3,
            rotation=rot))
    # 腰と足首の毛。獣の色を 3 箇所に散らすと、鬣が「肩当て」に見えなくなる
    rig.b("body").add(Cube(
        (-L.hip_w * 0.64, L.abdomen_bot - L.total * 0.010, -L.waist_d * 0.68),
        (L.hip_w * 1.28, L.total * 0.046, L.waist_d * 1.36), "fur", uv_scale=3))
    for side, sgn in (("right", -1), ("left", 1)):
        rig.b(f"{side}Shin").add(Cube(
            (sgn * L.stance - L.shin_t * 0.86, L.ankle_y + L.foot_h * 0.30,
             -L.shin_t * 0.90),
            (L.shin_t * 1.72, (L.knee_y - L.ankle_y) * 0.24, L.shin_t * 1.62),
            "fur", uv_scale=3))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        # 肩の毛束。鬣を肩の先まで伸ばして、肩幅そのものを稼ぐ
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.80, L.shoulder_y - L.arm_t * 0.96, -L.arm_t * 0.78),
            (L.arm_t * 1.60, L.arm_t * 1.20, L.arm_t * 1.56), "fur",
            uv_scale=3, rotation=(0, 0, -22 * sgn)))
        # 手首の毛。爪の付け根が太いと爪が長く見える
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.82, L.wrist_y, -L.forearm_t * 0.82),
            (L.forearm_t * 1.64, L.hand_l * 0.62, L.forearm_t * 1.64), "fur",
            uv_scale=3, rotation=(0, 0, -8 * sgn)))
    _restyle(rig, ("rightHand", "leftHand"), "skin")


def dress_toad(rig):
    """猫背・長い腕・喉袋・大きな脚。四つん這いの一歩手前に見せる。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    _bodysuit(rig, "suit", top=0.62, hem=0.34)         # 腹は素肌のまま残す
    _boots(rig, "cloth", top=0.30)
    chest = rig.b("chest")
    # 背中の瘤。猫背の実体。上端を後ろへ 24 度倒す
    chest.add(Cube((-L.chest_w * 0.52, L.chest_top - ch * 0.62, L.chest_d * 0.18),
                   (L.chest_w * 1.04, ch * 0.66, L.chest_d * 0.62), "skin",
                   uv_scale=4, rotation=(-24, 0, 0),
                   decals={"south": "scales", "up": "scales"}))
    # 喉袋: 2 段。下段が大きく前へ膨らむ
    neck = rig.b("neck")
    neck.add(Cube((-L.head_w * 0.34, L.shoulder_y - L.neck_h * 0.4, -L.head_d * 0.46),
                  (L.head_w * 0.68, L.neck_h * 1.5, L.head_d * 0.34), "skin",
                  uv_scale=5, rotation=(16, 0, 0)))
    chest.add(Cube((-L.head_w * 0.44, L.chest_top - ch * 0.20, -L.chest_d * 0.86),
                   (L.head_w * 0.88, ch * 0.30, L.chest_d * 0.50), "skin",
                   uv_scale=5, rotation=(28, 0, 0), decals={"north": "gills"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        lx = sgn * L.stance
        # 丸めた肩。上腕の付け根を包んで、首を落とし込む
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.74, L.shoulder_y - L.arm_t * 1.10, -L.arm_t * 0.74),
            (L.arm_t * 1.48, L.arm_t * 1.30, L.arm_t * 1.48), "suit",
            uv_scale=4, rotation=(10, 0, -14 * sgn)))
        # 跳ぶための脚。腿と脹脛を大きく張らせる
        rig.b(f"{side}Leg").add(Cube(
            (lx - L.thigh_t * 0.82, L.knee_y + (L.hip_y - L.knee_y) * 0.10,
             -L.thigh_t * 0.72),
            (L.thigh_t * 1.64, (L.hip_y - L.knee_y) * 0.74, L.thigh_t * 1.50),
            "skin", uv_scale=4, rotation=(0, 0, -8 * sgn),
            decals={"west": "scales", "east": "scales"}))
        rig.b(f"{side}Shin").add(Cube(
            (lx - L.shin_t * 0.86, L.ankle_y + (L.knee_y - L.ankle_y) * 0.30,
             -L.shin_t * 0.40),
            (L.shin_t * 1.72, (L.knee_y - L.ankle_y) * 0.56, L.shin_t * 1.10),
            "skin", uv_scale=4, rotation=(-10, 0, 0)))
        # 水掻きの足。指を 3 本広げる
        foot = rig.b(f"{side}Foot")
        foot.add(Cube((lx - L.shin_t * 0.96, 0, -L.foot_l * 0.50),
                      (L.shin_t * 1.92, L.foot_h * 0.90, L.foot_l * 0.62),
                      "skin", uv_scale=4))
        toe = rig.b(f"{side}Toe")
        for i in (-1, 0, 1):
            toe.add(Cube((lx + i * L.shin_t * 0.60 - L.shin_t * 0.28, 0,
                          -L.foot_l * 1.02),
                         (L.shin_t * 0.56, L.foot_h * 0.72, L.foot_l * 0.56),
                         "skin", uv_scale=4, rotation=(0, i * 14, 0)))
        # 長い指
        rig.b(f"{side}Hand").add(Cube(
            (cx - L.forearm_t * 0.54, L.wrist_y - L.hand_l * 2.0, -L.forearm_t * 0.44),
            (L.forearm_t * 1.08, L.hand_l * 1.0, L.forearm_t * 0.86), "skin",
            uv_scale=5, rotation=(20, 0, 0)))
    _belt(rig, "cloth", None)


def dress_juggernaut(rig):
    """ドーム兜と、頭を小さく見せる肩。兜は思い切って大きく丸く。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    h, w, d = L.head_h, L.head_w, L.head_d
    _bodysuit(rig, "plate")                # 布ではなく鈍い金属。ここが赤いと兜が沈む
    _belt(rig, "belt", "buckle")
    _boots(rig, "armor", top=0.80, cuff=0.10)
    head = rig.b("head")
    head.cubes.clear()          # 中身は絶対に見えない。丸ごと兜に置き換える
    # 5 段で丸みを作る。頭幅の 1.8 倍まで膨らませて初めて「ドーム」に見える。
    # 上端は身長ちょうど（chin + head_h）で止め、等身を狂わせない
    for y0, y1, fw, fd, style in (
            (-0.26, 0.06, 1.34, 1.36, "helm_dark"),   # 顎当て（首まで下りる）
            (0.02, 0.30, 1.66, 1.68, "helm"),         # 下ぶくれの段
            (0.26, 0.66, 1.80, 1.80, "helm"),         # 最大径
            (0.62, 0.88, 1.48, 1.50, "helm"),         # 冠
            (0.84, 1.00, 0.96, 0.98, "helm")):        # 天頂
        head.add(Cube((-w * fw / 2, L.chin + h * y0, -d * fd / 2 - d * 0.04),
                      (w * fw, h * (y1 - y0), d * fd), style, uv_scale=3,
                      decals={"up": "rivets"} if y1 > 0.95 else None))
    # 面。目も口も無い一枚板を前へ倒すと、こちらを見ていない威圧が出る
    head.add(Cube((-w * 0.56, L.chin + h * 0.10, -d * 0.96),
                  (w * 1.12, h * 0.46, d * 0.18), "helm_dark", uv_scale=5,
                  rotation=(-10, 0, 0), decals={"north": "panel_seam"}))
    # 眉庇。前へ突き出させて、面に影を落とす
    head.add(Cube((-w * 0.76, L.chin + h * 0.52, -d * 1.02),
                  (w * 1.52, h * 0.16, d * 0.36), "helm", uv_scale=4,
                  rotation=(14, 0, 0)))
    # 首を隠す襟。兜の下端と胸を繋いで、頭を胴に埋める
    rig.b("chest").add(Cube(
        (-w * 0.80, L.chest_top - ch * 0.16, -d * 0.66),
        (w * 1.60, ch * 0.30, d * 1.32), "helm_dark", uv_scale=3))
    # 胸当て。兜と同じ赤を胴の中心にも置いて、色を三段（赤-茶-赤）に散らす
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.56, L.chest_bot + ch * 0.34, -L.chest_d * 0.68),
        (L.chest_w * 1.12, ch * 0.52, L.chest_d * 0.42), "armor", uv_scale=3,
        decals={"north": "rivets"}))
    _wedges(rig, "armor", 24, uv=3)
    # 肩は外へ逃がす。中心のままだと 2.1×arm_t の肩当てが胸を覆って腕が消える
    _pauldrons(rig, "armor", span=1.90, drop=1.10, tilt=20, decal="rivets",
               uv=3, lip=0.46, out=1.16)
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        # 二枚目の肩当て。一枚だと平らな板に見える
        rig.b(f"{side}Shoulder").add(Cube(
            (cx * 1.16 - L.arm_t * 0.72, L.shoulder_y - L.arm_t * 0.26,
             -L.arm_t * 0.70),
            (L.arm_t * 1.44, L.arm_t * 0.78, L.arm_t * 1.40), "armor",
            uv_scale=3, rotation=(0, 0, -36 * sgn)))
        # 上腕の帯。肩当ての下に赤を一本入れて、腕の存在を残す
        rig.b(f"{side}Arm").add(Cube(
            (cx - L.arm_t * 0.62, L.elbow_y + (L.shoulder_y - L.elbow_y) * 0.10,
             -L.arm_t * 0.62),
            (L.arm_t * 1.24, (L.shoulder_y - L.elbow_y) * 0.46, L.arm_t * 1.24),
            "armor", uv_scale=3))
        # 前腕の籠手
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.90, L.wrist_y - L.hand_l * 0.2,
             -L.forearm_t * 0.90),
            (L.forearm_t * 1.80, (L.elbow_y - L.wrist_y) * 0.84,
             L.forearm_t * 1.80), "armor", uv_scale=3,
            decals={"west": "rivets", "east": "rivets"}))
    _restyle(rig, ("rightHand", "leftHand"), "armor")


def dress_quicksilver(rig):
    """前へ流れた髪と、後ろへ流れる衣装。止まっていても風の中にいる。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    _bodysuit(rig, "suit", top=0.92)
    _belt(rig, "accent", None)
    _boots(rig, "armor", top=0.46)
    _restyle(rig, ("rightHand", "leftHand"), "armor")
    # 胸の銀の楔。細い胴の上で肩だけを尖らせる
    _wedges(rig, "armor", 26, uv=5)
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.30, L.chest_top - ch * 0.52, -L.chest_d * 0.66),
        (L.chest_w * 0.60, ch * 0.52, L.chest_d * 0.16), "armor", uv_scale=6,
        rotation=(0, 0, 0), decals={"north": "brotherhood_mark"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        # 肩から後ろへ流れる帯。X を後ろへ倒し、外へも開く
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.50, L.shoulder_y - L.arm_t * 4.2, L.arm_t * 0.34),
            (L.arm_t * 1.00, L.arm_t * 4.3, L.arm_t * 0.20), "accent",
            uv_scale=4, rotation=(-42, 0, -16 * sgn),
            decals={"north": "cape_fold", "south": "cape_fold"}))
        # 脚は何も足さない。細さが速さになる。足首だけ絞る
        rig.b(f"{side}Shin").add(Cube(
            (sgn * L.stance - L.shin_t * 0.60, L.ankle_y, -L.shin_t * 0.66),
            (L.shin_t * 1.20, (L.knee_y - L.ankle_y) * 0.20, L.shin_t * 1.16),
            "accent", uv_scale=5))
    # 腰から後ろへ流れる二枚の裾
    for sgn in (-1, 1):
        rig.b("body").add(Cube(
            (sgn * L.hip_w * 0.10 - (L.hip_w * 0.42 if sgn < 0 else 0),
             L.abdomen_bot - L.total * 0.20, L.waist_d * 0.50),
            (L.hip_w * 0.42, L.total * 0.22, L.total * 0.012), "suit",
            uv_scale=4, rotation=(-30, 0, -8 * sgn),
            decals={"north": "cape_fold", "south": "cape_fold"}))
    # 前へ流れた髪。頭より前に出た庇が、横顔の輪郭を決める。
    # 3 枚を少しずつ前・下へずらして、風に押された束にする
    hair = rig.b("hair")
    for i, (wf, rot) in enumerate(((1.06, (30, 0, 0)), (0.92, (44, 0, 0)),
                                   (0.68, (58, 0, 0)))):
        hair.add(Cube((-L.head_w * wf / 2, L.chin + L.head_h * (0.80 - 0.10 * i),
                       -L.head_d * (0.56 + 0.30 * i)),
                      (L.head_w * wf, L.head_h * 0.28, L.head_d * 0.40),
                      "hair", uv_scale=4, rotation=rot))
    for sgn in (-1, 1):
        hair.add(Cube(((sgn * 0.32 - 0.16) * L.head_w, L.chin + L.head_h * 0.70,
                       -L.head_d * 0.42),
                      (L.head_w * 0.32, L.head_h * 0.34, L.head_d * 0.70),
                      "hair", uv_scale=4, rotation=(30, 0, -26 * sgn)))


def dress_pyro(rig):
    """背中の燃料タンクと腕の噴射装置。背面が重いシルエット。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    _bodysuit(rig, "suit")
    _belt(rig, "belt")
    _boots(rig, "cloth", top=0.56)
    chest = rig.b("chest")
    # タンク 2 本。外へ 8 度開くと 1 本の箱に見えなくなる
    for sgn in (-1, 1):
        chest.add(Cube(
            (sgn * L.chest_w * 0.06 - (L.chest_w * 0.36 if sgn < 0 else 0),
             L.chest_bot + ch * 0.16, L.chest_d * 0.48),
            (L.chest_w * 0.36, ch * 0.88, L.chest_d * 0.52), "armor",
            uv_scale=4, rotation=(0, 0, -8 * sgn),
            decals={"south": "panel_seam", "up": "vent"}))
    # タンクを繋ぐ調整器
    chest.add(Cube((-L.chest_w * 0.20, L.chest_bot + ch * 0.06, L.chest_d * 0.56),
                   (L.chest_w * 0.40, ch * 0.22, L.chest_d * 0.38), "cable",
                   uv_scale=5, decals={"south": "vent"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        # 肩の吊り帯。前後を斜めに渡す
        chest.add(Cube(
            (cx - L.arm_t * 0.34, L.chest_top - ch * 0.52, -L.chest_d * 0.66),
            (L.arm_t * 0.68, ch * 0.56, L.chest_d * 1.34), "armor", uv_scale=4,
            rotation=(0, 0, -10 * sgn), decals={"north": "panel_seam"}))
        # 前腕の外側を走るホース
        rig.b(f"{side}Forearm").add(Cube(
            (cx + sgn * L.forearm_t * 0.34, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.06,
             -L.forearm_t * 0.34),
            (L.forearm_t * 0.44, (L.elbow_y - L.wrist_y) * 0.84, L.forearm_t * 0.92),
            "cable", uv_scale=5, rotation=(0, 0, -6 * sgn)))
    _restyle(rig, ("rightHand", "leftHand"), "cloth")
    # 噴射装置。手袋を塗り替えた **後** に足す（塗り替えの対象外にする）
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        # 前腕の橙の筒。正面から見て黒一色にならないための一手
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.82, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.04,
             -L.forearm_t * 0.82),
            (L.forearm_t * 1.64, (L.elbow_y - L.wrist_y) * 0.48, L.forearm_t * 1.64),
            "armor", uv_scale=5, decals={"west": "vent", "east": "vent"}))
        rig.b(f"{side}Hand").add(Cube(
            (cx - L.forearm_t * 0.40, L.wrist_y - L.hand_l * 0.30, -L.forearm_t * 1.34),
            (L.forearm_t * 0.80, L.hand_l * 0.66, L.forearm_t * 1.14), "armor",
            uv_scale=6, rotation=(-8, 0, 0), decals={"north": "core"}))


def dress_avalanche(rig):
    """面を覆うゴーグルと、厚い前腕アーマー。重心の低い工兵。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    _bodysuit(rig, "suit")
    _belt(rig, "armor", "brotherhood_mark")
    _boots(rig, "armor", top=0.62, cuff=0.12)
    head = rig.b("head")
    # ゴーグルは頭より広く作る。ここだけが顔の情報なので、幅で読ませる
    head.add(Cube((-L.head_w * 0.60, L.chin + L.head_h * 0.40, -L.head_d * 0.66),
                  (L.head_w * 1.20, L.head_h * 0.26, L.head_d * 0.22), "goggle",
                  uv_scale=7, decals={"north": "goggles"}))
    for sgn in (-1, 1):
        # 左右のレンズ庇。Y に開いて顔を包む
        head.add(Cube((sgn * L.head_w * 0.30 - (L.head_w * 0.30 if sgn < 0 else 0),
                       L.chin + L.head_h * 0.38, -L.head_d * 0.62),
                      (L.head_w * 0.30, L.head_h * 0.30, L.head_d * 0.26),
                      "goggle", uv_scale=6, rotation=(0, 20 * sgn, 0)))
    # 帯（後頭部へ回す）
    head.add(Cube((-L.head_w * 0.54, L.chin + L.head_h * 0.46, -L.head_d * 0.10),
                  (L.head_w * 1.08, L.head_h * 0.14, L.head_d * 0.62), "cloth",
                  uv_scale=4))
    _wedges(rig, "armor", 20, uv=4)
    # 装備だけ鋼にする。アバランチは肌・服・岩が全部茶色で、
    # 明度差を作れる色がパレットに steel しか残っていない
    _pauldrons(rig, "steel", span=1.70, drop=1.05, tilt=22, decal="rivets", uv=4)
    # 高い襟。顎を隠すと目元だけが残って、表情が読めない相手になる
    rig.b("chest").add(Cube(
        (-L.head_w * 0.52, L.chest_top - ch * 0.10, -L.head_d * 0.50),
        (L.head_w * 1.04, ch * 0.34, L.head_d * 1.00), "armor", uv_scale=4,
        rotation=(-6, 0, 0)))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        fore = rig.b(f"{side}Forearm")
        # 厚い籠手。前腕の 2.0 倍まで太らせて、拳を大きく見せる。
        # 奥行きは抑える（深くすると腕ではなく箱を提げているように見える）
        fore.add(Cube(
            (cx - L.forearm_t * 1.00, L.wrist_y - L.hand_l * 0.20, -L.forearm_t * 0.86),
            (L.forearm_t * 2.00, (L.elbow_y - L.wrist_y) * 0.86, L.forearm_t * 1.72),
            "steel", uv_scale=4,
            decals={"west": "panel_seam", "east": "panel_seam"}))
        # 籠手の稜 3 枚。外へ倒して角を立てる
        for i in range(3):
            fore.add(Cube(
                (cx - L.forearm_t * 0.66, L.wrist_y +
                 (L.elbow_y - L.wrist_y) * (0.08 + 0.26 * i), -L.forearm_t * 1.02),
                (L.forearm_t * 1.32, (L.elbow_y - L.wrist_y) * 0.14,
                 L.forearm_t * 0.40), "armor", uv_scale=4,
                rotation=(0, 0, -(14 + 6 * i) * sgn)))
    _restyle(rig, ("rightHand", "leftHand"), "cloth")


def dress_blob(rig):
    """腹。bulk=2.10 を使い切る。他は全部この腹に食われてよい。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    body = rig.b("body")
    top = L.chest_bot + ch * 0.46
    bot = L.knee_y + (L.hip_y - L.knee_y) * 0.10
    band = (top - bot) / 5
    # 5 段で球を作る。角を落とすほど「箱を着た人」から離れる
    # 上下の段は前へ／後ろへ倒す。垂直に積むと球ではなくドラム缶になる
    for i, (fw, fd, rot) in enumerate((
            (0.66, 0.62, (16, 0, 0)), (0.90, 0.90, (8, 0, 0)),
            (1.00, 1.00, None), (0.96, 0.96, (-6, 0, 0)),
            (0.76, 0.72, (-14, 0, 0)))):
        w = L.shoulder_w * 0.92 * fw
        d = L.chest_d * 1.50 * fd
        body.add(Cube((-w / 2, bot + band * i, -d * 0.64),
                      (w, band * 1.02, d), "gut", uv_scale=2, rotation=rot,
                      decals={"north": "scales"} if i == 3 else None))
    # 胸板は腹より狭くする。狭いほど腹が出て見える
    rig.b("chest").add(Cube(
        (-L.shoulder_w * 0.34, L.chest_bot + ch * 0.28, -L.chest_d * 0.72),
        (L.shoulder_w * 0.68, ch * 0.76, L.chest_d * 1.40), "suit", uv_scale=2))
    # 首の肉。頭を肩へ埋めて、頭を小さく見せる
    rig.b("chest").add(Cube(
        (-L.head_w * 0.74, L.chest_top - ch * 0.10, -L.head_d * 0.72),
        (L.head_w * 1.48, ch * 0.30, L.head_d * 1.40), "gut", uv_scale=3))
    # 顎の肉。頭の下半分を広げないと、丸い胴の上に角ばった箱が乗る
    rig.b("head").add(Cube(
        (-L.head_w * 0.58, L.chin - L.head_h * 0.04, -L.head_d * 0.58),
        (L.head_w * 1.16, L.head_h * 0.34, L.head_d * 1.10), "skin",
        uv_scale=4, rotation=(-8, 0, 0)))
    # ベルトは腰ではなく **腹の一番太いところ** に回す。
    # 腰に巻いても腹の内側に埋まって一度も見えない
    w = L.shoulder_w * 0.92 * 1.04
    d = L.chest_d * 1.50 * 1.04
    body.add(Cube((-w / 2, bot + band * 2.5, -d * 0.64),
                  (w, band * 0.62, d), "cloth", uv_scale=3))
    # 徽章は帯とは別 cube。帯に載せると 3 テクセルに潰れて、ただの光る線になる
    body.add(Cube((-L.head_w * 0.30, bot + band * 2.58, -d * 0.66),
                  (L.head_w * 0.60, band * 0.46, d * 0.06), "armor",
                  uv_scale=8, decals={"north": "brotherhood_mark"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        lx = sgn * L.stance
        # 肩は丸く。角があると太って見えない
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.86, L.shoulder_y - L.arm_t * 1.30, -L.arm_t * 0.86),
            (L.arm_t * 1.72, L.arm_t * 1.50, L.arm_t * 1.72), "gut",
            uv_scale=2, rotation=(0, 0, -12 * sgn)))
        # 二の腕の肉。肘の手前でくびれる
        rig.b(f"{side}Arm").add(Cube(
            (cx - L.arm_t * 0.74, L.elbow_y + (L.shoulder_y - L.elbow_y) * 0.14,
             -L.arm_t * 0.74),
            (L.arm_t * 1.48, (L.shoulder_y - L.elbow_y) * 0.74, L.arm_t * 1.48),
            "gut", uv_scale=2))
        # 短いズボン。脚は腹の下から少しだけ見える。外へ倒してがに股にする
        rig.b(f"{side}Leg").add(Cube(
            (lx - L.thigh_t * 0.72, L.knee_y + (L.hip_y - L.knee_y) * 0.05,
             -L.thigh_t * 0.72),
            (L.thigh_t * 1.44, (L.hip_y - L.knee_y) * 0.62, L.thigh_t * 1.44),
            "suit", uv_scale=2, rotation=(0, 0, 7 * sgn)))
    _boots(rig, "cloth", top=0.36)


def dress_scarlet_witch(rig):
    """二本角の頭飾りと短いマント。腰を絞って上下を三角形にする。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    _bodysuit(rig, "suit", top=0.96)
    # 脚は明るい赤の長靴。黒い脚にすると上半身の赤が浮いて別人に見える
    _boots(rig, "cape", top=0.92, cuff=0.12)
    _restyle(rig, ("rightHand", "leftHand", "rightForearm", "leftForearm"),
             "cape")
    # コルセット。腰の一段だけ細く締めて、その上下を広げる
    rig.b("body").add(Cube(
        (-L.waist_w * 0.54, L.abdomen_bot, -L.waist_d * 0.56),
        (L.waist_w * 1.08, L.chest_bot - L.abdomen_bot, L.waist_d * 1.12),
        "armor", uv_scale=6, decals={"north": "panel_seam"}))
    # 腰の後ろだけに垂れる 2 枚。前に垂らすと樽になる
    for sgn in (-1, 1):
        rig.b("body").add(Cube(
            (sgn * L.hip_w * 0.06 - (L.hip_w * 0.40 if sgn < 0 else 0),
             L.abdomen_bot - L.total * 0.26, L.waist_d * 0.44),
            (L.hip_w * 0.40, L.total * 0.26, L.total * 0.011), "cape",
            uv_scale=3, rotation=(-8, 0, -14 * sgn),
            decals={"north": "cape_fold", "south": "cape_fold"}))
    _belt(rig, "armor", "buckle")
    # 短いマント: 肩から 2 段 + 裾を左右へ割る。
    # 全長は身長の 0.30 に留める。長くすると胴が消えて誰か判らなくなる
    z = L.chest_d * 0.54
    y = L.chest_top + L.total * 0.006
    seg = L.total * 0.10
    parent = "chest"
    for i in range(2):
        name = f"cape{i}"
        bone = rig.model.bone(name, (0, y, z), parent, rotation=(6 + 4 * i, 0, 0))
        rig.bones[name] = bone
        w = L.shoulder_w * (0.82 + 0.16 * i)
        bone.add(Cube((-w / 2, y - seg, z), (w, seg, L.total * 0.010), "cape",
                      uv_scale=3, decals={"north": "cape_fold",
                                          "south": "cape_fold"}))
        parent, y = name, y - seg
    for sgn, tag in ((-1, "R"), (1, "L")):
        name = f"cape2{tag}"
        bone = rig.model.bone(name, (0, y, z), parent, rotation=(12, 0, -14 * sgn))
        rig.bones[name] = bone
        w = L.shoulder_w * 0.56
        bone.add(Cube((sgn * L.shoulder_w * 0.01 - (w if sgn < 0 else 0),
                       y - seg * 1.1, z),
                      (w, seg * 1.1, L.total * 0.010), "cape", uv_scale=3,
                      decals={"north": "cape_fold", "south": "cape_fold"}))
    # 襟。マントの起点を立てると、首から上が別の形になる
    rig.b("chest").add(Cube(
        (-L.shoulder_w * 0.26, L.chest_top - ch * 0.04, L.chest_d * 0.20),
        (L.shoulder_w * 0.52, ch * 0.44, L.chest_d * 0.36), "cape_inner",
        uv_scale=4, rotation=(-28, 0, 0)))
    # 頭飾り: 額の帯と、後ろへ跳ね上がる二本の角
    head = rig.b("head")
    head.add(Cube((-L.head_w * 0.56, L.chin + L.head_h * 0.72, -L.head_d * 0.60),
                  (L.head_w * 1.12, L.head_h * 0.22, L.head_d * 0.34), "armor",
                  uv_scale=7, decals={"north": "panel_seam"}))
    for sgn in (-1, 1):
        head.add(Cube((sgn * L.head_w * 0.12 - (L.head_w * 0.30 if sgn < 0 else 0),
                       L.chin + L.head_h * 0.84, -L.head_d * 0.30),
                      (L.head_w * 0.30, L.head_h * 0.72, L.head_d * 0.26),
                      "armor", uv_scale=6, rotation=(24, 0, -26 * sgn)))
        head.add(Cube((sgn * L.head_w * 0.26 - (L.head_w * 0.20 if sgn < 0 else 0),
                       L.chin + L.head_h * 1.40, -L.head_d * 0.06),
                      (L.head_w * 0.20, L.head_h * 0.44, L.head_d * 0.20),
                      "armor", uv_scale=6, rotation=(34, 0, -34 * sgn)))


DRESS = {
    "mystique": dress_mystique,
    "sabretooth": dress_sabretooth,
    "toad": dress_toad,
    "juggernaut": dress_juggernaut,
    "quicksilver": dress_quicksilver,
    "pyro": dress_pyro,
    "avalanche": dress_avalanche,
    "blob": dress_blob,
    "scarlet_witch": dress_scarlet_witch,
}

# 顔の decal と、手足の underlay を差し替える色。
# 顔は素肌が出る相手だけ密度を上げる（兜組は uv を捨てて構わない）。
FACE = {
    "mystique": ("face", 10, "skin"),
    "sabretooth": ("feral_face", 9, "suit"),
    "toad": ("face", 9, "skin"),
    "juggernaut": (None, 2, "suit"),
    "quicksilver": ("face", 10, "suit"),
    "pyro": ("face", 10, "suit"),
    "avalanche": ("face", 9, "suit"),
    "blob": ("face", 6, "suit"),
    "scarlet_witch": ("face", 10, "suit"),
}


def build(key: str) -> Model:
    c = K.CHARACTERS[key]
    span = c["cm"] * (32.0 / 180.0) / 16.0            # ブロック単位の身長
    m = Model(K.geo(key), uv_scale=UV_SCALE.get(key, 4),
              visible_bounds=(max(2.4, span * 1.25), span + 0.8),
              vb_offset=(0, span * 0.5, 0), max_atlas=(512, 512))
    rig = HumanRig(m, Build(c["cm"], c["heads"], c["sh"], c["limb"],
                            female=c["female"], bulk=c["bulk"],
                            hunch=c.get("hunch", 0.0), **SHAPE.get(key, {})),
                   player_rig=True)
    rig.flesh()
    decal, uv, limb = FACE[key]
    _trim(rig, limb)
    if decal:
        _face(rig, decal, uv)
    DRESS[key](rig)
    if key in HAIR:
        rig.hair(HAIR[key], uv_scale=4)
    # 担当7の ally 技 VFX が掴む点。手と胸が無いと効果が足元に湧く
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        _locators(rig.b(f"{side}Hand"),
                  {f"{side}Hand": (cx, L.wrist_y - L.hand_l * 0.6, 0)})
    _locators(rig.b("chest"), {"chest": (0, L.chest_top - (L.chest_top -
                                                           L.chest_bot) * 0.35,
                                         -L.chest_d * 0.62)})
    _locators(rig.b("head"), {"head": (0, L.chin + L.head_h * 0.62,
                                       -L.head_d * 0.55)})
    return m


def main() -> None:
    print("brotherhood:")
    for key in K.BROTHERHOOD:
        emit(build(key), colours.ALL[K.CHARACTERS[key]["pal"]], key,
             seed=abs(hash(key)) % 9000 + 7)


if __name__ == "__main__":
    main()
