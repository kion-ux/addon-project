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
#:
#: .. warning::
#:    **これは移動アニメ専用**。技側から参照しないこと。
#:    技の拍は docs/DIRECTION.md §4-1 の式（撃発を絶対秒で固定する）で組む。
#:    こちらは比率固定なので、L を変えると撃発まで一緒に伸びて切れ味が落ちる。
EASE = {
    "anticipate": 0.10,     # 逆方向へ引く
    "wind": 0.26,           # 溜めきる
    "strike": 0.34,         # 撃発（ここが一番速い）
    "extend": 0.46,         # 伸びきり
    "settle": 0.78,         # 残心
    "end": 1.00,
}


def beats(total: float) -> dict:
    """EASE を任意の長さにスケールした秒数表を返す（移動アニメ専用）。"""
    return {k: round(v * total, 3) for k, v in EASE.items()}


# -------------------------------------------------------------- 波を重ねる
#: 待機の周期表（°/秒）。``math.cos`` は度で受けるので 360/値 が周期の秒数。
#:
#: 値どうしが整数比にならないよう選んである。62 と 31 のような整数比だと
#: 二本重ねても数秒で完全に同じ形へ戻り、結局ひとつの往復に見えてしまう。
HZ = {
    "breath": 84,      # 4.3 秒  呼吸
    "weight": 51,      # 7.1 秒  重心の左右移動
    "float": 32,       # 11.3 秒 浮遊のうねり
    "sway": 19,        # 18.9 秒 一番遅い漂い（これが単調さを殺す）
    "tremor": 313,     # 1.15 秒 指先・手首の微動
    "servo": 26,       # 13.8 秒 機械の待機
    "jitter": 421,     # 0.86 秒 機械の電気的な震え
}


def hz(name) -> float:
    return HZ.get(name, name) if isinstance(name, str) else name


def waves(*terms, base=0.0):
    """``waves((1.4, "breath"), (0.6, "float", 40), base=2)`` — 波の和。

    項は ``(振幅, 周期キーまたは °/秒, 位相)``。
    周期の違う波を 2〜3 本重ねると、往復が「呼吸」に変わる。
    """
    parts = [f"{base}"] if base else []
    for term in terms:
        amp = term[0]
        speed = hz(term[1] if len(term) > 1 else "breath")
        phase = term[2] if len(term) > 2 else 0
        ph = f" + {phase}" if phase else ""
        parts.append(f"math.cos({T} * {speed}{ph}) * {amp}")
    if not parts:
        return "0"
    return "(" + " + ".join(parts) + ")"


def gait(lo=0.35, hi=1.25, gain=1.0):
    """歩幅の強さ。

    ``swing()`` は既定で ``query.modified_move_speed`` を掛けるので、
    足の遅い大型は振り幅まで小さくなって止まって見える。
    下限で「遅くても大きく踏む」を、上限で「疾走しても暴れない」を作る。
    """
    return f"math.clamp({SPD} * {gain}, {lo}, {hi})"


def thud(amp, speed=1.0, phase=0, sharp=0.55, scale=SPD):
    """接地のたびに沈み込む上下動。沈んだまま留まり、抜けるときだけ速い。

    重い相手（センチネル）の体重は、腕の振りではなくここで読ませる。
    """
    return (f"math.pow(math.abs(math.cos({LIMB} * {speed} + {phase})), "
            f"{sharp}) * {-abs(amp)} * {scale}")


# -------------------------------------------------------------- トラック
def tag(t) -> str:
    """秒数をキーフレーム名にする。``0.26 -> "0.26"``"""
    return f"{round(float(t), 4):g}"


def track(rows):
    """``[(秒, 値), (秒, 値, "linear"), ...]`` をキーフレーム辞書にする。

    ``keys()`` と違い **時刻を float のまま書ける** ので、
    拍を計算で出す技・一人称のクリップはこちらを使う。

    第三要素で補間を選ぶ:

    ``smooth`` (既定)  通過点。catmullrom。
    ``linear``         到達点。撃発・接地・保持の両端・終端は必ずこれ。
                       等間隔でないキーを曲線で繋ぐと接線が暴走する。
    ``step``           その瞬間に飛ぶ（pre に直前の値を置く）。
    """
    out = {}
    prev = None
    for row in rows:
        t = row[0]
        value = [round(v, 3) if isinstance(v, float) else v for v in row[1]]
        mode = row[2] if len(row) > 2 else "smooth"
        key = tag(t)
        if mode == "step":
            out[key] = {"pre": list(prev if prev is not None else value),
                        "post": value}
        elif mode == "linear":
            out[key] = value
        else:
            out[key] = {"post": value, "lerp_mode": "catmullrom"}
        prev = value
    return out


def ramp(rows, start=0.0):
    """速度の折れ線から **角度の折れ線** を作る。

    ``[(秒, °/秒), ...]`` を受け、線形補間のキーにして返すので、
    区間ごとに *正確に* その角速度で回る。
    「900°/s で溜めて撃発の瞬間 120°/s へ落とす」ような
    急加速・急停止は、速度を直接書けるこの形でしか作れない。
    """
    angle = start
    out = [(rows[0][0], angle)]
    for (t0, speed), (t1, _n) in zip(rows, rows[1:]):
        angle += speed * (t1 - t0)
        out.append((t1, angle))
    return out


def spin_track(rows, axis=2, start=0.0):
    """``ramp()`` の結果を rotation のキーフレームにする（既定は Z 軸）。"""
    frames = []
    for t, angle in ramp(rows, start):
        v = [0.0, 0.0, 0.0]
        v[axis] = round(angle, 2)
        frames.append((t, v, "linear"))
    return track(frames)


# -------------------------------------------------------------- マント 6 段
#: profile -> (段ごとの遅れ 秒, ピーク角 °, 撃発時の引き戻し °)
CAPE_PROFILES = {
    "whip": (0.06, 46, 8),      # 前へ踏み込む技
    "flare": (0.08, 62, 12),    # 両手を掲げる技
    "settle": (0.05, 18, 4),    # 動きの小さい技
    "swirl": (0.10, 38, -10),   # 回る技（巻き込んでから開く）
}

#: 段ごとの減衰。cape0→5 は親子チェーンなので、末端ほど *小さく* しないと
#: 角度が累積して体を突き抜ける。
CAPE_DECAY = (1.00, 0.86, 0.74, 0.62, 0.52, 0.45)

#: 累積角の上限（°）。超えたら全段を一律スケールして収める。
CAPE_LIMIT = 70.0


def cape_fan(total, segments=6, decay=CAPE_DECAY):
    """**累積** ``total`` ° を段ごとの増分に配分する。

    cape0→5 は親子チェーンなので、各段に書いた角度はそのまま足し算される。
    「末端を大きく」と書くと先端の実効角が三桁になって体を突き抜ける。
    段ごとの値ではなく *合計* を指定させるのはそのため。
    """
    w = [decay[i] for i in range(segments)]
    k = total / sum(w)
    return tuple(round(x * k, 2) for x in w)


def _cape_amps(peak, segments, limit=CAPE_LIMIT):
    amps = [peak * CAPE_DECAY[i] for i in range(segments)]
    total = sum(amps)
    if total > limit:
        k = limit / total
        amps = [a * k for a in amps]
    return amps


def cape6(profile, length, strike, segments=6, limit=CAPE_LIMIT):
    """技のマント。**ピークは撃発から数える**（``strike + lag*(i+1)``）。

    割合で決めると、短い技はマントが腕より先に動き、長い技は
    クライマックスでマントが死ぬ。起点を撃発に固定すればどちらも起きない。

    裾（cape3-5）は L/R が逆位相に開く。板は pitch しか持てないので、
    裾が V に開かないと「翻った」に見えない。
    """
    lag, peak, back = CAPE_PROFILES[profile]
    amps = _cape_amps(peak, segments, limit)
    out: dict = {}
    for i in range(segments):
        amp = amps[i]
        pre = -back * CAPE_DECAY[i]
        t_peak = strike + lag * (i + 1)
        t_back = t_peak + length * 0.30
        t_end = max(length, t_back + 0.05)
        rows = [(0.0, [0, 0, 0], "linear")]
        if strike - lag > 0.04:
            rows.append((max(0.02, strike - lag), [pre * 0.45, 0, 0]))
        rows += [
            (strike, [pre, 0, 0], "linear"),
            (t_peak, [amp, 0, 0]),
            (t_back, [amp * 0.22, 0, 0]),
            (t_end, [0, 0, 0], "linear"),
        ]
        out[f"cape{i}"] = {"rotation": track(rows)}
        if i < 3:
            continue
        # 裾だけは実 cube が L/R に分かれている。ここで V に開く。
        flare = 6 + 5 * i
        yaw = 3 + 3 * i
        for sign, bone in ((1, f"cape{i}L"), (-1, f"cape{i}R")):
            out[bone] = {"rotation": track([
                (0.0, [0, 0, 0], "linear"),
                (strike, [0, sign * yaw * -0.3, sign * flare * -0.25], "linear"),
                (t_peak, [0, sign * yaw, sign * flare]),
                (t_back, [0, sign * yaw * -0.4, sign * flare * -0.4]),
                (t_end, [0, 0, 0], "linear"),
            ])}
    return out


def cape6_loop(rest, gain, lag=24, span=(-8, 62), scale=SPD, segments=6):
    """歩幅に同期して流れるマント（移動用）。

    ``span`` で締めるのが肝。上限が無いと疾走で 90° を越えて裏返る。
    """
    out: dict = {}
    for i in range(segments):
        x = (f"math.clamp({rest[i]} + {swing(gain[i], lag * i, scale=scale)}, "
             f"{span[0]}, {span[1]})")
        flare = 6 + 5 * i
        yaw = 3 + 3 * i
        if i < 3:
            out[f"cape{i}"] = rot(x,
                                  swing(yaw * 0.35, 180 + lag * i, scale=scale),
                                  swing(flare * 0.30, 90 + lag * i, scale=scale))
            continue
        out[f"cape{i}"] = rot(x, 0, 0)
        for sign, bone in ((1, f"cape{i}L"), (-1, f"cape{i}R")):
            out[bone] = rot(0,
                            swing(sign * yaw, lag * i, scale=scale),
                            swing(sign * flare, 90 + lag * i, scale=scale))
    return out


def cape6_drift(rest, amp, speed=("float", "sway", "weight"), segments=6,
                flare=0.28):
    """風にそよぐマント（待機・浮遊・落下用）。

    段ごとに周期をずらすので、6 段が一本の板として同時に動かない。

    ``flare`` は裾の開き。静止した空気では小さく（0.25 前後）、
    落下や疾走では大きく（0.5 以上）する。上段は面積が広いので
    ロールを大きく取ると胴の前まで回り込んで「赤い壁」になる。
    """
    out: dict = {}
    for i in range(segments):
        a = amp[i]
        s0 = hz(speed[i % len(speed)])
        s1 = hz(speed[(i + 1) % len(speed)])
        roll = 0.16 if i < 3 else 0.34
        out[f"cape{i}"] = rot(
            waves((a, s0, i * 37), (a * 0.42, s1, i * 61), base=rest[i]),
            waves((a * 0.5, s1, i * 53)),
            waves((a * roll, s0, 90 + i * 47)))
        if i < 3:
            continue
        for sign, bone in ((1, f"cape{i}L"), (-1, f"cape{i}R")):
            out[bone] = rot(0,
                            waves((sign * (3 + 3 * i) * 0.4, s1, i * 43)),
                            waves((sign * (6 + 5 * i) * flare, s0, i * 29)))
    return out


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
