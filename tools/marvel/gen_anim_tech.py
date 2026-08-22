# -*- coding: utf-8 -*-
"""技のアニメーション。本作で一番手をかけるところ。

作り方の指針
------------
1. **予備動作 → 溜め → 撃発 → 伸び → 残心** の五拍で組む。
   撃発の一拍だけを極端に短くすると、同じ角度でも「速く」見える。
2. 撃発の瞬間は *行き過ぎさせる*（オーバーシュート）。次のキーで戻す。
   これだけで手描きアニメの「詰め」に近い切れ味が出る。
3. 腕だけ動かさない。腰の捻り・胸の反り・首の向き・マントの遅れを必ず添える。
   身体の連動が無い技は、どれだけ速くても軽く見える。
4. マントは常に **一拍遅れて** 動く。慣性の表現はここが一番効く。

角度の目安（腕）
    0    真下に垂れる
  -90    正面へ水平
 -165    ほぼ真上
"""
from __future__ import annotations

import _path  # noqa: F401

import contract as K  # noqa: E402
from anim import clip, keys, merge  # noqa: E402
from common import animations_doc, write_json  # noqa: E402

A: dict = {}


# ===========================================================================
#  組み立てヘルパ
# ===========================================================================
def _tag(t: float) -> str:
    return "t" + f"{t:g}".replace(".", "_").replace("-", "m")


def build(frames, extra=None) -> dict:
    """``[(秒, {ボーン: [x,y,z] または {"r":..,"p":..,"s":..}}), ...]`` を束ねる。

    途中のキーで触れなかったボーンは、そのキーでは補間されるだけなので、
    「動かしたい瞬間だけ書く」ことができる。
    """
    per_bone: dict = {}
    for t, pose in frames:
        for bone, value in pose.items():
            ch = per_bone.setdefault(bone, {})
            if isinstance(value, dict):
                if "r" in value:
                    ch.setdefault("rotation", {})[_tag(t)] = list(value["r"])
                if "p" in value:
                    ch.setdefault("position", {})[_tag(t)] = list(value["p"])
                if "s" in value:
                    ch.setdefault("scale", {})[_tag(t)] = list(value["s"])
            else:
                ch.setdefault("rotation", {})[_tag(t)] = list(value)
    out = {}
    for bone, channels in per_bone.items():
        out[bone] = {name: keys(**frames_) for name, frames_ in channels.items()}
    if extra:
        out = merge(out, extra)
    return out


#: マントの動き方の型。(遅れ秒, 最大角, 戻り角)
CAPE_PROFILES = {
    "whip":   (0.06, 46, 8),    # 前へ踏み込む技 — 後ろへ大きく煽られる
    "flare":  (0.08, 62, 12),   # 両手を掲げる技 — 真上へ広がる
    "settle": (0.05, 18, 4),    # 動きの小さい技
    "swirl":  (0.10, 38, -10),  # 回る技 — 一度巻き込んでから開く
}


def cape(profile: str, length: float, segments: int = 4) -> dict:
    """技の長さに合わせてマントの遅れを自動生成する。"""
    lag, peak, back = CAPE_PROFILES[profile]
    out = {}
    for i in range(segments):
        d = lag * (i + 1)
        amp = peak * (0.55 + 0.15 * i)
        rest = 4 + i * 3
        frames = {
            _tag(0.0): [rest, 0, 0],
            _tag(min(length, d + length * 0.22)): [rest + amp, 0, 0],
            _tag(min(length, d + length * 0.52)): [rest - back, 0, 0],
            _tag(length): [rest, 0, 0],
        }
        out[f"cape{i}"] = {"rotation": keys(**frames)}
    return out


def tech(group: str, name: str, length: float, frames, cape_profile="whip",
         particles=None, loop=False, sounds=None) -> None:
    body = build(frames, cape(cape_profile, length))
    A[K.anim(group, name)] = clip(body, length=length, loop=loop,
                                  particles=particles, sound=sounds)


def P(**kw):
    """`P(rightArm=[-90,0,0], body=[0,20,0])` を素直に書くための糖衣。"""
    return kw


# ===========================================================================
#  マグニートーの技 15
# ===========================================================================

# --- 1. 磁力斥力 ------------------------------------------------------------
#  溜めで両手を胸元へ引き寄せ、撃発で一気に押し出す。腰から先に回す。
tech("tech", "repulse", 0.86, [
    (0.00, P(body=[0, 0, 0], chest=[0, 0, 0], head=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
    (0.14, P(body=[-6, 26, 0], chest=[-8, 14, 0], head=[-10, -14, 0],
             rightArm=[-52, 34, -10], leftArm=[-52, -34, 10],
             rightForearm=[-88, 0, 0], leftForearm=[-88, 0, 0],
             rightLeg=[-14, 0, 0], leftLeg=[10, 0, 0])),
    (0.26, P(body=[-10, 34, 0], chest=[-12, 18, 0],
             rightArm=[-46, 40, -12], leftArm=[-46, -40, 12],
             rightForearm=[-104, 0, 0], leftForearm=[-104, 0, 0])),
    (0.36, P(body=[10, -20, 0], chest=[14, -12, 0], head=[6, 8, 0],
             rightArm=[-96, -12, -6], leftArm=[-96, 12, 6],
             rightForearm=[-6, 0, 0], leftForearm=[-6, 0, 0],
             rightLeg=[18, 0, 0], leftLeg=[-14, 0, 0])),
    (0.48, P(body=[6, -12, 0], chest=[8, -6, 0],
             rightArm=[-84, -8, -6], leftArm=[-84, 8, 6],
             rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0])),
    (0.86, P(body=[0, 0, 0], chest=[0, 0, 0], head=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], "whip", particles={
    "0.30": {"effect": K.part("mag_field"), "locator": "rightHand"},
    "0.36": {"effect": K.part("repulse_wave")},
    "0.38": {"effect": K.part("mag_push")},
})

# --- 2. 磁力引力 ------------------------------------------------------------
#  掌を開いて前へ、指を握りながら引き込む。上体は後ろへ倒れる。
tech("tech", "attract", 0.92, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], body=[0, 0, 0])),
    (0.16, P(body=[8, -14, 0], chest=[6, -8, 0], head=[-4, 10, 0],
             rightArm=[-98, -16, -6], leftArm=[-72, 22, 8],
             rightForearm=[-4, 0, 0], leftForearm=[-26, 0, 0],
             rightHand=[-24, 0, 0])),
    (0.34, P(body=[6, -10, 0], rightArm=[-102, -12, -6],
             rightHand=[-30, 0, 0], leftArm=[-76, 18, 8])),
    (0.52, P(body=[-14, 20, 0], chest=[-10, 12, 0], head=[8, -12, 0],
             rightArm=[-42, 30, -14], leftArm=[-40, -26, 14],
             rightForearm=[-96, 0, 0], leftForearm=[-92, 0, 0],
             rightHand=[16, 0, 0], rightLeg=[-16, 0, 0], leftLeg=[12, 0, 0])),
    (0.66, P(body=[-8, 12, 0], rightArm=[-48, 24, -12],
             rightForearm=[-86, 0, 0])),
    (0.92, P(body=[0, 0, 0], chest=[0, 0, 0], head=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightHand=[0, 0, 0], rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], "swirl", particles={
    "0.18": {"effect": K.part("attract_funnel")},
    "0.50": {"effect": K.part("mag_pull")},
})

# --- 3. 金属剥奪 ------------------------------------------------------------
#  片手を突き出して握り、真横へ払う。剥ぎ取る動作。
tech("tech", "disarm", 0.78, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.12, P(body=[0, 30, 0], chest=[-6, 16, 0], head=[0, -18, 0],
             rightArm=[-58, 46, -8], rightForearm=[-58, 0, 0],
             leftArm=[-14, 0, 10])),
    (0.24, P(body=[0, 18, 0], rightArm=[-94, 16, -6], rightForearm=[-8, 0, 0],
             rightHand=[-18, 0, 0], head=[0, -8, 0])),
    (0.32, P(rightHand=[10, 0, 0], rightArm=[-96, 12, -6])),
    (0.44, P(body=[4, -34, 0], chest=[6, -20, 0], head=[0, 22, 0],
             rightArm=[-76, -58, -22], rightForearm=[-30, 0, 0],
             rightHand=[6, 0, 0], leftArm=[-8, 0, 16])),
    (0.56, P(body=[2, -20, 0], rightArm=[-56, -40, -16])),
    (0.78, P(body=[0, 0, 0], chest=[0, 0, 0], head=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], rightHand=[0, 0, 0])),
], "whip", particles={
    "0.26": {"effect": K.part("disarm_flash"), "locator": "rightHand"},
    "0.44": {"effect": K.part("metal_rip")},
})

# --- 4. 磁界斬 --------------------------------------------------------------
#  刺突。上体ごと前へ射出する。撃発は 0.08 秒だけ。
tech("tech", "lance", 0.74, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], body=[0, 0, 0])),
    (0.16, P(body={"r": [-4, 42, 0], "p": [0, 0, 2.0]}, chest=[-10, 22, 0],
             head=[-6, -24, 0], rightArm=[-30, 56, -12],
             rightForearm=[-118, 0, 0], leftArm=[-24, -30, 12],
             rightLeg=[-18, 0, 0])),
    (0.24, P(body={"r": [-6, 46, 0], "p": [0, 0, 2.6]},
             rightArm=[-26, 60, -12], rightForearm=[-126, 0, 0])),
    (0.32, P(body={"r": [14, -30, 0], "p": [0, 0, -3.4]}, chest=[16, -18, 0],
             head=[8, 16, 0], rightArm=[-100, -20, -4],
             rightForearm=[2, 0, 0], leftArm=[-40, 24, 14],
             rightLeg=[24, 0, 0], leftLeg=[-18, 0, 0])),
    (0.42, P(body={"r": [8, -18, 0], "p": [0, 0, -1.6]},
             rightArm=[-92, -14, -4])),
    (0.74, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], "whip", particles={
    "0.26": {"effect": K.part("mag_glyph"), "locator": "rightHand"},
    "0.32": {"effect": K.part("lance_streak")},
})

# --- 5. 鉄片嵐 --------------------------------------------------------------
#  両腕を広げて周囲の金属を巻き上げ、一気に前へ叩き込む。
tech("tech", "shard_storm", 1.42, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], body=[0, 0, 0])),
    (0.20, P(body={"r": [-10, 0, 0], "p": [0, 1.0, 0]}, chest=[-14, 0, 0],
             head=[-22, 0, 0], rightArm=[-104, 0, -46],
             leftArm=[-104, 0, 46], rightForearm=[-16, 0, 0],
             leftForearm=[-16, 0, 0])),
    (0.46, P(body={"r": [-14, 0, 0], "p": [0, 1.6, 0]},
             rightArm=[-132, 0, -34], leftArm=[-132, 0, 34],
             head=[-26, 0, 0])),
    (0.72, P(body={"r": [-16, -8, 0], "p": [0, 1.8, 0]},
             rightArm=[-150, 0, -22], leftArm=[-150, 0, 22],
             rightForearm=[-24, 0, 0], leftForearm=[-24, 0, 0])),
    (0.88, P(body={"r": [18, 12, 0], "p": [0, -0.6, 0]}, chest=[20, 6, 0],
             head=[14, 0, 0], rightArm=[-84, -10, -8], leftArm=[-84, 10, 8],
             rightForearm=[-4, 0, 0], leftForearm=[-4, 0, 0],
             rightLeg=[16, 0, 0], leftLeg=[-12, 0, 0])),
    (1.06, P(body={"r": [10, 6, 0], "p": [0, 0, 0]},
             rightArm=[-78, -6, -8], leftArm=[-78, 6, 8])),
    (1.42, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], "flare", particles={
    "0.24": {"effect": K.part("mag_aura")},
    "0.50": {"effect": K.part("storm_swirl")},
    "0.88": {"effect": K.part("shard_burst")},
})

# --- 6. 磁力障壁 ------------------------------------------------------------
#  踏み込んで腕を交差、展開後はその形を保つ。
tech("tech", "barrier", 1.10, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.12, P(body={"r": [10, 0, 0], "p": [0, -1.4, 0]}, chest=[-8, 0, 0],
             rightArm=[-40, 26, -20], leftArm=[-40, -26, 20],
             rightForearm=[-70, 0, 30], leftForearm=[-70, 0, -30],
             rightLeg=[-20, 0, 0], leftLeg=[16, 0, 0])),
    (0.26, P(body={"r": [4, 0, 0], "p": [0, -0.8, 0]},
             rightArm=[-62, 40, -28], leftArm=[-62, -40, 28],
             rightForearm=[-86, 0, 46], leftForearm=[-86, 0, -46],
             head=[-6, 0, 0])),
    (0.42, P(rightArm=[-66, 34, -26], leftArm=[-66, -34, 26],
             rightForearm=[-82, 0, 42], leftForearm=[-82, 0, -42])),
    (0.86, P(rightArm=[-64, 36, -27], leftArm=[-64, -36, 27],
             rightForearm=[-84, 0, 44], leftForearm=[-84, 0, -44])),
    (1.10, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], "settle", particles={
    "0.26": {"effect": K.part("barrier_hex")},
    "0.30": {"effect": K.part("mag_ring")},
})

# --- 7. 鋼鉄拘束 ------------------------------------------------------------
#  両手で何かを掴み、絞り込むように捻る。
tech("tech", "iron_bind", 1.06, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.18, P(body=[-4, 0, 0], chest=[-8, 0, 0], head=[-12, 0, 0],
             rightArm=[-88, -18, -14], leftArm=[-88, 18, 14],
             rightForearm=[-22, 0, 0], leftForearm=[-22, 0, 0],
             rightHand=[-26, 0, 0], leftHand=[-26, 0, 0])),
    (0.38, P(rightArm=[-92, -30, -18], leftArm=[-92, 30, 18],
             rightForearm=[-16, 0, -24], leftForearm=[-16, 0, 24],
             rightHand=[12, 0, 0], leftHand=[12, 0, 0],
             body=[2, 0, 0])),
    (0.56, P(rightArm=[-84, -46, -22], leftArm=[-84, 46, 22],
             rightForearm=[-10, 0, -40], leftForearm=[-10, 0, 40],
             chest=[6, 0, 0], head=[8, 0, 0])),
    (0.74, P(rightArm=[-80, -38, -20], leftArm=[-80, 38, 20])),
    (1.06, P(body=[0, 0, 0], chest=[0, 0, 0], head=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightHand=[0, 0, 0], leftHand=[0, 0, 0])),
], "settle", particles={
    "0.22": {"effect": K.part("mag_glyph")},
    "0.56": {"effect": K.part("bind_weld")},
})

# --- 8. 磁気圧壊 ------------------------------------------------------------
#  掌を開いて突き出し、握り込む。握った瞬間に全身が縮む。
tech("tech", "crush", 1.16, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.16, P(body=[-4, -18, 0], chest=[-8, -10, 0], head=[-8, 12, 0],
             rightArm=[-102, -20, -6], rightForearm=[-2, 0, 0],
             rightHand=[-34, 0, 0], leftArm=[-26, 16, 10])),
    (0.38, P(rightArm=[-104, -18, -6], rightHand=[-38, 0, 0],
             body=[-2, -14, 0])),
    (0.54, P(rightHand=[20, 0, 0], rightForearm=[-16, 0, 0],
             rightArm=[-96, -14, -8], body={"r": [8, -8, 0], "p": [0, -1.2, 0]},
             chest=[10, -4, 0], head=[6, 6, 0],
             rightLeg=[-10, 0, 0], leftLeg=[8, 0, 0])),
    (0.68, P(rightHand=[26, 0, 0], rightForearm=[-24, 0, 0],
             rightArm=[-88, -12, -8], body={"r": [12, -6, 0], "p": [0, -1.8, 0]})),
    (0.86, P(rightHand=[12, 0, 0], rightArm=[-70, -8, -6],
             body={"r": [4, -2, 0], "p": [0, -0.6, 0]})),
    (1.16, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], rightHand=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], "settle", particles={
    "0.20": {"effect": K.part("mag_field"), "locator": "rightHand"},
    "0.54": {"effect": K.part("crush_implode")},
    "0.58": {"effect": K.part("crush_blood")},
})

# --- 9. 大地隆起 ------------------------------------------------------------
#  沈み込んでから、大地ごと引き上げる。溜めが一番長い技。
tech("tech", "uprising", 1.60, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.22, P(body={"r": [26, 0, 0], "p": [0, -3.2, 0]}, chest=[-12, 0, 0],
             head=[-26, 0, 0], rightArm=[-16, 0, -30], leftArm=[-16, 0, 30],
             rightForearm=[-92, 0, 0], leftForearm=[-92, 0, 0],
             rightLeg=[-34, 0, 0], leftLeg=[-34, 0, 0],
             rightShin=[54, 0, 0], leftShin=[54, 0, 0])),
    (0.52, P(body={"r": [30, 0, 0], "p": [0, -3.8, 0]},
             rightArm=[-12, 0, -26], leftArm=[-12, 0, 26],
             rightForearm=[-102, 0, 0], leftForearm=[-102, 0, 0])),
    (0.74, P(body={"r": [-12, 0, 0], "p": [0, 1.2, 0]}, chest=[-16, 0, 0],
             head=[-30, 0, 0], rightArm=[-118, 0, -30],
             leftArm=[-118, 0, 30], rightForearm=[-46, 0, 0],
             leftForearm=[-46, 0, 0], rightLeg=[-8, 0, 0], leftLeg=[-8, 0, 0],
             rightShin=[16, 0, 0], leftShin=[16, 0, 0])),
    (0.94, P(body={"r": [-22, 0, 0], "p": [0, 2.4, 0]},
             rightArm=[-164, 0, -12], leftArm=[-164, 0, 12],
             rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
             head=[-34, 0, 0], rightLeg=[0, 0, 0], leftLeg=[0, 0, 0],
             rightShin=[0, 0, 0], leftShin=[0, 0, 0])),
    (1.18, P(body={"r": [-16, 0, 0], "p": [0, 1.4, 0]},
             rightArm=[-156, 0, -14], leftArm=[-156, 0, 14])),
    (1.60, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
], "flare", particles={
    "0.30": {"effect": K.part("mag_dust")},
    "0.74": {"effect": K.part("uprising_soil")},
    "0.94": {"effect": K.part("uprising_pillar")},
})

# --- 10. EMPパルス ----------------------------------------------------------
#  こめかみへ指を当て、目を閉じ、一拍置いて弾ける。
tech("tech", "emp", 1.24, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.18, P(rightArm=[-142, -34, -8], rightForearm=[-84, 0, 42],
             head=[6, -14, 0], chest=[-4, -6, 0], body=[2, -8, 0])),
    (0.52, P(rightArm=[-148, -36, -8], rightForearm=[-88, 0, 46],
             head=[8, -16, 0], body=[4, -10, 0])),
    (0.66, P(rightArm=[-150, -36, -8], rightForearm=[-90, 0, 48],
             body={"r": [6, -10, 0], "p": [0, -0.8, 0]})),
    (0.76, P(rightArm=[-120, -16, -14], rightForearm=[-52, 0, 20],
             head=[-12, 0, 0], chest=[-14, 0, 0],
             body={"r": [-10, 0, 0], "p": [0, 1.4, 0]},
             leftArm=[-34, 0, 28])),
    (0.94, P(rightArm=[-84, -8, -10], rightForearm=[-26, 0, 8],
             body={"r": [-4, 0, 0], "p": [0, 0.4, 0]})),
    (1.24, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0])),
], "settle", particles={
    "0.30": {"effect": K.part("mag_glyph"), "locator": "head"},
    "0.76": {"effect": K.part("emp_wave")},
    "0.78": {"effect": K.part("emp_arc")},
})

# --- 11. 磁極反転 -----------------------------------------------------------
#  掌を上に向けたまま、腕をゆっくり回して反転させる。
tech("tech", "polarity", 1.44, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.22, P(rightArm=[-72, -22, -24], leftArm=[-72, 22, 24],
             rightForearm=[-64, 0, 0], leftForearm=[-64, 0, 0],
             rightHand=[-32, 0, 0], leftHand=[-32, 0, 0],
             body=[-4, 0, 0], chest=[-6, 0, 0])),
    (0.60, P(rightArm=[-88, -34, -18], leftArm=[-88, 34, 18],
             rightForearm=[-40, 0, 0], leftForearm=[-40, 0, 0],
             rightHand=[0, 0, 0], leftHand=[0, 0, 0],
             head=[-10, 0, 0], body={"r": [-8, 0, 0], "p": [0, 1.0, 0]})),
    (0.92, P(rightArm=[-104, -20, -12], leftArm=[-104, 20, 12],
             rightForearm=[-18, 0, 0], leftForearm=[-18, 0, 0],
             rightHand=[34, 0, 0], leftHand=[34, 0, 0],
             body={"r": [-12, 0, 0], "p": [0, 1.6, 0]}, chest=[-10, 0, 0])),
    (1.14, P(rightArm=[-96, -14, -12], leftArm=[-96, 14, 12],
             rightHand=[26, 0, 0], leftHand=[26, 0, 0])),
    (1.44, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightHand=[0, 0, 0], leftHand=[0, 0, 0])),
], "swirl", particles={
    "0.26": {"effect": K.part("mag_glyph")},
    "0.92": {"effect": K.part("polarity_field")},
})

# --- 12. 磁気飛行 -----------------------------------------------------------
#  離陸の一発。踏み切って全身を伸ばす。以降は magneto.hover が受け持つ。
tech("tech", "flight", 0.88, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.14, P(body={"r": [22, 0, 0], "p": [0, -2.6, 0]}, chest=[-10, 0, 0],
             rightArm=[-8, 0, -24], leftArm=[-8, 0, 24],
             rightForearm=[-62, 0, 0], leftForearm=[-62, 0, 0],
             rightLeg=[-28, 0, 0], leftLeg=[-28, 0, 0],
             rightShin=[46, 0, 0], leftShin=[46, 0, 0])),
    (0.32, P(body={"r": [-26, 0, 0], "p": [0, 3.4, 0]}, chest=[-14, 0, 0],
             head=[-24, 0, 0], rightArm=[-140, 0, -26],
             leftArm=[-140, 0, 26], rightForearm=[-10, 0, 0],
             leftForearm=[-10, 0, 0], rightLeg=[10, 0, 0], leftLeg=[10, 0, 0],
             rightShin=[0, 0, 0], leftShin=[0, 0, 0],
             rightFoot=[36, 0, 0], leftFoot=[36, 0, 0])),
    (0.54, P(body={"r": [-14, 0, 0], "p": [0, 2.6, 0]},
             rightArm=[-96, 0, -30], leftArm=[-96, 0, 30],
             head=[-12, 0, 0])),
    (0.88, P(body={"r": [-4, 0, 0], "p": [0, 2.0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[-16, 0, -18], leftArm=[-16, 0, 18],
             rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0],
             rightLeg=[6, 0, 0], leftLeg=[6, 0, 0],
             rightFoot=[26, 0, 0], leftFoot=[26, 0, 0])),
], "flare", particles={
    "0.30": {"effect": K.part("flight_burst")},
    "0.34": {"effect": K.part("levitate_dust")},
})

# --- 13. 鋼鉄の玉座 ---------------------------------------------------------
#  足元へ手をやり、鉄を組み上げてから腰を下ろす。
tech("tech", "throne", 1.30, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.20, P(body={"r": [22, 14, 0], "p": [0, -2.0, 0]}, chest=[-10, 8, 0],
             head=[-24, -10, 0], rightArm=[-30, 20, -18],
             rightForearm=[-56, 0, 0], leftArm=[-24, -16, 18],
             leftForearm=[-50, 0, 0])),
    (0.48, P(body={"r": [12, 8, 0], "p": [0, -1.0, 0]},
             rightArm=[-58, 12, -22], leftArm=[-52, -10, 22],
             rightForearm=[-34, 0, 0], leftForearm=[-30, 0, 0],
             head=[-14, -6, 0])),
    (0.76, P(body={"r": [-6, 0, 0], "p": [0, 1.6, 0]}, chest=[-4, 0, 0],
             rightArm=[-38, 0, -20], leftArm=[-38, 0, 20],
             rightForearm=[-40, 0, 0], leftForearm=[-40, 0, 0],
             rightLeg=[-40, 0, -4], leftLeg=[-40, 0, 4],
             rightShin=[46, 0, 0], leftShin=[46, 0, 0])),
    (1.02, P(body={"r": [-2, 0, 0], "p": [0, -1.6, 0]},
             rightArm=[-10, 0, -14], leftArm=[-10, 0, 14],
             rightForearm=[-46, 0, 0], leftForearm=[-46, 0, 0],
             rightLeg=[-72, 0, -4], leftLeg=[-72, 0, 4],
             rightShin=[74, 0, 0], leftShin=[74, 0, 0])),
    (1.30, P(body={"r": [-2, 0, 0], "p": [0, -3.0, 0]}, chest=[-4, 0, 0],
             head=[0, 0, 0], rightArm=[-8, 0, -14], leftArm=[-8, 0, 14],
             rightForearm=[-46, 0, 0], leftForearm=[-46, 0, 0],
             rightLeg=[-72, 0, -4], leftLeg=[-72, 0, 4],
             rightShin=[74, 0, 0], leftShin=[74, 0, 0])),
], "settle", particles={
    "0.24": {"effect": K.part("mag_dust")},
    "0.76": {"effect": K.part("throne_dust")},
})

# --- 14. 磁力視 -------------------------------------------------------------
#  兜に手を添え、静かに見渡す。動きは最小。
tech("tech", "sight", 1.36, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.20, P(rightArm=[-136, -30, -10], rightForearm=[-78, 0, 38],
             head=[-4, -10, 0], chest=[-2, -4, 0])),
    (0.52, P(rightArm=[-138, -32, -10], rightForearm=[-80, 0, 40],
             head=[-6, 26, 0], chest=[-2, 10, 0], body=[0, 6, 0])),
    (0.88, P(rightArm=[-138, -32, -10], rightForearm=[-80, 0, 40],
             head=[-6, -30, 0], chest=[-2, -12, 0], body=[0, -8, 0])),
    (1.10, P(rightArm=[-110, -20, -10], rightForearm=[-56, 0, 26],
             head=[0, 0, 0], chest=[0, 0, 0], body=[0, 0, 0])),
    (1.36, P(rightArm=[0, 0, -4], rightForearm=[0, 0, 0], head=[0, 0, 0])),
], "settle", particles={
    "0.24": {"effect": K.part("sight_ping"), "locator": "head"},
    "0.60": {"effect": K.part("mag_glyph"), "locator": "head"},
})

# --- 15. 磁界の棺（必殺技）---------------------------------------------------
#  最長・最大。掲げ → 収縮 → 静止（溜め切り）→ 振り下ろし。
tech("tech", "sphere", 3.20, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.24, P(body={"r": [16, 0, 0], "p": [0, -2.4, 0]}, chest=[-10, 0, 0],
             head=[-18, 0, 0], rightArm=[-22, 0, -34], leftArm=[-22, 0, 34],
             rightForearm=[-80, 0, 0], leftForearm=[-80, 0, 0],
             rightLeg=[-24, 0, 0], leftLeg=[-24, 0, 0],
             rightShin=[38, 0, 0], leftShin=[38, 0, 0])),
    (0.62, P(body={"r": [-18, 0, 0], "p": [0, 2.6, 0]}, chest=[-20, 0, 0],
             head=[-32, 0, 0], rightArm=[-158, 0, -20],
             leftArm=[-158, 0, 20], rightForearm=[-14, 0, 0],
             leftForearm=[-14, 0, 0], rightLeg=[4, 0, 0], leftLeg=[4, 0, 0],
             rightShin=[0, 0, 0], leftShin=[0, 0, 0],
             rightFoot=[30, 0, 0], leftFoot=[30, 0, 0])),
    (1.10, P(body={"r": [-24, 0, 0], "p": [0, 5.0, 0]},
             rightArm=[-170, 0, -8], leftArm=[-170, 0, 8],
             head=[-38, 0, 0], chest=[-24, 0, 0])),
    (1.70, P(body={"r": [-26, 0, 0], "p": [0, 6.2, 0]},
             rightArm=[-172, 0, -6], leftArm=[-172, 0, 6],
             rightForearm=[-6, 0, 0], leftForearm=[-6, 0, 0])),
    (2.10, P(body={"r": [-28, 0, 0], "p": [0, 6.6, 0]},
             rightArm=[-176, 0, -4], leftArm=[-176, 0, 4],
             head=[-42, 0, 0])),
    (2.28, P(body={"r": [30, 0, 0], "p": [0, 0.4, 0]}, chest=[26, 0, 0],
             head=[22, 0, 0], rightArm=[-46, -8, -10], leftArm=[-46, 8, 10],
             rightForearm=[-6, 0, 0], leftForearm=[-6, 0, 0],
             rightLeg=[20, 0, 0], leftLeg=[-16, 0, 0])),
    (2.50, P(body={"r": [20, 0, 0], "p": [0, 0, 0]}, chest=[16, 0, 0],
             rightArm=[-30, -4, -8], leftArm=[-30, 4, 8])),
    (3.20, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0],
             rightFoot=[0, 0, 0], leftFoot=[0, 0, 0])),
], "flare", particles={
    "0.30": {"effect": K.part("mag_aura_max")},
    "0.70": {"effect": K.part("sphere_core")},
    "1.20": {"effect": K.part("sphere_orbit")},
    "2.10": {"effect": K.part("sphere_collapse")},
    "2.28": {"effect": K.part("sphere_detonate")},
})


# ===========================================================================
#  ブラザーフッドの技 27
# ===========================================================================
def ally(name, length, frames, cape_profile="settle", particles=None):
    tech("ally", name, length, frames, cape_profile, particles)


# --- ミスティーク -----------------------------------------------------------
ally("shapeshift", 1.20, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.24, P(body={"r": [0, 0, 0], "p": [0, -1.2, 0]},
             rightArm=[-28, 0, -46], leftArm=[-28, 0, 46],
             rightForearm=[-72, 0, 0], leftForearm=[-72, 0, 0],
             head=[-14, 0, 0], chest=[-8, 0, 0])),
    (0.56, P(body={"r": [0, 200, 0], "p": [0, 0.6, 0]},
             rightArm=[-70, 0, -24], leftArm=[-70, 0, 24], head=[0, 0, 0])),
    (0.86, P(body={"r": [0, 360, 0], "p": [0, 0, 0]},
             rightArm=[-14, 0, -12], leftArm=[-14, 0, 12],
             rightForearm=[-10, 0, 0], leftForearm=[-10, 0, 0])),
    (1.20, P(body={"r": [0, 360, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
], particles={"0.30": {"effect": K.part("shift_shimmer")}})

ally("venom_strike", 0.62, [
    (0.00, P(rightArm=[0, 0, -4])),
    (0.10, P(rightArm=[-126, -30, -14], rightForearm=[-56, 0, 0],
             body=[0, 34, 0], chest=[-6, 18, 0], head=[0, -20, 0])),
    (0.24, P(rightArm=[-58, 26, 6], rightForearm=[-8, 0, 0],
             body=[6, -26, 0], chest=[8, -14, 0], head=[0, 16, 0])),
    (0.36, P(rightArm=[-42, 18, 4])),
    (0.62, P(rightArm=[0, 0, -4], rightForearm=[0, 0, 0], body=[0, 0, 0],
             chest=[0, 0, 0], head=[0, 0, 0])),
], particles={"0.24": {"effect": K.part("venom_drip"), "locator": "rightHand"}})

ally("vanish", 0.90, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.16, P(body={"r": [18, 0, 0], "p": [0, -1.8, 0]},
             rightArm=[-16, 0, -30], leftArm=[-16, 0, 30], head=[-16, 0, 0])),
    (0.34, P(body={"r": [-8, 140, 0], "p": [0, 1.4, 0]},
             rightArm=[-70, 0, -40], leftArm=[-70, 0, 40])),
    (0.60, P(body={"r": [0, 300, 0], "p": [0, 0, 0]},
             rightArm=[-12, 0, -10], leftArm=[-12, 0, 10])),
    (0.90, P(body={"r": [0, 360, 0], "p": [0, 0, 0]}, head=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
], particles={"0.18": {"effect": K.part("shift_shimmer")}})

# --- セイバートゥース -------------------------------------------------------
ally("rend", 0.68, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.10, P(rightArm=[-142, -40, -22], leftArm=[-100, 40, 40],
             rightForearm=[-40, 0, 0], body=[-4, 42, 0], chest=[-8, 22, 0],
             head=[-6, -26, 0])),
    (0.24, P(rightArm=[-40, 44, 26], leftArm=[-132, -30, -30],
             rightForearm=[-6, 0, 0], leftForearm=[-42, 0, 0],
             body=[6, -34, 0], chest=[10, -18, 0], head=[4, 22, 0])),
    (0.40, P(rightArm=[-118, -26, -18], leftArm=[-38, -40, -22],
             leftForearm=[-6, 0, 0], body=[4, 26, 0], head=[0, -14, 0])),
    (0.68, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], rightForearm=[0, 0, 0],
             leftForearm=[0, 0, 0], body=[0, 0, 0], chest=[0, 0, 0],
             head=[0, 0, 0])),
], particles={"0.24": {"effect": K.part("claw_slash")},
              "0.40": {"effect": K.part("claw_slash")}})

ally("feral_roar", 1.10, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.20, P(body={"r": [16, 0, 0], "p": [0, -1.6, 0]}, chest=[-14, 0, 0],
             head=[-8, 0, 0], rightArm=[-30, 0, -48], leftArm=[-30, 0, 48],
             rightForearm=[-60, 0, 0], leftForearm=[-60, 0, 0])),
    (0.40, P(body={"r": [-14, 0, 0], "p": [0, 1.0, 0]}, chest=[-20, 0, 0],
             head=[-40, 0, 0], rightArm=[-56, 0, -62], leftArm=[-56, 0, 62],
             rightForearm=[-24, 0, 0], leftForearm=[-24, 0, 0])),
    (0.76, P(head=[-36, 0, 0], chest=[-18, 0, 0],
             rightArm=[-50, 0, -58], leftArm=[-50, 0, 58])),
    (1.10, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
], particles={"0.42": {"effect": K.part("roar_wave")}})

ally("regenerate", 1.30, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.22, P(body={"r": [22, 0, 0], "p": [0, -2.0, 0]}, chest=[10, 0, 0],
             head=[16, 0, 0], rightArm=[-44, 20, -14],
             rightForearm=[-84, 0, 0], leftArm=[-30, -14, 12],
             leftForearm=[-70, 0, 0])),
    (0.66, P(body={"r": [10, 0, 0], "p": [0, -1.0, 0]}, chest=[2, 0, 0],
             head=[4, 0, 0], rightArm=[-30, 12, -12],
             rightForearm=[-60, 0, 0])),
    (0.98, P(body={"r": [-8, 0, 0], "p": [0, 0.6, 0]}, chest=[-8, 0, 0],
             head=[-14, 0, 0], rightArm=[-16, 0, -20], leftArm=[-16, 0, 20],
             rightForearm=[-20, 0, 0], leftForearm=[-20, 0, 0])),
    (1.30, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
], particles={"0.26": {"effect": K.part("regen_knit")},
              "0.80": {"effect": K.part("regen_knit")}})

# --- トード -----------------------------------------------------------------
ally("tongue_lash", 0.76, [
    (0.00, P(head=[0, 0, 0], body=[0, 0, 0])),
    (0.12, P(head=[-20, 0, 0], chest=[-8, 0, 0],
             body={"r": [-8, 0, 0], "p": [0, 0, -1.0]})),
    (0.22, P(head=[26, 0, 0], chest=[14, 0, 0],
             body={"r": [16, 0, 0], "p": [0, -0.6, 2.4]},
             rightArm=[-20, 0, -34], leftArm=[-20, 0, 34])),
    (0.44, P(head=[10, 0, 0], chest=[6, 0, 0],
             body={"r": [6, 0, 0], "p": [0, 0, 0.8]})),
    (0.76, P(head=[0, 0, 0], chest=[0, 0, 0],
             body={"r": [0, 0, 0], "p": [0, 0, 0]},
             rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
], particles={"0.22": {"effect": K.part("tongue_slime"), "locator": "head"}})

ally("leap", 0.86, [
    (0.00, P(rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
    (0.16, P(body={"r": [34, 0, 0], "p": [0, -4.0, 0]}, chest=[-16, 0, 0],
             rightLeg=[-46, 0, 0], leftLeg=[-46, 0, 0],
             rightShin=[74, 0, 0], leftShin=[74, 0, 0],
             rightArm=[-10, 0, -26], leftArm=[-10, 0, 26])),
    (0.32, P(body={"r": [-22, 0, 0], "p": [0, 3.6, 0]}, chest=[-10, 0, 0],
             rightLeg=[14, 0, 0], leftLeg=[14, 0, 0],
             rightShin=[0, 0, 0], leftShin=[0, 0, 0],
             rightArm=[-140, 0, -20], leftArm=[-140, 0, 20])),
    (0.58, P(body={"r": [-6, 0, 0], "p": [0, 1.6, 0]},
             rightLeg=[-20, 0, 0], leftLeg=[-20, 0, 0],
             rightShin=[36, 0, 0], leftShin=[36, 0, 0],
             rightArm=[-60, 0, -30], leftArm=[-60, 0, 30])),
    (0.86, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0],
             rightShin=[0, 0, 0], leftShin=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
], particles={"0.18": {"effect": K.part("leap_dust")}})

ally("slime_spit", 0.72, [
    (0.00, P(head=[0, 0, 0])),
    (0.16, P(head=[-26, 0, 0], chest=[-10, 0, 0], body=[-6, 0, 0])),
    (0.28, P(head=[22, 0, 0], chest=[12, 0, 0],
             body={"r": [12, 0, 0], "p": [0, 0, 1.4]})),
    (0.46, P(head=[6, 0, 0], chest=[4, 0, 0], body={"r": [4, 0, 0],
                                                    "p": [0, 0, 0.4]})),
    (0.72, P(head=[0, 0, 0], chest=[0, 0, 0],
             body={"r": [0, 0, 0], "p": [0, 0, 0]})),
], particles={"0.28": {"effect": K.part("slime_splat"), "locator": "head"}})

# --- ジャガーノート ---------------------------------------------------------
ally("unstoppable", 1.40, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.22, P(body={"r": [26, 0, 0], "p": [0, -2.4, -2.0]}, chest=[-8, 0, 0],
             head=[-20, 0, 0], rightArm=[-34, 0, -18], leftArm=[-34, 0, 18],
             rightForearm=[-88, 0, 0], leftForearm=[-88, 0, 0],
             rightLeg=[-38, 0, 0], leftLeg=[22, 0, 0])),
    (0.50, P(body={"r": [34, 0, 0], "p": [0, -1.4, 3.0]},
             rightArm=[-48, 0, -14], leftArm=[-48, 0, 14],
             rightLeg=[36, 0, 0], leftLeg=[-32, 0, 0], head=[-26, 0, 0])),
    (0.86, P(body={"r": [34, 0, 0], "p": [0, -1.4, 3.0]},
             rightLeg=[-34, 0, 0], leftLeg=[38, 0, 0])),
    (1.10, P(body={"r": [18, 0, 0], "p": [0, -0.6, 1.0]},
             rightArm=[-24, 0, -16], leftArm=[-24, 0, 16],
             rightLeg=[10, 0, 0], leftLeg=[-8, 0, 0])),
    (1.40, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], particles={"0.26": {"effect": K.part("quake_dust")},
              "0.60": {"effect": K.part("impact_dust")}})

ally("quake_stomp", 1.00, [
    (0.00, P(rightLeg=[0, 0, 0])),
    (0.20, P(body={"r": [-14, 0, 0], "p": [0, 2.6, 0]}, chest=[-10, 0, 0],
             rightLeg=[-64, 0, 0], rightShin=[76, 0, 0],
             rightArm=[-130, 0, -22], leftArm=[-130, 0, 22])),
    (0.34, P(body={"r": [22, 0, 0], "p": [0, -2.8, 0]}, chest=[14, 0, 0],
             head=[16, 0, 0], rightLeg=[16, 0, 0], rightShin=[0, 0, 0],
             rightArm=[-16, 0, -14], leftArm=[-16, 0, 14])),
    (0.52, P(body={"r": [10, 0, 0], "p": [0, -1.0, 0]}, chest=[6, 0, 0],
             rightLeg=[6, 0, 0])),
    (1.00, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightLeg=[0, 0, 0], rightShin=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
], particles={"0.34": {"effect": K.part("slam_ring")},
              "0.36": {"effect": K.part("quake_crack")},
              "0.38": {"effect": K.part("quake_dust")}})

ally("hurl", 0.92, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.18, P(body={"r": [16, 0, 0], "p": [0, -1.6, 0]},
             rightArm=[-40, 24, -16], leftArm=[-40, -24, 16],
             rightForearm=[-92, 0, 0], leftForearm=[-92, 0, 0],
             head=[14, 0, 0])),
    (0.38, P(body={"r": [-18, -22, 0], "p": [0, 1.2, 0]}, chest=[-14, -12, 0],
             rightArm=[-158, 12, -12], leftArm=[-158, -12, 12],
             rightForearm=[-40, 0, 0], leftForearm=[-40, 0, 0],
             head=[-20, 8, 0])),
    (0.52, P(body={"r": [20, 26, 0], "p": [0, -0.4, 0]}, chest=[18, 14, 0],
             rightArm=[-52, -18, -8], leftArm=[-52, 18, 8],
             rightForearm=[-6, 0, 0], leftForearm=[-6, 0, 0],
             head=[12, -10, 0])),
    (0.92, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
], particles={"0.52": {"effect": K.part("debris_chunk")}})

# --- クイックシルバー -------------------------------------------------------
ally("blitz", 0.72, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.08, P(body={"r": [22, 0, 0], "p": [0, -0.8, -1.6]},
             rightArm=[-120, -20, -12], leftArm=[-20, 20, 20],
             rightForearm=[-60, 0, 0])),
    (0.16, P(body={"r": [18, -30, 0], "p": [0, 0, 2.4]},
             rightArm=[-88, -24, -6], rightForearm=[-4, 0, 0],
             leftArm=[-110, 20, 16], leftForearm=[-52, 0, 0])),
    (0.26, P(body={"r": [18, 30, 0], "p": [0, 0, 2.4]},
             leftArm=[-88, 24, 6], leftForearm=[-4, 0, 0],
             rightArm=[-110, -20, -16], rightForearm=[-52, 0, 0])),
    (0.36, P(body={"r": [18, -30, 0], "p": [0, 0, 2.4]},
             rightArm=[-88, -24, -6], rightForearm=[-4, 0, 0],
             leftArm=[-110, 20, 16])),
    (0.48, P(body={"r": [10, 0, 0], "p": [0, 0, 1.0]},
             rightArm=[-40, -8, -6], leftArm=[-40, 8, 6],
             rightForearm=[-20, 0, 0], leftForearm=[-20, 0, 0])),
    (0.72, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, rightArm=[0, 0, -4],
             leftArm=[0, 0, 4], rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
], particles={"0.16": {"effect": K.part("speed_line")},
              "0.26": {"effect": K.part("blur_after")},
              "0.36": {"effect": K.part("speed_line")}})

ally("afterimage", 0.80, [
    (0.00, P(body={"r": [0, 0, 0], "p": [0, 0, 0]})),
    (0.14, P(body={"r": [0, -46, 0], "p": [-2.2, 0, 0]},
             rightArm=[-40, 0, -30], leftArm=[-40, 0, 30], head=[0, 30, 0])),
    (0.34, P(body={"r": [0, 46, 0], "p": [2.2, 0, 0]},
             rightArm=[-40, 0, -30], leftArm=[-40, 0, 30], head=[0, -30, 0])),
    (0.54, P(body={"r": [0, -20, 0], "p": [-0.8, 0, 0]}, head=[0, 12, 0])),
    (0.80, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, head=[0, 0, 0],
             rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
], particles={"0.14": {"effect": K.part("blur_after")},
              "0.34": {"effect": K.part("blur_after")}})

ally("sonic_dash", 0.64, [
    (0.00, P(body={"r": [0, 0, 0], "p": [0, 0, 0]})),
    (0.10, P(body={"r": [30, 0, 0], "p": [0, -0.8, -1.2]}, chest=[-10, 0, 0],
             head=[-24, 0, 0], rightArm=[-70, 0, -34], leftArm=[-70, 0, 34],
             rightLeg=[-40, 0, 0], leftLeg=[24, 0, 0])),
    (0.28, P(body={"r": [36, 0, 0], "p": [0, -0.4, 3.2]},
             rightArm=[-120, 0, -20], leftArm=[-120, 0, 20],
             rightLeg=[40, 0, 0], leftLeg=[-36, 0, 0])),
    (0.44, P(body={"r": [16, 0, 0], "p": [0, 0, 1.0]},
             rightArm=[-40, 0, -16], leftArm=[-40, 0, 16],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
    (0.64, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
], particles={"0.12": {"effect": K.part("speed_line")}})

# --- パイロ -----------------------------------------------------------------
ally("flame_wave", 0.86, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.16, P(rightArm=[-56, 40, -14], rightForearm=[-70, 0, 0],
             body=[0, 34, 0], chest=[-6, 18, 0], head=[0, -20, 0])),
    (0.34, P(rightArm=[-92, -34, -8], rightForearm=[-12, 0, 0],
             body=[4, -30, 0], chest=[6, -16, 0], head=[0, 18, 0],
             leftArm=[-30, 20, 16])),
    (0.52, P(rightArm=[-84, -20, -8], body=[2, -16, 0])),
    (0.86, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], rightForearm=[0, 0, 0],
             body=[0, 0, 0], chest=[0, 0, 0], head=[0, 0, 0])),
], particles={"0.34": {"effect": K.part("flame_wave"), "locator": "rightHand"},
              "0.38": {"effect": K.part("ember_rise")}})

ally("fire_serpent", 1.16, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.20, P(rightArm=[-100, -14, -10], rightForearm=[-30, 0, 0],
             leftArm=[-96, 14, 10], leftForearm=[-30, 0, 0],
             body=[-4, 0, 0], chest=[-8, 0, 0], head=[-10, 0, 0])),
    (0.46, P(rightArm=[-108, -30, -8], leftArm=[-108, 30, 8],
             rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0],
             body=[-6, 0, 0])),
    (0.72, P(rightArm=[-92, -8, -12], leftArm=[-92, 8, 12],
             rightForearm=[-24, 0, 0], leftForearm=[-24, 0, 0],
             body=[4, 0, 0], chest=[6, 0, 0])),
    (1.16, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], rightForearm=[0, 0, 0],
             leftForearm=[0, 0, 0], body=[0, 0, 0], chest=[0, 0, 0],
             head=[0, 0, 0])),
], particles={"0.24": {"effect": K.part("flame_serpent")},
              "0.60": {"effect": K.part("ember_rise")}})

ally("ignite", 0.56, [
    (0.00, P(rightArm=[0, 0, -4])),
    (0.12, P(rightArm=[-104, -12, -8], rightForearm=[-24, 0, 0],
             rightHand=[-20, 0, 0], head=[-6, 8, 0])),
    (0.26, P(rightHand=[16, 0, 0], rightArm=[-100, -10, -8])),
    (0.56, P(rightArm=[0, 0, -4], rightForearm=[0, 0, 0], rightHand=[0, 0, 0],
             head=[0, 0, 0])),
], particles={"0.26": {"effect": K.part("ember_rise"), "locator": "rightHand"}})

# --- アバランチ -------------------------------------------------------------
ally("tremor", 0.90, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.20, P(body={"r": [26, 0, 0], "p": [0, -2.2, 0]}, chest=[-10, 0, 0],
             rightArm=[-30, 16, -18], leftArm=[-30, -16, 18],
             rightForearm=[-96, 0, 0], leftForearm=[-96, 0, 0],
             head=[-18, 0, 0])),
    (0.36, P(body={"r": [34, 0, 0], "p": [0, -3.0, 0]},
             rightArm=[-20, 10, -14], leftArm=[-20, -10, 14],
             rightForearm=[-110, 0, 0], leftForearm=[-110, 0, 0])),
    (0.58, P(body={"r": [16, 0, 0], "p": [0, -1.2, 0]},
             rightArm=[-34, 8, -18], leftArm=[-34, -8, 18])),
    (0.90, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0])),
], particles={"0.36": {"effect": K.part("quake_dust")},
              "0.40": {"effect": K.part("quake_crack")}})

ally("rockfall", 1.20, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.22, P(rightArm=[-150, 0, -18], leftArm=[-150, 0, 18],
             rightForearm=[-20, 0, 0], leftForearm=[-20, 0, 0],
             body={"r": [-14, 0, 0], "p": [0, 1.2, 0]}, head=[-30, 0, 0],
             chest=[-14, 0, 0])),
    (0.54, P(rightArm=[-166, 0, -10], leftArm=[-166, 0, 10],
             body={"r": [-18, 0, 0], "p": [0, 1.8, 0]}, head=[-34, 0, 0])),
    (0.72, P(rightArm=[-60, 0, -26], leftArm=[-60, 0, 26],
             rightForearm=[-16, 0, 0], leftForearm=[-16, 0, 0],
             body={"r": [16, 0, 0], "p": [0, -0.6, 0]}, head=[12, 0, 0],
             chest=[12, 0, 0])),
    (1.20, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], rightForearm=[0, 0, 0],
             leftForearm=[0, 0, 0], body={"r": [0, 0, 0], "p": [0, 0, 0]},
             chest=[0, 0, 0], head=[0, 0, 0])),
], particles={"0.30": {"effect": K.part("mag_dust")},
              "0.72": {"effect": K.part("rock_fall")}})

ally("fissure", 1.30, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.24, P(body={"r": [30, 0, 0], "p": [0, -2.8, 0]}, chest=[-12, 0, 0],
             head=[-22, 0, 0], rightArm=[-24, 20, -14],
             leftArm=[-24, -20, 14], rightForearm=[-104, 0, 0],
             leftForearm=[-104, 0, 0], rightLeg=[-30, 0, 0],
             leftLeg=[-30, 0, 0], rightShin=[48, 0, 0], leftShin=[48, 0, 0])),
    (0.52, P(body={"r": [36, 0, 0], "p": [0, -3.6, 0]},
             rightArm=[-16, 14, -10], leftArm=[-16, -14, 10],
             rightForearm=[-118, 0, 0], leftForearm=[-118, 0, 0])),
    (0.70, P(body={"r": [8, 0, 0], "p": [0, -0.8, 0]},
             rightArm=[-46, -30, -24], leftArm=[-46, 30, 24],
             rightForearm=[-40, 0, 0], leftForearm=[-40, 0, 0],
             chest=[6, 0, 0], head=[4, 0, 0])),
    (0.94, P(body={"r": [4, 0, 0], "p": [0, -0.2, 0]},
             rightArm=[-30, -20, -20], leftArm=[-30, 20, 20])),
    (1.30, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightForearm=[0, 0, 0], leftForearm=[0, 0, 0],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0],
             rightShin=[0, 0, 0], leftShin=[0, 0, 0])),
], particles={"0.70": {"effect": K.part("quake_crack")},
              "0.74": {"effect": K.part("quake_dust")}})

# --- ブロブ -----------------------------------------------------------------
ally("immovable", 1.10, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.24, P(body={"r": [12, 0, 0], "p": [0, -3.0, 0]}, chest=[-6, 0, 0],
             rightArm=[-26, 0, -50], leftArm=[-26, 0, 50],
             rightForearm=[-56, 0, 0], leftForearm=[-56, 0, 0],
             rightLeg=[-24, 0, -10], leftLeg=[-24, 0, 10],
             rightShin=[40, 0, 0], leftShin=[40, 0, 0], head=[8, 0, 0])),
    (0.62, P(body={"r": [10, 0, 0], "p": [0, -3.4, 0]},
             rightArm=[-30, 0, -54], leftArm=[-30, 0, 54])),
    (1.10, P(body={"r": [8, 0, 0], "p": [0, -3.0, 0]},
             rightArm=[-28, 0, -52], leftArm=[-28, 0, 52],
             rightLeg=[-22, 0, -10], leftLeg=[-22, 0, 10],
             rightShin=[38, 0, 0], leftShin=[38, 0, 0])),
], particles={"0.26": {"effect": K.part("slam_ring")},
              "0.30": {"effect": K.part("impact_dust")}})

ally("belly_bounce", 0.84, [
    (0.00, P(body={"r": [0, 0, 0], "p": [0, 0, 0]})),
    (0.16, P(body={"r": [-12, 0, 0], "p": [0, -1.0, -1.6]}, chest=[-14, 0, 0],
             rightArm=[-30, 0, -48], leftArm=[-30, 0, 48], head=[-10, 0, 0])),
    (0.30, P(body={"r": [16, 0, 0], "p": [0, 0.6, 2.6]}, chest=[18, 0, 0],
             rightArm=[-56, 0, -62], leftArm=[-56, 0, 62], head=[12, 0, 0])),
    (0.52, P(body={"r": [4, 0, 0], "p": [0, 0, 0.6]}, chest=[6, 0, 0],
             rightArm=[-20, 0, -30], leftArm=[-20, 0, 30])),
    (0.84, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
], particles={"0.30": {"effect": K.part("slam_ring")}})

ally("body_slam", 1.06, [
    (0.00, P(body={"r": [0, 0, 0], "p": [0, 0, 0]})),
    (0.22, P(body={"r": [-20, 0, 0], "p": [0, 3.0, 0]}, chest=[-14, 0, 0],
             rightArm=[-146, 0, -24], leftArm=[-146, 0, 24],
             rightLeg=[-30, 0, 0], leftLeg=[-30, 0, 0],
             rightShin=[46, 0, 0], leftShin=[46, 0, 0], head=[-24, 0, 0])),
    (0.40, P(body={"r": [40, 0, 0], "p": [0, -4.0, 1.8]}, chest=[22, 0, 0],
             rightArm=[-20, 0, -46], leftArm=[-20, 0, 46],
             rightLeg=[18, 0, 0], leftLeg=[18, 0, 0],
             rightShin=[0, 0, 0], leftShin=[0, 0, 0], head=[24, 0, 0])),
    (0.66, P(body={"r": [22, 0, 0], "p": [0, -2.4, 0.8]}, chest=[12, 0, 0])),
    (1.06, P(body={"r": [0, 0, 0], "p": [0, 0, 0]}, chest=[0, 0, 0],
             head=[0, 0, 0], rightArm=[0, 0, -4], leftArm=[0, 0, 4],
             rightLeg=[0, 0, 0], leftLeg=[0, 0, 0])),
], particles={"0.40": {"effect": K.part("slam_ring")},
              "0.42": {"effect": K.part("quake_dust")}})

# --- スカーレット・ウィッチ ---------------------------------------------------
ally("hex_bolt", 0.68, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.12, P(rightArm=[-64, 32, -16], rightForearm=[-72, 0, 0],
             rightHand=[-28, 0, 0], body=[0, 24, 0], chest=[-6, 14, 0],
             head=[0, -16, 0])),
    (0.26, P(rightArm=[-98, -14, -8], rightForearm=[-8, 0, 0],
             rightHand=[14, 0, 0], body=[4, -18, 0], chest=[6, -10, 0],
             head=[0, 14, 0], leftArm=[-24, 14, 14])),
    (0.40, P(rightArm=[-86, -8, -8], body=[2, -10, 0])),
    (0.68, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], rightForearm=[0, 0, 0],
             rightHand=[0, 0, 0], body=[0, 0, 0], chest=[0, 0, 0],
             head=[0, 0, 0])),
], particles={"0.26": {"effect": K.part("hex_bolt_trail"),
                       "locator": "rightHand"}})

ally("chaos_field", 1.34, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.22, P(rightArm=[-70, -26, -22], leftArm=[-70, 26, 22],
             rightForearm=[-66, 0, 0], leftForearm=[-66, 0, 0],
             body={"r": [-6, 0, 0], "p": [0, 0.8, 0]}, chest=[-10, 0, 0],
             head=[-14, 0, 0])),
    (0.56, P(rightArm=[-108, -40, -14], leftArm=[-108, 40, 14],
             rightForearm=[-28, 0, 0], leftForearm=[-28, 0, 0],
             body={"r": [-12, 0, 0], "p": [0, 1.6, 0]}, head=[-20, 0, 0])),
    (0.92, P(rightArm=[-118, -20, -10], leftArm=[-118, 20, 10],
             rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0],
             body={"r": [-8, 0, 0], "p": [0, 1.0, 0]})),
    (1.34, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], rightForearm=[0, 0, 0],
             leftForearm=[0, 0, 0], body={"r": [0, 0, 0], "p": [0, 0, 0]},
             chest=[0, 0, 0], head=[0, 0, 0])),
], particles={"0.26": {"effect": K.part("chaos_motes")},
              "0.60": {"effect": K.part("hex_wave")}})

ally("telekinesis", 1.10, [
    (0.00, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4])),
    (0.18, P(rightArm=[-96, -18, -8], rightForearm=[-16, 0, 0],
             rightHand=[-30, 0, 0], leftArm=[-40, 16, 14],
             body=[-2, -10, 0], head=[-6, 8, 0])),
    (0.42, P(rightArm=[-124, -14, -8], rightForearm=[-10, 0, 0],
             rightHand=[-14, 0, 0], body={"r": [-10, -6, 0], "p": [0, 0.8, 0]},
             chest=[-10, 0, 0], head=[-18, 6, 0])),
    (0.74, P(rightArm=[-146, -10, -8], rightHand=[0, 0, 0],
             body={"r": [-14, 0, 0], "p": [0, 1.4, 0]}, head=[-24, 0, 0])),
    (1.10, P(rightArm=[0, 0, -4], leftArm=[0, 0, 4], rightForearm=[0, 0, 0],
             rightHand=[0, 0, 0], body={"r": [0, 0, 0], "p": [0, 0, 0]},
             chest=[0, 0, 0], head=[0, 0, 0])),
], particles={"0.24": {"effect": K.part("tk_lift")},
              "0.74": {"effect": K.part("chaos_motes")}})


def main() -> None:
    K.ensure_dirs()
    expected = set()
    for group in ("tech", "ally"):
        for name in K.ANIM_GROUPS[group]:
            expected.add(K.anim(group, name))
    missing = sorted(expected - set(A))
    if missing:
        raise SystemExit(f"未実装の技アニメーション: {missing}")
    write_json(f"{K.ANIM_DIR}/marvel.tech.animation.json", animations_doc(A))
    print(f"animations (tech): {len(A)} clips")


if __name__ == "__main__":
    main()
