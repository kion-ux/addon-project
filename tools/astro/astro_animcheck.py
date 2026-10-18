# -*- coding: utf-8 -*-
"""アストロ・ナノギア — 書き出したアニメーションの共通の検査（ループの継ぎ目・振りの戻り）と、
q.anim_time を使う待機ループの長さ。

  loop_length(bones, base=6.0) -> 秒
        bones の中の全ての `q.anim_time * k`（k は度/秒）が、ループの長さ L で 360° のちょうど整数倍に
        なる最短の L（base 秒以上）。統合版は `loop: true` と animation_length があると L 秒ごとに
        q.anim_time を 0 に戻すので、k·L が 360 の倍数でない回転・sin は L 秒ごとに飛ぶ。
        q.anim_time を `* 数` 以外で使う式や、L が LOOP_MAX 秒を超える速さは ValueError。
  seam_errors(anims, where="") -> [str]
        `loop: true` のアニメ（animation_length があるか、キーフレームで長さが決まる物）の全チャンネルを
        時刻 0 と L で評価し（他の変数は同じ値に固定）、値が合わない物（回転は 360° を法として）。
        animation_length の無い式だけのループは q.anim_time が戻らないので調べない。
  rest_errors(anim, var, values=(0.0, 1.0), where="") -> [str]
        var（例 v.astro_sw）が values の時、全チャンネルが自然体（回転・位置 0、スケール 1）か。
        振りのアニメは振り始め（0）と振り終わり（1）で飛ばないこと。

Molang の評価は astro_scene.Molang（未知の名前は 0）。
"""
from __future__ import annotations

import math
import re
from fractions import Fraction

LOOP_MAX = 600.0          # 待機ループの長さの上限（秒）
_AT = r"(?:q|query)\.anim_time"
_NUM = r"(-?\d+(?:\.\d+)?)"


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def anim_time_rates(obj) -> list:
    """obj の中の `q.anim_time * k` / `k * q.anim_time` の k（度/秒）。他の使い方があれば ValueError。"""
    rates = []
    for s in _strings(obj):
        uses = len(re.findall(_AT, s))
        found = [float(x) for x in re.findall(_AT + r"\s*\*\s*\(?\s*" + _NUM, s)]
        found += [float(x) for x in re.findall(_NUM + r"\s*\*\s*" + _AT, s)]
        if len(found) != uses:
            raise ValueError(f"q.anim_time must be used as `q.anim_time * <deg/s>` in looping idles: {s}")
        rates += found
    return rates


def loop_length(bones, base=6.0) -> float:
    """全ての q.anim_time の速さが L 秒で 360° の整数倍になる最短の L（base 以上）。"""
    L = None
    for k in anim_time_rates(bones):
        if abs(k) < 1e-9:
            continue
        f = Fraction(abs(k)).limit_denominator(1000)
        if abs(float(f) - abs(k)) > 1e-6:
            raise ValueError(f"speed {k} is not a simple number")
        p = Fraction(360) / f                       # この速さの周期（秒）
        if L is None:
            L = p
        else:                                       # 分数の最小公倍数
            L = Fraction(math.lcm(L.numerator * p.denominator, p.numerator * L.denominator),
                         L.denominator * p.denominator)
    if L is None:
        return float(base)
    n = max(1, math.ceil(Fraction(base) / L - Fraction(1, 10 ** 9)))
    out = L * n
    if out > LOOP_MAX:
        raise ValueError(f"idle speeds {sorted(set(anim_time_rates(bones)))} deg/s need a {float(out):.1f}s loop "
                         f"(> {LOOP_MAX:g}s); use speeds whose gcd divides 360 nicely")
    return round(float(out), 6)


# ---------------------------------------------------------------------------
def _names(obj):
    out = set()
    for s in _strings(obj):
        for m in re.findall(r"\b((?:q|v|c|query|variable|context|t|temp)\.[A-Za-z_][A-Za-z_0-9]*)", s):
            out.add(m)
    return out


def _canon(n):
    return re.sub(r"^query\.", "q.", re.sub(r"^variable\.", "v.", re.sub(r"^context\.", "c.", n)))


def _vec(v, ev):
    if isinstance(v, (list, tuple)):
        return [ev(x) for x in v]
    x = ev(v)
    return [x, x, x]


def _keyed(ch, t, ev):
    """キーフレームのチャンネル（dict）を t で（キーの上なら値そのもの、間は線形 — 継ぎ目の比較にはキーの
    値しか使わない）。"""
    keys = sorted(ch, key=float)
    ts = [float(k) for k in keys]

    def val(k, side):
        v = ch[k]
        if isinstance(v, dict):
            v = v.get(side, v.get("post", v.get("pre")))
        return _vec(v, ev)
    if t <= ts[0]:
        return val(keys[0], "pre")
    if t >= ts[-1]:
        return val(keys[-1], "post")
    for i in range(len(ts) - 1):
        if ts[i] <= t <= ts[i + 1]:
            a, b = val(keys[i], "post"), val(keys[i + 1], "pre")
            u = (t - ts[i]) / ((ts[i + 1] - ts[i]) or 1.0)
            return [a[j] + (b[j] - a[j]) * u for j in range(3)]
    return val(keys[-1], "post")


def _channel_at(ch, t, env):
    from astro_scene import Molang
    e = dict(env)
    e["q.anim_time"] = t
    ev = Molang(e)
    if isinstance(ch, dict):
        return _keyed(ch, t, ev)
    return _vec(ch, ev)


def _close(chan, a, b, tol_deg=0.5, tol=0.01):
    for x, y in zip(a, b):
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        d = x - y
        if chan == "rotation":
            d = (d + 180.0) % 360.0 - 180.0
            if abs(d) > tol_deg:
                return False
        elif abs(d) > tol:
            return False
    return True


def seam_errors(anims: dict, where="") -> list:
    """ループの継ぎ目（時刻 0 と L）で値が飛ぶチャンネル。"""
    errs = []
    for name, a in sorted(anims.items()):
        if a.get("loop") is not True:
            continue
        L = a.get("animation_length")
        bones = a.get("bones", {})
        if L is None:
            ks = [float(k) for ch in bones.values() for v in ch.values() if isinstance(v, dict) for k in v]
            if not ks:
                continue                     # 式だけのループ: q.anim_time は戻らない
            L = max(ks)
        if L <= 0:
            continue
        names = {_canon(n) for n in _names(a)} - {"q.anim_time"}
        envs = [{n: 0.0 for n in names}, {n: 1.0 for n in names}, {n: 0.37 for n in names}]
        for bone, chans in bones.items():
            for chan, v in chans.items():
                for env in envs:
                    try:
                        v0, v1 = _channel_at(v, 0.0, env), _channel_at(v, float(L), env)
                    except Exception as exc:  # noqa: BLE001
                        errs.append(f"{where}{name} {bone}.{chan}: cannot evaluate ({exc})")
                        break
                    if not _close(chan, v0, v1):
                        errs.append(f"{where}{name} {bone}.{chan}: loop seam at {L:g}s "
                                    f"{[round(x, 2) for x in v1]} -> {[round(x, 2) for x in v0]}")
                        break
    return errs


def rest_errors(anim: dict, var: str, values=(0.0, 1.0), where="") -> list:
    """var が values の時に全チャンネルが自然体か（回転・位置 0、スケール 1）。他の変数は 0 と 1 の両方で。"""
    from astro_scene import Molang
    errs = []
    names = {_canon(n) for n in _names(anim)} - {_canon(var)}
    for bone, chans in anim.get("bones", {}).items():
        for chan, v in chans.items():
            if isinstance(v, dict):
                continue
            want = [1.0, 1.0, 1.0] if chan == "scale" else [0.0, 0.0, 0.0]
            bad = None
            for x in values:
                for other in (0.0, 1.0):
                    env = {n: other for n in names}
                    env[_canon(var)] = x
                    got = _vec(v, Molang(env))
                    if not _close(chan, got, want):
                        bad = (x, got)
                        break
                if bad:
                    break
            if bad:
                errs.append(f"{where}{bone}.{chan} is {[round(g, 2) for g in bad[1]]} at {var} = {bad[0]:g} "
                            f"(must be the rest pose so the start/end of the swing does not pop)")
    return errs
