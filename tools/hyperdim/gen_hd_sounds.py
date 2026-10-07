# -*- coding: utf-8 -*-
"""効果音をその場で合成して .ogg に書き出す（numpy + ffmpeg/libvorbis）。

素材の音声ファイルを一切使わず、ノイズの帯域掃引・FM・減衰包絡だけで
「風切り」「斬撃の金属音」「溜め」「必殺技のカットイン」などを作る。
各音は 2〜3 種類の揺らぎを持たせ、sound_definitions でランダムに鳴らす。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd_common import NS, RP, write_json  # noqa: E402

SR = 32000
SND_DIR = os.path.join(RP, "sounds", "hd")


def t_axis(dur):
    return np.arange(int(SR * dur)) / SR


def env(dur, attack=0.005, decay=None, curve=3.0):
    t = t_axis(dur)
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.clip(1 - (t - attack) / max((decay or dur) - attack, 1e-4), 0, 1) ** curve
    return a * d


def onepole_lp(x, cutoff):
    """時変カットオフの 1 次ローパス（cutoff は配列でも可）。"""
    cutoff = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def bandnoise(dur, f0, f1, q=1.0, rng=None):
    rng = rng or np.random.default_rng(0)
    n = rng.standard_normal(int(SR * dur))
    f = np.geomspace(max(f0, 20), max(f1, 20), len(n))
    lo = onepole_lp(n, f * (1 + 0.5 / q))
    hi = lo - onepole_lp(lo, f / (1 + 0.5 / q))
    return hi


def sine(dur, f, phase=0.0):
    t = t_axis(dur)
    f = np.broadcast_to(np.asarray(f, float), t.shape)
    return np.sin(2 * np.pi * np.cumsum(f) / SR + phase)


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def pad(x, dur):
    n = int(SR * dur)
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros(n - len(x))])


def mixdown(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def reverb(x, amount=0.3, length=0.6, seed=1):
    rng = np.random.default_rng(seed)
    n = int(SR * length)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir[0] = 0
    wet = np.convolve(x, ir)[:len(x) + n] * (amount / np.sqrt(n) * 6)
    return mixdown(x, wet)


# ---------------------------------------------------------------------------
#  音色
# ---------------------------------------------------------------------------
def s_swing(v, heavy=False):
    rng = np.random.default_rng(10 + v)
    dur = 0.42 if heavy else 0.26
    f0, f1 = (300, 1400) if heavy else (900, 4200)
    x = bandnoise(dur, f0 * (1 + v * 0.1), f1 * (1 + v * 0.08), 0.8, rng)
    e = np.sin(np.pi * np.clip(t_axis(dur) / dur, 0, 1)) ** 1.6
    return norm(x * e, 0.7)


def s_hit_slash(v):
    rng = np.random.default_rng(20 + v)
    dur = 0.5
    ring = sum(sine(dur, f * (1 + v * 0.03)) * a for f, a in
               ((2630, 0.5), (3870, 0.35), (5210, 0.25), (1720, 0.3)))
    ring *= env(dur, 0.002, dur, 4)
    burst = bandnoise(0.12, 2000, 6000, 1, rng) * env(0.12, 0.001, 0.12, 2)
    return norm(reverb(mixdown(ring * 0.6, burst), 0.25, 0.4, v))


def s_hit_heavy(v):
    rng = np.random.default_rng(30 + v)
    dur = 0.6
    t = t_axis(dur)
    thump = sine(dur, 90 * np.exp(-t * 8) + 42) * env(dur, 0.002, 0.45, 2.2)
    crunch = bandnoise(0.25, 400, 2400, 0.7, rng) * env(0.25, 0.001, 0.25, 2.5)
    return norm(mixdown(thump * 1.2, crunch * 0.8))


def s_dash(v):
    rng = np.random.default_rng(40 + v)
    dur = 0.45
    x = bandnoise(dur, 2500, 400, 0.6, rng)
    e = env(dur, 0.01, dur, 1.6)
    zip_ = sine(0.2, np.geomspace(1800, 600, int(SR * 0.2))) * env(0.2, 0.002, 0.2, 3) * 0.25
    return norm(mixdown(x * e, zip_), 0.8)


def s_jump(v):
    rng = np.random.default_rng(50 + v)
    dur = 0.35
    x = bandnoise(dur, 500, 2600, 0.8, rng) * env(dur, 0.01, dur, 2)
    chime = sine(dur, 1320 * (1 + v * 0.06)) * env(dur, 0.002, dur, 5) * 0.3
    return norm(mixdown(x, chime), 0.7)


def s_charge(v):
    dur = 1.0
    t = t_axis(dur)
    f = 220 * np.exp(t * 1.7) * (1 + v * 0.05)
    tone = sine(dur, f) * 0.5 + sine(dur, f * 2.01) * 0.3 + sine(dur, f * 3.02) * 0.15
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * (6 + t * 18) * t)
    shimmer = bandnoise(dur, 3000, 9000, 1.5, np.random.default_rng(60 + v)) * 0.2
    e = np.clip(t / dur, 0, 1) ** 1.3 * np.clip((dur - t) / 0.05, 0, 1)
    return norm((tone * trem + shimmer) * e, 0.75)


def s_cutin(v):
    """必殺技のカットイン: 高く伸びる「キィン」と低い衝撃。"""
    dur = 1.4
    t = t_axis(dur)
    kiin = (sine(dur, 3520 + 400 * np.sin(t * 9)) * 0.4 + sine(dur, 5280) * 0.2) * \
        env(dur, 0.01, dur, 2.5)
    boom = sine(dur, 70 * np.exp(-t * 3) + 30) * env(dur, 0.003, 0.9, 2) * 1.2
    air = bandnoise(dur, 6000, 800, 0.7, np.random.default_rng(70 + v)) * env(dur, 0.02, 0.8, 2) * 0.4
    return norm(reverb(mixdown(kiin, boom, air), 0.35, 0.9, 7))


def s_boom(v):
    rng = np.random.default_rng(80 + v)
    dur = 1.8
    t = t_axis(dur)
    low = sine(dur, 55 * np.exp(-t * 2.2) + 26) * env(dur, 0.004, 1.5, 2.2)
    rumble = onepole_lp(rng.standard_normal(len(t)), 260) * env(dur, 0.01, dur, 1.8) * 6
    crack = bandnoise(0.3, 800, 5000, 0.7, rng) * env(0.3, 0.001, 0.3, 2)
    return norm(reverb(mixdown(low * 1.4, rumble, crack * 0.7), 0.3, 1.0, 8))


def s_beam(v):
    dur = 0.9
    t = t_axis(dur)
    f = 180 + 40 * np.sin(2 * np.pi * 9 * t)
    buzz = np.sign(sine(dur, f)) * 0.3 + sine(dur, f * 4) * 0.3
    zap = bandnoise(dur, 4000, 1500, 1.2, np.random.default_rng(90 + v)) * 0.5
    e = env(dur, 0.01, dur, 1.4)
    return norm(onepole_lp((buzz + zap) * e, 5000), 0.75)


def s_arrow(v):
    rng = np.random.default_rng(100 + v)
    dur = 0.4
    t = t_axis(dur)
    twang = sine(dur, 330 * (1 + 0.3 * np.exp(-t * 30))) * env(dur, 0.001, 0.3, 3) * 0.6
    zip_ = bandnoise(dur, 5000, 1500, 1.0, rng) * env(dur, 0.03, dur, 2)
    return norm(mixdown(twang, zip_), 0.7)


def s_guard(v):
    dur = 0.6
    ring = sum(sine(dur, f * (1 + v * 0.02)) * a for f, a in
               ((1180, 0.5), (2360, 0.3), (3150, 0.25), (4720, 0.15)))
    return norm(reverb(ring * env(dur, 0.001, dur, 3.5), 0.3, 0.5, 9), 0.75)


def s_parry(v):
    dur = 0.9
    ring = sum(sine(dur, f) * a for f, a in ((2093, 0.5), (3136, 0.35), (4186, 0.25), (6272, 0.15)))
    return norm(reverb(ring * env(dur, 0.001, dur, 2.5), 0.45, 0.8, 10), 0.8)


def s_zap(v):
    rng = np.random.default_rng(110 + v)
    dur = 0.55
    n = rng.standard_normal(int(SR * dur))
    gate = (rng.random(int(SR * dur)) < 0.08).astype(float)
    gate = onepole_lp(gate, 900) * 8
    crackle = n * np.clip(gate, 0, 1)
    hum = np.sign(sine(dur, 120)) * 0.15
    return norm((crackle + hum) * env(dur, 0.002, dur, 1.5), 0.8)


def s_fire(v):
    rng = np.random.default_rng(120 + v)
    dur = 0.9
    roar = onepole_lp(rng.standard_normal(int(SR * dur)), np.geomspace(300, 2200, int(SR * dur)))
    pops = (rng.random(int(SR * dur)) < 0.004) * rng.standard_normal(int(SR * dur)) * 3
    return norm((roar * 4 + onepole_lp(pops, 3000)) * env(dur, 0.03, dur, 1.5), 0.8)


def s_wind(v):
    rng = np.random.default_rng(130 + v)
    dur = 0.8
    t = t_axis(dur)
    f = 600 + 900 * np.sin(np.pi * t / dur)
    x = bandnoise(dur, 400, 1600, 2.5, rng)
    x2 = onepole_lp(rng.standard_normal(len(t)), f) * 2
    return norm((x + x2) * np.sin(np.pi * t / dur) ** 1.2, 0.7)


def s_shadow(v):
    rng = np.random.default_rng(140 + v)
    dur = 0.6
    t = t_axis(dur)
    x = bandnoise(dur, 200, 900, 0.8, rng)
    e = (t / dur) ** 2.5 * np.clip((dur - t) / 0.04, 0, 1)            # 逆再生風に膨らむ
    low = sine(dur, 70 + 30 * t) * e * 0.5
    return norm(mixdown(x * e, low), 0.75)


def s_crack(v):
    rng = np.random.default_rng(150 + v)
    dur = 0.25
    snap = rng.standard_normal(int(SR * dur)) * env(dur, 0.0005, 0.05, 2)
    body_ = bandnoise(dur, 3000, 1200, 1, rng) * env(dur, 0.001, dur, 4) * 0.6
    return norm(reverb(mixdown(snap, body_), 0.2, 0.3, 11), 0.9)


def s_roar(v):
    rng = np.random.default_rng(160 + v)
    dur = 1.3
    t = t_axis(dur)
    f = 95 + 25 * np.sin(np.pi * t / dur) + 6 * rng.standard_normal(len(t)).cumsum() / SR * 40
    saw = 2 * ((np.cumsum(f) / SR) % 1.0) - 1
    growl = onepole_lp(saw * (0.7 + 0.3 * np.sin(2 * np.pi * 28 * t)), 1400)
    breath = bandnoise(dur, 500, 2500, 0.6, rng) * 0.35
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.6
    return norm(reverb((growl + breath) * e, 0.3, 0.7, 12), 0.85)


def s_ice(v):
    rng = np.random.default_rng(170 + v)
    dur = 0.7
    out = np.zeros(int(SR * dur))
    for k in range(9):
        st = int(rng.uniform(0, 0.25) * SR)
        f = rng.uniform(2500, 7000)
        ln = int(0.3 * SR)
        tone = np.sin(2 * np.pi * f * np.arange(ln) / SR) * np.exp(-np.arange(ln) / SR * 18)
        out[st:st + ln] += tone[:len(out) - st] * rng.uniform(0.3, 0.7)
    noise = bandnoise(0.15, 3000, 8000, 1, rng) * env(0.15, 0.001, 0.15, 2)
    return norm(mixdown(out, noise * 0.6), 0.8)


def s_ding(v):
    dur = 0.8
    x = sum(sine(dur, f) * a for f, a in ((1568, 0.5), (2349, 0.35), (3136, 0.2)))
    return norm(reverb(x * env(dur, 0.002, dur, 3), 0.4, 0.6, 13), 0.6)


def s_step(v):
    rng = np.random.default_rng(180 + v)
    dur = 0.22
    return norm(bandnoise(dur, 3500, 900, 0.8, rng) * env(dur, 0.005, dur, 1.8), 0.65)


SOUNDS = {
    "swing": (lambda v: s_swing(v), 3, "player"),
    "swing_heavy": (lambda v: s_swing(v, True), 3, "player"),
    "hit_slash": (s_hit_slash, 3, "player"),
    "hit_heavy": (s_hit_heavy, 3, "player"),
    "dash": (s_dash, 2, "player"),
    "jump": (s_jump, 2, "player"),
    "step": (s_step, 2, "player"),
    "charge": (s_charge, 1, "player"),
    "cutin": (s_cutin, 1, "player"),
    "boom": (s_boom, 2, "player"),
    "beam": (s_beam, 1, "player"),
    "arrow": (s_arrow, 2, "player"),
    "guard": (s_guard, 2, "player"),
    "parry": (s_parry, 1, "player"),
    "zap": (s_zap, 2, "player"),
    "fire": (s_fire, 2, "player"),
    "wind": (s_wind, 2, "player"),
    "shadow": (s_shadow, 2, "player"),
    "crack": (s_crack, 2, "player"),
    "roar": (s_roar, 1, "player"),
    "ice": (s_ice, 2, "player"),
    "ding": (s_ding, 1, "player"),
}


def write_ogg(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "a.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis",
                        "-q:a", "3", path], check=True)


def main():
    if not shutil.which("ffmpeg"):
        print("  ffmpeg が無いので効果音の生成を飛ばします（既存の .ogg を使用）")
        return
    os.makedirs(SND_DIR, exist_ok=True)
    defs = {}
    total = 0
    for name, (fn, variants, cat) in SOUNDS.items():
        entries = []
        for v in range(variants):
            path = os.path.join(SND_DIR, f"{name}_{v}.ogg")
            if not os.path.exists(path) or os.environ.get("HD_RESOUND"):
                write_ogg(path, fn(v))
            total += os.path.getsize(path)
            entries.append({"name": f"sounds/hd/{name}_{v}", "volume": 1.0})
        defs[f"{NS}.{name}"] = {"category": cat, "max_distance": 48.0, "sounds": entries}
    write_json(os.path.join(RP, "sounds", "sound_definitions.json"),
               {"format_version": "1.14.0", "sound_definitions": defs})
    print(f"  sounds: {len(SOUNDS)} ({total // 1024} KB)")


if __name__ == "__main__":
    main()
