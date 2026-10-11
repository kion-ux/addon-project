# -*- coding: utf-8 -*-
"""敵（センチネル / MRD）と、技が生む小物エンティティのモデル。

小物 (``K.PROP_ENTITIES``) は技の見た目そのものなので、ここが手を抜くと
どれだけ良いパーティクルを足しても画面が安っぽくなる。芯になる立体は必ず置く。

センチネルを「巨大」に見せているのは絶対寸法ではなく **比率** である。
40 ブロック先まで残るのは輪郭だけで、装甲のパネル割りは一切読めないので、
予算はすべて次の四つに寄せてある:

    ① 頭を素の 1.7 倍に膨らませる    ② 頭頂のフィンで輪郭を横へ 2 倍に伸ばす
    ③ 肩を胸板の 2.4 倍へ張り出す    ④ 腰を肩の 1/4.5 に絞る

素材の明度も同じ理由で三段に分けた。``steel``（明）は光の当たる面 ——
肩の天板・胸骨板・脛の前面 —— にだけ置き、``robot``（中）が本体、
``robot_dark``（暗）は関節と隙間に限る。全部を robot_dark で塗ると
レビューにあった「黒っぽい塊」に逆戻りする。
"""
from __future__ import annotations

import math

import _path  # noqa: F401

import colours  # noqa: E402
import contract as K  # noqa: E402
from common import emit  # noqa: E402
from mcmodel import Cube, Model  # noqa: E402
from rig import Build, HumanRig  # noqa: E402


# ===========================================================================
#  locator（パーティクルの発生位置）
# ===========================================================================
class RiggedModel(Model):
    """locator を書き出せる Model。

    VFX 側は ``"locator": "optic"`` で発生位置を指定するが、共有エンジンの
    ``mcmodel.Bone`` はまだ locators を持たない。``tools/mcmodel.py`` は別アドオンも
    使うので触らず、書き出しの直前にだけ差し込む。Bone 本体に入ったらこの層は消せる。
    """

    def to_json(self) -> dict:
        doc = super().to_json()
        for entry, bone in zip(doc["bones"], self.bones):
            found = getattr(bone, "marvel_locators", None)
            if found and "locators" not in entry:
                entry["locators"] = found
        return doc


def put_locators(bone, **points) -> None:
    store = getattr(bone, "marvel_locators", None)
    if store is None:
        store = {}
        bone.marvel_locators = store
    for name, pos in points.items():
        store[name] = [round(float(v), 3) for v in pos]


def _model(key: str, uv_scale: int, atlas=(1024, 1024)) -> RiggedModel:
    px = K.CHARACTERS[key]["cm"] * 32.0 / 180.0
    return RiggedModel(K.geo(key), uv_scale=uv_scale,
                       visible_bounds=(max(3.0, px / 9), max(3.0, px / 6.4)),
                       vb_offset=(0, px / 32, 0), max_atlas=atlas)


def _rig(model: RiggedModel, key: str) -> HumanRig:
    c = K.CHARACTERS[key]
    return HumanRig(model, Build(c["cm"], c["heads"], c["sh"], c["limb"],
                                 female=c["female"], bulk=c["bulk"]),
                    player_rig=True)


# ===========================================================================
#  センチネル
# ===========================================================================
def _out(x0: float, width: float, sgn: int) -> float:
    """``x0`` から外側（``sgn`` の向き）へ ``width`` 伸びる cube の origin。

    Cube は必ず +x へ伸びるので、右半身（sgn<0）は origin を引いておかないと
    左右のパーツが body の中心線を跨いで重なる。
    """
    return x0 if sgn > 0 else x0 - width


def sentinel_head(rig: HumanRig, prime: bool, uvh: int, uve: int) -> None:
    """兜のような頭部。首は作らない —— 首があると途端に人間に見える。

    素の頭（1/7.4 身）のままでは 40 ブロック先で人間と区別が付かないので、
    幅・高さとも 1.5 倍に膨らませ、下端を肩まで下ろして首を飲み込ませる。
    """
    L = rig.L
    hw, hh, hd = L.head_w, L.head_h, L.head_d
    head = rig.b("head")

    half = hw * (0.94 if prime else 0.90)
    bot = L.chin - hh * 0.22                            # 肩に載せて首を消す
    top = L.chin + hh * (1.50 if prime else 1.42)
    hs = top - bot
    fz = -hd * 0.80                                     # 顔の面
    bz = hd * (0.60 if prime else 0.68)                 # 後頭部

    head.add(Cube((-half, bot, fz + hd * 0.14),
                  (half * 2, hs, bz - fz - hd * 0.14), "robot",
                  uv_scale=uvh, decals={"up": "panel_seam"}))
    # 顔面。装甲板を一枚張るだけにして、目以外の情報を載せない。
    # ここに顎グリルや継ぎ目を描き込むと「顔」が散って一文字が効かなくなる。
    head.add(Cube((-half * 0.90, bot + hs * 0.08, fz),
                  (half * 1.80, hs * 0.86, hd * 0.18), "steel",
                  uv_scale=uvh, rotation=(-6 if prime else -3, 0, 0),
                  decals={"north": "sentinel_face"}))

    # --- オプティックバー: 庇・枠・芯の 3 cube。敵の表情はここにしかない
    eye_y = bot + hs * 0.48
    eye_h = hs * (0.10 if prime else 0.13)
    head.add(Cube((-half * 0.96, eye_y + eye_h * 1.25, fz - hd * 0.20),
                  (half * 1.92, hs * 0.10, hd * 0.34), "robot_dark",
                  uv_scale=uvh, rotation=(22, 0, 0)))                   # 庇
    head.add(Cube((-half * 0.92, eye_y - eye_h * 0.42, fz - hd * 0.10),
                  (half * 1.84, eye_h * 1.84, hd * 0.12), "cable",
                  uv_scale=uvh))                                        # 枠
    head.add(Cube((-half * 0.86, eye_y, fz - hd * 0.17),
                  (half * 1.72, eye_h, hd * 0.10), "optic", uv_scale=uve,
                  decals={"north": "sentinel_optic"}))                  # 芯
    put_locators(head, optic=(0, eye_y + eye_h * 0.5, fz - hd * 0.26))

    # 顎。低く小さく。グリルは口ではなく排気で、目の一文字を邪魔しない大きさに
    head.add(Cube((-half * 0.62, bot, fz - hd * 0.02),
                  (half * 1.24, hs * 0.17, hd * 0.50), "robot",
                  uv_scale=uvh, decals={"north": "rivets"}))
    if prime:
        # 前へ突き出す顎。真横のシルエットで Mk-I と一番はっきり違う所
        head.add(Cube((-half * 0.42, bot - hs * 0.09, fz - hd * 0.36),
                      (half * 0.84, hs * 0.20, hd * 0.44), "steel",
                      uv_scale=uvh, rotation=(26, 0, 0)))
        # 頬の楔。Mk-I は角を落とした量産機、プライムは全部の面を尖らせる
        for sgn in (-1, 1):
            head.add(Cube((_out(sgn * half * 0.72, half * 0.34, sgn),
                           bot + hs * 0.14, fz - hd * 0.02),
                          (half * 0.34, hs * 0.44, hd * 0.52), "robot_dark",
                          uv_scale=uvh,
                          pivot=(sgn * half * 0.72, bot + hs * 0.36, 0),
                          rotation=(0, 0, sgn * 17)))

    # 頭頂の稜線。前後に走らせると、正面からも真横からも高さが出る
    head.add(Cube((-half * 0.26, top - hs * 0.07, fz + hd * 0.04),
                  (half * 0.52, hs * (0.20 if prime else 0.14),
                   (bz - fz) * 0.86), "steel", uv_scale=uvh,
                  rotation=(-5, 0, 0)))
    # 後頭部のケーブル函。cable ほど暗いと背面が背景に溶けるので一段明るく置く
    head.add(Cube((-half * 0.56, bot + hs * 0.20, bz - hd * 0.08),
                  (half * 1.12, hs * 0.42, hd * 0.26), "robot_dark",
                  uv_scale=uvh, decals={"south": "rivets"}))

    # --- 頭頂フィン: 遠景の読みはここで決まる ------------------------
    #  板は「厚み 1 : 弦 5」の刃にして、Y に 38 度捻る。捻らないと正面から
    #  ただの棒に見える（前回の失敗がこれ）。Z で跳ね上げ、X で牛角化を防ぐ。
    fin_len = hh * (1.24 if prime else 1.10)
    fin_t = half * (0.24 if prime else 0.27)
    chord = hd * (0.84 if prime else 0.92)
    yaw = 44 if prime else 38
    for sgn in (-1, 1):
        px = sgn * half * 0.86
        py = bot + hs * 0.50
        pz = hd * 0.02
        head.add(Cube((_out(px, fin_t * 1.15, sgn), py - hs * 0.06,
                       pz - chord * 0.60),
                      (fin_t * 1.15, hs * 0.34, chord * 1.10), "robot",
                      uv_scale=uvh, pivot=(px, py, pz),
                      rotation=(0, sgn * yaw, -sgn * 20)))         # 根元
        head.add(Cube((_out(px, fin_t, sgn), py,
                       pz - chord * 0.52),
                      (fin_t, fin_len, chord), "steel",
                      uv_scale=uvh, pivot=(px, py, pz),
                      rotation=(-13 if prime else -10, sgn * yaw,
                                -sgn * (28 if prime else 34))))    # 主翼
        head.add(Cube((_out(px, fin_t * 0.78, sgn), py + fin_len * 0.90,
                       pz - chord * 0.40),
                      (fin_t * 0.78, fin_len * 0.58, chord * 0.74), "steel",
                      uv_scale=uvh, pivot=(px, py, pz),
                      rotation=(-6, sgn * yaw,
                                -sgn * (44 if prime else 50))))    # 先端
    if prime:
        # 額の一対のアンテナ。上へ抜ける細い線が「指揮機」に見せる
        for sgn in (-1, 1):
            head.add(Cube((_out(sgn * half * 0.30, half * 0.09, sgn),
                           top - hs * 0.02, fz + hd * 0.34),
                          (half * 0.09, hs * 0.42, hd * 0.09), "hazard",
                          uv_scale=uve, pivot=(sgn * half * 0.30, top, fz),
                          rotation=(-15, 0, -sgn * 11)))


def sentinel_torso(rig: HumanRig, prime: bool, uvb: int, uve: int) -> None:
    """胸を厚く、腰を細く。逆三角はパウルドロンではなく **この差** で作る。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    chest = rig.b("chest")
    body = rig.b("body")
    cw = L.chest_w * (0.66 if prime else 0.68)          # 半幅
    cd = L.chest_d * (0.80 if prime else 0.76)          # 半奥行

    # 上胸。奥行を幅と同じだけ取ると、正面から見ても「厚い」と判る。
    # 下端を chest_bot まで落として、腹（暗い帯）より胸を必ず長く保つ。
    chest.add(Cube((-cw, L.chest_bot + ch * 0.04, -cd),
                   (cw * 2, ch * 0.96, cd * 2), "robot", uv_scale=uvb,
                   decals={"east": "panel_seam", "west": "panel_seam"}))
    # 胸骨板。全身で一番明るい面。ここが暗いと胴が一枚の黒い箱に潰れる
    chest.add(Cube((-cw * 0.54, L.chest_bot + ch * 0.20, -cd * 1.14),
                   (cw * 1.08, ch * 0.70, cd * 0.22), "steel", uv_scale=uvb,
                   decals={"north": "panel_seam"}))
    # 動力炉。crush / emp で露出させる部位なので、初めから穴として彫っておく
    core_y = L.chest_bot + ch * 0.52
    chest.add(Cube((-cw * 0.34, core_y - ch * 0.03, -cd * 1.24),
                   (cw * 0.68, ch * 0.30, cd * 0.14), "cable", uv_scale=uvb))
    chest.add(Cube((-cw * 0.25, core_y + ch * 0.01, -cd * 1.29),
                   (cw * 0.50, ch * 0.22, cd * 0.10), "optic", uv_scale=uve,
                   decals={"north": "sentinel_optic"}))
    put_locators(chest, core=(0, core_y + ch * 0.12, -cd * 1.38))

    # 鎖骨の楔。肩へ向かう斜線が「広い」の実体。左右が中心を跨がないよう _out
    for sgn in (-1, 1):
        wedge = cw * 0.90
        chest.add(Cube((_out(sgn * cw * 0.16, wedge, sgn),
                        L.chest_top - ch * 0.30, -cd * 0.74),
                       (wedge, ch * 0.28, cd * 1.48), "robot", uv_scale=uvb,
                       pivot=(sgn * cw * 0.16, L.chest_top - ch * 0.16, 0),
                       rotation=(0, 0, sgn * (26 if prime else 21))))
        # 側面の排気。胸の外側に暗い帯を回すと厚みの角が読める
        chest.add(Cube((_out(sgn * cw, cw * 0.18, sgn),
                        L.chest_bot + ch * 0.34, -cd * 0.52),
                       (cw * 0.18, ch * 0.66, cd * 1.04), "robot_dark",
                       uv_scale=uvb,
                       decals={"east" if sgn > 0 else "west": "vent_grill"}))
    # 背板
    chest.add(Cube((-cw * 0.82, L.chest_bot + ch * 0.20, cd * 0.84),
                   (cw * 1.64, ch * 0.74, cd * 0.32), "steel", uv_scale=uvb,
                   decals={"south": "rivets"}))

    # --- 腰。胸板の 1/2 まで絞る。ここを絞らないと肩がいくら広くても効かない
    ww = L.waist_w * 0.42
    body.add(Cube((-ww, L.abdomen_bot, -L.waist_d * 0.40),
                  (ww * 2, L.chest_bot - L.abdomen_bot + ch * 0.06,
                   L.waist_d * 0.80), "robot_dark", uv_scale=uvb))
    body.add(Cube((-L.hip_w * 0.39, L.pelvis_bot, -L.waist_d * 0.48),
                  (L.hip_w * 0.78, L.abdomen_bot - L.pelvis_bot + L.total * 0.01,
                   L.waist_d * 0.96), "robot", uv_scale=uvb,
                  decals={"north": "panel_seam"}))
    # 腰の張り出し。脚の付け根を外へ振ると、細い腰がさらに細く見える
    for sgn in (-1, 1):
        flare = L.hip_w * 0.26
        body.add(Cube((_out(sgn * L.hip_w * 0.36, flare, sgn),
                       L.pelvis_bot, -L.waist_d * 0.44),
                      (flare, (L.abdomen_bot - L.pelvis_bot) * 1.15,
                       L.waist_d * 0.92), "robot_dark", uv_scale=uvb,
                      pivot=(sgn * L.hip_w * 0.44, L.hip_y, 0),
                      rotation=(0, 0, sgn * 15)))
    if prime:
        # 背部の推進ユニット。真横のシルエットが Mk-I と決定的に変わる
        for sgn in (-1, 1):
            nac = cw * 0.66
            chest.add(Cube((_out(sgn * cw * 0.86, nac, sgn),
                            L.chest_bot + ch * 0.28, cd * 1.04),
                           (nac, ch * 0.80, cd * 0.66), "robot_dark",
                           uv_scale=uvb,
                           pivot=(sgn * cw * 0.86, L.chest_top, cd),
                           rotation=(-9, 0, sgn * 8)))
            chest.add(Cube((_out(sgn * cw * 0.82, nac * 0.82, sgn),
                            L.chest_bot + ch * 0.22, cd * 1.26),
                           (nac * 0.82, ch * 0.22, cd * 0.46), "optic",
                           uv_scale=uve, decals={"south": "sentinel_optic"}))
        # フェーズ 2 の機体色変更で差し替える独立ボーン（§7-5）
        panel = rig.model.bone("phasePanel", (0, L.chest_top, -cd), "chest")
        panel.add(Cube((-cw * 0.46, L.chest_top - ch * 0.28, -cd * 1.18),
                       (cw * 0.92, ch * 0.18, cd * 0.22), "hazard",
                       uv_scale=uve, decals={"north": "hazard_stripe"}))


def sentinel_limbs(rig: HumanRig, prime: bool, uvb: int, uve: int) -> None:
    L = rig.L
    at = L.arm_t
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - at / 2)
        ox = cx + sgn * at * 0.76            # パウルドロンの中心は肩より外
        sh = rig.b(f"{side}Shoulder")
        # 肩。胸板の 2.4 倍まで張り出させる。上下にも厚みを持たせないと
        # 「棚板」に見えてしまうので、高さは腕の太さの 2 倍近く取る。
        sh.add(Cube((ox - at * 1.22, L.shoulder_y - at * 1.90, -at * 1.16),
                    (at * 2.44, at * 1.95, at * 2.32), "robot", uv_scale=uvb,
                    decals={"up": "rivets"}))
        # 天板。up 面は FACE_LIGHT が 1.18 倍で拾うので、明色を置くと一番効く
        sh.add(Cube((ox - at * 1.06, L.shoulder_y - at * 0.14, -at * 0.98),
                    (at * 2.12, at * 0.54, at * 1.96), "steel", uv_scale=uvb,
                    pivot=(cx, L.shoulder_y, 0),
                    rotation=(0, 0, -sgn * (20 if prime else 14))))
        # 下縁のリップ。逆へ傾けて肩の下に段差を作り、腕へ繋ぐ
        sh.add(Cube((ox - at * 1.02, L.shoulder_y - at * 2.42, -at * 0.92),
                    (at * 2.04, at * 0.60, at * 1.84), "robot_dark",
                    uv_scale=uvb, pivot=(cx, L.shoulder_y - at, 0),
                    rotation=(0, 0, sgn * (18 if prime else 13))))
        if prime:
            # 肩の砲。角ばった突起を足して「新型」を一目で読ませる
            sh.add(Cube((ox - at * 0.43 + sgn * at * 0.62,
                         L.shoulder_y + at * 0.16, -at * 1.60),
                        (at * 0.86, at * 0.92, at * 2.10), "robot_dark",
                        uv_scale=uvb, pivot=(ox, L.shoulder_y, 0),
                        rotation=(-6, 0, -sgn * 13)))

        arm = rig.b(f"{side}Arm")
        cx += sgn * at * 0.24               # 肩の張り出しに合わせて腕も外へ
        arm.add(Cube((cx - at * 0.56, L.elbow_y + at * 0.10, -at * 0.56),
                     (at * 1.12, L.shoulder_y - L.elbow_y - at * 0.10,
                      at * 1.12), "robot_dark", uv_scale=uvb))
        arm.add(Cube((cx - at * 0.68, L.elbow_y + at * 0.44, -at * 0.72),
                     (at * 1.36, (L.shoulder_y - L.elbow_y) * 0.50, at * 0.46),
                     "robot", uv_scale=uvb))

        fore = rig.b(f"{side}Forearm")
        ft = L.forearm_t
        fl = L.elbow_y - L.wrist_y
        fore.add(Cube((cx - ft * 0.86, L.wrist_y, -ft * 0.86),
                      (ft * 1.72, fl * 0.94, ft * 1.72), "robot",
                      uv_scale=uvb))
        # 前腕の外側板。腕が上がったとき画面で一番大きく動く面
        fore.add(Cube((_out(cx + sgn * ft * 0.86, ft * 0.42, sgn),
                       L.wrist_y + fl * 0.10, -ft * 0.76),
                      (ft * 0.42, fl * 0.74, ft * 1.52), "steel",
                      uv_scale=uvb,
                      pivot=(cx, L.wrist_y + fl * 0.5, 0),
                      rotation=(0, 0, -sgn * 6)))
        fore.add(Cube((cx - ft * 0.96, L.elbow_y - fl * 0.18, -ft * 0.96),
                      (ft * 1.92, fl * 0.26, ft * 1.92), "cable",
                      uv_scale=uvb))

        hand = rig.b(f"{side}Hand")
        hand.add(Cube((cx - ft * 0.78, L.wrist_y - L.hand_l * 1.35, -ft * 0.72),
                      (ft * 1.56, L.hand_l * 1.35, ft * 1.44), "robot_dark",
                      uv_scale=uvb))
        hand.add(Cube((cx - ft * 0.56, L.wrist_y - L.hand_l * 1.52, -ft * 0.52),
                      (ft * 1.12, L.hand_l * 0.30, ft * 1.04), "optic",
                      uv_scale=uve, decals={"down": "sentinel_optic"}))
        put_locators(hand, **{("muzzle" if sgn < 0 else "muzzle_l"):
                              (cx, L.wrist_y - L.hand_l * 1.75, 0)})

        # --- 脚。前面だけ明色にして、暗い機体に縦の光を通す
        # 脚は細く、左右へ開く。二本に割れて初めて腰の細さが効く。
        # 膝だけ明色にすると、遠景で脚の長さが読めて背が高く見える。
        lx = sgn * (L.stance + L.thigh_t * 0.32)
        tt, st = L.thigh_t, L.shin_t
        leg = rig.b(f"{side}Leg")
        leg.add(Cube((lx - tt * 0.50, L.knee_y, -tt * 0.54),
                     (tt * 1.00, L.hip_y - L.knee_y + tt * 0.34, tt * 1.08),
                     "robot_dark", uv_scale=uvb))
        leg.add(Cube((lx - tt * 0.40, L.knee_y + (L.hip_y - L.knee_y) * 0.12,
                      -tt * 0.78),
                     (tt * 0.80, (L.hip_y - L.knee_y) * 0.80, tt * 0.32),
                     "robot", uv_scale=uvb))
        shin = rig.b(f"{side}Shin")
        kl = L.knee_y - L.ankle_y
        shin.add(Cube((lx - st * 0.78, L.knee_y - kl * 0.20, -st * 0.80),
                      (st * 1.56, kl * 0.30, st * 1.60), "robot",
                      uv_scale=uvb, rotation=(-12, 0, 0)))          # 膝
        shin.add(Cube((lx - st * 0.46, L.knee_y - kl * 0.17, -st * 0.96),
                      (st * 0.92, kl * 0.24, st * 0.30), "steel",
                      uv_scale=uvb, rotation=(-12, 0, 0)))          # 膝の皿
        shin.add(Cube((lx - st * 0.58, L.ankle_y, -st * 0.58),
                      (st * 1.16, kl * 0.86, st * 1.18), "robot_dark",
                      uv_scale=uvb))
        shin.add(Cube((lx - st * 0.46, L.ankle_y + kl * 0.06, -st * 0.86),
                      (st * 0.92, kl * 0.74, st * 0.34), "robot",
                      uv_scale=uvb))
        # 足は大きく踏ませる。接地面が広いほど重量が読める
        foot = rig.b(f"{side}Foot")
        foot.add(Cube((lx - st * 1.02, 0, -L.foot_l * 0.52),
                      (st * 2.04, L.foot_h * 1.50, L.foot_l * 0.92),
                      "robot", uv_scale=uvb, decals={"up": "rivets"}))
        foot.add(Cube((lx - st * 0.78, L.foot_h * 0.26, L.foot_l * 0.32),
                      (st * 1.56, L.foot_h * 1.10, L.foot_l * 0.36),
                      "robot_dark", uv_scale=uvb, rotation=(14, 0, 0)))
        toe = rig.b(f"{side}Toe")
        toe.add(Cube((lx - st * 0.94, 0, -L.foot_l * 1.06),
                     (st * 1.88, L.foot_h * 1.15, L.foot_l * 0.56),
                     "robot_dark", uv_scale=uvb))
    put_locators(rig.b("body"), feet=(0, L.pelvis_bot, 0))


def build_sentinel(key: str, prime: bool = False) -> RiggedModel:
    """``rig.flesh()`` は呼ばない。

    素の人体ボリュームを敷いてから装甲を被せると、隙間から暗い suit 色が覗いて
    全身が黒く沈む（レビューの「黒っぽい塊」の正体）。機械に肉は要らないので、
    画面に出る立体だけを直接置く。cube 予算もその分を輪郭に回せる。
    """
    uvb = 1 if prime else 2
    uvh = 2 if prime else 4
    uve = 3 if prime else 5
    m = _model(key, uvb)
    rig = _rig(m, key)
    sentinel_head(rig, prime, uvh, uve)
    sentinel_torso(rig, prime, uvb, uve)
    sentinel_limbs(rig, prime, uvb, uve)
    return m


# ===========================================================================
#  センチネル・ドローン — 脚を持たない浮遊体
# ===========================================================================
def build_drone() -> RiggedModel:
    """頭でっかちの浮遊偵察機。``head`` が本体で、``body`` は下に抱えた推進ポッド。

    三枚のフィンは **進行方向（Z 軸）まわりに 120 度** で配る。ボーンの Z 回転を
    枝の根元に置き、cube をその pivot から生やすので、どの角度でも必ず繋がる。
    人型のボーンを一切使わないことが、そのまま「人ではない」の説明になる。
    """
    m = _model("sentinel_drone", 4, atlas=(512, 512))
    rig = _rig(m, "sentinel_drone")
    L = rig.L
    hw, hh, hd = L.head_w, L.head_h, L.head_d

    head = rig.b("head")
    half = hw * 0.86
    bot = L.chin - hh * 0.46
    top = L.chin + hh * 0.86
    hs = top - bot
    fz, bz = -hd * 0.88, hd * 0.58
    head.add(Cube((-half, bot, fz + hd * 0.16),
                  (half * 2, hs, bz - fz - hd * 0.16), "robot", uv_scale=4,
                  decals={"up": "panel_seam"}))
    head.add(Cube((-half * 0.88, bot + hs * 0.12, fz),
                  (half * 1.76, hs * 0.80, hd * 0.20), "steel", uv_scale=5,
                  rotation=(-9, 0, 0), decals={"north": "sentinel_face"}))
    eye_y = bot + hs * 0.46
    head.add(Cube((-half * 0.94, eye_y + hs * 0.17, fz - hd * 0.20),
                  (half * 1.88, hs * 0.11, hd * 0.34), "robot_dark",
                  uv_scale=4, rotation=(22, 0, 0)))                    # 庇
    head.add(Cube((-half * 0.86, eye_y, fz - hd * 0.17),
                  (half * 1.72, hs * 0.15, hd * 0.10), "optic", uv_scale=7,
                  decals={"north": "sentinel_optic"}))                 # 芯
    head.add(Cube((-half * 0.54, bot + hs * 0.02, bz - hd * 0.06),
                  (half * 1.08, hs * 0.44, hd * 0.24), "cable", uv_scale=4,
                  decals={"south": "rivets"}))
    put_locators(head, optic=(0, eye_y + hs * 0.08, fz - hd * 0.26))

    # 推進ポッド。頭の下端に食い込ませて、浮いた別部品に見せない
    body = rig.b("body")
    body.add(Cube((-half * 0.50, bot - hh * 0.44, -hd * 0.40),
                  (half * 1.00, hh * 0.52, hd * 0.80), "robot_dark",
                  uv_scale=4))
    body.add(Cube((-half * 0.36, bot - hh * 0.60, -hd * 0.28),
                  (half * 0.72, hh * 0.20, hd * 0.56), "optic", uv_scale=6,
                  decals={"down": "sentinel_optic"}))
    put_locators(body, core=(0, bot - hh * 0.20, 0))

    # 三枚のフィン。頭の**重心**から放射させると、どの向きからも 3 枚とも見える。
    # 頭の後ろに生やすと正面から消えてしまい、遠景でただの箱に戻る。
    px, py, pz = 0.0, bot + hs * 0.45, bz * 0.40
    for i in range(3):
        fin = m.bone(f"fin{i}", (px, py, pz), "head", rotation=(0, 0, i * 120.0))
        fin.add(Cube((-half * 0.19, py, pz - hd * 0.46),
                     (half * 0.38, hh * 1.44, hd * 0.92), "robot_dark",
                     uv_scale=4, pivot=(px, py, pz), rotation=(-20, 0, 0)))
        fin.add(Cube((-half * 0.13, py + hh * 1.34, pz - hd * 0.30),
                     (half * 0.26, hh * 0.26, hd * 0.44), "optic",
                     uv_scale=6, pivot=(px, py, pz), rotation=(-20, 0, 0)))
    return m


# ===========================================================================
#  MRD 隊員 — センチネルの巨大さを測る物差し
# ===========================================================================
def build_mrd() -> RiggedModel:
    """全身を装甲で覆うので ``flesh()`` は使わない。素肌は一切出ない。"""
    m = _model("mrd_trooper", 3, atlas=(512, 512))
    rig = _rig(m, "mrd_trooper")
    L = rig.L
    hw, hh, hd = L.head_w, L.head_h, L.head_d
    ch = L.chest_top - L.chest_bot

    head = rig.b("head")
    head.add(Cube((-hw * 0.64, L.chin + hh * 0.12, -hd * 0.64),
                  (hw * 1.28, hh * 0.94, hd * 1.24), "armor", uv_scale=5,
                  decals={"up": "rivets"}))
    head.add(Cube((-hw * 0.66, L.chin + hh * 0.60, -hd * 0.76),
                  (hw * 1.32, hh * 0.16, hd * 0.26), "armor", uv_scale=5,
                  rotation=(17, 0, 0)))                       # 庇
    head.add(Cube((-hw * 0.60, L.chin + hh * 0.32, -hd * 0.72),
                  (hw * 1.20, hh * 0.30, hd * 0.16), "goggle", uv_scale=6,
                  decals={"north": "goggles"}))
    head.add(Cube((-hw * 0.46, L.chin, -hd * 0.56),
                  (hw * 0.92, hh * 0.36, hd * 0.92), "cloth", uv_scale=5))
    # 肩の照明。左右非対称のこの一個で、遠くからでも MRD と判る
    head.add(Cube((hw * 0.62, L.chin + hh * 0.44, -hd * 0.40),
                  (hw * 0.34, hh * 0.34, hd * 0.52), "hazard", uv_scale=6,
                  rotation=(0, 0, -14), decals={"north": "mag_core"}))

    chest = rig.b("chest")
    chest.add(Cube((-L.chest_w * 0.54, L.chest_bot + ch * 0.24,
                    -L.chest_d * 0.56),
                   (L.chest_w * 1.08, ch * 0.80, L.chest_d * 1.12), "armor",
                   uv_scale=4, decals={"north": "rivets"}))
    chest.add(Cube((-L.chest_w * 0.30, L.chest_bot + ch * 0.36,
                    -L.chest_d * 0.66),
                   (L.chest_w * 0.60, ch * 0.40, L.chest_d * 0.16), "hazard",
                   uv_scale=5, decals={"north": "hazard_stripe"}))
    chest.add(Cube((-L.chest_w * 0.40, L.chest_bot + ch * 0.30,
                    L.chest_d * 0.52),
                   (L.chest_w * 0.80, ch * 0.66, L.chest_d * 0.34), "cable",
                   uv_scale=4, decals={"south": "vent_grill"}))
    put_locators(chest, core=(0, L.chest_bot + ch * 0.60, -L.chest_d * 0.70))

    body = rig.b("body")
    body.add(Cube((-L.waist_w * 0.52, L.abdomen_bot, -L.waist_d * 0.54),
                  (L.waist_w * 1.04, L.chest_bot - L.abdomen_bot,
                   L.waist_d * 1.08), "suit", uv_scale=4))
    body.add(Cube((-L.hip_w * 0.54, L.pelvis_bot, -L.waist_d * 0.58),
                  (L.hip_w * 1.08, L.abdomen_bot - L.pelvis_bot,
                   L.waist_d * 1.16), "cloth", uv_scale=4,
                  decals={"north": "rivets"}))

    at, ft = L.arm_t, L.forearm_t
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - at / 2)
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - at * 0.74, L.shoulder_y - at * 1.10, -at * 0.74),
            (at * 1.48, at * 1.16, at * 1.48), "armor", uv_scale=4,
            pivot=(cx, L.shoulder_y, 0), rotation=(0, 0, -sgn * 8)))
        rig.b(f"{side}Arm").add(Cube(
            (cx - at * 0.50, L.elbow_y, -at * 0.50),
            (at, L.shoulder_y - L.elbow_y, at), "suit", uv_scale=4))
        rig.b(f"{side}Forearm").add(Cube(
            (cx - ft * 0.60, L.wrist_y, -ft * 0.60),
            (ft * 1.20, L.elbow_y - L.wrist_y, ft * 1.20), "armor",
            uv_scale=4))
        rig.b(f"{side}Hand").add(Cube(
            (cx - ft * 0.56, L.wrist_y - L.hand_l, -ft * 0.46),
            (ft * 1.12, L.hand_l, ft * 0.92), "cloth", uv_scale=4))
        lx = sgn * L.stance
        rig.b(f"{side}Leg").add(Cube(
            (lx - L.thigh_t * 0.54, L.knee_y, -L.thigh_t * 0.54),
            (L.thigh_t * 1.08, L.hip_y - L.knee_y, L.thigh_t * 1.08), "suit",
            uv_scale=4))
        rig.b(f"{side}Shin").add(Cube(
            (lx - L.shin_t * 0.62, L.ankle_y, -L.shin_t * 0.70),
            (L.shin_t * 1.24, L.knee_y - L.ankle_y, L.shin_t * 1.30), "armor",
            uv_scale=4))
        rig.b(f"{side}Foot").add(Cube(
            (lx - L.shin_t * 0.66, 0, -L.foot_l * 0.60),
            (L.shin_t * 1.32, L.foot_h * 1.20, L.foot_l * 1.00), "cloth",
            uv_scale=4))
    return m


# ===========================================================================
#  小物 — 技の見た目そのもの
# ===========================================================================
#  作りの決まりごと:
#    * 投射体は ``hull``（静止）と ``body``（prop.spin が回す）に分ける。
#      進行方向 −Z へ伸びた芯を hull に置き、body には磁力に引かれて付き従う
#      小片だけを入れる。全部を body に入れると、槍が横倒しに回って遅く見える。
#    * 芯は必ず白（``visor``）に寄せ、技の基調色は殻の一段だけに使う（DIRECTION §2-2）。
#    * cube は 1 体 24 以内。大きく見せたい物ほど、少ない cube を大きく置く。
# ===========================================================================
def _prop(key: str, uv_scale: int, bounds, atlas=(256, 256),
          offset=(0, 0, 0)) -> RiggedModel:
    return RiggedModel(K.geo(key), uv_scale=uv_scale, visible_bounds=bounds,
                       vb_offset=offset, max_atlas=atlas)


def build_metal_shard() -> Model:
    """鉄片。引き千切られた鉄板を、磁力が矢のように前へ向けている。"""
    m = _prop("metal_shard", 5, (1.3, 1.0))
    hull = m.bone("hull", (0, 0, 0))
    hull.add(Cube((-0.85, -0.85, -9.4), (1.7, 1.7, 6.8), "steel"))   # 明るい穂先
    hull.add(Cube((-1.6, -1.6, -3.4), (3.2, 3.2, 6.6), "shard"))
    hull.add(Cube((-2.9, -0.55, -1.6), (5.8, 1.1, 5.4), "shard",
                  inflate=-0.35, rotation=(0, 0, 9)))                # 水平のヒレ
    hull.add(Cube((-0.55, -2.9, -1.2), (1.1, 5.8, 4.6), "shard",
                  inflate=-0.35, rotation=(0, 0, 6)))                # 垂直のヒレ
    # 尾の磁力。動かしている力が見えないと、ただの落下物になる
    hull.add(Cube((-1.35, -1.35, 3.4), (2.7, 2.7, 1.6), "magnet",
                  uv_scale=8, decals={"south": "mag_core"}))
    body = m.bone("body", (0, 0, 0))
    for i in range(3):
        a = i * 2 * math.pi / 3
        body.add(Cube((3.4 * math.cos(a) - 0.9, 3.4 * math.sin(a) - 0.5, -0.4),
                      (1.8, 1.0, 2.6), "shard", uv_scale=6,
                      rotation=(i * 31, i * 24, math.degrees(a))))
    put_locators(hull, tip=(0, 0, -9.4))
    m.pack()
    return m


def build_orbit_shard() -> Model:
    """段階 3 で 3 体を周回させるので、ここだけは徹底して軽く（6 cube）。"""
    m = _prop("orbit_shard", 6, (1.0, 1.0))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-2.4, -2.6, -4.0), (4.8, 5.2, 8.0), "shard"))
    b.add(Cube((-1.2, -4.2, -2.6), (2.4, 8.4, 5.2), "steel", inflate=-0.6,
               rotation=(7, 0, 17)))
    b.add(Cube((-3.6, -1.4, -2.2), (7.2, 2.8, 4.4), "shard", inflate=-0.6,
               rotation=(0, 12, -24)))
    b.add(Cube((-0.9, -0.9, -0.9), (1.8, 1.8, 1.8), "magnet", uv_scale=8,
               decals={"north": "mag_core", "south": "mag_core"}))
    m.pack()
    return m


def build_debris() -> Model:
    """瓦礫。剥き出しの鉄筋を刺すと、一目で「壊された物」に見える。"""
    m = _prop("debris", 3, (1.6, 1.6))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-3.6, -3.0, -3.4), (7.2, 6.0, 6.8), "rock"))
    b.add(Cube((-6.6, -2.4, -2.6), (13.2, 4.8, 5.2), "rock", inflate=-0.8,
               rotation=(0, 13, 9)))
    b.add(Cube((-2.8, -6.4, -2.8), (5.6, 12.8, 5.6), "rock", inflate=-1.0,
               rotation=(11, 0, -16)))
    b.add(Cube((-2.4, -2.4, -6.8), (4.8, 4.8, 13.6), "stone", inflate=-0.9,
               rotation=(-8, 17, 0)))
    # 鉄筋。細い線が一本あるだけで塊のスケールが読める
    for rot, org in (((0, 0, 62), (-1.0, 2.0, -1.0)),
                     ((24, 0, -48), (-0.9, 1.4, 1.0)),
                     ((-14, 36, 0), (0.6, -3.6, -0.9))):
        b.add(Cube(org, (1.8, 9.6, 1.8), "shard", uv_scale=5, inflate=-0.45,
                   rotation=rot))
    m.pack()
    return m


def _bolt(key: str, shell: str, glyph: str, length: float, r: float,
          hexed: bool) -> Model:
    """弾は前後に長く。丸い玉は、どれだけ速く飛ばしても速く見えない。"""
    m = _prop(key, 4, (1.4, 1.2), atlas=(512, 512))
    hull = m.bone("hull", (0, 0, 0))
    # 白い芯を殻より前へ出す。撃発の白 → 縁の基調色、という順序を立体で作る
    hull.add(Cube((-r * 0.44, -r * 0.44, -length * 0.74),
                  (r * 0.88, r * 0.88, length * 0.62), "visor", uv_scale=6,
                  decals={"north": "mag_core"}))
    if hexed:
        # 六角柱: 細長い板を 60 度ずつ回して重ねる
        for i in range(3):
            hull.add(Cube((-r, -r * 0.52, -length * 0.34),
                          (r * 2, r * 1.04, length * 0.78), shell,
                          uv_scale=4, inflate=-0.2,
                          rotation=(0, 0, i * 60),
                          decals={"north": glyph} if i == 0 else None))
    else:
        hull.add(Cube((-r * 0.92, -r * 0.92, -length * 0.34),
                      (r * 1.84, r * 1.84, length * 0.74), shell, uv_scale=4,
                      decals={"north": glyph, "east": "flame_lick",
                              "west": "flame_lick"}))
        # 後ろへ流れる炎の舌
        for i, ang in enumerate((28, -28, 0)):
            hull.add(Cube((-r * 0.34, -r * 0.34, length * 0.36),
                          (r * 0.68, r * 0.68, length * 0.44), "flame",
                          uv_scale=4, inflate=-0.15,
                          pivot=(0, 0, length * 0.36),
                          rotation=(ang if i < 2 else 0, 0,
                                    0 if i < 2 else 34)))
    body = m.bone("body", (0, 0, 0))
    for i in range(3):
        a = i * 2 * math.pi / 3
        body.add(Cube((r * 1.25 * math.cos(a) - 0.7,
                       r * 1.25 * math.sin(a) - 0.7, -1.0),
                      (1.4, 1.4, 3.4), "energy", uv_scale=6,
                      rotation=(0, 0, math.degrees(a))))
    m.pack()
    return m


def build_sentinel_beam() -> Model:
    """センチネルのビーム。3 ブロック分の長さで初めて「線」に見える。"""
    m = _prop("sentinel_beam", 2, (3.4, 1.4), atlas=(512, 512))
    hull = m.bone("hull", (0, 0, 0))
    # 白熱の芯。側面に vent_grill を貼ると、長さ方向へ発光の筋が通る
    hull.add(Cube((-1.2, -1.2, -26.0), (2.4, 2.4, 52.0), "visor", uv_scale=3,
                  decals={"east": "vent_grill", "west": "vent_grill",
                          "up": "vent_grill", "down": "vent_grill"}))
    hull.add(Cube((-2.8, -2.8, -21.0), (5.6, 5.6, 42.0), "base", uv_scale=2,
                  inflate=-0.6))
    hull.add(Cube((-1.5, -1.5, -30.5), (3.0, 3.0, 5.2), "visor", uv_scale=4,
                  inflate=-0.5))                                   # 尖った先端
    hull.add(Cube((-4.6, -4.6, 12.0), (9.2, 9.2, 10.0), "energy", uv_scale=2,
                  inflate=-2.2, decals={"south": "mag_core"}))     # 撃った側の火口
    body = m.bone("body", (0, 0, 0))
    for i in range(3):
        body.add(Cube((-4.4, -0.7, -14.0), (8.8, 1.4, 26.0), "energy",
                      uv_scale=2, inflate=-0.5, rotation=(0, 0, i * 60)))
    m.pack()
    return m


def build_barrier_dome() -> Model:
    """磁力障壁。六角面を **1 枚ずつ独立ボーン** にしてある。

    §5-5 の「被弾した六角だけ白く割れる」を実現するには、面ごとに
    向きと可視を触れる必要がある。緯度は cube の X 回転、経度はボーン の Y 回転で
    与える —— 一個の cube 回転では XYZ の順が固定で、経度が先に掛かってしまう。
    """
    R, cy = 42.0, 36.0
    m = _prop("barrier_dome", 1, (6.4, 6.4), atlas=(512, 512),
              offset=(0, 2.2, 0))
    body = m.bone("body", (0, 0, 0))
    # (緯度, 枚数, 半幅, 半高, 経度のずらし)
    rings = ((-34.0, 7, 15.6, 13.0, 0.0), (0.0, 8, 16.4, 13.4, 22.5),
             (36.0, 5, 19.6, 13.8, 0.0), (70.0, 3, 12.8, 16.0, 60.0))
    n = 0
    for lat, count, pw, ph, off in rings:
        y = cy + R * math.sin(math.radians(lat))
        z = -R * math.cos(math.radians(lat))
        for i in range(count):
            yaw = off + 360.0 * i / count
            bone = m.bone(f"hex{n}", (0, cy, 0), "body", rotation=(0, yaw, 0))
            bone.add(Cube((-pw, y - ph, z - 1.2), (pw * 2, ph * 2, 2.4),
                          "plate", uv_scale=1,
                          rotation=(-lat, 0, 0),
                          decals={"north": "hex_sigil", "south": "mag_lines"}))
            n += 1
    put_locators(body, core=(0, cy, 0))
    m.pack()
    return m


def build_ruin_sphere() -> Model:
    """磁界の棺。白熱した核を、圧し潰された鉄板が三重に取り巻く。

    破片を立方体で散らすと紙吹雪にしかならない。球面に **接する板** として
    並べ、隙間から核を覗かせると「潰されている最中」に見える。
    板は中心を pivot にした Y 回転一つで置けるので、ボーンを増やさずに済む。

    ``core`` は prop.pulse が scale を脈打たせるボーンなので、殻もその子にして
    一緒に呼吸させる。半径が伸び縮みすると圧縮の途中に見える。
    """
    R = 38.0
    m = _prop("ruin_sphere", 1, (6.6, 6.6), atlas=(512, 512))
    core = m.bone("core", (0, 0, 0))
    core.add(Cube((-17, -17, -17), (34, 34, 34), "visor", uv_scale=2,
                  decals={"north": "mag_core", "south": "mag_core"}))
    # 磁極。核を貫く二本の軸が、球を「握られている物」に見せる
    for axis in (0, 1):
        size = [6.0, 6.0, 6.0]
        size[axis] = R * 1.7
        core.add(Cube([-v / 2 for v in size], size, "energy", uv_scale=2))

    def plates(bone, count, phase, w, h):
        for i in range(count):
            yaw = phase + 360.0 * i / count
            bone.add(Cube((-w / 2, -h / 2, -R - 2.5), (w, h, 5.0), "shard",
                          uv_scale=1, pivot=(0, 0, 0),
                          rotation=(0, yaw, 0),
                          decals={"north": "panel_seam"}))

    # 赤道の環。prop.pulse が Y に回すボーン
    ring = m.bone("ring", (0, 0, 0), "core")
    plates(ring, 6, 0.0, 26.0, 24.0)
    # 傾いた二枚の殻。角度をずらすと球殻の網目が二重に見える
    for s, (tilt, spin) in enumerate(((62, 24), (-52, 71))):
        shell = m.bone(f"shell{s}", (0, 0, 0), "core", rotation=(tilt, spin, 0))
        plates(shell, 4, 22.0 * (s + 1), 24.0, 22.0)
    put_locators(core, core=(0, 0, 0))
    m.pack()
    return m


def build_steel_platform() -> Model:
    """鋼鉄の玉座。乗る物なので甲板を 2.5 ブロック幅まで広げ、背もたれを付ける。

    背もたれの一枚があるかないかで「足場」と「玉座」が分かれる。
    """
    m = _prop("steel_platform", 2, (3.4, 2.2), atlas=(512, 512),
              offset=(0, 0.5, 0))
    body = m.bone("body", (0, 0, 0))
    body.add(Cube((-20, 0.6, -20), (40, 3.4, 40), "steel", uv_scale=2,
                  decals={"up": "panel_seam"}))
    # 45 度ずらした二枚目で八角形に見せる。輪郭が丸いほど「浮いている」。
    # 甲板より **低く** 置かないと、明るい踏み面を自分で隠してしまう。
    body.add(Cube((-16, -0.2, -16), (32, 3.4, 32), "shard", uv_scale=2,
                  rotation=(0, 45, 0)))
    body.add(Cube((-15, -3.4, -15), (30, 3.6, 30), "shard", uv_scale=2,
                  decals={"down": "rivets"}))
    for ang in (26, -26):
        body.add(Cube((-2.4, -6.2, -14), (4.8, 3.4, 28), "cable", uv_scale=2,
                      rotation=(0, ang, 0)))
    body.add(Cube((-4.5, 3.4, -4.5), (9.0, 3.0, 9.0), "magnet", uv_scale=4,
                  decals={"up": "mag_core"}))
    # 玉座の背と肘掛け
    body.add(Cube((-11, 4.0, 14.5), (22, 12.5, 3.6), "steel", uv_scale=2,
                  rotation=(13, 0, 0), decals={"north": "panel_seam"}))
    for sgn in (-1, 1):
        body.add(Cube((sgn * 13 - 2.0, 3.4, 2.0), (4.0, 8.0, 14.0), "shard",
                      uv_scale=2, pivot=(sgn * 13, 3.4, 9.0),
                      rotation=(0, 0, -sgn * 9)))
    ring = m.bone("ring", (0, 0, 0), "body")
    for i in range(6):
        a = i * 2 * math.pi / 6
        ring.add(Cube((24 * math.cos(a) - 2.4, -6.0, 24 * math.sin(a) - 2.4),
                      (4.8, 3.0, 4.8), "energy", uv_scale=3,
                      rotation=(0, -math.degrees(a), 0)))
    put_locators(body, core=(0, 5.0, 0))
    m.pack()
    return m


def build_iron_cage() -> Model:
    """鋼鉄拘束。標的より頭ひとつぶん高くし、格子を内側へ倒して覆い被せる。

    垂直の筒だと「囲い」で終わる。上を絞ると初めて「檻」になる。
    """
    m = _prop("iron_cage", 2, (2.6, 3.6), atlas=(512, 512), offset=(0, 1.4, 0))
    body = m.bone("body", (0, 0, 0))
    R, H = 13.5, 46.0
    for i in range(8):
        yaw = 360.0 * i / 8
        bar = m.bone(f"bar{i}", (0, 0, 0), "body", rotation=(0, yaw, 0))
        # 支柱。X に倒して先端を内側へ寄せる（正の値で上が −Z 側＝内へ）
        bar.add(Cube((-2.0, 1.0, -R - 2.0), (4.0, H, 4.0), "shard",
                     uv_scale=3, pivot=(0, 1.0, -R),
                     rotation=(-6, 0, 0)))
        # 足元の座金。地面に噛んでいる感じが出る
        bar.add(Cube((-3.2, 0, -R - 3.2), (6.4, 3.2, 6.4), "steel",
                     uv_scale=3, decals={"up": "rivets"}))
    # 天冠。交点をここに集めると、溶接火花（bind_weld）の置き場になる
    for i in range(6):
        a = i * 2 * math.pi / 6
        body.add(Cube((8.6 * math.cos(a) - 2.6, H - 1.0,
                       8.6 * math.sin(a) - 2.6), (5.2, 4.2, 5.2), "magnet",
                      uv_scale=3, rotation=(0, -math.degrees(a), 0),
                      decals={"up": "mag_core"}))
    put_locators(body, core=(0, H * 0.5, 0))
    m.pack()
    return m


PROPS = {
    "metal_shard": (build_metal_shard, "shard"),
    "orbit_shard": (build_orbit_shard, "shard"),
    "debris": (build_debris, "debris"),
    "hex_bolt": (lambda: _bolt("hex_bolt", "base", "hex_sigil", 21.0, 2.9,
                               True), "energy_crimson"),
    "fire_bolt": (lambda: _bolt("fire_bolt", "base", "mag_core", 22.0, 3.0,
                                False), "energy_fire"),
    "sentinel_beam": (build_sentinel_beam, "energy_orange"),
    "barrier_dome": (build_barrier_dome, "energy_violet"),
    "ruin_sphere": (build_ruin_sphere, "energy_violet"),
    "steel_platform": (build_steel_platform, "shard"),
    "iron_cage": (build_iron_cage, "shard"),
}


def main() -> None:
    print("enemies:")
    emit(build_sentinel("sentinel"), colours.SENTINEL, "sentinel", seed=301)
    emit(build_sentinel("prime_sentinel", prime=True), colours.PRIME_SENTINEL,
         "prime_sentinel", seed=302)
    emit(build_mrd(), colours.MRD, "mrd_trooper", seed=303)
    emit(build_drone(), colours.SENTINEL, "sentinel_drone", seed=304)

    print("props:")
    for key, (fn, pal) in PROPS.items():
        emit(fn(), colours.ALL[pal], key, seed=abs(hash(key)) % 8000 + 11)


if __name__ == "__main__":
    main()
