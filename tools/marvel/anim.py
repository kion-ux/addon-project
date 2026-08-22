# -*- coding: utf-8 -*-
"""アニメーションを書くための共通語彙。

移動アニメ担当と技アニメ担当が **同じ語彙** で書けるように、
Molang の定型と、キーフレームの組み立てをここに集約する。

滑らかさについて
----------------
Bedrock のキーフレームは既定で線形補間なので、そのままだと動きが硬い。
``smooth=True`` を渡すと各キーに ``lerp_mode: "catmullrom"`` が付き、
キーとキーの間が曲線で繋がる。これが「映画のような滑らかさ」の土台になる。

タイミングについて
------------------
気持ちのいいアクションは *等間隔ではない*。
``ease`` の定数（予備動作→溜め→撃発→残心）を使うと、
どの技も同じリズムの骨格を共有できる。
"""
from __future__ import annotations

# -------------------------------------------------------------- Molang
LIMB = "query.modified_distance_moved * 38.17"
SPD = "query.modified_move_speed"
T = "query.anim_time"
LIFE = "query.life_time"
GROUND = "query.is_on_ground"
SNEAK = "query.is_sneaking"
USING = "query.is_using_item"
DELTA = "query.delta_time"


def swing(amp, phase=0, speed=1.0, scale=SPD):
    """歩幅に同期して振れる。歩き・走りの基礎。"""
    ph = f" + {phase}" if phase else ""
    return f"math.cos({LIMB} * {speed}{ph}) * {amp} * {scale}"


def bob(amp, hz=62, phase=0):
    """時間に同期して揺れる。待機の呼吸、マントのそよぎ。"""
    ph = f" + {phase}" if phase else ""
    return f"math.cos({T} * {hz}{ph}) * {amp}"


def bob2(amp, hz=62, phase=0, hz2=23, amp2=0.4):
    """周期の違う二つの波を重ねる。単調な往復に見えなくなる。"""
    return (f"(math.cos({T} * {hz} + {phase}) * {amp} + "
            f"math.sin({T} * {hz2} + {phase}) * {amp * amp2})")


def drift(amp, hz=17, phase=0):
    """ゆっくりした漂い。浮遊、マント、髪。"""
    return f"math.sin({T} * {hz} + {phase}) * {amp}"


def rot(x=0, y=0, z=0):
    return {"rotation": [x, y, z]}


def pos(x=0, y=0, z=0):
    return {"position": [x, y, z]}


def scale(x=1, y=None, z=None):
    return {"scale": [x, y if y is not None else x, z if z is not None else x]}


def rp(r, p):
    return {"rotation": list(r), "position": list(p)}


def rps(r=None, p=None, s=None):
    d = {}
    if r:
        d["rotation"] = list(r)
    if p:
        d["position"] = list(p)
    if s:
        d["scale"] = list(s)
    return d


def keys(_smooth=True, **frames):
    """``keys(t0=[0,0,0], t0_12=[...])`` — キー名の ``_`` は ``.`` になる。

    ``t`` を外した残りが秒数。既定で catmullrom 補間が付く。
    """
    out = {}
    for k, v in frames.items():
        time = k.lstrip("t").replace("_", ".")
        if _smooth and isinstance(v, (list, tuple)):
            out[time] = {"post": list(v), "lerp_mode": "catmullrom"}
        else:
            out[time] = v
    return out


def hold(**frames):
    """線形（ピタッと止めたいとき）。"""
    return keys(_smooth=False, **frames)


def step(t, value):
    """その瞬間に飛ぶキー（pre と post を分ける）。"""
    return {str(t): {"pre": list(value), "post": list(value)}}


def clip(bones, length=None, loop=True, blend=None, sound=None,
         particles=None, timeline=None, start_delay=None,
         override=None):
    d = {"loop": loop, "bones": bones}
    if length:
        d["animation_length"] = length
    if blend is not None:
        d["blend_weight"] = blend
    if sound:
        d["sound_effects"] = sound
    if particles:
        d["particle_effects"] = particles
    if timeline:
        d["timeline"] = timeline
    if start_delay:
        d["start_delay"] = start_delay
    if override:
        d["override_previous_animation"] = True
    return d


def fx(**frames):
    """``particle_effects`` の糖衣。``fx(t0_2="marvel:mag_push")``"""
    return {k.lstrip("t").replace("_", "."):
            ({"effect": v} if isinstance(v, str) else v)
            for k, v in frames.items()}


def sfx(**frames):
    return {k.lstrip("t").replace("_", "."):
            ({"effect": v} if isinstance(v, str) else v)
            for k, v in frames.items()}


# -------------------------------------------------------------- リズム
#: 技一発の標準リズム（秒）。予備動作 → 溜め → 撃発 → 伸び → 残心。
EASE = {
    "anticipate": 0.10,     # 逆方向へ引く
    "wind": 0.26,           # 溜めきる
    "strike": 0.34,         # 撃発（ここが一番速い）
    "extend": 0.46,         # 伸びきり
    "settle": 0.78,         # 残心
    "end": 1.00,
}


def beats(total: float) -> dict:
    """EASE を任意の長さにスケールした秒数表を返す。"""
    return {k: round(v * total, 3) for k, v in EASE.items()}


def merge(*bone_dicts) -> dict:
    """複数のボーン辞書を重ねる（後勝ち、キー単位）。"""
    out: dict = {}
    for d in bone_dicts:
        for bone, channels in d.items():
            out.setdefault(bone, {}).update(channels)
    return out


# -------------------------------------------------------------- 定型ポーズ
def mirror(bones: dict) -> dict:
    """right ↔ left を入れ替え、Y/Z 回転の符号を反転した鏡像を返す。"""
    out = {}
    for name, ch in bones.items():
        if name.startswith("right"):
            new = "left" + name[5:]
        elif name.startswith("left"):
            new = "right" + name[4:]
        else:
            new = name
        nc = {}
        for chan, val in ch.items():
            if chan == "rotation" and isinstance(val, list):
                nc[chan] = [val[0], _neg(val[1]), _neg(val[2])]
            elif chan == "position" and isinstance(val, list):
                nc[chan] = [_neg(val[0]), val[1], val[2]]
            else:
                nc[chan] = val
        out[new] = nc
    return out


def _neg(v):
    if isinstance(v, (int, float)):
        return -v
    return f"-({v})"
