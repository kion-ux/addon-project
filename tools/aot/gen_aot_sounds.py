# -*- coding: utf-8 -*-
"""効果音をその場で合成して .ogg に書き出す（素材の音声は一切使わない）。

超次元と同じ道具（ノイズの帯域掃引・FM・減衰包絡、gen_hd_sounds の関数）で、
立体機動装置のアンカー射出・巻き取りのモーター・ガスの噴射・刃の斬撃と交換・
巨人の足音とうめき声・蒸気・雷槍の爆発・信煙弾を作る。各音 2〜3 種の揺らぎ付き。
"""
from __future__ import annotations

import os
import shutil

import numpy as np

import aot_common as C
from aot_common import NS, RP, write_json
from gen_hd_sounds import (SR, bandnoise, env, mixdown, norm, onepole_lp, reverb, sine, t_axis,
                           write_ogg)

SND_DIR = os.path.join(RP, "sounds", "aot")


def rng(k):
    return np.random.default_rng(k)


def lowpass(x, f):
    return onepole_lp(onepole_lp(x, f), f)


# ---------------------------------------------------------------------------
#  立体機動装置
# ---------------------------------------------------------------------------
def s_anchor(v):
    """アンカー射出: 圧縮ガスの破裂音・金属のクラック・ワイヤーの風切り。"""
    r = rng(10 + v)
    burst = bandnoise(0.09, 2500, 7000, 1.0, r) * env(0.09, 0.001, 0.09, 2.2)
    clank = sum(sine(0.25, f * (1 + v * 0.04)) * a for f, a in ((1830, 0.5), (2710, 0.35), (4120, 0.2)))
    clank *= env(0.25, 0.001, 0.25, 5)
    dur = 0.45
    whiz = bandnoise(dur, 5200, 1400, 2.0, r) * env(dur, 0.02, dur, 1.4) * 0.6
    return norm(mixdown(burst, clank * 0.55, np.concatenate([np.zeros(int(SR * 0.03)), whiz])), 0.85)


def s_hook(v):
    """アンカーが刺さる: 鈍い打撃と、肉や木に食い込む軋み。"""
    r = rng(20 + v)
    dur = 0.3
    t = t_axis(dur)
    thump = sine(dur, 160 * np.exp(-t * 14) + 70) * env(dur, 0.001, 0.22, 2.5)
    crunch = bandnoise(0.12, 600, 2200, 0.8, r) * env(0.12, 0.001, 0.12, 2)
    return norm(mixdown(thump, crunch * 0.7), 0.8)


def s_reel(v):
    """巻き取り: モーターの唸りとラチェットの刻み（0.5 秒を繰り返して鳴らす）。"""
    r = rng(30 + v)
    dur = 0.5
    t = t_axis(dur)
    f = 420 + 90 * v + 60 * t / dur
    motor = sine(dur, f + 18 * np.sin(2 * np.pi * 31 * t)) * 0.4 + sine(dur, f * 2.01) * 0.2
    clicks = np.zeros_like(t)
    for k in range(int(dur * 44)):
        i = int(k / 44 * SR)
        n = min(len(t) - i, int(SR * 0.004))
        clicks[i:i + n] += r.standard_normal(n) * np.linspace(1, 0, n)
    hiss = bandnoise(dur, 3000, 5000, 1.0, r) * 0.15
    e = np.clip(t / 0.03, 0, 1) * np.clip((dur - t) / 0.05, 0, 1)
    return norm((motor + clicks * 0.35 + hiss) * e, 0.6)


def s_gas(v):
    """ガスの噴射: 圧の抜ける長い「シュッ」。"""
    r = rng(40 + v)
    dur = 0.42
    x = bandnoise(dur, 6500, 2200, 0.7, r) * env(dur, 0.004, dur, 1.6)
    return norm(x, 0.7)


def s_boost(v):
    r = rng(50 + v)
    dur = 0.6
    gas = bandnoise(dur, 7000, 1500, 0.6, r) * env(dur, 0.003, dur, 1.3)
    whoosh = bandnoise(dur, 900, 300, 1.2, r) * env(dur, 0.05, dur, 1.5) * 0.6
    return norm(mixdown(gas, whoosh), 0.85)


# ---------------------------------------------------------------------------
#  刃
# ---------------------------------------------------------------------------
def s_swing(v):
    r = rng(60 + v)
    dur = 0.24
    x = bandnoise(dur, 1500 * (1 + v * 0.1), 5200, 0.9, r)
    e = np.sin(np.pi * np.clip(t_axis(dur) / dur, 0, 1)) ** 1.6
    ring = sine(dur, 3900 + v * 200) * env(dur, 0.01, dur, 6) * 0.15
    return norm(x * e + ring, 0.7)


def s_cut(v):
    """肉を斬る: 湿った裂ける音と、刃の短い鳴り。"""
    r = rng(70 + v)
    dur = 0.38
    slice_ = bandnoise(0.2, 3000, 700, 0.8, r) * env(0.2, 0.002, 0.2, 2.0)
    t = t_axis(dur)
    squish = bandnoise(dur, 250, 160, 1.5, r) * env(dur, 0.01, dur, 2.5) * 0.9
    ring = sine(dur, 2900 + 150 * v) * env(dur, 0.001, dur, 7) * 0.25
    return norm(mixdown(slice_, squish, ring), 0.85)


def s_nape(v):
    """うなじを削ぐ: 深く大きな斬撃、噴き出す血、蒸気の尾。"""
    r = rng(80 + v)
    dur = 1.1
    t = t_axis(dur)
    slash = bandnoise(0.35, 4000, 500, 0.7, r) * env(0.35, 0.002, 0.35, 1.6)
    gush = lowpass(r.standard_normal(len(t)), 900) * env(dur, 0.04, 0.6, 2.0) * 1.4
    thud = sine(dur, 90 * np.exp(-t * 6) + 45) * env(dur, 0.003, 0.5, 2.2)
    hiss = bandnoise(dur, 5000, 3000, 0.8, r) * np.clip((t - 0.25) / 0.2, 0, 1) * env(dur, 0.3, dur, 1.2) * 0.5
    ring = sine(dur, 2600) * env(dur, 0.001, 0.5, 6) * 0.25
    return norm(reverb(mixdown(slash, gush * 0.6, thud, hiss, ring), 0.2, 0.5, v), 0.95)


def s_swap(v):
    """刃の交換: 古い刃を捨てる金属音、新しい刃を差し込む「カチャッ」。"""
    r = rng(90 + v)
    out = np.zeros(int(SR * 0.55))
    for k, (at, f) in enumerate(((0.0, 2400), (0.18, 3100), (0.26, 1900))):
        i = int(at * SR)
        n = int(SR * 0.2)
        click = (sine(0.2, f * (1 + v * 0.05)) * 0.5 + bandnoise(0.2, 3000, 6000, 1, r) * 0.4)
        out[i:i + n] += (click * env(0.2, 0.001, 0.2, 6))[:len(out) - i]
    scrape = bandnoise(0.15, 5000, 2000, 1.5, r) * env(0.15, 0.01, 0.15, 2) * 0.4
    out[int(0.05 * SR):int(0.05 * SR) + len(scrape)] += scrape
    return norm(out, 0.7)


def s_break(v):
    r = rng(100 + v)
    dur = 0.6
    crack = bandnoise(0.05, 3000, 8000, 1.0, r) * env(0.05, 0.0005, 0.05, 2)
    ring = sum(sine(dur, f) * a for f, a in ((3400, 0.5), (5100, 0.3), (2200, 0.25))) * env(dur, 0.001, dur, 5)
    return norm(mixdown(crack, ring * 0.6), 0.8)


# ---------------------------------------------------------------------------
#  巨人
# ---------------------------------------------------------------------------
def s_step_titan(v):
    """巨人の足音: 地響きの低い打撃と土の崩れる音。"""
    r = rng(110 + v)
    dur = 1.0
    t = t_axis(dur)
    thud = sine(dur, 55 * np.exp(-t * 4) + 32 + v * 4) * env(dur, 0.004, 0.7, 2.0)
    rumble = lowpass(r.standard_normal(len(t)), 180) * env(dur, 0.01, dur, 1.6) * 2.5
    dirt = bandnoise(0.3, 800, 300, 0.8, r) * env(0.3, 0.005, 0.3, 2) * 0.3
    return norm(mixdown(thud * 1.3, rumble, dirt), 0.95)


def s_groan(v):
    """巨人のうめき: 低い喉の唸りを母音の共鳴で濁らせる。"""
    r = rng(120 + v)
    dur = 1.8
    t = t_axis(dur)
    f0 = (68 + v * 9) * (1 + 0.06 * np.sin(2 * np.pi * 3.1 * t)) * (1 - 0.12 * t / dur)
    phase = np.cumsum(f0) / SR
    saw = 2 * (phase % 1.0) - 1
    breath = r.standard_normal(len(t)) * 0.2
    src = saw + breath
    out = np.zeros_like(src)
    for fc, bw, g in ((520 + v * 40, 1.0, 1.0), (880, 1.2, 0.6), (2400, 2.0, 0.15)):
        lo = onepole_lp(src, fc * 1.3)
        out += (lo - onepole_lp(lo, fc / 1.3)) * g
    e = np.clip(t / 0.3, 0, 1) * np.clip((dur - t) / 0.6, 0, 1)
    return norm(reverb(out * e, 0.3, 0.8, v), 0.8)


def s_bite(v):
    r = rng(130 + v)
    dur = 0.6
    t = t_axis(dur)
    chomp = sine(dur, 120 * np.exp(-t * 10) + 60) * env(dur, 0.002, 0.3, 2.5)
    bones = np.zeros_like(t)
    for k in range(5):
        i = int((0.03 + k * 0.05 + r.random() * 0.02) * SR)
        n = int(SR * 0.03)
        bones[i:i + n] += bandnoise(0.03, 1500, 4000, 1, r) * env(0.03, 0.001, 0.03, 2)
    return norm(mixdown(chomp, bones * 0.7), 0.9)


def s_fall(v):
    """巨人が倒れる: 長い地響き。"""
    r = rng(140 + v)
    dur = 1.8
    t = t_axis(dur)
    boom = sine(dur, 40 * np.exp(-t * 2) + 26) * env(dur, 0.01, 1.4, 1.8)
    rumble = lowpass(r.standard_normal(len(t)), 140) * env(dur, 0.02, dur, 1.2) * 3
    crash = bandnoise(0.6, 1200, 200, 0.6, r) * env(0.6, 0.01, 0.6, 2) * 0.5
    return norm(reverb(mixdown(boom * 1.4, rumble, crash), 0.25, 0.9, v), 0.95)


def s_steam(v):
    """蒸気: 揺らぎながら長く続く噴出音。"""
    r = rng(150 + v)
    dur = 1.6
    t = t_axis(dur)
    x = bandnoise(dur, 5500, 3500, 0.7, r) * (0.7 + 0.3 * np.sin(2 * np.pi * (4 + v) * t))
    e = np.clip(t / 0.15, 0, 1) * np.clip((dur - t) / 0.7, 0, 1)
    return norm(x * e, 0.55)


# ---------------------------------------------------------------------------
#  雷槍・信煙弾・その他
# ---------------------------------------------------------------------------
def s_spear_fire(v):
    r = rng(160 + v)
    dur = 0.7
    pop = bandnoise(0.08, 400, 2000, 0.8, r) * env(0.08, 0.001, 0.08, 2) * 1.2
    whoosh = bandnoise(dur, 3000, 600, 1.0, r) * env(dur, 0.01, dur, 1.4)
    return norm(mixdown(pop, whoosh * 0.7), 0.85)


def s_fuse(v):
    """雷槍の導火: パチパチと弾ける音。"""
    r = rng(170 + v)
    dur = 1.2
    out = np.zeros(int(SR * dur))
    for k in range(70):
        i = int(r.random() * (dur - 0.02) * SR)
        n = int(SR * 0.006)
        out[i:i + n] += r.standard_normal(n) * np.linspace(1, 0, n) * (0.4 + r.random())
    hiss = bandnoise(dur, 4000, 6000, 1, r) * 0.18
    return norm(out + hiss, 0.6)


def s_boom(v):
    """雷槍の爆発: 雷鳴のような裂ける音と、重い爆風。"""
    r = rng(180 + v)
    dur = 2.0
    t = t_axis(dur)
    boom = sine(dur, 60 * np.exp(-t * 3) + 34) * env(dur, 0.002, 1.2, 1.8) * 1.4
    blast = lowpass(r.standard_normal(len(t)), 600) * env(dur, 0.001, dur, 2.6) * 3
    crack = bandnoise(0.25, 6000, 1500, 0.8, r) * env(0.25, 0.0005, 0.25, 1.4)
    return norm(reverb(mixdown(boom, blast, crack), 0.35, 1.0, v), 0.98)


def s_flare(v):
    """信煙弾: 発射の破裂と、昇っていく笛のような音。"""
    r = rng(190 + v)
    dur = 1.4
    t = t_axis(dur)
    pop = bandnoise(0.1, 500, 3000, 0.8, r) * env(0.1, 0.001, 0.1, 2) * 1.2
    whistle = sine(dur, 900 + 1400 * (t / dur) ** 0.7) * env(dur, 0.05, dur, 1.4) * 0.25
    fizz = bandnoise(dur, 4000, 7000, 1, r) * env(dur, 0.02, dur, 1.2) * 0.4
    return norm(mixdown(pop, whistle, fizz), 0.8)


def s_kill(v):
    """討伐の合図: 短い太鼓と低い和音。"""
    dur = 1.0
    t = t_axis(dur)
    drum = sine(dur, 90 * np.exp(-t * 12) + 55) * env(dur, 0.002, 0.4, 2.5)
    chord = sum(sine(dur, f) * a for f, a in ((220, 0.35), (277, 0.25), (330, 0.25), (440, 0.15)))
    chord *= env(dur, 0.04, dur, 2.2)
    return norm(reverb(mixdown(drum, chord * 0.6), 0.3, 0.7, v), 0.7)


SOUNDS = {
    "anchor": (s_anchor, 3, "player"),
    "hook": (s_hook, 2, "player"),
    "reel": (s_reel, 2, "player"),
    "gas": (s_gas, 3, "player"),
    "boost": (s_boost, 2, "player"),
    "swing": (s_swing, 3, "player"),
    "cut": (s_cut, 3, "player"),
    "nape": (s_nape, 2, "player"),
    "swap": (s_swap, 2, "player"),
    "break": (s_break, 2, "player"),
    "titan_step": (s_step_titan, 3, "hostile"),
    "titan_groan": (s_groan, 3, "hostile"),
    "titan_bite": (s_bite, 2, "hostile"),
    "titan_fall": (s_fall, 2, "hostile"),
    "steam": (s_steam, 2, "hostile"),
    "spear_fire": (s_spear_fire, 2, "player"),
    "fuse": (s_fuse, 1, "player"),
    "boom": (s_boom, 2, "player"),
    "flare": (s_flare, 2, "player"),
    "kill": (s_kill, 1, "player"),
}


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
            if not os.path.exists(path) or os.environ.get("AOT_RESOUND"):
                write_ogg(path, fn(v))
            total += os.path.getsize(path)
            entries.append({"name": f"sounds/aot/{name}_{v}", "volume": 1.0})
        far = 96.0 if name in ("titan_step", "titan_fall", "boom", "flare", "titan_groan") else 40.0
        defs[f"{NS}.{name}"] = {"category": cat, "max_distance": far, "sounds": entries}
    write_json(os.path.join(RP, "sounds", "sound_definitions.json"),
               {"format_version": "1.14.0", "sound_definitions": defs})
    print(f"  sounds: {len(SOUNDS)} ({total // 1024} KB)")
    _ = C


if __name__ == "__main__":
    main()
