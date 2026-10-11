# -*- coding: utf-8 -*-
"""技のアニメーション。本作で一番手をかけるところ。

拍・行き過ぎ量・身体の連動は docs/DIRECTION.md §4 が正典で、
このモジュールはその表を **計算で** 再現する。
秒数を手で書くと技ごとに必ずずれるので、技ごとに書くのは
「その技にしか無い姿勢」だけにしてある。

一本の技の骨格
--------------
    a    ニュートラル
    b    予備（撃発と *逆* へ引く。ここだけは行き過ぎ禁止）
    mid  溜めの途中（長い技だけ）
    c    溜めきり            ← ここから linear。曲線で繋ぐと芯が消える
    s    完全静止（必殺のみ。c と同値の 2 キー）
    d    撃発 = オーバーシュートの頂点
    e    戻り着地（目標角の 3% 手前で止める）
    g    残心の中間
    f    終端

``d`` に書くのは **目標の角度** であって、行き過ぎた角度ではない。
行き過ぎ量（軽 12% / 重 18% / 必殺 22%）と戻り先は系統ごとの率から
自動で作る。手で書くと技ごとに量がばらついて、15 技が揃わない。

身体の連動は「書かなくても付く」ようにしてある。
``body`` を書けば ``chest`` (0.55 倍) と ``neck`` (逆 0.4 倍) が、
腕を書けば ``*Shoulder`` の持ち上げが、頭を書けば ``hair`` の遅れが付く。
ボーンごとの遅れ（支持脚 -0.02 → 手 +0.09 → マント）は composer が
時刻をずらして与えるので、姿勢だけ考えればよい。

角度の目安（腕）
    0    真下に垂れる
  -90    正面へ水平
 -165    ほぼ真上
"""
from __future__ import annotations

import _path  # noqa: F401

import contract as K  # noqa: E402
from anim import cape6, clip, merge, tag, track  # noqa: E402
from common import animations_doc, write_json  # noqa: E402

A: dict = {}


# ===========================================================================
#  1. 拍
# ===========================================================================
#: 系統ごとの拍。**撃発と戻りだけ絶対秒** で、L を変えても切れ味が落ちない。
#: 比率で持つと、長い技ほど撃発が鈍って全部同じ速さに見える。
FAMILIES = {
    #            予備   溜めきり  完全静止  撃発    戻り   行き過ぎ
    "light": dict(ready=0.18, wind=0.28, still=None,
                  strike=0.06, land=0.13, over=0.12),
    "heavy": dict(ready=0.12, wind=0.46, still=None,
                  strike=0.09, land=0.20, over=0.18),
    "ult":   dict(ready=0.08, wind=0.50, still=0.60,
                  strike=0.08, land=0.18, over=0.22),
}

#: 撃発の 1 フレームだけ潰す量（§4-7）。潰さないと角度をいくら詰めても
#: 「当たった」感触が乗らない。
SQUASH = {
    "light": {"chest": [1.00, 0.94, 1.06]},
    "heavy": {"chest": [1.04, 0.90, 1.08], "body": [1.04, 0.90, 1.08]},
    "ult":   {"chest": [1.06, 0.88, 1.10], "body": [1.06, 0.88, 1.10],
              "head": [1.06, 0.88, 1.10]},
}

#: 撃発キーを 0 とした遅れ（秒）。駆動順は
#: 支持脚 → 腰 → 胸 → 肩 → 上腕 → 前腕 → 手 → マント。
#: **後ろから順に検索する**ので "Forearm" は "Arm" より先に置く。
LAG = (
    ("Shoulder", 0.04),
    ("Forearm", 0.07),
    ("Hand", 0.09),
    ("Arm", 0.05),
    ("Shin", -0.02), ("Foot", -0.02), ("Toe", -0.02), ("Leg", -0.02),
    ("hair", 0.12), ("head", 0.10), ("neck", 0.06), ("chest", 0.03),
    ("body", 0.00),
)

#: 前腕は上腕の 1.4 倍の角速度で追い越す（しなり）。手はさらに遅れて振れる。
OVER_MUL = (("Forearm", 1.40), ("Hand", 1.25), ("hair", 1.30))

#: 位置の行き過ぎは角度より控えめ（§4-3）。腰が跳ねると足が滑って見える。
OVER_POS = 0.08

#: 戻り着地は目標ちょうどに置かない。3% 手前で止めて残心へ渡すと芯が残る。
UNDERSHOOT = 0.03

#: マントの累積上限。profile ごとに変えているのは、70° 一律で正規化すると
#: settle (18°) まで flare (62°) と同じ振り幅に化けて、profile が死ぬため。
CAPE_LIMIT = {"whip": 70.0, "flare": 70.0, "swirl": 52.0, "settle": 26.0}

#: 技 -> (系統, L 秒, マントの型, 保持系か)
TIMING = {
    "repulse":     ("light", 0.72, "whip",   False),
    "attract":     ("light", 0.75, "swirl",  False),
    "disarm":      ("light", 0.70, "whip",   False),
    "lance":       ("light", 0.68, "whip",   False),
    "flight":      ("light", 0.62, "flare",  True),
    "sight":       ("light", 0.78, "settle", True),
    "barrier":     ("light", 0.86, "settle", True),
    "iron_bind":   ("heavy", 1.06, "swirl",  False),
    "emp":         ("heavy", 1.10, "flare",  False),
    "crush":       ("heavy", 1.16, "whip",   False),
    "throne":      ("heavy", 1.24, "settle", False),
    "shard_storm": ("heavy", 1.30, "flare",  False),
    "polarity":    ("heavy", 1.36, "flare",  False),
    "uprising":    ("heavy", 1.50, "flare",  False),
    "sphere":      ("ult",   3.00, "flare",  False),
}

#: 静止ポーズのボーン既定値。腕だけは肩幅ぶん開いているのが素の立ち姿。
REST = {"rightArm": [0, 0, -4], "leftArm": [0, 0, 4]}

CHAN = {"r": "rotation", "p": "position", "s": "scale"}
ORDER = ("b", "mid", "c", "s", "d", "e")

#: 到達点は linear、通過点は catmullrom（§4-6）。
#: 撃発の直前キーと撃発キーの *両方* を linear にしないと、
#: 0.06 秒の撃発に 0.30 秒の溜めの接線が漏れて、止めたい所で止まらない。
MODE = {"a": "smooth", "b": "smooth", "mid": "smooth", "c": "linear",
        "s": "linear", "d": "linear", "e": "linear", "g": "smooth",
        "f": "linear",
        # 二撃目・三撃目（連撃技）。到達点なので linear。
        "x": "linear", "xs": "smooth"}


def times(family: str, length: float) -> dict:
    """§4-2 の実キー時刻表。丸めた `t_c` から撃発を数えるので表と一致する。"""
    f = FAMILIES[family]
    t = {"a": 0.0,
         "b": round(f["ready"] * length, 2),
         "c": round(f["wind"] * length, 2)}
    t["mid"] = round(t["b"] + (t["c"] - t["b"]) * 0.45, 2)
    if f["still"]:
        t["s"] = round(f["still"] * length, 2)
    t["d"] = round(t.get("s", t["c"]) + f["strike"], 2)
    t["e"] = round(t["d"] + f["land"], 2)
    t["g"] = round(t["e"] + (length - t["e"]) * 0.42, 2)
    t["f"] = round(length, 2)
    return t


def lag_of(bone: str) -> float:
    for token, value in LAG:
        if token in bone:
            return value
    return 0.0


def over_mul(bone: str) -> float:
    for token, value in OVER_MUL:
        if token in bone:
            return value
    return 1.0


# ===========================================================================
#  2. 組み立て
# ===========================================================================
def P(**kw):
    """`P(rightArm=[-90, 0, 0], body=[0, 20, 0])` を素直に書くための糖衣。

    値は回転のリスト、または ``{"r": .., "p": .., "s": ..}``。
    """
    return kw


def _rest(bone: str, chan: str) -> list:
    if chan == "p":
        return [0, 0, 0]
    if chan == "s":
        return [1, 1, 1]
    return list(REST.get(bone, [0, 0, 0]))


def _norm(pose: dict) -> dict:
    out = {}
    for bone, value in pose.items():
        if isinstance(value, dict):
            out[bone] = {k: [float(v) for v in val]
                         for k, val in value.items() if k in CHAN}
        else:
            out[bone] = {"r": [float(v) for v in value]}
    return out


def _r(v: float) -> float:
    """丸めたうえで -0.0 を潰す。JSON に -0.0 が並ぶと差分が読みにくい。"""
    v = round(v, 1)
    return 0.0 if v == 0 else v


def _scaled(vec, k, cap=None):
    out = [_r(v * k) for v in vec]
    if cap is not None:
        out = [max(-cap, min(cap, v)) for v in out]
    return out


def _autofill(frames, authored):
    """腰・腕を書いたら、胸・首・髪・肩が勝手に付いてくる。

    現行 15 技で ``neck`` と ``*Shoulder`` が一度も使われていなかったのが
    「全部の技が腕だけに見える」原因なので、書き忘れようが無い形にする。
    明示的に書いた技では自動生成を止める（後から上書きすると喧嘩する）。
    """
    want_chest = "chest" not in authored
    want_neck = "neck" not in authored
    want_hair = "hair" not in authored
    want_sh = not {"rightShoulder", "leftShoulder"} & authored
    for _beat, _t, pose in frames:
        body = pose.get("body", {}).get("r")
        if body:
            if want_chest:
                pose.setdefault("chest", {})["r"] = _scaled(body, 0.55)
            if want_neck:
                # 頭は置いていかれる。腰と逆へ 0.4 倍。
                pose.setdefault("neck", {})["r"] = _scaled(body, -0.40)
        head = pose.get("head", {}).get("r")
        if head and want_hair:
            # 白髪は兜の下なので、突き抜けないよう 8° で頭打ちにする。
            pose.setdefault("hair", {})["r"] = _scaled(head, -0.22, cap=8)
        if not want_sh:
            continue
        for side, sign in (("right", -1), ("left", 1)):
            arm = pose.get(side + "Arm", {}).get("r")
            if arm is None:
                continue
            lift = max(0.0, min(8.0, -arm[0] / 22.0))
            pose[side + "Shoulder"] = {"r": [0, 0, _r(sign * lift)]}


def _previous(frames, upto, bone, chan):
    for i in range(upto - 1, -1, -1):
        val = frames[i][2].get(bone, {}).get(chan)
        if val is not None:
            return val
    return _rest(bone, chan)


def _strike_keys(frames, family, explicit_land, no_over=()):
    """撃発の目標角から、行き過ぎ頂点と戻り着地を作る。

    行き過ぎは *進んできた向き* に足す。目標角そのものに掛けると、
    まっすぐ伸ばす前腕（-104 → -6）が 0.2° しか行き過ぎず、
    しなりが完全に消える。
    """
    idx = next(i for i, f in enumerate(frames) if f[0] == "d")
    over = FAMILIES[family]["over"]
    apex, land = {}, {}
    for bone, channels in frames[idx][2].items():
        for chan, value in channels.items():
            if chan == "s":
                apex.setdefault(bone, {})["s"] = value
                continue
            if bone in no_over:
                # 一回転する技は行き過ぎさせない。回りきってから戻すと、
                # 360° の途中で逆回転して見える。
                apex.setdefault(bone, {})[chan] = list(value)
                land.setdefault(bone, {})[chan] = list(value)
                continue
            prev = _previous(frames, idx, bone, chan)
            # 位置だけは系統によらず 8%。腰が角度と同じ率で跳ねると足が滑る。
            k = OVER_POS if chan == "p" else over * over_mul(bone)
            apex.setdefault(bone, {})[chan] = [
                _r(v + (v - p) * k) for v, p in zip(value, prev)]
            land.setdefault(bone, {})[chan] = [
                _r(v - (v - p) * UNDERSHOOT) for v, p in zip(value, prev)]
    for bone, channels in (explicit_land or {}).items():
        land.setdefault(bone, {}).update(channels)
    frames[idx][2] = apex
    return land


def _series(frames, bone):
    rows = sorted((t, pose[bone]["r"][0]) for _b, t, pose in frames
                  if "r" in pose.get(bone, {}))
    def at(t):
        if not rows:
            return 0.0
        if t <= rows[0][0]:
            return rows[0][1]
        for (t0, a), (t1, b) in zip(rows, rows[1:]):
            if t0 <= t <= t1:
                k = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return a + (b - a) * k
        return rows[-1][1]
    return at


def _cape_gravity(cape_bones, frames, gain=0.85, root="cape0"):
    """胸が反った分だけ、マントの根本を戻す。

    マントは親（胸）に固定されているので、上体を 40° 反らすと
    マントも 40° 前へ倒れて **脚を突き抜ける**。布は重力で下を向くので、
    反った分は根本で打ち消す。前傾側は打ち消さない —
    前へ踏み込めば慣性でマントは後ろへ流れる。そちらは cape6 の振りが正しい。
    """
    body, chest = _series(frames, "body"), _series(frames, "chest")
    track_ = cape_bones.get(root, {}).get("rotation")
    if not track_:
        return cape_bones
    for key, value in track_.items():
        adjust = -gain * min(0.0, body(float(key)) + chest(float(key)))
        if not adjust:
            continue
        vec = value["post"] if isinstance(value, dict) else value
        vec[0] = _r(vec[0] + adjust)
    return cape_bones


#: 腕と脚は body の **子ではない**（どちらも root ボーン）。
#: 腰を上下させると肩と腿だけ取り残されて、腰で体が分かれて見える。
CARRY = (("rightArm", 1.0), ("leftArm", 1.0),
         ("rightLeg", 0.0), ("leftLeg", 0.0))

#: 追従の位置だけは遅らせない。1 tick でも遅れると腰に隙間が開く。
NO_LAG = {(bone, "p") for bone, _up in CARRY}


def _carry_body(frames):
    """腰の平行移動を、腕（全部）と脚（浮いた分だけ）へ配る。

    沈み込みで脚まで下げると足が地面へめり込む。膝を折って沈むのが正しいので、
    下向きは腕だけ、上向き（浮遊・跳躍）は脚も連れて行く。
    """
    for _beat, _t, pose in frames:
        shift = pose.get("body", {}).get("p")
        if shift is None:
            continue
        for bone, down in CARRY:
            if "p" in pose.get(bone, {}):
                continue
            y = shift[1] if (down or shift[1] > 0) else 0.0
            pose.setdefault(bone, {})["p"] = [shift[0], y, shift[2]]


def _blend(a, b, k):
    return [_r(x + (y - x) * k) for x, y in zip(a, b)]


def assemble(frames, length, lag_extra=None) -> dict:
    """``[(拍, 秒, ポーズ)]`` を、ボーンごとの遅れを付けてキーに落とす。

    最初と最後のキーだけは遅らせない。ここをずらすと、
    クリップの頭と尻でボーンが取り残されて前後の動きと繋がらない。
    """
    lag_extra = lag_extra or {}
    per: dict = {}
    for beat, t, pose in frames:
        mode = MODE[beat]
        for bone, channels in pose.items():
            base_lag = lag_extra.get(bone, lag_of(bone))
            for chan, value in channels.items():
                lag = 0.0 if (bone, chan) in NO_LAG else base_lag
                when = (t if t <= 0 or t >= length
                        else min(length, max(0.0, t + lag)))
                rows = per.setdefault(bone, {}).setdefault(chan, {})
                rows[tag(when)] = (when, value, mode)
    out = {}
    for bone, channels in per.items():
        out[bone] = {CHAN[chan]: track([rows[k] for k in
                                        sorted(rows, key=float)])
                     for chan, rows in channels.items()}
    return out


def compose(group, name, family, length, cape_profile, hold_pose, spec,
            particles=None, lag_extra=None, cape_bones=None):
    t = times(family, length)
    frames = []
    for beat in ORDER:
        if beat not in t:
            continue
        if beat == "s" and "s" not in spec:
            # 完全静止 = 溜めきりと同値の 2 キー。この 0.30 秒の無音が必殺の条件。
            pose = _norm(spec["c"])
        elif beat in spec:
            pose = _norm(spec[beat])
        else:
            continue
        frames.append([beat, t[beat], pose])

    for extra in spec.get("extra", ()):
        mode = extra[2] if len(extra) > 2 else "d"
        frames.append(["x" if mode in ("d", "linear") else "xs",
                       extra[0], _norm(extra[1])])

    authored = {b for _k, _t, pose in frames for b in pose}
    _autofill(frames, authored)

    explicit_land = _norm(spec["e"]) if "e" in spec else None
    frames = [f for f in frames if f[0] != "e"]
    land = _strike_keys(frames, family, explicit_land,
                        set(spec.get("no_over", ())))
    # 連撃技は戻り着地も残心も要らない。二撃目そのものが次の到達点で、
    # 間に「少し戻る」キーを挟むと、撃った腕がいちいち引っ込んで見える。
    chain = bool(spec.get("chain"))
    if not chain:
        frames.append(["e", t["e"], land])

    touched = {b for _k, _t, pose in frames for b in pose}
    end = {}
    for bone in touched:
        chans = {c for _k, _t, pose in frames for c in pose.get(bone, {})}
        end[bone] = {}
        for chan in chans:
            if chan == "s":
                continue
            if not hold_pose:
                end[bone][chan] = _rest(bone, chan)
                continue
            # 保持系は着地の値をそのまま終端に置く。同値 2 キーの linear なので
            # 「構えたまま止まる」。ここをニュートラルへ寄せると保持が解け始める。
            end[bone][chan] = land.get(bone, {}).get(
                chan, _previous(frames, len(frames), bone, chan))
    for bone, channels in _norm(spec.get("end", {})).items():
        end.setdefault(bone, {}).update(channels)

    start = {b: {c: _rest(b, c) for c in end[b]} for b in end}
    frames.insert(0, ["a", 0.0, start])

    if not hold_pose and not chain:
        # 残心の中間。着地から終端へ直線で戻すと、最後だけ機械に見える。
        mid = {}
        for bone, channels in end.items():
            for chan, value in channels.items():
                src = land.get(bone, {}).get(chan)
                if src is None:
                    continue
                mid.setdefault(bone, {})[chan] = _blend(src, value, 0.55)
        if mid:
            frames.append(["g", t["g"], mid])
    frames.append(["f", t["f"], end])

    for bone, value in SQUASH[family].items():
        if bone not in touched:
            continue
        frames.append(["c", round(t["d"] - 0.03, 2), {bone: {"s": [1, 1, 1]}}])
        frames.append(["d", t["d"], {bone: {"s": list(value)}}])
        frames.append(["e", t["e"], {bone: {"s": [1, 1, 1]}}])

    _carry_body(frames)
    bones = assemble(frames, length, lag_extra)
    if cape_profile:
        cape_bones = cape_bones or cape6(
            cape_profile, length, t["d"], limit=CAPE_LIMIT[cape_profile])
        bones = merge(bones, _cape_gravity(cape_bones, frames))
    A[K.anim(group, name)] = clip(
        bones, length=length,
        loop="hold_on_last_frame" if hold_pose else False,
        particles=particles, override=True)
    return t


def tech(name, particles=None, lag_extra=None, **spec):
    family, length, cape_profile, hold_pose = TIMING[name]
    t = compose("tech", name, family, length, cape_profile, hold_pose, spec,
                particles=particles, lag_extra=lag_extra)
    return t


def fxline(tech_name, rows) -> dict:
    """撃発の tick を 0 とした相対 tick で ``particle_effects`` を組む。

    絵と煙は 1〜2 tick の話なので、秒で書くと必ずずれる。技の名前から
    撃発時刻を引くので、拍を変えてもエフェクトが勝手に付いてくる。

    - 加算の層を同じ tick に 2 枚置くと白が濁る（§5-1）ので衝突は例外にする。
    - クリップ終端より後ろの tick は **一度も再生されない**。末尾で頭打ちにする。
    """
    family, length = (TIMING.get(tech_name) or ALLY_TIMING[tech_name])[:2]
    base = round(times(family, length)["d"] * 20)
    last = int(length * 20) - 1
    out: dict = {}
    for row in rows:
        offset, name = row[0], row[1]
        if name not in K.PARTICLES:
            raise SystemExit(f"contract に無いパーティクル: {name}")
        tick = max(0, base + offset)
        # 尻の余韻がクリップより長い分は、終端から詰めて必ず鳴らす。
        # 溢れていない同 tick の重なりは author の間違いなので落とす。
        while tick > last or (tick > 0 and tag(tick / 20.0) in out
                              and base + offset > last):
            tick -= 1
        key = tag(tick / 20.0)
        if key in out:
            raise SystemExit(f"同じ tick に 2 枚: {tech_name} {name} @ {key}")
        effect = {"effect": K.part(name)}
        if len(row) > 2 and row[2]:
            effect["locator"] = row[2]
        out[key] = effect
    return out


# ===========================================================================
#  3. マグニートーの技 15
# ===========================================================================
#  決め絵（撃発の一枚絵）は 15 種すべて別のものにする。§5-5 の表が正典。

# --- 1. 磁力斥力 ------------------------------------------------------------
#  決め絵: 両掌を前下へ突き出し、腰は開ききり、前脚を深く踏み抜く。
tech(
    "repulse",
    b=P(body=[-4, 24, 0], head=[-6, -16, 0],
        rightArm=[-26, 30, -6], leftArm=[-30, -18, 8],
        rightForearm=[-70, 0, 0], leftForearm=[-70, 0, 0],
        rightLeg=[-10, 0, 0], leftLeg=[8, 0, 0]),
    c=P(body=[-8, 30, 0], head=[-8, -20, 0],
        rightArm=[-40, 36, -10], leftArm=[-40, -24, 12],
        rightForearm=[-104, 0, 0], leftForearm=[-104, 0, 0],
        rightHand=[-22, 0, 0], leftHand=[-22, 0, 0],
        rightLeg=[-14, 0, 0], leftLeg=[10, 0, 0], rightShin=[18, 0, 0]),
    d=P(body={"r": [10, -18, 0], "p": [0, -1.4, 1.2]}, head=[4, 6, 0],
        rightArm=[-90, -10, -6], leftArm=[-90, 10, 6],
        rightForearm=[-4, 0, 0], leftForearm=[-4, 0, 0],
        rightHand=[12, 0, 0], leftHand=[12, 0, 0],
        rightLeg=[20, 0, 0], leftLeg=[-26, 0, 0],
        rightShin=[6, 0, 0], leftShin=[30, 0, 0], rightFoot=[14, 0, 0]),
    lag_extra={"rightLeg": 0.06, "rightShin": 0.06},   # 右は遊脚
    particles=fxline("repulse", [
        (-5, "mag_field", "rightHand"),
        (-1, "mag_spark", "rightHand"),
        (0, "repulse_wave"),
        (1, "mag_ring_wide"),
        (2, "mag_push"),
        (3, "impact_dust"),
        (4, "shard_burst"),
        (11, "mag_dust"),
    ]))

# --- 2. 磁力引力 ------------------------------------------------------------
#  決め絵: 肘を肋の後ろまで引き込み、上体は仰け反る。粒が顔へ向かって加速する。
tech(
    "attract",
    b=P(body={"r": [6, -10, 0], "p": [0, 0, 0.8]}, head=[-4, 8, 0],
        rightArm=[-96, -14, -6], rightForearm=[-6, 0, 0],
        rightHand=[-30, 0, 0], leftArm=[-58, 18, 10],
        leftForearm=[-20, 0, 0]),
    c=P(body={"r": [8, -12, 0], "p": [0, 0, 1.2]}, head=[-6, 10, 0],
        rightArm=[-104, -16, -6], rightForearm=[-4, 0, 0],
        rightHand=[-38, 0, 0], leftArm=[-64, 20, 10]),
    d=P(body={"r": [-16, 22, 0], "p": [0, 0.4, -1.4]}, head=[10, -14, 0],
        rightArm=[-34, 34, -16], rightForearm=[-110, 0, 0],
        rightHand=[24, 0, 0], leftArm=[-70, -30, 14],
        leftForearm=[-40, 0, 0], leftHand=[16, 0, 0],
        rightLeg=[-14, 0, 0], leftLeg=[10, 0, 0], rightShin=[16, 0, 0]),
    particles=fxline("attract", [
        (-5, "mag_field", "rightHand"),
        (-1, "attract_funnel"),
        (0, "mag_pull"),
        (2, "metal_glint"),
        (4, "debris_dust"),
        (10, "mag_dust"),
    ]))

# --- 3. 金属剥奪 ------------------------------------------------------------
#  決め絵: 右腕を真横へ薙ぎ払いきり、掌を開く。首だけが逆へ残る。
tech(
    "disarm",
    b=P(body=[-2, 34, 0], head=[0, -22, 0],
        rightArm=[-64, 52, -10], rightForearm=[-40, 0, 0],
        rightHand=[-16, 0, 0], leftArm=[-16, 0, 12]),
    c=P(body=[-4, 40, 0], head=[-2, -26, 0],
        rightArm=[-72, 58, -12], rightForearm=[-48, 0, 0],
        rightHand=[-26, 0, 0], leftArm=[-18, 4, 12],
        rightLeg=[-12, 0, 0], leftLeg=[8, 0, 0]),
    d=P(body={"r": [4, -36, 0], "p": [0, 0, 0.6]}, head=[0, 26, 0],
        rightArm=[-84, -54, -20], rightForearm=[-14, 0, 0],
        rightHand=[22, 0, 0], leftArm=[-10, 12, 18],
        rightLeg=[10, 0, 0], leftLeg=[-8, 0, 0]),
    particles=fxline("disarm", [
        (-5, "mag_field", "rightHand"),
        (-1, "mag_glyph", "chest"),
        (0, "disarm_flash"),
        (2, "metal_rip"),
        (4, "rust_flake"),
        (6, "debris_dust"),
        (12, "mag_dust"),
    ]))

# --- 4. 磁界斬 --------------------------------------------------------------
#  決め絵: フェンシングの突き。右腕は水平、左腕は真後ろ、後脚が伸びきる。
tech(
    "lance",
    b=P(body={"r": [-4, 44, 0], "p": [0, 0, -1.6]}, head=[-4, -26, 0],
        rightArm=[-30, 52, -10], rightForearm=[-116, 0, 0],
        leftArm=[-20, -26, 10], rightLeg=[-16, 0, 0], leftLeg=[8, 0, 0]),
    c=P(body={"r": [-6, 50, 0], "p": [0, -0.6, -2.2]}, head=[-6, -28, 0],
        rightArm=[-26, 56, -12], rightForearm=[-124, 0, 0],
        rightHand=[-14, 0, 0], leftArm=[-22, -30, 10],
        rightLeg=[-20, 0, 0], rightShin=[26, 0, 0]),
    d=P(body={"r": [6, -26, 0], "p": [0, -1.0, 3.0]}, head=[2, 12, 0],
        rightArm=[-92, -18, -4], rightForearm=[-2, 0, 0],
        rightHand=[-6, 0, 0], leftArm=[-14, 30, 22], leftForearm=[-8, 0, 0],
        rightLeg=[26, 0, 0], leftLeg=[-30, 0, 0],
        rightShin=[2, 0, 0], leftShin=[34, 0, 0], rightFoot=[18, 0, 0]),
    lag_extra={"rightLeg": 0.06, "rightShin": 0.06, "rightFoot": 0.06},
    particles=fxline("lance", [
        (-4, "mag_field", "rightHand"),
        (-1, "mag_spark", "rightHand"),
        (0, "lance_streak"),
        (1, "shard_trail"),
        (3, "lance_impact"),
        (5, "impact_dust"),
        (10, "mag_dust"),
    ]))

# --- 5. 磁気飛行 ------------------------------------------------------------
#  決め絵: 爪先まで一直線。腕は後ろへ 45°、顎が上がる。以降は hover が受ける。
tech(
    "flight",
    b=P(body={"r": [20, 0, 0], "p": [0, -2.4, 0]}, head=[-14, 0, 0],
        rightArm=[-6, 0, -20], leftArm=[-6, 0, 20],
        rightForearm=[-56, 0, 0], leftForearm=[-56, 0, 0],
        rightLeg=[-26, 0, 0], leftLeg=[-26, 0, 0],
        rightShin=[44, 0, 0], leftShin=[44, 0, 0]),
    c=P(body={"r": [24, 0, 0], "p": [0, -3.0, 0]}, head=[-18, 0, 0],
        rightArm=[-4, 0, -16], leftArm=[-4, 0, 16],
        rightForearm=[-64, 0, 0], leftForearm=[-64, 0, 0],
        rightLeg=[-34, 0, 0], leftLeg=[-34, 0, 0],
        rightShin=[56, 0, 0], leftShin=[56, 0, 0],
        rightFoot=[-14, 0, 0], leftFoot=[-14, 0, 0]),
    d=P(body={"r": [-22, 0, 0], "p": [0, 3.6, 0]}, head=[-26, 0, 0],
        rightArm=[30, 0, -30], leftArm=[30, 0, 30],
        rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
        rightLeg=[12, 0, 0], leftLeg=[12, 0, 0],
        rightShin=[0, 0, 0], leftShin=[0, 0, 0],
        rightFoot=[34, 0, 0], leftFoot=[34, 0, 0]),
    end=P(body={"r": [-14, 0, 0], "p": [0, 2.8, 0]}, head=[-18, 0, 0],
          rightArm=[22, 0, -26], leftArm=[22, 0, 26],
          rightForearm=[-12, 0, 0], leftForearm=[-12, 0, 0],
          rightLeg=[8, 0, 0], leftLeg=[8, 0, 0],
          rightFoot=[28, 0, 0], leftFoot=[28, 0, 0]),
    particles=fxline("flight", [
        (-4, "mag_field", "feet"),
        (0, "flight_burst"),
        (1, "levitate_dust"),
        (3, "flight_trail"),
        (6, "cape_wind"),
    ]))

# --- 6. 磁力視 --------------------------------------------------------------
#  決め絵: 指を兜のこめかみへ。動きは最小で、首だけが静かに振れる。
tech(
    "sight",
    b=P(rightArm=[-116, -26, -8], rightForearm=[-64, 0, 30],
        head=[-2, -6, 0], body=[0, 2, 0]),
    c=P(rightArm=[-132, -30, -10], rightForearm=[-76, 0, 38],
        rightHand=[-10, 0, 0], head=[-4, 6, 0], body=[0, 4, 0]),
    d=P(rightArm=[-140, -33, -10], rightForearm=[-84, 0, 44],
        rightHand=[-14, 0, 6], head=[-6, 16, 0], body=[0, 6, 0],
        leftArm=[-12, 6, 6]),
    end=P(rightArm=[-138, -32, -10], rightForearm=[-82, 0, 42],
          rightHand=[-12, 0, 4], head=[-6, -22, 0], body=[0, -8, 0],
          leftArm=[-10, 4, 6]),
    particles=fxline("sight", [
        (-5, "mag_field", "helm"),
        (0, "sight_ping", "helm"),
        (3, "mag_glyph", "helm"),
        (8, "mag_line"),
    ]))

# --- 7. 磁力障壁 ------------------------------------------------------------
#  決め絵: 前腕を胸前で交差し、顎を引いて踏み止まる。展開後はその形を保つ。
tech(
    "barrier",
    b=P(body={"r": [4, 0, 0], "p": [0, -0.8, 0]}, head=[-2, 0, 0],
        rightArm=[-30, 30, -26], leftArm=[-30, -30, 26],
        rightForearm=[-40, 0, 20], leftForearm=[-40, 0, -20],
        rightLeg=[-16, 0, 0], leftLeg=[12, 0, 0]),
    c=P(body={"r": [8, 0, 0], "p": [0, -1.6, 0]}, head=[-8, 0, 0],
        rightArm=[-52, 40, -30], leftArm=[-52, -40, 30],
        rightForearm=[-76, 0, 40], leftForearm=[-76, 0, -40],
        rightLeg=[-22, 0, 0], leftLeg=[16, 0, 0],
        rightShin=[28, 0, 0], leftShin=[8, 0, 0]),
    d=P(body={"r": [6, 0, 0], "p": [0, -1.2, 0]}, head=[-12, 0, 0],
        rightArm=[-66, 26, -22], leftArm=[-66, -26, 22],
        rightForearm=[-92, 0, 52], leftForearm=[-92, 0, -52],
        rightHand=[-12, 0, 0], leftHand=[-12, 0, 0],
        rightLeg=[-20, 0, -4], leftLeg=[16, 0, 4],
        rightShin=[26, 0, 0], leftShin=[10, 0, 0]),
    particles=fxline("barrier", [
        (-5, "mag_field", "chest"),
        (-1, "mag_spark", "chest"),
        (0, "barrier_hex"),
        (2, "mag_ring"),
        (6, "mag_glyph"),
        (14, "mag_dust"),
    ]))

# --- 8. 鋼鉄拘束 ------------------------------------------------------------
#  決め絵: 腰高で両手を握り、内へ捻り込む万力。腰が沈み、肘が張る。
tech(
    "iron_bind",
    b=P(body={"r": [-6, 0, 0], "p": [0, 0.6, 0]}, head=[-10, 0, 0],
        rightArm=[-60, -34, -22], leftArm=[-60, 34, 22],
        rightForearm=[-30, 0, -18], leftForearm=[-30, 0, 18],
        rightHand=[-24, 0, 0], leftHand=[-24, 0, 0]),
    mid=P(body=[-2, 0, 0], rightArm=[-76, -30, -18], leftArm=[-76, 30, 18],
          rightForearm=[-28, 0, -24], leftForearm=[-28, 0, 24]),
    c=P(body={"r": [-2, 0, 0], "p": [0, 0, 0.4]}, head=[-4, 0, 0],
        rightArm=[-88, -26, -16], leftArm=[-88, 26, 16],
        rightForearm=[-26, 0, -30], leftForearm=[-26, 0, 30],
        rightHand=[-30, 0, 0], leftHand=[-30, 0, 0]),
    d=P(body={"r": [10, 0, 0], "p": [0, -1.6, 0]}, head=[12, 0, 0],
        rightArm=[-74, 28, -30], leftArm=[-74, -28, 30],
        rightForearm=[-16, 0, -58], leftForearm=[-16, 0, 58],
        rightHand=[16, 0, 0], leftHand=[16, 0, 0],
        rightLeg=[-18, 0, -6], leftLeg=[-18, 0, 6],
        rightShin=[26, 0, 0], leftShin=[26, 0, 0]),
    particles=fxline("iron_bind", [
        (-10, "mag_field", "rightHand"),
        (-6, "mag_glyph"),
        (-2, "mag_line"),
        (0, "bind_weld"),
        (2, "mag_spark"),
        (4, "shard_spark"),
        (8, "impact_dust"),
        (16, "mag_dust"),
    ]))

# --- 9. EMPパルス -----------------------------------------------------------
#  決め絵: こめかみから両手を真横下へ振り抜き、頭を仰け反らせて胸を開く。
tech(
    "emp",
    b=P(body=[2, 0, 0], head=[4, 0, 0],
        rightArm=[-140, -30, -8], leftArm=[-140, 30, 8],
        rightForearm=[-80, 0, 44], leftForearm=[-80, 0, -44]),
    mid=P(body=[3, 0, 0], head=[7, 0, 0],
          rightArm=[-144, -32, -7], leftArm=[-144, 32, 7],
          rightForearm=[-86, 0, 47], leftForearm=[-86, 0, -47]),
    c=P(body={"r": [4, 0, 0], "p": [0, -0.8, 0]}, head=[10, 0, 0],
        rightArm=[-148, -34, -6], leftArm=[-148, 34, 6],
        rightForearm=[-92, 0, 50], leftForearm=[-92, 0, -50],
        rightHand=[-14, 0, 0], leftHand=[-14, 0, 0],
        rightLeg=[-8, 0, 0], leftLeg=[-8, 0, 0]),
    d=P(body={"r": [-16, 0, 0], "p": [0, 1.6, 0]}, head=[-30, 0, 0],
        rightArm=[-30, -24, -52], leftArm=[-30, 24, 52],
        rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
        rightHand=[-16, 0, 0], leftHand=[-16, 0, 0],
        rightLeg=[-6, 0, 0], leftLeg=[-6, 0, 0],
        rightShin=[10, 0, 0], leftShin=[10, 0, 0]),
    particles=fxline("emp", [
        (-10, "mag_field", "helm"),
        (-5, "mag_glyph", "helm"),
        (-1, "mag_spark", "helm"),
        (0, "emp_wave"),
        (2, "emp_arc"),
        (5, "mag_ring"),
        (10, "mag_dust"),
    ]))

# --- 10. 磁気圧壊 -----------------------------------------------------------
#  決め絵: 前で握り締めた拳へ、全身が内側へ縮む。肩が上がり、胸が丸まる。
tech(
    "crush",
    b=P(body=[-4, -14, 0], head=[-6, 10, 0],
        rightArm=[-96, -18, -6], rightForearm=[-8, 0, 0],
        rightHand=[-36, 0, 0], leftArm=[-24, 14, 10]),
    mid=P(body=[-5, -15, 0], rightArm=[-100, -19, -6],
          rightHand=[-39, 0, 0]),
    c=P(body={"r": [-6, -16, 0], "p": [0, 0.4, 0]}, head=[-8, 12, 0],
        rightArm=[-104, -20, -6], rightForearm=[-4, 0, 0],
        rightHand=[-42, 0, 0], leftArm=[-28, 16, 10],
        leftForearm=[-18, 0, 0]),
    d=P(body={"r": [14, -8, 0], "p": [0, -2.0, 0]}, head=[10, 4, 0],
        rightArm=[-84, -14, -10], rightForearm=[-26, 0, 0],
        rightHand=[30, 0, 0], leftArm=[-36, 16, 14],
        leftForearm=[-30, 0, 0], leftHand=[24, 0, 0],
        rightLeg=[-14, 0, -4], leftLeg=[-12, 0, 4],
        rightShin=[20, 0, 0], leftShin=[18, 0, 0]),
    particles=fxline("crush", [
        (-10, "mag_field", "rightHand"),
        (-4, "mag_line"),
        (0, "crush_implode"),
        (2, "crush_blood"),
        (4, "debris_chunk"),
        (7, "impact_dust"),
        (14, "mag_dust"),
    ]))

# --- 11. 鋼鉄の玉座 ---------------------------------------------------------
#  決め絵: 立ち上がりざま両腕を低く外へ払い、顎を上げる。足元へ鉄板が集まる。
tech(
    "throne",
    b=P(body={"r": [18, 10, 0], "p": [0, -1.6, 0]}, head=[-20, -8, 0],
        rightArm=[-26, 18, -14], leftArm=[-22, -14, 14],
        rightForearm=[-50, 0, 0], leftForearm=[-50, 0, 0]),
    mid=P(body={"r": [20, 8, 0], "p": [0, -1.9, 0]}, head=[-22, -4, 0],
          rightArm=[-33, 20, -16], leftArm=[-29, -16, 16],
          rightForearm=[-56, 0, 0], leftForearm=[-56, 0, 0]),
    c=P(body={"r": [22, 6, 0], "p": [0, -2.2, 0]}, head=[-24, 0, 0],
        rightArm=[-40, 22, -18], leftArm=[-36, -18, 18],
        rightForearm=[-62, 0, 0], leftForearm=[-62, 0, 0],
        rightHand=[-18, 0, 0], leftHand=[-18, 0, 0],
        rightLeg=[-26, 0, 0], leftLeg=[-26, 0, 0],
        rightShin=[38, 0, 0], leftShin=[38, 0, 0]),
    # EMP も腕を左右へ張るので、玉座は **低く後ろへ** 開いて差を付ける。
    # 掌を下へ向けたまま浮き上がる、王が椅子に降りる形。
    d=P(body={"r": [-8, 0, 0], "p": [0, 1.4, 0]}, head=[-18, 0, 0],
        rightArm=[12, -10, -32], leftArm=[12, 10, 32],
        rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
        rightHand=[22, 0, 0], leftHand=[22, 0, 0],
        rightLeg=[-6, 0, -4], leftLeg=[-6, 0, 4],
        rightShin=[8, 0, 0], leftShin=[8, 0, 0],
        rightFoot=[16, 0, 0], leftFoot=[16, 0, 0]),
    particles=fxline("throne", [
        (-11, "mag_field", "feet"),
        (-5, "mag_dust"),
        (0, "throne_dust"),
        (2, "debris_chunk"),
        (4, "metal_glint"),
        (8, "debris_dust"),
        (16, "rust_flake"),
    ]))

# --- 12. 鉄片嵐 -------------------------------------------------------------
#  決め絵: 右腕は標的へ真っ直ぐ、左腕は後ろ上へ水平に払う半身。環から 1 発ずつ抜ける。
tech(
    "shard_storm",
    b=P(body=[-6, 18, 0], head=[-14, -10, 0],
        rightArm=[-40, 24, -14], leftArm=[-40, -20, 14],
        rightForearm=[-70, 0, 0], leftForearm=[-70, 0, 0]),
    mid=P(body={"r": [-8, 22, 0], "p": [0, 0.4, 0]}, head=[-17, -12, 0],
          rightArm=[-70, 27, -20], leftArm=[-70, -23, 20],
          rightForearm=[-50, 0, 0], leftForearm=[-50, 0, 0]),
    c=P(body={"r": [-10, 26, 0], "p": [0, 0.8, 0]}, head=[-20, -14, 0],
        rightArm=[-96, 30, -26], leftArm=[-96, -26, 26],
        rightForearm=[-30, 0, 0], leftForearm=[-30, 0, 0],
        rightHand=[-20, 0, 0], leftHand=[-20, 0, 0],
        rightLeg=[-10, 0, 0], leftLeg=[6, 0, 0]),
    d=P(body={"r": [6, -22, 0], "p": [0, -0.4, 0.8]}, head=[2, 14, 0],
        rightArm=[-94, -6, -6], rightForearm=[-2, 0, 0],
        rightHand=[-10, 0, 0], leftArm=[-58, 40, 40],
        leftForearm=[-20, 0, 0], leftHand=[14, 0, 0],
        rightLeg=[16, 0, 0], leftLeg=[-20, 0, 0],
        rightShin=[4, 0, 0], leftShin=[22, 0, 0]),
    lag_extra={"rightLeg": 0.06, "rightShin": 0.06},
    particles=fxline("shard_storm", [
        (-12, "mag_aura"),
        (-7, "storm_swirl"),
        (-2, "shard_spark"),
        (0, "shard_burst"),
        (2, "shard_trail"),
        (5, "metal_glint"),
        (9, "impact_dust"),
        (16, "mag_dust"),
    ]))

# --- 13. 磁極反転 -----------------------------------------------------------
#  決め絵: 前上 45° に伸ばした両腕の掌を **返す**。体が反り、周囲が同時に浮く。
tech(
    "polarity",
    b=P(body={"r": [4, 0, 0], "p": [0, -0.6, 0]}, head=[6, 0, 0],
        rightArm=[-70, -20, -20], leftArm=[-70, 20, 20],
        rightForearm=[-56, 0, 0], leftForearm=[-56, 0, 0],
        rightHand=[-34, 0, 0], leftHand=[-34, 0, 0]),
    mid=P(body={"r": [6, 0, 0], "p": [0, -1.0, 0]}, head=[8, 0, 0],
          rightArm=[-77, -24, -18], leftArm=[-77, 24, 18],
          rightForearm=[-50, 0, 0], leftForearm=[-50, 0, 0],
          rightHand=[-37, 0, 0], leftHand=[-37, 0, 0]),
    c=P(body={"r": [8, 0, 0], "p": [0, -1.4, 0]}, head=[10, 0, 0],
        rightArm=[-84, -28, -16], leftArm=[-84, 28, 16],
        rightForearm=[-44, 0, 0], leftForearm=[-44, 0, 0],
        rightHand=[-40, 0, 0], leftHand=[-40, 0, 0],
        rightLeg=[-10, 0, 0], leftLeg=[-10, 0, 0],
        rightShin=[14, 0, 0], leftShin=[14, 0, 0]),
    d=P(body={"r": [-18, 0, 0], "p": [0, 2.0, 0]}, head=[-24, 0, 0],
        rightArm=[-124, -12, -10], leftArm=[-124, 12, 10],
        rightForearm=[-6, 0, 0], leftForearm=[-6, 0, 0],
        rightHand=[40, 0, 0], leftHand=[40, 0, 0],
        rightLeg=[6, 0, 0], leftLeg=[6, 0, 0],
        rightShin=[0, 0, 0], leftShin=[0, 0, 0]),
    particles=fxline("polarity", [
        (-12, "mag_field", "chest"),
        (-6, "mag_glyph"),
        (-1, "mag_spark"),
        (0, "polarity_field"),
        (3, "mag_ring_wide"),
        (7, "levitate_dust"),
        (14, "mag_dust"),
    ]))

# --- 14. 大地隆起 -----------------------------------------------------------
#  決め絵: 深く沈んだ姿勢から両腕で鉱脈を掬い上げ、踵が地を離れる。
tech(
    "uprising",
    b=P(body={"r": [24, 0, 0], "p": [0, -3.0, 0]}, head=[-24, 0, 0],
        rightArm=[-14, 0, -28], leftArm=[-14, 0, 28],
        rightForearm=[-86, 0, 0], leftForearm=[-86, 0, 0],
        rightHand=[-20, 0, 0], leftHand=[-20, 0, 0],
        rightLeg=[-32, 0, 0], leftLeg=[-32, 0, 0],
        rightShin=[52, 0, 0], leftShin=[52, 0, 0]),
    mid=P(body={"r": [27, 0, 0], "p": [0, -3.4, 0]}, head=[-26, 0, 0],
          rightArm=[-12, 0, -26], leftArm=[-12, 0, 26],
          rightForearm=[-93, 0, 0], leftForearm=[-93, 0, 0],
          rightLeg=[-35, 0, 0], leftLeg=[-35, 0, 0],
          rightShin=[56, 0, 0], leftShin=[56, 0, 0]),
    c=P(body={"r": [30, 0, 0], "p": [0, -3.8, 0]}, head=[-28, 0, 0],
        rightArm=[-10, 0, -24], leftArm=[-10, 0, 24],
        rightForearm=[-100, 0, 0], leftForearm=[-100, 0, 0],
        rightHand=[-26, 0, 0], leftHand=[-26, 0, 0],
        rightLeg=[-38, 0, 0], leftLeg=[-38, 0, 0],
        rightShin=[60, 0, 0], leftShin=[60, 0, 0],
        rightFoot=[-16, 0, 0], leftFoot=[-16, 0, 0]),
    # 掲げる技が三つ（大地隆起・磁極反転・磁界の棺）あるので、ここだけは
    # 腕を V に開いて掌を上へ向ける。棺は逆に平行のまま掲げる。
    d=P(body={"r": [-24, 0, 0], "p": [0, 3.0, 0]}, head=[-38, 0, 0],
        rightArm=[-140, 0, -48], leftArm=[-140, 0, 48],
        rightForearm=[-46, 0, 0], leftForearm=[-46, 0, 0],
        rightHand=[20, 0, 0], leftHand=[20, 0, 0],
        rightLeg=[4, 0, 0], leftLeg=[4, 0, 0],
        rightShin=[0, 0, 0], leftShin=[0, 0, 0],
        rightFoot=[26, 0, 0], leftFoot=[26, 0, 0]),
    particles=fxline("uprising", [
        (-14, "mag_dust", "feet"),
        (-8, "mag_field", "feet"),
        (-2, "uprising_soil"),      # 先に地面が割れる。この順序が命。
        (0, "uprising_pillar"),
        (2, "debris_chunk"),
        (5, "impact_dust"),
        (9, "debris_dust"),
        (18, "rust_flake"),
    ]))

# --- 15. 磁界の棺（必殺技）---------------------------------------------------
#  決め絵: 頭上で完全静止 0.30 秒 → 全体重で振り下ろす。静止と撃発の落差が全て。
tech(
    "sphere",
    b=P(body={"r": [18, 0, 0], "p": [0, -2.4, 0]}, head=[-16, 0, 0],
        rightArm=[-20, 0, -32], leftArm=[-20, 0, 32],
        rightForearm=[-78, 0, 0], leftForearm=[-78, 0, 0],
        rightLeg=[-24, 0, 0], leftLeg=[-24, 0, 0],
        rightShin=[38, 0, 0], leftShin=[38, 0, 0]),
    mid=P(body={"r": [-14, 0, 0], "p": [0, 2.4, 0]}, head=[-30, 0, 0],
          rightArm=[-136, 0, -18], leftArm=[-136, 0, 18],
          rightForearm=[-28, 0, 0], leftForearm=[-28, 0, 0],
          rightHand=[-16, 0, 0], leftHand=[-16, 0, 0],
          rightLeg=[-4, 0, 0], leftLeg=[-4, 0, 0],
          rightShin=[10, 0, 0], leftShin=[10, 0, 0]),
    c=P(body={"r": [-26, 0, 0], "p": [0, 5.6, 0]}, head=[-40, 0, 0],
        rightArm=[-172, 0, -6], leftArm=[-172, 0, 6],
        rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
        rightHand=[-8, 0, 0], leftHand=[-8, 0, 0],
        rightLeg=[4, 0, 0], leftLeg=[4, 0, 0],
        rightShin=[0, 0, 0], leftShin=[0, 0, 0],
        rightFoot=[28, 0, 0], leftFoot=[28, 0, 0]),
    d=P(body={"r": [30, 0, 0], "p": [0, -1.2, 0.6]}, head=[26, 0, 0],
        rightArm=[-52, -10, -14], leftArm=[-52, 10, 14],
        rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0],
        rightHand=[18, 0, 0], leftHand=[18, 0, 0],
        rightLeg=[-22, 0, -6], leftLeg=[-22, 0, 6],
        rightShin=[30, 0, 0], leftShin=[30, 0, 0],
        rightFoot=[-8, 0, 0], leftFoot=[-8, 0, 0]),
    particles=fxline("sphere", [
        (-38, "mag_aura_max"),
        (-36, "sphere_orbit"),
        (-26, "sphere_core"),
        (-18, "mag_line"),
        (-14, "sphere_orbit"),
        (-8, "mag_spark"),          # 静止の頭。ここから 6 tick 全停止。
        (0, "sphere_collapse"),
        (2, "sphere_detonate"),
        (3, "shard_burst"),
        (4, "debris_chunk"),
        (6, "impact_dust"),
        (12, "debris_dust"),
        (22, "mag_dust"),
    ]))


# ===========================================================================
#  4. ブラザーフッドの技 27
# ===========================================================================
#  仲間はマントを持たない（スカーレット・ウィッチだけ 3 段）。
#  拍はマグニートーと同じ規約で揃えるが、決め絵はその能力らしさを優先する。

#: clip -> (系統, L 秒, 保持系か)
ALLY_TIMING = {
    "shapeshift": ("heavy", 1.20, False),
    "venom_strike": ("light", 0.66, False),
    "vanish": ("light", 0.84, False),
    "rend": ("light", 0.74, False),
    "feral_roar": ("heavy", 1.10, False),
    "regenerate": ("heavy", 1.30, False),
    "tongue_lash": ("light", 0.78, False),
    "leap": ("light", 0.84, False),
    "slime_spit": ("light", 0.72, False),
    "unstoppable": ("heavy", 1.40, False),
    "quake_stomp": ("heavy", 1.00, False),
    "hurl": ("heavy", 1.06, False),
    "blitz": ("light", 0.76, False),
    "afterimage": ("light", 0.80, False),
    "sonic_dash": ("light", 0.68, False),
    "flame_wave": ("light", 0.86, False),
    "fire_serpent": ("heavy", 1.16, False),
    "ignite": ("light", 0.60, False),
    "tremor": ("heavy", 1.00, False),
    "rockfall": ("heavy", 1.20, False),
    "fissure": ("heavy", 1.30, False),
    "immovable": ("heavy", 1.10, True),
    "belly_bounce": ("light", 0.84, False),
    "body_slam": ("heavy", 1.06, False),
    "hex_bolt": ("light", 0.70, False),
    "chaos_field": ("heavy", 1.34, False),
    "telekinesis": ("heavy", 1.10, True),
}


def witch_cape(length, strike):
    """スカーレット・ウィッチの 3 段マント（裾は cape2L/R の 2 枚だけ）。"""
    out = cape6("whip", length, strike, segments=2, limit=34.0)
    flare, yaw = 16, 9
    t_peak = min(strike + 0.06 * 3, length - 0.10)
    t_back = min(t_peak + length * 0.30, length - 0.04)
    for sign, bone in ((1, "cape2L"), (-1, "cape2R")):
        out[bone] = {"rotation": track([
            (0.0, [0, 0, 0], "linear"),
            (strike, [0, sign * yaw * -0.3, sign * flare * -0.25], "linear"),
            (t_peak, [0, sign * yaw, sign * flare]),
            (t_back, [0, sign * yaw * -0.4, sign * flare * -0.4]),
            (length, [0, 0, 0], "linear"),
        ])}
    return out


def ally(name, particles=None, lag_extra=None, cape=None, **spec):
    family, length, hold_pose = ALLY_TIMING[name]
    t = times(family, length)
    compose("ally", name, family, length, "whip" if cape else None, hold_pose,
            spec, particles=particles, lag_extra=lag_extra,
            cape_bones=cape(length, t["d"]) if cape else None)


# --- ミスティーク -----------------------------------------------------------
#  決め絵: 一回転しきった瞬間、腕が体に巻き付いて別人の輪郭になる。
ally(
    "shapeshift",
    b=P(body={"r": [0, -26, 0], "p": [0, -1.2, 0]}, head=[-14, 12, 0],
        rightArm=[-28, 0, -46], leftArm=[-28, 0, 46],
        rightForearm=[-72, 0, 0], leftForearm=[-72, 0, 0]),
    c=P(body={"r": [0, -34, 0], "p": [0, -1.6, 0]}, head=[-18, 16, 0],
        rightArm=[-36, 0, -52], leftArm=[-36, 0, 52],
        rightForearm=[-86, 0, 0], leftForearm=[-86, 0, 0],
        rightHand=[-24, 0, 0], leftHand=[-24, 0, 0]),
    no_over=("body",),
    d=P(body={"r": [0, 336, 0], "p": [0, 0.6, 0]}, head=[6, -20, 0],
        rightArm=[-66, 0, -18], leftArm=[-66, 0, 18],
        rightForearm=[-24, 0, 0], leftForearm=[-24, 0, 0],
        rightHand=[10, 0, 0], leftHand=[10, 0, 0]),
    end=P(body={"r": [0, 360, 0], "p": [0, 0, 0]}),
    particles=fxline("shapeshift", [(-8, "shift_shimmer"), (0, "shift_shimmer"),
                            (6, "mag_dust")]))

#  決め絵: 手刀を突き入れた腕一本の直線。上体はその線に乗る。
ally(
    "venom_strike",
    b=P(body=[0, 34, 0], head=[0, -20, 0],
        rightArm=[-126, -30, -14], rightForearm=[-56, 0, 0],
        rightHand=[-18, 0, 0], leftArm=[-20, -14, 10]),
    c=P(body=[-2, 40, 0], head=[-2, -24, 0],
        rightArm=[-134, -34, -14], rightForearm=[-64, 0, 0],
        rightHand=[-24, 0, 0], rightLeg=[-12, 0, 0], leftLeg=[8, 0, 0]),
    d=P(body={"r": [6, -26, 0], "p": [0, 0, 1.4]}, head=[0, 16, 0],
        rightArm=[-88, 20, 4], rightForearm=[-6, 0, 0],
        rightHand=[14, 0, 0], leftArm=[-16, 22, 16],
        rightLeg=[14, 0, 0], leftLeg=[-16, 0, 0], leftShin=[20, 0, 0]),
    particles=fxline("venom_strike", [(-3, "venom_drip", "rightHand"),
                            (0, "venom_drip", "rightHand"),
                            (4, "claw_slash")]))

#  決め絵: 沈み込みからの半回転。輪郭が薄れる瞬間に腕が消える。
ally(
    "vanish",
    b=P(body={"r": [18, 0, 0], "p": [0, -1.8, 0]}, head=[-16, 0, 0],
        rightArm=[-16, 0, -30], leftArm=[-16, 0, 30],
        rightLeg=[-22, 0, 0], leftLeg=[-22, 0, 0],
        rightShin=[34, 0, 0], leftShin=[34, 0, 0]),
    c=P(body={"r": [22, -20, 0], "p": [0, -2.2, 0]}, head=[-20, 10, 0],
        rightArm=[-24, 0, -36], leftArm=[-24, 0, 36],
        rightForearm=[-30, 0, 0], leftForearm=[-30, 0, 0],
        rightLeg=[-28, 0, 0], leftLeg=[-28, 0, 0],
        rightShin=[42, 0, 0], leftShin=[42, 0, 0]),
    no_over=("body",),
    d=P(body={"r": [-10, 300, 0], "p": [0, 1.4, 0]}, head=[8, -18, 0],
        rightArm=[-74, 0, -44], leftArm=[-74, 0, 44],
        rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
        rightLeg=[6, 0, 0], leftLeg=[6, 0, 0],
        rightShin=[0, 0, 0], leftShin=[0, 0, 0]),
    end=P(body={"r": [0, 360, 0], "p": [0, 0, 0]}),
    particles=fxline("vanish", [(-5, "shift_shimmer"), (0, "shift_shimmer"),
                            (5, "blur_after"), (12, "mag_dust")]))

# --- セイバートゥース -------------------------------------------------------
#  決め絵: 右爪が振り抜けた直後、左爪が入る二段。体は逆へ捻れたまま。
ally(
    "rend",
    chain=True,
    b=P(body=[-4, 42, 0], head=[-6, -26, 0],
        rightArm=[-142, -40, -22], leftArm=[-100, 40, 40],
        rightForearm=[-40, 0, 0], leftForearm=[-20, 0, 0]),
    c=P(body=[-6, 48, 0], head=[-8, -30, 0],
        rightArm=[-150, -44, -24], leftArm=[-104, 44, 44],
        rightForearm=[-48, 0, 0], rightHand=[-20, 0, 0],
        rightLeg=[-14, 0, 0], leftLeg=[10, 0, 0]),
    d=P(body={"r": [6, -34, 0], "p": [0, 0, 0.8]}, head=[4, 22, 0],
        rightArm=[-40, 44, 26], rightForearm=[-6, 0, 0],
        rightHand=[16, 0, 0], leftArm=[-132, -30, -30],
        leftForearm=[-42, 0, 0], rightLeg=[12, 0, 0], leftLeg=[-14, 0, 0]),
    # 二撃目。ここも到達点なので linear で止める。
    extra=[(0.44, P(body=[4, 26, 0], head=[0, -14, 0],
                    rightArm=[-118, -26, -18], rightForearm=[-30, 0, 0],
                    leftArm=[-38, -46, -26], leftForearm=[-6, 0, 0],
                    leftHand=[14, 0, 0]), "d")],
    particles=fxline("rend", [(0, "claw_slash"), (2, "hurt_spark"),
                            (9, "claw_slash"), (12, "blood_red")]))

#  決め絵: 顎を天へ向け、腕を左右へ張り出した咆哮。胸が最大に開く。
ally(
    "feral_roar",
    b=P(body={"r": [16, 0, 0], "p": [0, -1.6, 0]}, head=[-6, 0, 0],
        rightArm=[-30, 0, -48], leftArm=[-30, 0, 48],
        rightForearm=[-60, 0, 0], leftForearm=[-60, 0, 0]),
    mid=P(body={"r": [10, 0, 0], "p": [0, -1.0, 0]}, head=[-16, 0, 0],
          rightArm=[-40, 0, -54], leftArm=[-40, 0, 54],
          rightForearm=[-46, 0, 0], leftForearm=[-46, 0, 0]),
    c=P(body={"r": [4, 0, 0], "p": [0, -0.4, 0]}, head=[-26, 0, 0],
        rightArm=[-48, 0, -58], leftArm=[-48, 0, 58],
        rightForearm=[-34, 0, 0], leftForearm=[-34, 0, 0],
        rightLeg=[-12, 0, -6], leftLeg=[-12, 0, 6]),
    d=P(body={"r": [-16, 0, 0], "p": [0, 1.0, 0]}, head=[-44, 0, 0],
        rightArm=[-62, 0, -66], leftArm=[-62, 0, 66],
        rightForearm=[-20, 0, 0], leftForearm=[-20, 0, 0],
        rightHand=[-18, 0, 0], leftHand=[-18, 0, 0],
        rightLeg=[-8, 0, -8], leftLeg=[-8, 0, 8]),
    particles=fxline("feral_roar", [(-6, "mag_dust"), (0, "roar_wave"),
                            (3, "impact_dust"), (10, "debris_dust")]))

#  決め絵: 傷口を握り締めて背を丸め、そこから胸を開いて起き上がる。
ally(
    "regenerate",
    b=P(body={"r": [22, 0, 0], "p": [0, -2.0, 0]}, head=[16, 0, 0],
        rightArm=[-44, 20, -14], leftArm=[-30, -14, 12],
        rightForearm=[-84, 0, 0], leftForearm=[-70, 0, 0],
        rightHand=[-26, 0, 0]),
    mid=P(body={"r": [18, 0, 0], "p": [0, -1.6, 0]}, head=[12, 0, 0],
          rightArm=[-38, 16, -13], rightForearm=[-74, 0, 0],
          rightHand=[-32, 0, 0]),
    c=P(body={"r": [14, 0, 0], "p": [0, -1.2, 0]}, head=[8, 0, 0],
        rightArm=[-32, 12, -12], rightForearm=[-64, 0, 0],
        rightHand=[-36, 0, 0], rightLeg=[-14, 0, 0], leftLeg=[-14, 0, 0],
        rightShin=[22, 0, 0], leftShin=[22, 0, 0]),
    d=P(body={"r": [-14, 0, 0], "p": [0, 1.0, 0]}, head=[-20, 0, 0],
        rightArm=[-14, 0, -24], leftArm=[-14, 0, 24],
        rightForearm=[-16, 0, 0], leftForearm=[-16, 0, 0],
        rightHand=[10, 0, 0], rightLeg=[2, 0, 0], leftLeg=[2, 0, 0],
        rightShin=[0, 0, 0], leftShin=[0, 0, 0]),
    particles=fxline("regenerate", [(-10, "regen_knit"), (-4, "blood_red"),
                            (0, "regen_knit"), (8, "mag_dust")]))

# --- トード -----------------------------------------------------------------
#  決め絵: 顎が伸びきり、舌が出る一拍。肩は逆に引けている。
ally(
    "tongue_lash",
    b=P(body={"r": [-10, 0, 0], "p": [0, 0, -1.0]}, head=[-22, 0, 0],
        rightArm=[-14, 0, -18], leftArm=[-14, 0, 18],
        rightForearm=[-40, 0, 0], leftForearm=[-40, 0, 0]),
    c=P(body={"r": [-14, 0, 0], "p": [0, 0.4, -1.6]}, head=[-30, 0, 0],
        rightArm=[-20, 0, -22], leftArm=[-20, 0, 22],
        rightForearm=[-52, 0, 0], leftForearm=[-52, 0, 0],
        rightLeg=[-16, 0, 0], leftLeg=[-16, 0, 0],
        rightShin=[24, 0, 0], leftShin=[24, 0, 0]),
    d=P(body={"r": [18, 0, 0], "p": [0, -0.6, 2.4]}, head=[28, 0, 0],
        rightArm=[-26, 0, -34], leftArm=[-26, 0, 34],
        rightForearm=[-10, 0, 0], leftForearm=[-10, 0, 0],
        rightLeg=[-6, 0, 0], leftLeg=[-6, 0, 0],
        rightShin=[8, 0, 0], leftShin=[8, 0, 0]),
    particles=fxline("tongue_lash", [(-2, "tongue_slime", "head"),
                            (0, "tongue_slime", "head"),
                            (6, "slime_splat")]))

#  決め絵: 空中で体を折り畳んだ最高点。膝が胸に付く。
ally(
    "leap",
    b=P(body={"r": [30, 0, 0], "p": [0, -3.4, 0]}, head=[-14, 0, 0],
        rightArm=[-10, 0, -26], leftArm=[-10, 0, 26],
        rightLeg=[-42, 0, 0], leftLeg=[-42, 0, 0],
        rightShin=[68, 0, 0], leftShin=[68, 0, 0]),
    c=P(body={"r": [36, 0, 0], "p": [0, -4.2, 0]}, head=[-18, 0, 0],
        rightArm=[6, 0, -30], leftArm=[6, 0, 30],
        rightForearm=[-20, 0, 0], leftForearm=[-20, 0, 0],
        rightLeg=[-50, 0, 0], leftLeg=[-50, 0, 0],
        rightShin=[80, 0, 0], leftShin=[80, 0, 0],
        rightFoot=[-20, 0, 0], leftFoot=[-20, 0, 0]),
    d=P(body={"r": [-20, 0, 0], "p": [0, 3.6, 0]}, head=[-22, 0, 0],
        rightArm=[-140, 0, -20], leftArm=[-140, 0, 20],
        rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0],
        rightLeg=[-34, 0, 0], leftLeg=[-34, 0, 0],
        rightShin=[54, 0, 0], leftShin=[54, 0, 0],
        rightFoot=[16, 0, 0], leftFoot=[16, 0, 0]),
    particles=fxline("leap", [(-2, "leap_dust"), (0, "impact_dust"),
                            (8, "mag_dust")]))

#  決め絵: 上体ごと吐き出す。首が前へ抜け、肩が置き去りになる。
ally(
    "slime_spit",
    b=P(body=[-8, 0, 0], head=[-26, 0, 0],
        rightArm=[-12, 0, -14], leftArm=[-12, 0, 14]),
    c=P(body={"r": [-12, 0, 0], "p": [0, 0.2, -0.8]}, head=[-34, 0, 0],
        rightArm=[-16, 0, -18], leftArm=[-16, 0, 18],
        rightForearm=[-24, 0, 0], leftForearm=[-24, 0, 0]),
    d=P(body={"r": [14, 0, 0], "p": [0, 0, 1.4]}, head=[26, 0, 0],
        rightArm=[-24, 0, -26], leftArm=[-24, 0, 26],
        rightForearm=[-6, 0, 0], leftForearm=[-6, 0, 0]),
    particles=fxline("slime_spit", [(0, "slime_splat", "head"), (4, "tongue_slime")]))

# --- ジャガーノート ---------------------------------------------------------
#  決め絵: 肩から突っ込む。前傾が最大で、後脚が地を蹴り抜けている。
ally(
    "unstoppable",
    b=P(body={"r": [26, 0, 0], "p": [0, -2.4, -2.0]}, head=[-20, 0, 0],
        rightArm=[-34, 0, -18], leftArm=[-34, 0, 18],
        rightForearm=[-88, 0, 0], leftForearm=[-88, 0, 0],
        rightLeg=[-38, 0, 0], leftLeg=[22, 0, 0]),
    mid=P(body={"r": [30, 0, 0], "p": [0, -2.0, 0.4]}, head=[-24, 0, 0],
          rightArm=[-42, 0, -16], leftArm=[-42, 0, 16],
          rightLeg=[10, 0, 0], leftLeg=[-16, 0, 0]),
    c=P(body={"r": [34, 0, 0], "p": [0, -1.6, 2.0]}, head=[-26, 0, 0],
        rightArm=[-50, 0, -14], leftArm=[-50, 0, 14],
        rightForearm=[-96, 0, 0], leftForearm=[-96, 0, 0],
        rightLeg=[34, 0, 0], leftLeg=[-30, 0, 0],
        rightShin=[6, 0, 0], leftShin=[40, 0, 0]),
    d=P(body={"r": [40, 0, 0], "p": [0, -1.0, 3.4]}, head=[-30, 0, 0],
        rightArm=[-30, 0, -22], leftArm=[-30, 0, 22],
        rightForearm=[-70, 0, 0], leftForearm=[-70, 0, 0],
        rightLeg=[-36, 0, 0], leftLeg=[38, 0, 0],
        rightShin=[46, 0, 0], leftShin=[4, 0, 0]),
    particles=fxline("unstoppable", [(-14, "quake_dust"), (-6, "impact_dust"),
                            (0, "slam_ring"), (2, "quake_crack"),
                            (5, "debris_chunk"), (12, "quake_dust")]))

#  決め絵: 踏み抜いた脚が真下に伸びきり、上体は逆に反り返る。
ally(
    "quake_stomp",
    b=P(body={"r": [-14, 0, 0], "p": [0, 2.6, 0]}, head=[-12, 0, 0],
        rightArm=[-130, 0, -22], leftArm=[-130, 0, 22],
        rightLeg=[-64, 0, 0], rightShin=[76, 0, 0]),
    mid=P(body={"r": [-18, 0, 0], "p": [0, 3.0, 0]}, head=[-16, 0, 0],
          rightArm=[-146, 0, -18], leftArm=[-146, 0, 18],
          rightLeg=[-70, 0, 0], rightShin=[84, 0, 0]),
    c=P(body={"r": [-20, 0, 0], "p": [0, 3.2, 0]}, head=[-18, 0, 0],
        rightArm=[-152, 0, -16], leftArm=[-152, 0, 16],
        rightForearm=[-10, 0, 0], leftForearm=[-10, 0, 0],
        rightLeg=[-72, 0, 0], rightShin=[88, 0, 0], rightFoot=[-24, 0, 0]),
    d=P(body={"r": [24, 0, 0], "p": [0, -2.8, 0]}, head=[18, 0, 0],
        rightArm=[-16, 0, -14], leftArm=[-16, 0, 14],
        rightForearm=[-32, 0, 0], leftForearm=[-32, 0, 0],
        rightLeg=[16, 0, 0], rightShin=[0, 0, 0], rightFoot=[8, 0, 0],
        leftLeg=[-10, 0, 0], leftShin=[14, 0, 0]),
    particles=fxline("quake_stomp", [(-4, "quake_dust"), (0, "slam_ring"),
                            (1, "quake_crack"), (3, "impact_dust"),
                            (6, "rock_fall"), (14, "quake_dust")]))

#  決め絵: 投げ切った腕が体の外へ抜け、腰が正面を向ききる。
ally(
    "hurl",
    b=P(body={"r": [16, 0, 0], "p": [0, -1.6, 0]}, head=[14, 0, 0],
        rightArm=[-40, 24, -16], leftArm=[-40, -24, 16],
        rightForearm=[-92, 0, 0], leftForearm=[-92, 0, 0]),
    mid=P(body={"r": [-4, -12, 0], "p": [0, 0, 0]}, head=[-6, 4, 0],
          rightArm=[-104, 18, -14], leftArm=[-104, -18, 14],
          rightForearm=[-70, 0, 0], leftForearm=[-70, 0, 0]),
    c=P(body={"r": [-18, -22, 0], "p": [0, 1.2, 0]}, head=[-20, 8, 0],
        rightArm=[-158, 12, -12], leftArm=[-158, -12, 12],
        rightForearm=[-40, 0, 0], leftForearm=[-40, 0, 0],
        rightHand=[-22, 0, 0], leftHand=[-22, 0, 0],
        rightLeg=[-12, 0, 0], leftLeg=[8, 0, 0]),
    d=P(body={"r": [22, 26, 0], "p": [0, -0.4, 0.8]}, head=[12, -10, 0],
        rightArm=[-52, -18, -8], leftArm=[-52, 18, 8],
        rightForearm=[-6, 0, 0], leftForearm=[-6, 0, 0],
        rightHand=[18, 0, 0], leftHand=[18, 0, 0],
        rightLeg=[14, 0, 0], leftLeg=[-16, 0, 0], leftShin=[20, 0, 0]),
    particles=fxline("hurl", [(-8, "metal_glint"), (0, "debris_chunk"),
                            (3, "debris_dust"), (10, "impact_dust")]))

# --- クイックシルバー -------------------------------------------------------
#  決め絵: 三連撃。腕が入れ替わるたびに残像だけが遅れて残る。
ally(
    "blitz",
    chain=True,
    b=P(body={"r": [22, 0, 0], "p": [0, -0.8, -1.6]}, head=[-10, 0, 0],
        rightArm=[-120, -20, -12], leftArm=[-20, 20, 20],
        rightForearm=[-60, 0, 0]),
    c=P(body={"r": [24, -14, 0], "p": [0, -0.4, 0.6]}, head=[-8, 8, 0],
        rightArm=[-126, -24, -10], rightForearm=[-70, 0, 0],
        rightHand=[-16, 0, 0], leftArm=[-24, 24, 22]),
    d=P(body={"r": [18, -30, 0], "p": [0, 0, 2.4]}, head=[0, 18, 0],
        rightArm=[-88, -24, -6], rightForearm=[-4, 0, 0],
        rightHand=[12, 0, 0], leftArm=[-110, 20, 16],
        leftForearm=[-52, 0, 0], rightLeg=[10, 0, 0], leftLeg=[-14, 0, 0]),
    extra=[(0.42, P(body={"r": [18, 30, 0], "p": [0, 0, 2.4]},
                    head=[0, -18, 0],
                    leftArm=[-88, 24, 6], leftForearm=[-4, 0, 0],
                    leftHand=[12, 0, 0], rightArm=[-110, -20, -16],
                    rightForearm=[-52, 0, 0], rightHand=[-14, 0, 0],
                    rightLeg=[-14, 0, 0], leftLeg=[10, 0, 0]), "d"),
           (0.56, P(body={"r": [16, -26, 0], "p": [0, 0, 2.0]},
                    head=[0, 16, 0],
                    rightArm=[-92, -22, -6], rightForearm=[-6, 0, 0],
                    rightHand=[10, 0, 0], leftArm=[-102, 18, 14],
                    leftForearm=[-44, 0, 0], rightLeg=[8, 0, 0],
                    leftLeg=[-12, 0, 0]), "d")],
    particles=fxline("blitz", [(-2, "speed_line"), (0, "blur_after"),
                            (2, "hurt_spark"), (5, "blur_after"),
                            (8, "speed_line"), (11, "blur_after")]))

#  決め絵: 左右へ振れきった瞬間、体が斜めに傾いだまま止まる。
ally(
    "afterimage",
    chain=True,
    b=P(body={"r": [0, -30, 0], "p": [-1.2, 0, 0]}, head=[0, 20, 0],
        rightArm=[-30, 0, -24], leftArm=[-30, 0, 24]),
    c=P(body={"r": [0, -42, 0], "p": [-2.0, 0, 0]}, head=[0, 28, 0],
        rightArm=[-38, 0, -30], leftArm=[-38, 0, 30],
        rightLeg=[-14, 0, 0], leftLeg=[10, 0, 0]),
    d=P(body={"r": [0, 46, 0], "p": [2.2, 0, 0]}, head=[0, -30, 0],
        rightArm=[-44, 0, -32], leftArm=[-44, 0, 32],
        rightForearm=[-18, 0, 0], leftForearm=[-18, 0, 0],
        rightLeg=[12, 0, 0], leftLeg=[-14, 0, 0]),
    extra=[(0.50, P(body={"r": [0, -22, 0], "p": [-1.0, 0, 0]},
                    head=[0, 14, 0],
                    rightArm=[-26, 0, -20], leftArm=[-26, 0, 20],
                    rightLeg=[-8, 0, 0], leftLeg=[6, 0, 0]), "d")],
    particles=fxline("afterimage", [(-3, "speed_line"), (0, "blur_after"),
                            (6, "blur_after"), (11, "speed_line")]))

#  決め絵: 前傾が限界まで倒れ、後脚が地面から離れる直前。
ally(
    "sonic_dash",
    b=P(body={"r": [28, 0, 0], "p": [0, -0.8, -1.2]}, head=[-22, 0, 0],
        rightArm=[-70, 0, -34], leftArm=[-70, 0, 34],
        rightLeg=[-40, 0, 0], leftLeg=[24, 0, 0]),
    c=P(body={"r": [32, 0, 0], "p": [0, -1.0, -1.6]}, head=[-26, 0, 0],
        rightArm=[-80, 0, -38], leftArm=[-80, 0, 38],
        rightForearm=[-24, 0, 0], leftForearm=[-24, 0, 0],
        rightLeg=[-48, 0, 0], leftLeg=[28, 0, 0], rightShin=[36, 0, 0]),
    d=P(body={"r": [38, 0, 0], "p": [0, -0.4, 3.2]}, head=[-30, 0, 0],
        rightArm=[-118, 0, -20], leftArm=[-118, 0, 20],
        rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
        rightLeg=[42, 0, 0], leftLeg=[-36, 0, 0],
        rightShin=[4, 0, 0], leftShin=[44, 0, 0]),
    particles=fxline("sonic_dash", [(-3, "speed_line"), (0, "blur_after"),
                            (4, "speed_line"), (9, "impact_dust")]))

# --- パイロ -----------------------------------------------------------------
#  決め絵: 掌を返して炎を送り出す。上体が開き、指先が的を指す。
ally(
    "flame_wave",
    b=P(body=[0, 34, 0], head=[0, -20, 0],
        rightArm=[-56, 40, -14], rightForearm=[-70, 0, 0],
        rightHand=[-24, 0, 0], leftArm=[-18, -12, 12]),
    c=P(body=[-2, 40, 0], head=[-2, -24, 0],
        rightArm=[-62, 46, -16], rightForearm=[-80, 0, 0],
        rightHand=[-32, 0, 0], rightLeg=[-12, 0, 0], leftLeg=[8, 0, 0]),
    d=P(body={"r": [6, -30, 0], "p": [0, 0, 1.0]}, head=[0, 18, 0],
        rightArm=[-92, -34, -8], rightForearm=[-12, 0, 0],
        rightHand=[20, 0, 0], leftArm=[-30, 20, 16],
        rightLeg=[10, 0, 0], leftLeg=[-14, 0, 0], leftShin=[18, 0, 0]),
    particles=fxline("flame_wave", [(-4, "ember_rise", "rightHand"),
                            (0, "flame_wave", "rightHand"),
                            (2, "ember_rise"), (10, "quake_dust")]))

#  決め絵: 両手で蛇の胴を撫でるように送り出す。掌が向き合ったまま前へ。
ally(
    "fire_serpent",
    b=P(body=[-4, 0, 0], head=[-10, 0, 0],
        rightArm=[-100, -14, -10], leftArm=[-96, 14, 10],
        rightForearm=[-30, 0, 0], leftForearm=[-30, 0, 0]),
    mid=P(body=[-5, 0, 0], head=[-13, 0, 0],
          rightArm=[-104, -22, -9], leftArm=[-102, 22, 9],
          rightForearm=[-22, 0, 0], leftForearm=[-22, 0, 0]),
    c=P(body={"r": [-6, 0, 0], "p": [0, 0.6, 0]}, head=[-16, 0, 0],
        rightArm=[-108, -30, -8], leftArm=[-108, 30, 8],
        rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0],
        rightHand=[-20, 0, 0], leftHand=[-20, 0, 0]),
    d=P(body={"r": [10, 0, 0], "p": [0, -0.6, 1.2]}, head=[8, 0, 0],
        rightArm=[-88, -6, -14], leftArm=[-88, 6, 14],
        rightForearm=[-28, 0, 0], leftForearm=[-28, 0, 0],
        rightHand=[16, 0, 0], leftHand=[16, 0, 0],
        rightLeg=[-10, 0, 0], leftLeg=[8, 0, 0]),
    particles=fxline("fire_serpent", [(-10, "ember_rise"), (-4, "flame_serpent"),
                            (0, "flame_serpent"), (4, "ember_rise"),
                            (14, "quake_dust")]))

#  決め絵: 指を弾いた瞬間。動くのは手首と首だけ。
ally(
    "ignite",
    b=P(rightArm=[-104, -12, -8], rightForearm=[-24, 0, 0],
        rightHand=[-24, 0, 0], head=[-6, 8, 0], body=[0, -6, 0]),
    c=P(rightArm=[-108, -14, -8], rightForearm=[-28, 0, 0],
        rightHand=[-32, 0, 0], head=[-8, 10, 0], body=[0, -8, 0]),
    d=P(rightArm=[-100, -8, -8], rightForearm=[-16, 0, 0],
        rightHand=[20, 0, 0], head=[-4, 4, 0], body=[2, -4, 0]),
    particles=fxline("ignite", [(0, "ember_rise", "rightHand"),
                            (3, "flame_wave", "rightHand")]))

# --- アバランチ -------------------------------------------------------------
#  決め絵: 両掌を地に叩きつけ、腰まで沈む。肩が耳の高さまで上がる。
ally(
    "tremor",
    b=P(body={"r": [26, 0, 0], "p": [0, -2.2, 0]}, head=[-18, 0, 0],
        rightArm=[-30, 16, -18], leftArm=[-30, -16, 18],
        rightForearm=[-96, 0, 0], leftForearm=[-96, 0, 0]),
    mid=P(body={"r": [20, 0, 0], "p": [0, -1.6, 0]}, head=[-14, 0, 0],
          rightArm=[-42, 14, -20], leftArm=[-42, -14, 20],
          rightForearm=[-84, 0, 0], leftForearm=[-84, 0, 0]),
    c=P(body={"r": [14, 0, 0], "p": [0, -1.0, 0]}, head=[-10, 0, 0],
        rightArm=[-56, 12, -22], leftArm=[-56, -12, 22],
        rightForearm=[-70, 0, 0], leftForearm=[-70, 0, 0],
        rightLeg=[-18, 0, -4], leftLeg=[-18, 0, 4]),
    d=P(body={"r": [36, 0, 0], "p": [0, -3.2, 0]}, head=[10, 0, 0],
        rightArm=[-18, 10, -14], leftArm=[-18, -10, 14],
        rightForearm=[-112, 0, 0], leftForearm=[-112, 0, 0],
        rightHand=[-18, 0, 0], leftHand=[-18, 0, 0],
        rightLeg=[-34, 0, -6], leftLeg=[-34, 0, 6],
        rightShin=[48, 0, 0], leftShin=[48, 0, 0]),
    particles=fxline("tremor", [(-4, "quake_dust"), (0, "quake_crack"),
                            (2, "slam_ring"), (5, "debris_dust"),
                            (12, "quake_dust")]))

#  決め絵: 頭上へ差し上げた両腕を、真下へ叩き落とす。岩はその後に落ちる。
ally(
    "rockfall",
    b=P(body={"r": [-14, 0, 0], "p": [0, 1.2, 0]}, head=[-30, 0, 0],
        rightArm=[-150, 0, -18], leftArm=[-150, 0, 18],
        rightForearm=[-20, 0, 0], leftForearm=[-20, 0, 0]),
    mid=P(body={"r": [-16, 0, 0], "p": [0, 1.5, 0]}, head=[-32, 0, 0],
          rightArm=[-158, 0, -14], leftArm=[-158, 0, 14],
          rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0]),
    c=P(body={"r": [-18, 0, 0], "p": [0, 1.8, 0]}, head=[-34, 0, 0],
        rightArm=[-166, 0, -10], leftArm=[-166, 0, 10],
        rightForearm=[-10, 0, 0], leftForearm=[-10, 0, 0],
        rightHand=[-16, 0, 0], leftHand=[-16, 0, 0],
        rightLeg=[-6, 0, 0], leftLeg=[-6, 0, 0]),
    d=P(body={"r": [18, 0, 0], "p": [0, -0.8, 0]}, head=[14, 0, 0],
        rightArm=[-54, 0, -28], leftArm=[-54, 0, 28],
        rightForearm=[-18, 0, 0], leftForearm=[-18, 0, 0],
        rightHand=[14, 0, 0], leftHand=[14, 0, 0],
        rightLeg=[-14, 0, 0], leftLeg=[-14, 0, 0],
        rightShin=[20, 0, 0], leftShin=[20, 0, 0]),
    particles=fxline("rockfall", [(-10, "mag_dust"), (-3, "quake_crack"),
                            (0, "rock_fall"), (4, "debris_chunk"),
                            (8, "debris_dust"), (16, "quake_dust")]))

#  決め絵: 両腕を左右へ引き裂く。腰は沈んだまま、胸だけが開く。
ally(
    "fissure",
    b=P(body={"r": [30, 0, 0], "p": [0, -2.8, 0]}, head=[-22, 0, 0],
        rightArm=[-24, 20, -14], leftArm=[-24, -20, 14],
        rightForearm=[-104, 0, 0], leftForearm=[-104, 0, 0],
        rightLeg=[-30, 0, 0], leftLeg=[-30, 0, 0],
        rightShin=[48, 0, 0], leftShin=[48, 0, 0]),
    mid=P(body={"r": [33, 0, 0], "p": [0, -3.2, 0]}, head=[-24, 0, 0],
          rightArm=[-20, 17, -12], leftArm=[-20, -17, 12],
          rightForearm=[-112, 0, 0], leftForearm=[-112, 0, 0]),
    c=P(body={"r": [36, 0, 0], "p": [0, -3.6, 0]}, head=[-26, 0, 0],
        rightArm=[-16, 14, -10], leftArm=[-16, -14, 10],
        rightForearm=[-120, 0, 0], leftForearm=[-120, 0, 0],
        rightHand=[-24, 0, 0], leftHand=[-24, 0, 0],
        rightLeg=[-36, 0, -4], leftLeg=[-36, 0, 4],
        rightShin=[56, 0, 0], leftShin=[56, 0, 0]),
    d=P(body={"r": [10, 0, 0], "p": [0, -1.0, 0]}, head=[6, 0, 0],
        rightArm=[-46, -34, -26], leftArm=[-46, 34, 26],
        rightForearm=[-36, 0, 0], leftForearm=[-36, 0, 0],
        rightHand=[16, 0, 0], leftHand=[16, 0, 0],
        rightLeg=[-16, 0, -8], leftLeg=[-16, 0, 8],
        rightShin=[24, 0, 0], leftShin=[24, 0, 0]),
    particles=fxline("fissure", [(-8, "quake_dust"), (-2, "quake_crack"),
                            (0, "quake_crack"), (3, "rock_fall"),
                            (6, "debris_dust"), (14, "quake_dust")]))

# --- ブロブ -----------------------------------------------------------------
#  決め絵: 両脚を地に埋め、腕を張って根を張る。以降その形を保つ。
ally(
    "immovable",
    b=P(body={"r": [12, 0, 0], "p": [0, -2.0, 0]}, head=[6, 0, 0],
        rightArm=[-26, 0, -50], leftArm=[-26, 0, 50],
        rightForearm=[-56, 0, 0], leftForearm=[-56, 0, 0],
        rightLeg=[-18, 0, -8], leftLeg=[-18, 0, 8],
        rightShin=[30, 0, 0], leftShin=[30, 0, 0]),
    mid=P(body={"r": [11, 0, 0], "p": [0, -2.4, 0]}, head=[7, 0, 0],
          rightArm=[-28, 0, -52], leftArm=[-28, 0, 52]),
    c=P(body={"r": [10, 0, 0], "p": [0, -2.8, 0]}, head=[8, 0, 0],
        rightArm=[-30, 0, -54], leftArm=[-30, 0, 54],
        rightForearm=[-60, 0, 0], leftForearm=[-60, 0, 0],
        rightLeg=[-22, 0, -10], leftLeg=[-22, 0, 10],
        rightShin=[38, 0, 0], leftShin=[38, 0, 0]),
    d=P(body={"r": [8, 0, 0], "p": [0, -3.4, 0]}, head=[10, 0, 0],
        rightArm=[-34, 0, -58], leftArm=[-34, 0, 58],
        rightForearm=[-52, 0, 0], leftForearm=[-52, 0, 0],
        rightHand=[-16, 0, 0], leftHand=[-16, 0, 0],
        rightLeg=[-26, 0, -12], leftLeg=[-26, 0, 12],
        rightShin=[44, 0, 0], leftShin=[44, 0, 0],
        rightFoot=[-10, 0, 0], leftFoot=[-10, 0, 0]),
    particles=fxline("immovable", [(-4, "quake_dust"), (0, "slam_ring"),
                            (2, "impact_dust"), (8, "quake_dust")]))

#  決め絵: 腹が前へ突き出しきり、腕と頭が後ろへ流れる。
ally(
    "belly_bounce",
    b=P(body={"r": [-14, 0, 0], "p": [0, -1.0, -1.6]}, head=[-12, 0, 0],
        rightArm=[-30, 0, -48], leftArm=[-30, 0, 48],
        rightForearm=[-30, 0, 0], leftForearm=[-30, 0, 0]),
    c=P(body={"r": [-18, 0, 0], "p": [0, -1.4, -2.2]}, head=[-16, 0, 0],
        rightArm=[-38, 0, -54], leftArm=[-38, 0, 54],
        rightForearm=[-40, 0, 0], leftForearm=[-40, 0, 0],
        rightLeg=[-16, 0, -6], leftLeg=[-16, 0, 6]),
    d=P(body={"r": [18, 0, 0], "p": [0, 0.6, 2.6]}, head=[14, 0, 0],
        rightArm=[-58, 0, -64], leftArm=[-58, 0, 64],
        rightForearm=[-14, 0, 0], leftForearm=[-14, 0, 0],
        rightHand=[-14, 0, 0], leftHand=[-14, 0, 0],
        rightLeg=[8, 0, -4], leftLeg=[8, 0, 4]),
    particles=fxline("belly_bounce", [(0, "slam_ring"), (2, "impact_dust"),
                            (9, "quake_dust")]))

#  決め絵: 全体重が地面に着く瞬間。両腕が体の外へ投げ出される。
ally(
    "body_slam",
    b=P(body={"r": [-20, 0, 0], "p": [0, 3.0, 0]}, head=[-24, 0, 0],
        rightArm=[-146, 0, -24], leftArm=[-146, 0, 24],
        rightLeg=[-30, 0, 0], leftLeg=[-30, 0, 0],
        rightShin=[46, 0, 0], leftShin=[46, 0, 0]),
    mid=P(body={"r": [-24, 0, 0], "p": [0, 3.6, 0]}, head=[-28, 0, 0],
          rightArm=[-158, 0, -18], leftArm=[-158, 0, 18],
          rightLeg=[-36, 0, 0], leftLeg=[-36, 0, 0],
          rightShin=[54, 0, 0], leftShin=[54, 0, 0]),
    c=P(body={"r": [-26, 0, 0], "p": [0, 4.0, 0]}, head=[-30, 0, 0],
        rightArm=[-166, 0, -14], leftArm=[-166, 0, 14],
        rightForearm=[-12, 0, 0], leftForearm=[-12, 0, 0],
        rightLeg=[-40, 0, 0], leftLeg=[-40, 0, 0],
        rightShin=[60, 0, 0], leftShin=[60, 0, 0],
        rightFoot=[-18, 0, 0], leftFoot=[-18, 0, 0]),
    d=P(body={"r": [42, 0, 0], "p": [0, -4.2, 1.8]}, head=[26, 0, 0],
        rightArm=[-18, 0, -48], leftArm=[-18, 0, 48],
        rightForearm=[-8, 0, 0], leftForearm=[-8, 0, 0],
        rightLeg=[20, 0, 0], leftLeg=[20, 0, 0],
        rightShin=[0, 0, 0], leftShin=[0, 0, 0],
        rightFoot=[10, 0, 0], leftFoot=[10, 0, 0]),
    particles=fxline("body_slam", [(-4, "quake_dust"), (0, "slam_ring"),
                            (1, "quake_crack"), (3, "impact_dust"),
                            (7, "debris_dust"), (16, "quake_dust")]))

# --- スカーレット・ウィッチ ---------------------------------------------------
#  決め絵: 掌を返して弾を放つ。指先が的を指し、上体は逆へ流れる。
ally(
    "hex_bolt",
    b=P(body=[0, 24, 0], head=[0, -16, 0],
        rightArm=[-64, 32, -16], rightForearm=[-72, 0, 0],
        rightHand=[-28, 0, 0], leftArm=[-18, -10, 12]),
    c=P(body=[-2, 30, 0], head=[-2, -20, 0],
        rightArm=[-70, 38, -18], rightForearm=[-82, 0, 0],
        rightHand=[-36, 0, 0], rightLeg=[-10, 0, 0], leftLeg=[8, 0, 0]),
    d=P(body={"r": [4, -20, 0], "p": [0, 0, 0.8]}, head=[0, 16, 0],
        rightArm=[-98, -14, -8], rightForearm=[-8, 0, 0],
        rightHand=[18, 0, 0], leftArm=[-24, 14, 14],
        rightLeg=[8, 0, 0], leftLeg=[-10, 0, 0]),
    cape=witch_cape,
    particles=fxline("hex_bolt", [(-3, "chaos_motes", "rightHand"),
                            (0, "hex_bolt_trail", "rightHand"),
                            (4, "chaos_motes")]))

#  決め絵: 両腕で球を抱えるように押し広げる。指が内へ向いたまま。
ally(
    "chaos_field",
    b=P(body={"r": [-6, 0, 0], "p": [0, 0.8, 0]}, head=[-14, 0, 0],
        rightArm=[-70, -26, -22], leftArm=[-70, 26, 22],
        rightForearm=[-66, 0, 0], leftForearm=[-66, 0, 0]),
    mid=P(body={"r": [-9, 0, 0], "p": [0, 1.2, 0]}, head=[-17, 0, 0],
          rightArm=[-90, -34, -18], leftArm=[-90, 34, 18],
          rightForearm=[-46, 0, 0], leftForearm=[-46, 0, 0]),
    c=P(body={"r": [-12, 0, 0], "p": [0, 1.6, 0]}, head=[-20, 0, 0],
        rightArm=[-108, -40, -14], leftArm=[-108, 40, 14],
        rightForearm=[-28, 0, 0], leftForearm=[-28, 0, 0],
        rightHand=[-26, 0, 0], leftHand=[-26, 0, 0]),
    d=P(body={"r": [-4, 0, 0], "p": [0, 0.4, 0]}, head=[-8, 0, 0],
        rightArm=[-118, -16, -10], leftArm=[-118, 16, 10],
        rightForearm=[-10, 0, 0], leftForearm=[-10, 0, 0],
        rightHand=[20, 0, 0], leftHand=[20, 0, 0],
        rightLeg=[-8, 0, 0], leftLeg=[-8, 0, 0]),
    cape=witch_cape,
    particles=fxline("chaos_field", [(-12, "chaos_motes"), (-4, "hex_wave"),
                            (0, "hex_wave"), (4, "chaos_motes"),
                            (12, "mag_dust")]))

#  決め絵: 掌を上へ返して吊り上げる。動きは小さく、指だけが開く。
ally(
    "telekinesis",
    b=P(body=[-2, -10, 0], head=[-6, 8, 0],
        rightArm=[-96, -18, -8], rightForearm=[-16, 0, 0],
        rightHand=[-30, 0, 0], leftArm=[-40, 16, 14]),
    mid=P(body={"r": [-6, -8, 0], "p": [0, 0.4, 0]}, head=[-12, 6, 0],
          rightArm=[-110, -16, -8], rightForearm=[-12, 0, 0],
          rightHand=[-22, 0, 0], leftArm=[-50, 14, 12]),
    c=P(body={"r": [-10, -6, 0], "p": [0, 0.8, 0]}, head=[-18, 6, 0],
        rightArm=[-124, -14, -8], rightForearm=[-10, 0, 0],
        rightHand=[-14, 0, 0], leftArm=[-58, 12, 12],
        leftForearm=[-20, 0, 0]),
    d=P(body={"r": [-16, 0, 0], "p": [0, 1.4, 0]}, head=[-26, 0, 0],
        rightArm=[-148, -10, -8], rightForearm=[-6, 0, 0],
        rightHand=[24, 0, 0], leftArm=[-70, 10, 12],
        leftForearm=[-14, 0, 0], leftHand=[16, 0, 0]),
    cape=witch_cape,
    particles=fxline("telekinesis", [(-10, "tk_lift"), (0, "tk_lift"),
                            (4, "chaos_motes"), (12, "mag_dust")]))


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
