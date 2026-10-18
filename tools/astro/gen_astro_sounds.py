# -*- coding: utf-8 -*-
"""アストロ・ナノギア — 効果音をその場で合成して .ogg と sound_definitions.json を書き出す。

素材の音声ファイルは一切使わず、numpy だけで「発振（FM・帯域制限ノコギリ波・スーパーソウ）」
「時間で動くフィルタ（STFT 上で周波数ごとのゲインを掛ける。帯域ノイズの掃引・共振ローパス・フォルマント）」
「打撃の層（ピッチの落ちるサイン波の胴鳴り＋ノイズの立ち上がり＋金属のモード合成）」
「粒（ナノマシンのさえずり・破片・泡・火花を数百粒ばらまくグラニュラー）」
「歪み（tanh の飽和）・可変ディレイ（フランジャー・ドップラー）・フィードバックエコー・
FFT 畳み込みのリバーブ・逆再生のスウェル」を重ねて、変身・機動・戦闘・惑星の元素・UI・敵の
62 種の音を作る。各音は 2〜3 種の揺らぎ（ピッチと乱数の種）を持ち、sound_definitions でランダムに鳴らす。
乱数の種は名前と番号から決まり、ffmpeg も bitexact で書き出すので、作り直しても同じファイルになる。
最後に直流と超低域を切り、端に短いフェードを掛け、ピーク -1 dBFS に揃える（音量差は定義の volume で付ける）。
hyperdim の gen_hd_sounds.py を土台にしたが、サンプルごとの Python ループは使わずに全てベクトル化している。

  python3 tools/astro/gen_astro_sounds.py              変わった時だけ作り直す（生成器の内容のハッシュで判定）
  python3 tools/astro/gen_astro_sounds.py --force      全部作り直す
  python3 tools/astro/gen_astro_sounds.py swarm hit    指定した音だけ作り直す
  python3 tools/astro/gen_astro_sounds.py --preview    ASTRO_SCRATCH/sounds.png に波形とスペクトログラムの一覧
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
try:
    from astro_data import NS  # noqa: E402
except Exception:  # pragma: no cover - astro_data が壊れていても音だけは作れるように
    NS = "astro"

RP = os.path.join(ROOT, "packs", "astro_RP")
SND_REL = "sounds/astro"
SND_DIR = os.path.join(RP, *SND_REL.split("/"))
DEFS_PATH = os.path.join(RP, "sounds", "sound_definitions.json")
SCRATCH = os.environ.get("ASTRO_SCRATCH", os.path.join(ROOT, "build_preview", "astro"))
STAMP = os.path.join(SCRATCH, "sounds_stamp.json")

SR = 44100
NYQ = SR / 2
OGG_Q = "4"
PEAK_DB = -1.0
TAU = 2 * np.pi


# ===========================================================================
#  基本
# ===========================================================================
def ns(d):
    return max(1, int(round(d * SR)))


def tt(d):
    return np.arange(ns(d)) / SR


def K(*pts, log=True):
    """時間の曲線。K((t0, v0), (t1, v1), ...) → t を受け取る関数。log=True は対数で補間（周波数向け）。"""
    ts = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    if log:
        lv = np.log(np.maximum(vs, 1e-9))
        return lambda t: np.exp(np.interp(t, ts, lv))
    return lambda t: np.interp(t, ts, vs)


def L(*pts):
    return K(*pts, log=False)


def ev(c, d):
    """曲線・配列・定数を長さ d 秒の配列にする。"""
    n = ns(d)
    if callable(c):
        return c(np.arange(n) / SR)
    a = np.asarray(c, float)
    if a.ndim == 0:
        return np.full(n, float(a))
    if len(a) == n:
        return a
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(a)), a)


def _cv(c, t):
    return c(t) if callable(c) else c


def norm(x, peak=1.0):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return x * (peak / m) if m > 0 else x


def _endfade(a, dur=0.025):
    """鳴ったまま途切れる層の末尾を滑らかに閉じる（プチッというクリック防止）。"""
    if len(a) < 64:
        return a
    pk = float(np.max(np.abs(a)))
    if pk <= 0 or float(np.max(np.abs(a[-32:]))) < pk * 1e-3:
        return a
    n = min(ns(dur), len(a) // 4)
    a = a.copy()
    a[len(a) - n:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(n) / n)
    return a


def mix(*items):
    """配列、または (開始秒, 配列[, 倍率]) を足し合わせる。"""
    parts = []
    for it in items:
        if isinstance(it, tuple):
            t0, a = it[0], it[1]
            g = it[2] if len(it) > 2 else 1.0
        else:
            t0, a, g = 0.0, it, 1.0
        parts.append((int(round(t0 * SR)), _endfade(np.asarray(a, float)), g))
    n = max(o + len(a) for o, a, _ in parts)
    out = np.zeros(n)
    for o, a, g in parts:
        out[o:o + len(a)] += a * g
    return out


def fit(x, d):
    n = ns(d)
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros(n - len(x))])


# ---- 包絡 ------------------------------------------------------------------
def perc(d, a=0.001, tau=0.1):
    t = tt(d)
    return np.minimum(t / max(a, 1e-5), 1.0) * np.exp(-np.maximum(t - a, 0) / tau)


def envp(d, *pts):
    """区分線形の包絡。envp(d, (t, a), ...)"""
    return np.interp(tt(d), [p[0] for p in pts], [p[1] for p in pts])


def rise(d, p=2.0):
    return (tt(d) / d) ** p


def arch(d, p=1.0):
    return np.sin(np.pi * np.clip(tt(d) / d, 0, 1)) ** p


def lfo(rate, d, depth=1.0, phase=0.0):
    """0..1 を往復する正弦の LFO（rate は曲線でも可）。"""
    return 1 - depth + depth * (0.5 + 0.5 * np.sin(TAU * np.cumsum(ev(rate, d)) / SR + phase))


# ---- 発振 ------------------------------------------------------------------
def ph(f, d):
    return TAU * np.cumsum(ev(f, d)) / SR


def sine(f, d, p0=0.0):
    return np.sin(ph(f, d) + p0)


def saw(f, d, p0=0.0):
    """polyBLEP の帯域制限ノコギリ波。"""
    fa = ev(f, d)
    dt = np.clip(fa / SR, 1e-7, 0.5)
    p = (p0 + np.cumsum(dt)) % 1.0
    y = 2 * p - 1
    m = p < dt
    x = p[m] / dt[m]
    y[m] -= x + x - x * x - 1
    m = p > 1 - dt
    x = (p[m] - 1) / dt[m]
    y[m] -= x * x + x + x + 1
    return y


def sqr(f, d, hard=5.0, p0=0.0):
    """角の丸い矩形波（tanh で潰した正弦）。デジタルなビープ・クラクション向け。"""
    return np.tanh(hard * np.sin(ph(f, d) + p0)) / np.tanh(hard)


def fm(fc, ratio, index, d, p0=0.0):
    pc = ph(fc, d)
    pm = ph(ev(fc, d) * ratio, d)
    return np.sin(pc + ev(index, d) * np.sin(pm) + p0)


def supersaw(f, d, rng, voices=5, det=0.012):
    fa = ev(f, d)
    out = np.zeros(len(fa))
    for k in range(voices):
        o = (k - (voices - 1) / 2) / max((voices - 1) / 2, 1)
        out += saw(fa * (1 + det * o), d, rng.random())
    return out / np.sqrt(voices)


def wn(d, rng):
    return rng.standard_normal(ns(d))


def wobble(d, rate, rng):
    """滑らかな乱数の揺れ（平均 0・標準偏差 1）。"""
    x = ffilt(wn(d + 0.2, rng), lp=rate, order=2)[:ns(d)]
    s = float(np.std(x)) or 1.0
    return x / s


# ===========================================================================
#  フィルタ（FFT・STFT。ゼロ位相）
# ===========================================================================
def _lp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order))


def _hp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-3)) ** (2 * order))


def _bp(f, fc, q=1.0):
    f = np.maximum(f, 1e-3)
    x = q * (f / fc - fc / f)
    return 1.0 / np.sqrt(1.0 + x * x)


def ffilt(x, lp=None, hp=None, bp=None, q=1.0, order=2, peaks=()):
    """時間で変わらないフィルタ。peaks=[(fc, 倍率, q), ...] は共振の山。"""
    pad = 2048
    n = len(x) + 2 * pad
    X = np.fft.rfft(np.concatenate([np.zeros(pad), x, np.zeros(pad)]))
    f = np.fft.rfftfreq(n, 1 / SR)
    H = np.ones_like(f)
    if lp:
        H *= _lp(f, lp, order)
    if hp:
        H *= _hp(f, hp, order)
    if bp:
        H *= _bp(f, bp, q)
    for fc, g, pq in peaks:
        H *= 1 + (g - 1) * _bp(f, fc, pq)
    return np.fft.irfft(X * H, n)[pad:pad + len(x)]


_HANN = {}


def tvf(x, G, nfft=1024, hop=256):
    """時間で動くフィルタ。G(t, f) がゲイン（t は (フレーム, 1)、f は (1, ビン) の配列）。"""
    if nfft not in _HANN:
        _HANN[nfft] = 0.5 - 0.5 * np.cos(TAU * np.arange(nfft) / nfft)
    w = _HANN[nfft]
    n = len(x)
    xp = np.concatenate([np.zeros(nfft), x, np.zeros(nfft + hop * 4)])
    nfr = 1 + (len(xp) - nfft) // hop
    nfr -= nfr % 4
    idx = hop * np.arange(nfr)[:, None] + np.arange(nfft)[None, :]
    X = np.fft.rfft(xp[idx] * w, axis=1)
    tc = ((hop * np.arange(nfr) + nfft / 2 - nfft) / SR)[:, None]
    f = np.maximum(np.fft.rfftfreq(nfft, 1 / SR), 1.0)[None, :]
    g = G(np.maximum(tc, 0.0), f)
    Y = np.fft.irfft(X * g, n=nfft, axis=1) * w
    out = np.zeros(hop * nfr + nfft * 2)
    for j in range(4):                       # hop = nfft/4 なので 4 本ずつ重ならずに並べられる
        blk = Y[j::4].ravel()
        out[j * hop:j * hop + len(blk)] += blk
    return out[nfft:nfft + n] / 1.5


def Gbp(fc, q=1.0):
    return lambda t, f: _bp(f, _cv(fc, t), q)


def Glp(fc, order=2):
    return lambda t, f: _lp(f, _cv(fc, t), order)


def Ghp(fc, order=2):
    return lambda t, f: _hp(f, _cv(fc, t), order)


def Gres(fc, q=4.0, res=2.0, order=2):
    """共振ローパス（シンセのフィルタ掃引）。"""
    return lambda t, f: _lp(f, _cv(fc, t), order) + res * _bp(f, _cv(fc, t), q)


def Gform(fcs, q=6.0, floor=0.05, gains=None):
    gains = gains or [1.0] * len(fcs)
    return lambda t, f: floor + sum(g * _bp(f, _cv(c, t), q) for c, g in zip(fcs, gains))


def Gmul(*gs):
    def g(t, f):
        out = 1.0
        for h in gs:
            out = out * h(t, f)
        return out
    return g


def cn(d, G, rng):
    """色付きノイズ（白色ノイズを時間で動くフィルタに通す）。ピークを 1 に揃えて返す。"""
    return norm(tvf(wn(d, rng), G))


# ===========================================================================
#  エフェクト
# ===========================================================================
def drive(x, k=2.0):
    x = norm(x)
    return np.tanh(k * x) / np.tanh(k)


def crush(x, hold):
    i = (np.arange(len(x)) // hold) * hold
    return x[i]


def vdelay(x, dsec):
    """可変ディレイ（フランジャー・コーラス・ドップラー）。dsec は秒の配列・曲線・定数。"""
    n = np.arange(len(x), dtype=float)
    d = ev(dsec, len(x) / SR)[:len(x)] * SR
    return np.interp(n - d, n, x, left=0.0, right=0.0)


def flanger(x, rate=0.4, lo=0.0008, hi=0.004, mixw=0.7):
    d = len(x) / SR
    dl = lo + (hi - lo) * lfo(rate, d)
    return x + mixw * vdelay(x, dl[:len(x)])


def resamp(x, ratio):
    """再生速度を ratio 倍にする（ピッチと長さが変わる）。"""
    m = int(len(x) / ratio)
    return np.interp(np.arange(m) * ratio, np.arange(len(x)), x)


def conv(x, ir):
    n = len(x) + len(ir) - 1
    nf = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nf) * np.fft.rfft(ir, nf), nf)[:n]


@functools.lru_cache(maxsize=64)
def _ir(t60, damp, pre, seed):
    rng = np.random.default_rng(9000 + seed)
    d = min(t60 * 1.1, 3.2)
    nz = rng.standard_normal(ns(d))
    ir = tvf(nz, lambda t, f: np.exp(-6.91 * t / t60 * (1 + f / damp)))
    ir *= np.minimum(tt(d) / 0.006, 1.0)
    er = np.zeros(ns(0.05))                                   # 初期反射
    for k in range(6):
        er[int(rng.uniform(0.004, 0.045) * SR)] += rng.uniform(-0.6, 0.6)
    ir = mix(ir * 0.8, er)
    ir = np.concatenate([np.zeros(ns(pre)), ir])
    return ir / np.sqrt(np.sum(ir ** 2))


def reverb(x, wet=0.3, t60=1.0, damp=5000.0, pre=0.012, hp=120.0, seed=0):
    ir = _ir(round(t60, 3), round(damp, 1), round(pre, 4), seed)
    src = ffilt(x, hp=hp) if hp else x
    w = conv(src, ir) * wet
    return mix(x, w)


def echo(x, delay=0.12, fb=0.4, taps=4, lp=3500.0):
    out = [x]
    w = x
    for k in range(1, taps + 1):
        w = ffilt(w, lp=lp, order=1) * fb
        out.append((delay * k, w))
    return mix(*out)


def rev(x):
    return x[::-1].copy()


# ===========================================================================
#  音の部品
# ===========================================================================
PLATE = (1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501, 4.06, 4.61)
BAR = (1.0, 2.756, 5.404, 8.933)
BELL = (0.56, 0.92, 1.19, 1.71, 2.0, 2.74, 3.0, 3.76, 4.07)
BLADE = (1.0, 1.47, 2.09, 2.56, 3.37, 4.13)


def modal(d, freqs, amps, taus, rng=None, a=0.0004):
    t = tt(d)[None, :]
    F = np.asarray(freqs, float)[:, None]
    A = np.asarray(amps, float)[:, None]
    T = np.asarray(taus, float)[:, None]
    p0 = (rng.uniform(0, TAU, len(F)) if rng is not None else np.zeros(len(F)))[:, None]
    y = (A * np.sin(TAU * F * t + p0) * np.exp(-t / T)).sum(axis=0)
    return y * np.minimum(tt(d) / a, 1.0)


def metal(d, f0, ratios, rng, tau=0.3, bright=1.0, spread=0.01, dpow=0.7, a=0.0004):
    """金属のモード合成（板・棒・鐘の非整数倍音）。"""
    r = np.asarray(ratios, float)
    fr = f0 * r * (1 + spread * rng.standard_normal(len(r)))
    keep = fr < NYQ * 0.9
    amps = r ** (-bright) * rng.uniform(0.55, 1.0, len(r))
    taus = tau * r ** (-dpow)
    return norm(modal(d, fr[keep], amps[keep], taus[keep], rng, a))


def thump(d, f0, f1, tf=0.04, ta=0.15, a=0.0008, h2=0.18):
    """ピッチの落ちる胴鳴り（キック・着地・爆発の芯）。"""
    t = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t / tf)
    p = ph(f, d)
    return (np.sin(p) + h2 * np.sin(2 * p)) * perc(d, a, ta)


def click(rng, d=0.008, hp=1500.0, lp=14000.0, tau=0.0012):
    x = wn(d, rng) * np.exp(-tt(d) / tau)
    return norm(ffilt(x, hp=hp, lp=lp))


def burst(d, rng, tau=0.05, a=0.0005, **flt):
    """減衰するノイズの塊（ffilt の引数で色を付ける）。"""
    return norm(ffilt(wn(d, rng), **flt)) * perc(d, a, tau)


def whoosh(d, rng, fc, q=1.0, env=None):
    x = cn(d, Gbp(fc, q), rng)
    return x * (env if env is not None else arch(d, 1.2))


def scatter(d, count, dens, rng, make, tail=0.6):
    """粒をばらまく。dens(t) が密度、make(rng, t) が粒の配列を返す。"""
    tg = np.linspace(0, d, 2048)
    w = np.maximum(dens(tg), 1e-9)
    cdf = np.cumsum(w)
    cdf /= cdf[-1]
    times = np.sort(np.interp(rng.random(count), cdf, tg))
    out = np.zeros(ns(d + tail))
    for ti in times:
        g = make(rng, float(ti))
        s = int(ti * SR)
        e = min(len(out), s + len(g))
        if e > s:
            out[s:e] += g[:e - s]
    return out


def ping(f, tau, d=None, a=0.0003, p0=0.0):
    d = d or min(tau * 6, 1.5)
    t = tt(d)
    return np.sin(TAU * f * t + p0) * np.exp(-t / tau) * np.minimum(t / a, 1)


def bubble(f0, tau, risef=1.8, d=None):
    """泡の「ポコッ」（上がるピッチの減衰正弦）。"""
    d = d or tau * 5
    t = tt(d)
    f = f0 * (1 + (risef - 1) * t / d)
    return np.sin(ph(f, d)) * np.exp(-t / tau) * np.minimum(t / 0.0006, 1)


def g_ping(lo, hi, tlo, thi, amp=(0.3, 1.0), drift=0.0, dur=1.0):
    """金属の小さな粒。drift で時間とともに音程が上がる（負なら下がる）。"""
    def make(rng, t):
        f = np.exp(rng.uniform(np.log(lo), np.log(hi))) * (1 + drift * t / dur)
        return ping(min(f, NYQ * 0.9), rng.uniform(tlo, thi), p0=rng.uniform(0, TAU)) * rng.uniform(*amp)
    return make


def g_click(hp=2000.0, lp=12000.0, amp=(0.2, 1.0), tau=(0.0006, 0.002)):
    def make(rng, t):
        return click(rng, 0.012, hp=hp, lp=lp, tau=rng.uniform(*tau)) * rng.uniform(*amp)
    return make


def g_chitter(lo, hi, amp=(0.2, 0.7)):
    """虫の羽音のような細かい FM の粒（ナノマシンのさえずり）。"""
    def make(rng, t):
        d = rng.uniform(0.006, 0.02)
        f = np.exp(rng.uniform(np.log(lo), np.log(hi)))
        x = fm(L((0, f), (d, f * rng.uniform(0.8, 1.3))), 1.41, 2.5, d) * arch(d, 1.5)
        return x * rng.uniform(*amp)
    return make


def g_bubble(lo, hi, tau=(0.008, 0.03), amp=(0.3, 1.0), risef=(1.5, 2.6)):
    def make(rng, t):
        f = np.exp(rng.uniform(np.log(lo), np.log(hi)))
        return bubble(f, rng.uniform(*tau), rng.uniform(*risef)) * rng.uniform(*amp)
    return make


def g_debris(lo=600.0, hi=4000.0, amp=(0.1, 0.8)):
    def make(rng, t):
        fc = np.exp(rng.uniform(np.log(lo), np.log(hi)))
        d = rng.uniform(0.01, 0.04)
        x = norm(ffilt(wn(d, rng), bp=fc, q=1.5)) * perc(d, 0.0005, d / 4)
        return x * rng.uniform(*amp)
    return make


def g_spark(amp=(0.2, 1.0)):
    """電気の火花の粒（明るいノイズの短い弾け）。"""
    def make(rng, t):
        d = rng.uniform(0.002, 0.012)
        x = norm(ffilt(wn(d, rng), hp=rng.uniform(1500, 5000))) * perc(d, 0.0002, d / 3)
        return x * rng.uniform(*amp)
    return make


def decay_dens(tau, t0=0.0):
    return lambda t: np.exp(-np.maximum(t - t0, 0) / tau) * (t >= t0)


def blast(d, rng, pf=1.0, size=1.0, debris=40):
    """爆発の層: 裂ける音・胴鳴り・炎の塊・地鳴り・破片。"""
    sub = thump(d, 105 * pf, 28 * pf, tf=0.07 * size, ta=0.32 * size, h2=0.3)
    crack = burst(0.25, rng, tau=0.012 * size, hp=700)
    body = cn(d, Glp(K((0, 7000), (0.25 * size, 1500), (d, 380)), 2), rng) * perc(d, 0.002, 0.2 * size)
    body = drive(body, 3.0)
    rum = norm(ffilt(wn(d, rng), lp=190, order=3)) * (0.7 + 0.3 * wobble(d, 7, rng)) * perc(d, 0.02, 0.5 * size)
    deb = scatter(d, debris, decay_dens(0.35 * size, 0.04), rng, g_debris())
    return mix(sub * 1.0, crack * 0.85, body * 0.75, rum * 0.7, deb * 0.3)


def clack(rng, pf=1.0, weight=1.0):
    """サーボのカチャッ（部位が噛み合う音）。"""
    return mix(click(rng, 0.012, hp=900) * 0.9,
               metal(0.2, 1250 * pf, PLATE, rng, tau=0.035, bright=0.8) * 0.65,
               thump(0.1, 300 * pf, 120 * pf, tf=0.008, ta=0.022) * 0.7 * weight,
               (0.011, click(rng, 0.01, hp=2500) * 0.4))


def servo(d, f0, f1, rng, level=1.0):
    """サーボのウィーン。"""
    f = K((0, f0), (d, f1))
    x = saw(f, d) * 0.6 + sine(lambda t: f(t) * 2.0, d) * 0.3
    x = ffilt(x, lp=3200, hp=200) * arch(d, 0.8) * (0.8 + 0.2 * lfo(55, d))
    return norm(x) * level


def chord(d, freqs, rng, tau=0.6, a=0.02, shimmer=0.35, vib=0.003, amps=None):
    """揺らめく和音（AM と微小なビブラート）。"""
    out = np.zeros(ns(d))
    amps = amps or [1.0 / (1 + 0.3 * i) for i in range(len(freqs))]
    for f, g in zip(freqs, amps):
        r1, r2 = rng.uniform(4, 9), rng.uniform(5, 13)
        fv = f * (1 + vib * np.sin(TAU * r1 * tt(d) + rng.uniform(0, TAU)))
        out += sine(fv, d, rng.uniform(0, TAU)) * g * lfo(r2, d, shimmer, rng.uniform(0, TAU))
    return out * perc(d, a, tau)


def swell(d, rng, f0, f1, q=1.0, p=3.0):
    """逆再生風に膨らむ帯域ノイズ。"""
    return cn(d, Gbp(K((0, f0), (d, f1)), q), rng) * rise(d, p)


def reversed_hit(d, rng, f0=600.0, t60=1.2):
    """打撃にリバーブを掛けて逆再生した「吸い込み」のスウェル（d 秒の終わりで最大）。"""
    hit = mix(burst(0.3, rng, tau=0.05, hp=400, lp=9000), metal(0.6, f0, BELL, rng, tau=0.3) * 0.5)
    tail = reverb(hit, 1.0, t60=t60, pre=0.0, seed=3)
    tail = fit(tail, d)
    return norm(rev(tail)) * np.minimum((d - tt(d)) / 0.004, 1.0)


# ===========================================================================
#  音色
# ===========================================================================
SOUNDS: dict[str, dict] = {}


def snd(name, variants, cat="player", dist=32.0, vol=1.0, mind=None, dur=None, sat=0.0, fade=0.05, hp=30.0):
    def deco(fn):
        SOUNDS[name] = dict(fn=fn, variants=variants, cat=cat, dist=dist, vol=vol, mind=mind,
                            dur=dur, sat=sat, fade=fade, hp=hp)
        return fn
    return deco


def pv(v, *vals):
    return vals[v % len(vals)]


# ---- 変身 ------------------------------------------------------------------
@snd("core_on", 2, dist=24, vol=0.9, dur=1.5)
def s_core_on(v, rng):
    pf = pv(v, 1.0, 0.92)
    d = 1.15
    f = K((0, 150 * pf), (0.8, 1900 * pf), (d, 2050 * pf))
    fa = ev(f, d)
    whine = fm(fa, 2.0, L((0, 2.4), (d, 0.4)), d) * 0.55 + sine(fa * 0.5, d) * 0.3 + sine(fa * 1.5, d) * 0.08
    e = envp(d, (0, 0), (0.02, 0.35), (0.75, 1.0), (0.97, 0.85), (d, 0))
    whine *= e * lfo(K((0, 7), (d, 34)), d, 0.35)
    synth = supersaw(fa * 0.25, d, rng, 5, 0.01)
    synth = norm(tvf(synth, Gres(K((0, 250), (0.9, 7000), (d, 5000)), 5, 2.5))) * e
    latch = mix(click(rng, 0.01, hp=2000) * 0.8, metal(0.15, 1750 * pf, PLATE, rng, tau=0.03) * 0.5,
                thump(0.3, 150, 50, 0.03, 0.08) * 0.7)
    ready = mix(ping(2637 * pf, 0.12), (0.0, ping(3951 * pf, 0.08) * 0.4))
    x = mix(norm(whine) * 0.75, synth * 0.3, latch * 0.8, (0.88, ready * 0.35))
    return reverb(x, 0.25, t60=0.9, damp=6000)


@snd("core_ring", 2, dist=24, vol=0.8, dur=1.6)
def s_core_ring(v, rng):
    pf = pv(v, 1.0, 1.12)
    d = 1.3
    t = tt(d)
    spin = K((0, 6), (d, 15))
    sp = np.cumsum(ev(spin, d)) / SR * TAU
    out = np.zeros(len(t))
    for i, (r, g) in enumerate(((1, 1.0), (2.01, 0.6), (2.99, 0.45), (4.2, 0.35), (5.43, 0.28), (6.8, 0.2), (8.9, 0.12))):
        f0 = 220 * pf * r
        fv = f0 * (1 + 0.004 * np.sin(sp + i * 0.9))               # 回転のドップラー
        am = 0.6 + 0.4 * np.sin(sp * (1 + i % 3) + i * 1.7)
        out += (sine(fv, d) + 0.7 * sine(fv * 1.003, d)) * g * am
    sheen = cn(d, Gbp(4200 * pf, 6), rng) * (0.5 + 0.5 * np.sin(sp * 2)) * 0.35
    hum = (sine(55 * pf, d) + 0.5 * sine(110 * pf, d)) * 0.3
    e = envp(d, (0, 0), (0.22, 1), (0.95, 0.9), (d, 0))
    deploy = metal(0.9, 1400 * pf, BELL, rng, tau=0.4, bright=0.7)
    x = mix(norm(out) * e * 0.8, sheen * e, hum * e, deploy * 0.3)
    return reverb(x, 0.2, t60=1.0, damp=7000)


@snd("swarm", 3, dist=24, vol=0.85, dur=1.6)
def s_swarm(v, rng):
    d = 1.25
    dens = L((0, 0.1), (0.15, 1.0), (0.95, 1.0), (d, 0.15))
    spin = pv(v, 5.5, 4.2, 7.0)

    def spiral(rng, t):                       # 螺旋を描いて流れる: 粒の音程が周期的にうねりながら上がる
        f = np.exp(rng.uniform(np.log(2200), np.log(7000))) * (1 + 0.5 * t / d) * (1 + 0.25 * np.sin(TAU * spin * t))
        return ping(min(f, NYQ * 0.9), rng.uniform(0.002, 0.012), p0=rng.uniform(0, TAU)) * rng.uniform(0.3, 1.0)
    pings = scatter(d, 420, dens, rng, spiral)
    clicks = scatter(d, 260, dens, rng, g_click(2500, 12000, (0.1, 0.6)))
    chit = scatter(d, 220, dens, rng, g_chitter(1200, 3600))
    flow = cn(d, Gbp(K((0, 700), (d, 3600)), 1.1), rng) * ev(dens, d) * lfo(5.0, d, 0.4)
    hum = sine(K((0, 90), (d, 160)), d) * ev(dens, d) * 0.25
    x = mix(norm(pings) * 0.7, norm(clicks) * 0.5, norm(chit) * 0.55, flow * 0.45, hum)
    x = flanger(x, rate=0.9, lo=0.0005, hi=0.003, mixw=0.6)
    return reverb(x, 0.18, t60=0.7, damp=8000)


@snd("assemble_click", 3, dist=20, vol=0.75, dur=0.4)
def s_assemble_click(v, rng):
    pf = pv(v, 1.0, 0.8, 1.25)
    whir = servo(0.05, 650 * pf, 1150 * pf, rng, 0.25)
    x = mix(whir, (0.04, clack(rng, pf)))
    return reverb(drive(x, 1.8), 0.12, t60=0.35, damp=8000)


@snd("armor_lock", 2, dist=28, vol=0.9, dur=0.95, sat=1.5)
def s_armor_lock(v, rng):
    pf = pv(v, 1.0, 0.88)
    pre = servo(0.09, 420 * pf, 900 * pf, rng, 0.35)
    clamp = mix(thump(0.45, 115 * pf, 45, tf=0.03, ta=0.12) * 1.0,
                metal(0.5, 380 * pf, PLATE, rng, tau=0.12, bright=0.8) * 0.55,
                click(rng, 0.02, hp=800) * 0.8,
                burst(0.12, rng, tau=0.03, bp=1500, q=0.7) * 0.6)
    clamp = drive(clamp, 2.5)
    latch = metal(0.12, 2300 * pf, PLATE, rng, tau=0.02)
    hiss = cn(0.65, Gmul(Ghp(K((0, 7000), (0.65, 4200))), Glp(13000)), rng) * envp(0.65, (0, 0), (0.015, 1), (0.2, 0.55), (0.65, 0))
    x = mix(pre, (0.08, clamp), (0.15, latch * 0.35), (0.17, hiss * 0.4))
    return reverb(x, 0.15, t60=0.6, damp=5000)


@snd("visor_on", 2, dist=20, vol=0.8, dur=0.9)
def s_visor_on(v, rng):
    pf = pv(v, 1.0, 1.06)
    d = 0.42
    sw = supersaw(K((0, 300 * pf), (d, 1250 * pf)), d, rng, 5, 0.008)
    sw = norm(tvf(sw, Gres(K((0, 500), (0.3, 9000), (d, 6000)), 4, 2.0))) * envp(d, (0, 0), (0.18, 1), (d, 0))
    b1 = sqr(2637 * pf, 0.055, 2.5) * envp(0.055, (0, 0), (0.003, 1), (0.045, 0.8), (0.055, 0))
    b2 = sqr(3951 * pf, 0.11, 2.5) * envp(0.11, (0, 0), (0.003, 1), (0.03, 0.7), (0.11, 0))
    spark = scatter(0.35, 40, L((0, 0.2), (0.2, 1), (0.35, 0)), rng, g_ping(6000, 12000, 0.004, 0.02))
    x = mix(sw * 0.55, (0.17, b1 * 0.35), (0.25, b2 * 0.35), (0.1, norm(spark) * 0.25))
    return reverb(echo(x, 0.085, 0.3, 3, 6000), 0.2, t60=0.7, damp=8000)


@snd("transform_burst", 2, dist=48, vol=1.0, mind=4, dur=2.5, sat=1.8, fade=0.3)
def s_transform_burst(v, rng):
    pf = pv(v, 1.0, 0.93)
    t0 = 0.11
    pre = swell(t0, rng, 1500, 9000, 0.8, 3) * 0.6 + sine(K((0, 500), (t0, 1600)), t0) * rise(t0, 4) * 0.25
    impact = mix(thump(1.4, 150 * pf, 30 * pf, tf=0.07, ta=0.5, h2=0.35) * 1.0,
                 burst(0.25, rng, tau=0.025, hp=1200) * 0.8,
                 drive(burst(0.6, rng, tau=0.12, lp=1800, hp=120), 3) * 0.6,
                 fm(K((0, 1400), (0.4, 180)), 1.5, L((0, 8), (0.4, 0)), 0.4) * perc(0.4, 0.001, 0.12) * 0.35,
                 metal(1.6, 410 * pf, BELL, rng, tau=0.7, bright=0.6) * 0.3)
    impact = reverb(impact, 0.3, t60=1.4, hp=200)
    tb = 0.85
    rs = swell(tb - 0.32, rng, 2500, 10000, 0.9, 3) * 0.5 + \
        sine(K((0, 600 * pf), (tb - 0.32, 2400 * pf)), tb - 0.32) * rise(tb - 0.32, 4) * 0.25
    bloom = chord(1.6, [f * pf for f in (1760, 2217, 2637, 3520, 4435, 5274)], rng, tau=0.55, a=0.03)
    spark = scatter(1.6, 110, decay_dens(0.5), rng, g_ping(4000, 12000, 0.005, 0.04))
    air = cn(1.6, Gmul(Ghp(5000), Glp(13000)), rng) * perc(1.6, 0.01, 0.45)
    tail = reverb(mix(norm(bloom) * 0.7, norm(spark) * 0.45, air * 0.3), 0.45, t60=1.8, damp=9000)
    return mix((0, pre * 0.6), (t0, norm(impact)), (0.32, rs * 0.5), (tb, norm(tail) * 0.55))


@snd("weapon_form", 2, dist=24, vol=0.9, dur=1.3)
def s_weapon_form(v, rng):
    pf = pv(v, 1.0, 1.1)
    dm = 0.48
    wob = wobble(dm, 18, rng)
    gloop = sine(180 * pf * (1 + 0.45 * wob) * ev(K((0, 0.8), (dm, 1.6)), dm), dm)
    squelch = tvf(saw(110 * pf * (1 + 0.1 * wob), dm), Gres(lambda t: 500 + 1500 * (0.5 + 0.5 * np.sin(TAU * 9 * t)) * (1 + t * 3), 6, 3))
    bub = fit(scatter(dm, 30, L((0, 0.3), (0.3, 1), (dm, 0.5)), rng, g_bubble(300, 1300, amp=(0.2, 0.7))), dm)
    morph = mix(gloop * 0.5, norm(squelch) * 0.35, norm(bub) * 0.5) * envp(dm, (0, 0), (0.25, 0.8), (dm - 0.04, 1), (dm, 0.3))
    rush = swell(0.14, rng, 2000, 9000, 1.2, 2.5)
    shing = mix(metal(0.8, 2900 * pf, BLADE, rng, tau=0.4, bright=0.6, dpow=0.4) * 0.6,
                click(rng, 0.01, hp=3000) * 0.6,
                cn(0.3, Gbp(K((0, 9000), (0.3, 6000)), 1.6), rng) * perc(0.3, 0.001, 0.07) * 0.5,
                ping(5800 * pf, 0.25) * 0.15)
    x = mix(morph, (dm - 0.14, rush * 0.35), (dm - 0.02, shing))
    return reverb(x, 0.25, t60=1.0, damp=9000)


@snd("revert", 2, dist=24, vol=0.9, dur=1.5)
def s_revert(v, rng):
    pf = pv(v, 1.0, 0.92)
    d = 1.15
    f = K((0, 1700 * pf), (d, 150 * pf))
    whine = (fm(f, 1.0, 1.4, d) * 0.6 + sine(lambda t: f(t) * 0.5, d) * 0.35) * envp(d, (0, 0), (0.03, 1), (0.6, 0.6), (d, 0))
    clanks = mix((0.04, clack(rng, 1.0 * pf)), (0.27, clack(rng, 0.84 * pf) * 0.8), (0.5, clack(rng, 0.7 * pf) * 0.65))
    back = scatter(0.9, 260, L((0, 1), (0.9, 0.05)), rng, g_ping(1800, 7000, 0.002, 0.01, drift=-0.6, dur=0.9))
    hiss = cn(0.55, Gmul(Ghp(3200), Glp(12000)), rng) * perc(0.55, 0.01, 0.15)
    x = mix(norm(whine) * 0.5, clanks * 0.7, norm(back) * 0.35, hiss * 0.3)
    return reverb(x, 0.2, t60=0.9)


@snd("power_down", 2, dist=24, vol=0.9, dur=1.7, fade=0.15)
def s_power_down(v, rng):
    pf = pv(v, 1.0, 0.9)
    d = 1.3
    t = tt(d)
    f = 900 * pf * np.exp(-t * 2.8) + 22
    tone = tvf(saw(f, d) * 0.6 + sine(f * 2, d) * 0.3, Glp(lambda tc: 900 * pf * np.exp(-tc * 2.8) * 6 + 200))
    tone = norm(tone) * np.exp(-t * 1.2) * np.minimum(t / 0.01, 1)
    hum = (sqr(60 * np.exp(-t * 0.8), d, 3) * 0.5 + sine(120 * np.exp(-t * 0.8), d) * 0.4) * np.exp(-t * 2.2)
    fizz = scatter(0.8, 70, decay_dens(0.25, 0.05), rng, g_spark((0.1, 0.6)))
    relay = mix(thump(0.25, 180, 80, 0.02, 0.06), click(rng, 0.01, hp=1200) * 0.6)
    clunk = mix(thump(0.3, 120, 50, 0.02, 0.08), metal(0.3, 260 * pf, PLATE, rng, tau=0.07) * 0.5)
    x = mix(relay * 0.6, (0.02, tone * 0.7), hum * 0.35, (0.05, norm(fizz) * 0.3), (1.08, clunk * 0.55))
    return reverb(x, 0.2, t60=0.8)


# ---- 機動 ------------------------------------------------------------------
@snd("thrust", 3, dist=24, vol=0.8, dur=0.65, sat=1.5)
def s_thrust(v, rng):
    pf = pv(v, 1.0, 0.9, 1.1)
    d = 0.55
    jet = cn(d, Gmul(Glp(K((0, 7500 * pf), (d, 1400 * pf)), 2), Ghp(300)), rng) * perc(d, 0.004, 0.17)
    rum = norm(ffilt(wn(d, rng), lp=260)) * perc(d, 0.004, 0.2)
    pop = mix(click(rng, 0.01, hp=1000), thump(0.15, 200 * pf, 70, 0.015, 0.04) * 0.8)
    whine = sine(K((0, 1500 * pf), (d, 850 * pf)), d) * perc(d, 0.01, 0.12) * 0.12
    return mix(drive(mix(jet * 0.9, rum * 0.7), 2.5), pop * 0.6, whine)


@snd("jump", 3, dist=20, vol=0.7, dur=0.5)
def s_jump(v, rng):
    pf = pv(v, 1.0, 1.08, 0.93)
    d = 0.36
    puff = cn(d, Gbp(K((0, 600 * pf), (d, 2600 * pf)), 0.8), rng) * perc(d, 0.004, 0.08)
    chirp = (sine(K((0, 320 * pf), (0.25, 980 * pf)), 0.25) + 0.35 * sine(K((0, 640 * pf), (0.25, 1960 * pf)), 0.25)) * arch(0.25, 1.5)
    kchk = mix(click(rng, 0.008, hp=1500), metal(0.08, 1600 * pf, PLATE, rng, tau=0.02) * 0.6)
    push = thump(0.15, 130 * pf, 60, 0.02, 0.05)
    return mix(drive(puff, 1.8) * 0.8, chirp * 0.22, kchk * 0.35, push * 0.5)


@snd("boost", 3, dist=32, vol=0.9, dur=0.95, sat=1.6)
def s_boost(v, rng):
    pf = pv(v, 1.0, 0.92, 1.08)
    d = 0.85
    e = envp(d, (0, 0), (0.02, 1), (0.3, 0.75), (d, 0))
    src = cn(d, Gmul(Glp(K((0, 9000 * pf), (d, 1700 * pf)), 2), Ghp(180)), rng)
    roar = flanger(src, rate=1.6, lo=0.0004, hi=0.0035, mixw=0.85) * e
    low = norm(ffilt(wn(d, rng), lp=300)) * e
    ign = mix(burst(0.1, rng, tau=0.01, hp=1000), thump(0.2, 170 * pf, 50, 0.02, 0.06) * 0.9)
    whine = sine(K((0, 1900 * pf), (d, 650 * pf)), d) * e * 0.1
    return mix(drive(mix(norm(roar) * 0.9, low * 0.6), 2.2), ign * 0.6, whine)


@snd("hover", 3, dist=16, vol=0.45, dur=0.6, fade=0.06)
def s_hover(v, rng):
    pf = pv(v, 1.0, 0.94, 1.06)
    d = 0.55
    e = arch(d, 0.9)
    fc = 900 * pf * (1 + 0.15 * wobble(d, 4, rng))
    puff = cn(d, Gbp(lambda t: np.interp(t, tt(d), fc), 0.6), rng)
    turb = 0.75 + 0.25 * wobble(d, 16, rng)
    rum = norm(ffilt(wn(d, rng), lp=300))
    hum = sine(95 * pf, d) + 0.4 * sine(190 * pf, d)
    return mix(puff * turb * e * 0.8, rum * e * 0.45, hum * e * 0.12)


@snd("step", 3, dist=16, vol=0.5, dur=0.3)
def s_step(v, rng):
    pf = pv(v, 1.0, 0.9, 1.1)
    x = mix(thump(0.22, 140 * pf, 60, 0.02, 0.05) * 1.0,
            metal(0.2, 1500 * pf, PLATE, rng, tau=0.03) * 0.3,
            burst(0.08, rng, tau=0.018, lp=2200, hp=300) * 0.5,
            (0.05, servo(0.045, 900 * pf, 1300 * pf, rng, 0.12)))
    return drive(x, 1.6)


@snd("just_dodge", 2, dist=24, vol=0.9, dur=1.6, fade=0.2)
def s_just_dodge(v, rng):
    pf = pv(v, 1.0, 1.06)
    d = 0.7
    wh = cn(d, Gbp(K((0, 6500), (d, 330)), 1.0), rng) * envp(d, (0, 0), (0.02, 1), (0.5, 0.35), (d, 0))
    tape = sine(K((0, 1200 * pf), (d, 140 * pf)), d) * envp(d, (0, 0), (0.02, 1), (d, 0)) * 0.2
    warp = sine(K((0, 72), (0.6, 44)), 0.6) * arch(0.6, 0.8) * 0.35
    chime = mix(metal(1.3, 1568 * pf, BELL, rng, tau=0.6, bright=0.8, spread=0.003) * 0.6,
                ping(3136 * pf, 0.5) * 0.3, ping(4699 * pf, 0.35) * 0.2)
    ch = reverb(echo(chime, 0.11, 0.4, 4, 7000), 0.5, t60=1.6, damp=9000)
    return mix(norm(wh) * 0.6, tape, warp, (0.12, norm(ch) * 0.55))


@snd("land", 3, dist=24, vol=0.8, dur=0.75, sat=1.5)
def s_land(v, rng):
    pf = pv(v, 1.0, 0.9, 1.1)
    hit = mix(thump(0.5, 110 * pf, 38, 0.04, 0.14, h2=0.3) * 1.0,
              burst(0.25, rng, tau=0.05, lp=1200, hp=120) * 0.7,
              metal(0.35, 620 * pf, PLATE, rng, tau=0.07) * 0.35,
              scatter(0.35, 15, decay_dens(0.08, 0.02), rng, g_debris(800, 3500)) * 0.3)
    absorb = servo(0.36, 700 * pf, 380 * pf, rng, 0.16)
    hiss = cn(0.25, Ghp(4500), rng) * perc(0.25, 0.01, 0.06) * 0.15
    return mix(drive(hit, 2.0), (0.08, absorb), (0.12, hiss))


@snd("barrier", 2, dist=24, vol=0.85, dur=1.15)
def s_barrier(v, rng):
    pf = pv(v, 1.0, 1.1)
    d = 0.9
    e = envp(d, (0, 0), (0.05, 1), (0.6, 0.6), (d, 0))
    vw = supersaw(K((0, 70 * pf), (0.25, 140 * pf), (d, 135 * pf)), d, rng, 5, 0.015)
    vw = norm(tvf(vw, Gres(K((0, 200), (0.25, 3500), (d, 1100)), 4, 2.0))) * e
    hum = (sine(120 * pf, d) + 0.5 * sine(240 * pf, d) + 0.25 * sine(360 * pf, d)) * lfo(18, d, 0.35) * e
    cry = chord(d, [2400 * pf, 3600 * pf, 4800 * pf], rng, tau=0.3, a=0.01, shimmer=0.6)
    spark = scatter(0.6, 40, decay_dens(0.25), rng, g_ping(5000, 11000, 0.004, 0.02))
    x = mix(vw * 0.55, norm(hum) * 0.4, norm(cry) * 0.25, norm(spark) * 0.2)
    return reverb(x, 0.25, t60=0.9, damp=8000)


@snd("barrier_hit", 3, dist=24, vol=0.8, dur=0.7)
def s_barrier_hit(v, rng):
    pf = pv(v, 1.0, 1.12, 0.9)
    pingm = norm(modal(0.5, [1900 * pf * r for r in (1, 1.5, 2.3, 3.1)], [1, 0.6, 0.45, 0.3], [0.25, 0.18, 0.12, 0.08], rng))
    zap = fm(K((0, 2400 * pf), (0.12, 600 * pf)), 1.414, 4, 0.12) * perc(0.12, 0.0005, 0.04)
    thoom = thump(0.25, 200 * pf, 90, 0.02, 0.07)
    crk = scatter(0.12, 20, decay_dens(0.04), rng, g_spark((0.2, 0.7)))
    x = mix(pingm * 0.55, zap * 0.4, thoom * 0.5, norm(crk) * 0.3)
    return reverb(echo(x, 0.06, 0.3, 3, 5000), 0.2, t60=0.6, damp=8000)


# ---- 戦闘 ------------------------------------------------------------------
@snd("swing", 3, dist=20, vol=0.7, dur=0.36)
def s_swing(v, rng):
    pf = pv(v, 1.0, 1.1, 0.9)
    d = 0.3
    e = envp(d, (0, 0), (0.09, 1), (d, 0)) ** 1.4
    sw = cn(d, Gbp(K((0, 1500 * pf), (0.11, 5200 * pf), (d, 2400 * pf)), 1.2), rng) * e
    hum = ffilt(saw(K((0, 320 * pf), (0.1, 430 * pf), (d, 250 * pf)), d), lp=2500) * e
    sring = ping(3200 * pf, 0.08, d) * envp(d, (0, 0), (0.07, 0), (0.1, 1), (d, 1))
    return mix(sw * 0.8, norm(hum) * 0.22, sring * 0.07)


@snd("swing_heavy", 3, dist=24, vol=0.8, dur=0.6, sat=1.3)
def s_swing_heavy(v, rng):
    pf = pv(v, 1.0, 0.9, 1.08)
    d = 0.5
    e = envp(d, (0, 0), (0.16, 1), (d, 0)) ** 1.3
    sw = cn(d, Gbp(K((0, 500 * pf), (0.18, 2300 * pf), (d, 900 * pf)), 0.9), rng) * e
    rum = norm(ffilt(wn(d, rng), lp=320)) * e
    hum = ffilt(saw(K((0, 110 * pf), (0.17, 165 * pf), (d, 85 * pf)), d) + 0.5 * sine(K((0, 55 * pf), (0.17, 82 * pf), (d, 42 * pf)), d), lp=1800) * e
    return mix(sw * 0.8, rum * 0.4, norm(hum) * 0.3)


@snd("hit", 3, dist=24, vol=0.85, dur=0.38, sat=2.0)
def s_hit(v, rng):
    pf = pv(v, 1.0, 1.1, 0.9)
    return mix(click(rng, 0.008, hp=2000) * 0.9,
               thump(0.3, 160 * pf, 55, 0.018, 0.06) * 1.0,
               drive(burst(0.12, rng, tau=0.025, bp=2200 * pf, q=0.7), 4) * 0.55,
               fm(3000 * pf, 2.71, L((0, 3), (0.1, 0)), 0.1) * perc(0.1, 0.0005, 0.03) * 0.3)


@snd("hit_heavy", 3, dist=32, vol=0.95, dur=0.75, sat=2.5)
def s_hit_heavy(v, rng):
    pf = pv(v, 1.0, 0.9, 1.1)
    x = mix(thump(0.6, 120 * pf, 38, 0.03, 0.16, h2=0.3) * 1.1,
            drive(burst(0.3, rng, tau=0.06, lp=2500, hp=200), 5) * 0.75,
            click(rng, 0.01, hp=1500) * 0.9,
            scatter(0.3, 14, decay_dens(0.08, 0.02), rng, g_debris()) * 0.3)
    return reverb(x, 0.18, t60=0.7, hp=200)


@snd("hit_metal", 3, dist=28, vol=0.85, dur=0.7)
def s_hit_metal(v, rng):
    pf = pv(v, 1.0, 1.15, 0.87)
    x = mix(metal(0.6, 780 * pf, PLATE, rng, tau=0.18, bright=0.6) * 0.75,
            metal(0.4, 1730 * pf, BAR, rng, tau=0.08) * 0.4,
            click(rng, 0.01, hp=2000) * 0.8,
            thump(0.15, 200 * pf, 100, 0.01, 0.04) * 0.5)
    return reverb(drive(x, 1.5), 0.15, t60=0.6, damp=7000)


@snd("crit", 2, dist=32, vol=1.0, dur=0.95, sat=2.0)
def s_crit(v, rng):
    pf = pv(v, 1.0, 1.08)
    pre = swell(0.05, rng, 3000, 9000, 1.0, 2.5)
    core = mix(thump(0.5, 150 * pf, 42, 0.025, 0.13, h2=0.3), drive(burst(0.25, rng, tau=0.045, lp=3000, hp=250), 4) * 0.7,
               click(rng, 0.01, hp=1800) * 0.9)
    kiin = (sine(3520 * pf * (1 + 0.004 * np.sin(TAU * 7 * tt(0.7))), 0.7) * 0.6 + sine(4693 * pf, 0.7) * 0.35 + sine(7040 * pf, 0.7) * 0.15) * perc(0.7, 0.001, 0.22)
    sh = cn(0.3, Gmul(Ghp(7000), Glp(14000)), rng) * perc(0.3, 0.001, 0.12)
    x = mix(pre * 0.4, (0.05, core), (0.05, kiin * 0.4), (0.05, sh * 0.3))
    return echo(x, 0.07, 0.25, 2, 6000)


@snd("laser", 3, dist=32, vol=0.75, dur=0.6)
def s_laser(v, rng):
    pf = pv(v, 1.0, 1.15, 0.88)
    d = 0.22
    pew = fm(K((0, 2600 * pf), (d, 380 * pf)), 1.5, L((0, 5), (d, 1)), d) * perc(d, 0.002, 0.08)
    zz = cn(0.1, Gbp(4000 * pf, 1.5), rng) * perc(0.1, 0.0005, 0.03)
    x = mix(pew * 0.8, zz * 0.3)
    return echo(x, 0.075, 0.35, 3, 4000)


@snd("beam_charge", 2, dist=32, vol=0.85, dur=1.1, fade=0.04)
def s_beam_charge(v, rng):
    pf = pv(v, 1.0, 0.92)
    d = 1.0
    f = K((0, 180 * pf), (d, 1500 * pf))
    tones = sum(sine(lambda t, k=k: f(t) * k, d) * g for k, g in ((1.0, 0.5), (1.006, 0.4), (2.01, 0.25), (0.5, 0.3)))
    tones *= lfo(K((0, 5), (d, 32)), d, 0.5)
    spark = fit(scatter(d, 160, lambda t: (t / d) ** 2, rng, g_ping(4000, 10000, 0.003, 0.015)), d)
    low = norm(tvf(saw(55 * pf, d), Glp(K((0, 200), (d, 1400))))) * 0.5
    suck = cn(d, Gbp(K((0, 500), (d, 6000)), 2), rng) * 0.4
    x = mix(norm(tones) * 0.6, norm(spark) * 0.3, low, suck) * rise(d, 1.2)
    return x


@snd("beam_fire", 2, dist=48, vol=1.0, mind=4, dur=1.45, sat=2.0, fade=0.15)
def s_beam_fire(v, rng):
    pf = pv(v, 1.0, 0.9)
    d = 1.25
    e = envp(d, (0, 0), (0.01, 1), (0.85, 0.8), (d, 0))
    jit = 1 + 0.02 * wobble(d, 60, rng)
    body = supersaw(55 * pf * jit, d, rng, 5, 0.02) + 0.6 * supersaw(110 * pf * jit, d, rng, 3, 0.015) + 0.3 * saw(165 * pf * jit, d)
    body = ffilt(drive(body, 4), lp=3500) * (0.75 + 0.25 * np.abs(wobble(d, 70, rng)).clip(0, 1.5) / 1.5)
    band = cn(d, Gmul(Gbp(2500, 0.5), Ghp(800)), rng) * lfo(60, d, 0.4)
    siz = cn(d, Ghp(7000), rng) * (0.6 + 0.4 * wobble(d, 30, rng).clip(-1, 1))
    blastx = mix(thump(0.6, 160 * pf, 40, 0.03, 0.18), burst(0.2, rng, tau=0.02, hp=900) * 0.8,
                 fm(K((0, 1800), (0.3, 200)), 1.5, 6, 0.3) * perc(0.3, 0.001, 0.08) * 0.4)
    x = mix(norm(body) * e * 0.6, band * e * 0.45, siz * e * 0.2, blastx * 0.8)
    return reverb(x, 0.2, t60=1.0, hp=200)


@snd("explosion", 3, dist=40, vol=1.0, mind=3, dur=1.5, sat=2.5, fade=0.15)
def s_explosion(v, rng):
    pf = pv(v, 1.0, 0.9, 1.12)
    return reverb(blast(1.2, rng, pf, 1.0, 40), 0.25, t60=1.2, hp=150)


@snd("explosion_big", 2, dist=48, vol=1.0, mind=6, dur=2.8, sat=3.0, fade=0.3)
def s_explosion_big(v, rng):
    pf = pv(v, 1.0, 0.88)
    a = blast(2.4, rng, 0.8 * pf, 2.0, 90)
    b = blast(1.6, rng, 1.1 * pf, 1.2, 30)
    x = mix(a, (0.17, b * 0.7))
    x = echo(x, 0.32, 0.3, 2, 1200)
    return reverb(x, 0.3, t60=2.0, hp=120)


@snd("impact_heavy", 3, dist=40, vol=1.0, mind=3, dur=1.0, sat=2.5)
def s_impact_heavy(v, rng):
    pf = pv(v, 1.0, 0.9, 1.1)
    x = mix(thump(0.9, 100 * pf, 30, 0.05, 0.25, h2=0.35) * 1.3,
            drive(burst(0.4, rng, tau=0.08, lp=1800, hp=120), 4) * 0.8,
            click(rng, 0.012, hp=1200) * 0.8,
            scatter(0.75, 40, decay_dens(0.2, 0.03), rng, g_debris(500, 3500)) * 0.35,
            metal(0.5, 300 * pf, PLATE, rng, tau=0.1) * 0.3)
    return reverb(x, 0.2, t60=0.9, hp=160)


# ---- 惑星の元素 ------------------------------------------------------------
@snd("liquid", 3, dist=24, vol=0.85, dur=1.0)
def s_liquid(v, rng):
    pf = pv(v, 1.0, 0.88, 1.12)
    spl = cn(0.5, Gbp(K((0, 3000 * pf), (0.5, 1200 * pf)), 0.8), rng) * perc(0.5, 0.003, 0.09)
    bub = scatter(0.6, 38, lambda t: np.exp(-t / 0.18), rng, g_bubble(250 * pf, 1400 * pf, (0.012, 0.04), risef=(1.6, 3.0)))
    sheen = metal(0.7, 1100 * pf, BELL, rng, tau=0.25, bright=0.7)
    sheen = flanger(sheen, 2.5, 0.001, 0.004, 0.8)
    bub_m = bub * (0.8 + 0.2 * sine(1700 * pf, len(bub) / SR))           # 金属っぽい揺らぎ
    plop = thump(0.15, 180 * pf, 80, 0.02, 0.04)
    x = mix(spl * 0.55, norm(bub_m) * 0.7, norm(sheen) * 0.22, plop * 0.4)
    return reverb(x, 0.2, t60=0.7, damp=6000)


@snd("zap", 3, dist=24, vol=0.8, dur=0.6)
def s_zap(v, rng):
    pf = pv(v, 1.0, 1.12, 0.9)
    d = 0.48
    dens = lambda t: np.exp(-t / 0.15)  # noqa: E731
    sparks = scatter(d, 180, dens, rng, g_spark())
    gate = np.abs(ffilt(np.abs(sparks[:ns(d)]), lp=120))
    gate = norm(gate)
    buzz = drive(sqr(120 * pf * (1 + 0.03 * wobble(d, 30, rng)), d, 4) + 0.6 * saw(240 * pf, d), 5)
    buzz = ffilt(buzz, lp=5000) * gate
    siz = cn(d, Ghp(6000), rng) * perc(d, 0.002, 0.12)
    x = mix(norm(sparks) * 0.7, buzz * 0.45, siz * 0.25, click(rng, 0.008, hp=2000) * 0.6)
    return x


@snd("thunder", 2, dist=64, vol=1.0, mind=8, dur=2.3, sat=2.0, fade=0.3)
def s_thunder(v, rng):
    pf = pv(v, 1.0, 0.85)
    d = 2.1
    crack = mix(burst(0.3, rng, tau=0.02, hp=500), drive(cn(0.4, Ghp(300), rng) * perc(0.4, 0.001, 0.08), 3) * 0.7)
    lead = mix(*[(t, click(rng, 0.02, hp=800, tau=0.004) * g) for t, g in ((0.0, 0.6), (0.045, 0.75), (0.08, 0.9), (0.105, 1.0))])
    roll_env = envp(d, (0, 0), (0.1, 0.6), (0.4, 1), (d, 0)) ** 1.2
    bursts = 0.55 + 0.45 * np.clip(wobble(d, 5, rng), -1, 1.5) / 1.5
    roll = norm(ffilt(wn(d, rng), lp=420 * pf, order=2)) * roll_env * bursts
    sub = norm(ffilt(wn(d, rng), lp=110, order=3)) * roll_env
    siz = cn(0.6, Ghp(5000), rng) * perc(0.6, 0.002, 0.15) * norm(np.abs(ffilt(wn(0.6, rng), lp=80)))
    x = mix(lead * 0.5, (0.11, crack), (0.1, roll * 0.8), (0.1, sub * 0.7), (0.11, siz * 0.3))
    return reverb(x, 0.3, t60=1.8, hp=100)


@snd("ice_crack", 3, dist=24, vol=0.8, dur=0.7)
def s_ice_crack(v, rng):
    pf = pv(v, 1.0, 1.1, 0.9)

    def crk(rng, t):
        fs = rng.uniform(2800, 7500, 3) * pf
        x = mix(click(rng, 0.01, hp=2500, tau=0.0008), norm(modal(0.08, fs, [1, 0.6, 0.4], rng.uniform(0.01, 0.04, 3), rng)) * 0.6)
        return x * rng.uniform(0.2, 0.9) * np.exp(-t / 0.2)
    micro = scatter(0.38, 11, L((0, 1), (0.38, 0.3)), rng, crk)
    snap = mix(click(rng, 0.012, hp=2500), metal(0.2, 3300 * pf, PLATE, rng, tau=0.03) * 0.7)
    creak = sine(K((0.0, 1800 * pf), (0.2, 900 * pf)) , 0.2) * (1 + 0.5 * wobble(0.2, 200, rng)) * arch(0.2, 1)
    thunk = thump(0.12, 300 * pf, 150, 0.01, 0.03)
    x = mix(snap, (0.02, norm(micro) * 0.7), (0.05, creak * 0.1), thunk * 0.3)
    return reverb(x, 0.15, t60=0.5, damp=10000)


@snd("ice_shatter", 2, dist=32, vol=0.9, dur=1.3)
def s_ice_shatter(v, rng):
    pf = pv(v, 1.0, 0.92)
    hit = mix(click(rng, 0.015, hp=1500), burst(0.15, rng, tau=0.03, hp=1500) * 0.8, thump(0.15, 220 * pf, 90, 0.01, 0.04) * 0.6)

    def shard(rng, t):
        f0 = rng.uniform(3000, 10500) * pf
        x = modal(0.25, [f0, f0 * rng.uniform(1.3, 1.9), f0 * rng.uniform(2.1, 2.9)], [1, 0.5, 0.3], [rng.uniform(0.02, 0.12)] * 3, rng)
        return x * rng.uniform(0.15, 1.0)
    tink = scatter(1.0, 130, lambda t: np.exp(-t / 0.22) + 0.15 * np.exp(-((t - 0.45) / 0.12) ** 2), rng, shard)
    sus = cn(1.0, Gbp(8000, 1.0), rng) * perc(1.0, 0.002, 0.25)
    x = mix(hit * 0.8, norm(tink) * 0.65, sus * 0.25)
    return reverb(x, 0.3, t60=1.2, damp=10000)


@snd("wind", 3, dist=32, vol=0.8, dur=1.4, fade=0.12)
def s_wind(v, rng):
    pf = pv(v, 1.0, 0.86, 1.14)
    d = 1.25
    fc = K((0, 500 * pf), (0.4, 1400 * pf), (0.9, 900 * pf), (d, 1700 * pf))
    howl = cn(d, Gbp(fc, 6), rng) * 0.6 + cn(d, Gbp(lambda t: fc(t) * 1.9, 8), rng) * 0.3
    broad = cn(d, Gmul(Glp(3200), Ghp(250)), rng) * (0.7 + 0.3 * wobble(d, 6, rng).clip(-1, 1))
    low = norm(ffilt(wn(d, rng), lp=200))
    e = envp(d, (0, 0), (0.12, 0.8), (0.5, 1), (d, 0))
    x = mix(howl * 0.7, broad * 0.5, low * 0.4) * e
    return flanger(x, 0.6, 0.0005, 0.004, 0.5)


@snd("gust", 3, dist=32, vol=0.85, dur=0.75, sat=1.5)
def s_gust(v, rng):
    pf = pv(v, 1.0, 0.9, 1.1)
    n = ns(0.009)
    nwave = np.linspace(1, -1, n)
    nwave = ffilt(np.concatenate([nwave, np.zeros(ns(0.05))]), lp=6000)
    boom = mix(nwave, (0.02, nwave * 0.6), thump(0.25, 90 * pf, 40, 0.02, 0.07) * 0.8)
    d = 0.6
    g = cn(d, Gbp(K((0, 700 * pf), (0.15, 3500 * pf), (d, 800 * pf)), 0.9), rng) * envp(d, (0, 0), (0.02, 0.6), (0.1, 1), (d, 0))
    wh = cn(d, Gbp(K((0, 2400 * pf), (d, 1500 * pf)), 7), rng) * arch(d, 1.5)
    return mix(norm(boom) * 0.8, g * 0.8, wh * 0.2)


@snd("water_wave", 2, dist=32, vol=0.9, dur=1.8, fade=0.2)
def s_water_wave(v, rng):
    pf = pv(v, 1.0, 0.9)
    sw = cn(0.5, Glp(K((0, 300), (0.5, 2500 * pf))), rng) * rise(0.5, 2.0)
    crash = cn(0.9, Gmul(Glp(7000), Ghp(150)), rng) * perc(0.9, 0.02, 0.35)
    thud = thump(0.5, 90 * pf, 40, 0.04, 0.12)
    foam = cn(1.1, Gbp(4000 * pf, 0.6), rng) * perc(1.1, 0.05, 0.45) * (0.7 + 0.3 * wobble(1.1, 40, rng).clip(-1, 1))
    bub = scatter(0.9, 34, L((0, 1), (0.9, 0.2)), rng, g_bubble(900, 3200, (0.004, 0.015), (0.1, 0.5)))
    x = mix(sw * 0.6, (0.48, crash), (0.48, thud * 0.6), (0.6, foam * 0.5), (0.65, norm(bub) * 0.3))
    return reverb(x, 0.25, t60=1.0)


@snd("splash", 3, dist=24, vol=0.8, dur=0.75)
def s_splash(v, rng):
    pf = pv(v, 1.0, 1.1, 0.9)
    bloop = sine(K((0, 220 * pf), (0.06, 700 * pf)), 0.06) * perc(0.06, 0.001, 0.025)
    spray = cn(0.5, Gbp(2500 * pf, 0.7), rng) * perc(0.5, 0.005, 0.12)
    drops = scatter(0.5, 22, decay_dens(0.2, 0.04), rng, g_bubble(800 * pf, 3000 * pf, (0.004, 0.012), (0.2, 0.7)))
    x = mix(bloop * 0.6, spray * 0.7, thump(0.12, 150 * pf, 70, 0.015, 0.03) * 0.4, norm(drops) * 0.45)
    return reverb(x, 0.18, t60=0.6)


@snd("gravity", 2, dist=40, vol=1.0, dur=1.75, sat=1.5, fade=0.2)
def s_gravity(v, rng):
    pf = pv(v, 1.0, 0.88)
    d = 1.55
    t = tt(d)
    bend = ev(K((0, 1.15), (d, 0.82)), d)
    throb = (0.5 + 0.5 * np.sin(TAU * 4.5 * t - np.pi / 2)) ** 2
    sub = sine(48 * pf * bend, d) + sine(49.5 * pf * bend, d) + 0.3 * sine(96 * pf * bend, d)
    sub = drive(sub, 2.0) * (0.35 + 0.65 * throb)
    wub = tvf(saw(96 * pf * bend, d), Glp(lambda tc: 200 + 700 * (0.5 + 0.5 * np.sin(TAU * 4.5 * tc - np.pi / 2)) ** 2, 3))
    dark = norm(ffilt(wn(d, rng), lp=350)) * (0.4 + 0.6 * throb)
    suck = cn(d, Gbp(K((0, 200), (d, 1300)), 3), rng) * rise(d, 2)
    e = envp(d, (0, 0), (0.1, 1), (d - 0.3, 1), (d, 0))
    return mix(sub * 0.8, norm(wub) * 0.45, dark * 0.35, suck * 0.3) * e


@snd("ring_spin", 3, dist=32, vol=0.85, dur=1.2, sat=1.5, fade=0.1)
def s_ring_spin(v, rng):
    pf = pv(v, 1.0, 0.9, 1.12)
    d = 1.05
    f = K((0, 180 * pf), (0.15, 420 * pf), (d, 380 * pf))
    bz = saw(f, d) + saw(lambda t: f(t) * 1.007, d) * 0.8
    bz = tvf(bz, Gbp(lambda tc: 2600 + 1300 * np.sin(TAU * 12 * tc), 1.2))
    bz = ffilt(bz, peaks=[(2300, 3, 6), (3700, 2.5, 6)]) * lfo(22, d, 0.4)
    ringm = norm(modal(d, [f0 * pf for f0 in (1210, 1930, 2780, 3640)], [1, 0.7, 0.5, 0.35], [2, 2, 2, 2], rng)) * lfo(12, d, 0.6)
    wh = cn(d, Gbp(1200 * pf, 1.5), rng) * lfo(12, d, 0.6)
    e = envp(d, (0, 0), (0.08, 1), (d - 0.25, 0.9), (d, 0))
    return mix(drive(bz, 2) * 0.55, ringm * 0.2, wh * 0.35) * e


@snd("clock_tick", 3, dist=24, vol=0.7, dur=0.35)
def s_clock_tick(v, rng):
    pf = pv(v, 1.0, 0.72, 1.12)
    tk = mix(click(rng, 0.006, hp=3000, tau=0.0006),
             norm(modal(0.1, [3200 * pf, 4870 * pf, 6900 * pf], [1, 0.6, 0.4], [0.03, 0.02, 0.015], rng)) * 0.6,
             (0.012, click(rng, 0.006, hp=3500, tau=0.0005) * 0.45),
             thump(0.05, 900 * pf, 500 * pf, 0.005, 0.01) * 0.3)
    return reverb(echo(tk, 0.06, 0.2, 2, 6000), 0.15, t60=0.4, damp=9000)


@snd("time_stop", 2, dist=48, vol=1.0, mind=4, dur=2.6, fade=0.35)
def s_time_stop(v, rng):
    pf = pv(v, 1.0, 0.92)
    ticks = []
    for i, (t, g) in enumerate(((0.0, 0.5), (0.22, 0.6), (0.4, 0.7), (0.54, 0.8), (0.64, 0.9))):
        q = pf * (1.0 if i % 2 == 0 else 0.74)
        ticks.append((t, mix(click(rng, 0.006, hp=3000, tau=0.0006),
                             norm(modal(0.12, [3200 * q, 4870 * q, 6900 * q], [1, 0.6, 0.4], [0.04, 0.03, 0.02], rng)) * 0.6) * g))
    tk = reverb(mix(*ticks), 0.2, t60=0.8, damp=8000)
    tf_ = 1.25
    rs = reversed_hit(0.8, rng, 520 * pf, t60=1.3)
    up = swell(0.8, rng, 300, 5000, 1.5, 3)
    freeze = mix(thump(1.2, 70 * pf, 30, 0.05, 0.5, h2=0.3),
                 metal(1.2, 110 * pf, BELL, rng, tau=1.0, bright=0.5) * 0.6,
                 burst(0.2, rng, tau=0.03, hp=400) * 0.4)
    drone = chord(1.15, [1318 * pf, 1975 * pf, 2637 * pf, 1322 * pf], rng, tau=0.7, a=0.08, shimmer=0.3, vib=0.001)
    tail = reverb(mix(drive(freeze, 2) * 0.9, (0.0, norm(drone) * 0.35)), 0.4, t60=2.0, damp=6000)
    return mix(tk * 0.7, (tf_ - 0.8, rs * 0.55), (tf_ - 0.8, up * 0.3), (tf_, norm(tail)))


@snd("flare", 3, dist=32, vol=0.9, dur=1.1, sat=1.8)
def s_flare(v, rng):
    pf = pv(v, 1.0, 0.9, 1.1)
    d = 0.95
    roar = cn(d, Glp(K((0, 600 * pf), (0.15, 4500 * pf), (d, 1200 * pf)), 2), rng) * perc(d, 0.03, 0.3)
    low = norm(ffilt(wn(d, rng), lp=250)) * perc(d, 0.02, 0.3)
    pops = scatter(d, 30, decay_dens(0.35, 0.03), rng, g_debris(1000, 4000, (0.1, 0.6)))
    plasma = fm(K((0, 400 * pf), (d, 900 * pf)), 2, L((0, 4), (d, 1)), d) * envp(d, (0, 0), (0.1, 1), (d, 0))
    return mix(drive(mix(roar, low * 0.7), 2.2) * 0.8, norm(pops) * 0.3, plasma * 0.18)


@snd("corona", 2, dist=32, vol=0.85, dur=1.8, fade=0.2)
def s_corona(v, rng):
    pf = pv(v, 1.0, 1.12)
    d = 1.55
    dr = chord(d, [220 * pf * r for r in (1, 1.5, 2, 3, 4.01, 5.04, 6)], rng, tau=10, a=0.3, shimmer=0.5, vib=0.004)
    e = envp(d, (0, 0), (0.3, 1), (d - 0.35, 0.85), (d, 0))
    siz = cn(d, Ghp(4000), rng) * (0.5 + 0.5 * wobble(d, 25, rng).clip(-1, 1))
    crk = scatter(d, 60, L((0, 0.3), (0.4, 1), (d, 0.4)), rng, g_spark((0.1, 0.5)))
    low = norm(ffilt(wn(d, rng), lp=300))
    x = mix(norm(dr) * 0.55 * e, siz * 0.22 * e, norm(crk) * 0.25, low * 0.3 * e)
    return reverb(x, 0.3, t60=1.4, damp=7000)


@snd("supernova", 2, dist=64, vol=1.0, mind=8, dur=3.7, sat=3.0, fade=0.4)
def s_supernova(v, rng):
    pf = pv(v, 1.0, 0.9)
    di = 1.6
    t = tt(di)
    imp_rev = reversed_hit(di, rng, 300 * pf, t60=1.6)
    f = K((0, 80 * pf), (di, 1200 * pf))
    tones = sum(fm(lambda tt_, k=k: f(tt_) * k, 1.5, L((0, 0.5), (di, 3)), di) * g for k, g in ((1, 0.5), (1.5, 0.35), (2.01, 0.25)))
    spark = fit(scatter(di, 220, lambda tt_: (tt_ / di) ** 3, rng, g_ping(3000, 11000, 0.003, 0.012)), di)
    suck = cn(di, Gbp(K((0, 200), (di, 8000)), 1.5), rng)
    rate = np.cumsum(2 + 18 * (t / di) ** 2) / SR
    sub = sine(K((0, 30), (di, 62)), di) * (0.5 + 0.5 * np.sin(TAU * rate))
    implosion = mix(imp_rev * 0.5, norm(tones) * 0.35, norm(spark) * 0.3, suck * 0.4, sub * 0.4) * rise(di, 2.2)
    implosion *= np.minimum((di - t) / 0.01, 1.0)
    big = blast(2.0, rng, 1.5 * pf, 2.2, 100)
    shine = chord(1.8, [f0 * pf for f0 in (880, 1320, 1760, 2640, 3520)], rng, tau=0.6, a=0.02)
    exp_ = mix(norm(big), norm(shine) * 0.2)
    exp_ = reverb(echo(exp_, 0.28, 0.25, 2, 1500), 0.3, t60=2.0, hp=120)
    return mix(implosion * 0.7, (di + 0.06, norm(exp_)))


@snd("meteor", 2, dist=48, vol=1.0, mind=6, dur=2.5, sat=2.5, fade=0.3)
def s_meteor(v, rng):
    pf = pv(v, 1.0, 0.9)
    di = 1.15
    roar = cn(di, Gbp(K((0, 400 * pf), (di, 2200 * pf)), 0.7), rng) * rise(di, 2.5)
    rum = norm(ffilt(wn(di, rng), lp=260)) * rise(di, 2)
    burn = fit(scatter(di, 70, lambda t: (t / di) ** 2, rng, g_debris(1000, 5000, (0.1, 0.5))), di)
    whistle = sine(K((0, 2400 * pf), (di, 800 * pf)), di) * rise(di, 1.5) * 0.12
    incoming = mix(drive(mix(roar, rum * 0.6), 1.8) * 0.8, norm(burn) * 0.25, whistle)
    incoming *= np.minimum((di - tt(di)) / 0.02, 1.0)
    hit = reverb(blast(1.3, rng, 0.9 * pf, 1.3, 60), 0.28, t60=1.4, hp=140)
    return mix(incoming * 0.75, (di, norm(hit)))


# ---- UI ---------------------------------------------------------------------
@snd("cutin", 2, dist=48, vol=1.0, mind=4, dur=1.6, sat=2.0, fade=0.25)
def s_cutin(v, rng):
    pf = pv(v, 1.0, 1.06)
    t0 = 0.1
    win = swell(t0, rng, 1000, 8000, 1.0, 2.5)
    ring = norm(modal(1.0, [2800 * pf * r for r in (1, 1.33, 1.5, 2.0, 2.67)], [1, 0.6, 0.5, 0.4, 0.3], [0.5, 0.4, 0.35, 0.3, 0.2], rng))
    bright = burst(0.15, rng, tau=0.05, hp=5000)
    notes = [146.8, 220.0, 293.7, 440.0, 587.3]
    stab = sum(supersaw(n * pf, 0.9, rng, 3, 0.01) for n in notes)
    stab = norm(tvf(stab, Glp(K((0, 8000), (0.9, 1000)), 2))) * perc(0.9, 0.004, 0.3)
    boom = thump(1.0, 90 * pf, 35, 0.05, 0.4)
    hit = mix(ring * 0.4, bright * 0.5, click(rng, 0.01, hp=2000) * 0.7, stab * 0.5, boom * 0.8)
    return mix(win * 0.4, (t0, reverb(hit, 0.35, t60=1.5, hp=180)))


@snd("ui_open", 2, cat="ui", dist=16, vol=0.6, dur=0.5)
def s_ui_open(v, rng):
    pf = pv(v, 1.0, 1.12)

    def blip(f0, f1, d):
        return (sqr(K((0, f0), (d, f1)), d, 1.6) * 0.7 + sine(K((0, f0 * 2), (d, f1 * 2)), d) * 0.2) * envp(d, (0, 0), (0.003, 1), (d * 0.6, 0.7), (d, 0))
    wh = cn(0.18, Gbp(K((0, 2000), (0.18, 6500)), 1.2), rng) * arch(0.18, 1.5)
    x = mix(blip(880 * pf, 900 * pf, 0.06), (0.06, blip(1320 * pf, 1360 * pf, 0.09)), wh * 0.2)
    return reverb(echo(x, 0.07, 0.25, 2, 6000), 0.12, t60=0.4, damp=9000)


@snd("ui_select", 3, cat="ui", dist=16, vol=0.5, dur=0.2)
def s_ui_select(v, rng):
    pf = pv(v, 1.0, 1.12, 0.89)
    d = 0.08
    b = sine(K((0, 2400 * pf), (d, 1800 * pf)), d) * perc(d, 0.001, 0.025) + 0.2 * sine(K((0, 4800 * pf), (d, 3600 * pf)), d) * perc(d, 0.001, 0.015)
    return mix(b, click(rng, 0.004, hp=4000, tau=0.0004) * 0.25)


@snd("ui_back", 2, cat="ui", dist=16, vol=0.55, dur=0.35)
def s_ui_back(v, rng):
    pf = pv(v, 1.0, 0.9)

    def blip(f0, f1, d):
        return sqr(K((0, f0), (d, f1)), d, 1.4) * envp(d, (0, 0), (0.003, 1), (d * 0.5, 0.6), (d, 0))
    x = mix(blip(1320 * pf, 1250 * pf, 0.06), (0.07, blip(880 * pf, 780 * pf, 0.09)))
    return reverb(x, 0.12, t60=0.35, damp=8000)


@snd("alert", 2, dist=24, vol=0.7, dur=0.75)
def s_alert(v, rng):
    pf = pv(v, 1.0, 1.0)
    pulses = ((0.0, 0.25), (0.32, 0.25)) if v == 0 else ((0.0, 0.14), (0.19, 0.14), (0.38, 0.14))
    out = []
    for t0, d in pulses:
        f = K((0, 700 * pf), (d, 920 * pf))
        x = saw(f, d) * 0.5 + sqr(f, d, 3) * 0.5 + 0.3 * sqr(lambda t: f(t) * 1.5, d, 3)
        x = ffilt(drive(x, 2.5), lp=4000) * envp(d, (0, 0), (0.01, 1), (d - 0.015, 1), (d, 0))
        out.append((t0, x))
    return reverb(mix(*out), 0.12, t60=0.4)


@snd("overheat", 2, dist=24, vol=0.85, dur=1.65, fade=0.2)
def s_overheat(v, rng):
    pf = pv(v, 1.0, 1.06)
    beeps = []
    for i in range(6):
        f = (1760 if i % 2 == 0 else 1320) * pf
        beeps.append((i * 0.125, sqr(f, 0.08, 2.5) * envp(0.08, (0, 0), (0.003, 1), (0.07, 0.8), (0.08, 0))))
    alarm = mix(*beeps)
    d = 1.4
    hiss = cn(d, Gmul(Ghp(2500), Gbp(6000, 0.5)), rng) * envp(d, (0, 0), (0.02, 1), (0.3, 0.8), (d, 0)) ** 1.3
    pings = scatter(1.2, 5, L((0, 1), (1.2, 1)), rng, g_ping(2500, 5000, 0.05, 0.15, (0.3, 0.7)))
    sag = saw(K((0, 80), (d, 50)), d) * perc(d, 0.01, 0.5)
    x = mix(alarm * 0.45, (0.05, hiss * 0.6), (0.1, norm(pings) * 0.2), (0.0, norm(ffilt(sag, lp=900)) * 0.2))
    return reverb(x, 0.15, t60=0.6)


@snd("sync_up", 2, dist=24, vol=0.8, dur=1.6, fade=0.2)
def s_sync_up(v, rng):
    pf = pv(v, 1.0, 1.122)
    notes = (1046.5, 1318.5, 1568.0, 2093.0, 2637.0, 3136.0)
    arp = []
    for i, n in enumerate(notes):
        d = 0.5
        b = fm(n * pf, 2.0, L((0, 2.5), (d, 0.2)), d) * perc(d, 0.002, 0.18) * (0.7 + 0.06 * i)
        arp.append((i * 0.07, b))
    fin = chord(1.0, [n * pf for n in (1046.5, 1568.0, 2093.0, 2637.0)], rng, tau=0.5, a=0.01, shimmer=0.4)
    spark = scatter(0.9, 50, decay_dens(0.35), rng, g_ping(5000, 11000, 0.004, 0.02))
    x = mix(*arp, (0.42, norm(fin) * 0.5), (0.4, norm(spark) * 0.2))
    return reverb(echo(x, 0.11, 0.3, 3, 7000), 0.35, t60=1.4, damp=9000)


# ---- 敵 ---------------------------------------------------------------------
@snd("drone_hum", 2, cat="hostile", dist=24, vol=0.55, dur=1.15, fade=0.1)
def s_drone_hum(v, rng):
    pf = pv(v, 1.0, 1.12)
    d = 1.05
    war = 1 + 0.02 * np.sin(TAU * 5 * tt(d))
    bz = saw(110 * pf * war, d) + saw(110 * pf * 1.013 * war, d) + 0.3 * sqr(55 * pf * war, d, 3)
    bz = ffilt(bz, lp=1800) * lfo(38, d, 0.25)
    wh = sine(880 * pf * war * (1 + 0.01 * wobble(d, 3, rng)), d) * 0.08
    air = cn(d, Gbp(700, 0.8), rng) * lfo(38, d, 0.4) * 0.2
    e = envp(d, (0, 0), (0.15, 1), (d - 0.25, 1), (d, 0))
    return mix(norm(bz) * 0.6, wh, air) * e


@snd("drone_laser", 3, cat="hostile", dist=32, vol=0.8, dur=0.65)
def s_drone_laser(v, rng):
    pf = pv(v, 1.0, 0.88, 1.1)
    d = 0.3
    z = fm(K((0, 1500 * pf), (d, 220 * pf)), 0.51, L((0, 6), (d, 2)), d) * sine(330 * pf, d) * perc(d, 0.002, 0.1)
    z = mix(drive(z, 2), cn(0.12, Gbp(2500 * pf, 1.2), rng) * perc(0.12, 0.0005, 0.03) * 0.3)
    return echo(z, 0.09, 0.35, 3, 2500)


@snd("sentinel_step", 3, cat="hostile", dist=24, vol=0.8, dur=0.45, sat=1.5)
def s_sentinel_step(v, rng):
    pf = pv(v, 1.0, 0.9, 1.08)
    x = mix(thump(0.35, 90 * pf, 32, 0.03, 0.12, h2=0.35) * 1.2,
            metal(0.3, 330 * pf, PLATE, rng, tau=0.08) * 0.4,
            burst(0.1, rng, tau=0.02, lp=1800, hp=150) * 0.5,
            (0.03, cn(0.2, Ghp(3000), rng) * perc(0.2, 0.005, 0.06) * 0.25),
            (0.05, servo(0.2, 300 * pf, 200 * pf, rng, 0.12)))
    return drive(x, 2.0)


@snd("sentinel_slam", 2, cat="hostile", dist=48, vol=1.0, mind=4, dur=1.3, sat=3.0, fade=0.15)
def s_sentinel_slam(v, rng):
    pf = pv(v, 1.0, 0.9)
    x = mix(thump(1.0, 80 * pf, 26, 0.05, 0.35, h2=0.4) * 1.3,
            drive(burst(0.4, rng, tau=0.08, lp=2000, hp=120), 4) * 0.8,
            click(rng, 0.015, hp=1000) * 0.9,
            cn(0.7, Gbp(K((0, 2000), (0.7, 300)), 0.8), rng) * perc(0.7, 0.01, 0.25) * 0.6,
            scatter(0.9, 45, decay_dens(0.25, 0.03), rng, g_debris(400, 3000)) * 0.35,
            metal(0.6, 220 * pf, PLATE, rng, tau=0.15) * 0.3)
    return reverb(x, 0.25, t60=1.3, hp=150)


@snd("nemesis_roar", 2, cat="hostile", dist=64, vol=1.0, mind=8, dur=2.4, sat=2.5, fade=0.3)
def s_nemesis_roar(v, rng):
    pf = pv(v, 1.0, 0.88)
    d = 2.0
    jit = 1 + 0.04 * wobble(d, 28, rng)
    f0 = ev(K((0, 70 * pf), (0.3, 96 * pf), (1.4, 86 * pf), (d, 52 * pf)), d) * jit
    src = saw(f0, d) + 0.7 * saw(f0 * 1.006, d) + 0.4 * sqr(f0 / 2, d, 3)
    src = src * (0.75 + 0.25 * sine(f0 * 1.41, d))                       # リング変調で機械っぽく
    vox = tvf(src, Gform([K((0, 700), (d, 380)), K((0, 1150), (d, 780)), K((0, 2600), (d, 2350))], q=5, floor=0.08, gains=[1, 0.7, 0.4]))
    screech = fm(2400 * pf * jit, 1.41, 2.0, d) * 0.5
    screech = flanger(screech, 0.7, 0.001, 0.006, 0.8)
    breath = cn(d, Gbp(1500, 0.6), rng)
    e = envp(d, (0, 0), (0.15, 0.9), (0.4, 1), (1.4, 0.8), (d, 0))
    x = mix(drive(norm(vox), 3) * 0.75, norm(screech) * 0.12, breath * 0.25) * e
    sub = sine(f0 / 2, d) * e * 0.35
    return reverb(mix(x, sub), 0.35, t60=1.6, hp=150)


@snd("nemesis_charge", 2, cat="hostile", dist=48, vol=1.0, mind=4, dur=1.35, fade=0.05)
def s_nemesis_charge(v, rng):
    pf = pv(v, 1.0, 0.9)
    d = 1.25
    a = saw(K((0, 55 * pf), (d, 220 * pf)), d) + saw(K((0, 77.8 * pf), (d, 311 * pf)), d)
    a = drive(tvf(a, Glp(K((0, 200), (d, 5000)), 2)), 2.5)
    suck = cn(d, Gbp(K((0, 300), (d, 4000)), 2), rng) * rise(d, 2.5)
    crk = fit(scatter(d, 90, lambda t: (t / d) ** 2, rng, g_debris(300, 2500, (0.1, 0.6))), d)
    t = tt(d)
    rate = np.cumsum(3 + 15 * (t / d) ** 2) / SR
    sub = sine(K((0, 40), (d, 70)), d) * (0.5 + 0.5 * np.sin(TAU * rate))
    return mix(a * 0.5, suck * 0.45, norm(crk) * 0.25, sub * 0.5) * rise(d, 1.3)


@snd("nemesis_spawn", 2, cat="hostile", dist=64, vol=1.0, mind=8, dur=3.3, sat=2.0, fade=0.4)
def s_nemesis_spawn(v, rng):
    pf = pv(v, 1.0, 0.9)
    d = 3.0
    f = K((0, 110 * pf), (d, 38 * pf))
    dr = sum(saw(lambda t, r=r: f(t) * r, d, rng.random()) * g for r, g in ((1, 1), (1.006, 0.8), (1.5, 0.5), (1.189, 0.4), (2.0, 0.3)))
    dr = drive(tvf(dr, Glp(K((0, 3000), (d, 380)), 2)), 2.0) * lfo(0.7, d, 0.3)
    rs = reversed_hit(0.9, rng, 200 * pf, t60=1.6)
    boom = thump(2.0, 60 * pf, 22, 0.1, 0.9, h2=0.4)
    rum = norm(ffilt(wn(d, rng), lp=120, order=3)) * (0.7 + 0.3 * wobble(d, 2, rng).clip(-1, 1))
    groan = []
    for t0 in (1.3, 2.1):
        g = metal(0.9, 95 * pf, PLATE, rng, tau=0.6, bright=0.4)
        g = vdelay(g, np.linspace(0, 0.03, len(g)))                        # ゆっくり伸びてピッチが落ちる
        groan.append((t0, g * 0.25))
    e = envp(d, (0, 0), (0.3, 0.7), (0.9, 1), (d - 0.6, 0.8), (d, 0))
    x = mix(dr * 0.5 * e, rs * 0.5, (0.9, boom * 0.9), rum * 0.4 * e, *groan)
    return reverb(x, 0.4, t60=2.4, hp=120)


# ===========================================================================
#  書き出し
# ===========================================================================
def master(x, spec):
    x = np.asarray(x, float)
    if spec["dur"]:
        x = fit(x, spec["dur"])
    x = ffilt(x, hp=spec["hp"], lp=16500, order=2)           # 直流と超低域、Vorbis が削る超高域を先に切る
    # 末尾の無音を詰める（-66 dB 以下）
    blk = 256
    nb = len(x) // blk
    if nb > 4:
        lv = np.abs(x[:nb * blk]).reshape(nb, blk).max(axis=1)
        above = np.nonzero(lv > np.max(lv) * 10 ** (-66 / 20))[0]
        if len(above):
            x = x[:min(len(x), (above[-1] + 2) * blk)]
    x = norm(x)
    if spec["sat"] > 0:
        k = spec["sat"]
        x = np.tanh(k * x) / np.tanh(k)
    fi = ns(0.0012)
    fo = min(ns(spec["fade"]), len(x) // 3)
    x[:fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
    x[len(x) - fo:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo)
    x -= np.mean(x) * np.hanning(len(x)) / np.mean(np.hanning(len(x)))   # 残った直流を端を動かさずに消す
    return norm(x, 10 ** (PEAK_DB / 20))


def render(name, v):
    spec = SOUNDS[name]
    rng = np.random.default_rng(zlib.crc32(f"{NS}.{name}:{v}".encode()))
    return master(spec["fn"](v, rng), spec)


def _encode(path, x):
    pcm = np.round(np.clip(x, -1, 1) * 32767).astype("<i2")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0",
                    "-c:a", "libvorbis", "-q:a", OGG_Q, "-fflags", "+bitexact", "-flags:a", "+bitexact",
                    "-map_metadata", "-1", path], input=pcm.tobytes(), check=True)


def write_ogg(path, x):
    """書き出して復号し、Vorbis の量子化でピークが -1 dBFS を越えたら下げて書き直す（割れ防止）。"""
    target = 10 ** (PEAK_DB / 20)
    g = 1.0
    for _ in range(5):
        _encode(path, x * g)
        pk = float(np.max(np.abs(decode(path))))
        if pk <= target * 1.03:
            break
        g *= target / pk * 0.995


def decode(path):
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "pipe:1"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").astype(float)


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)


def src_hash():
    with open(os.path.abspath(__file__), "rb") as fh:
        h = hashlib.sha256(fh.read())
    h.update(f"{SR}:{OGG_Q}".encode())
    return h.hexdigest()


def file_name(name, v):
    return f"{name}_{v}"


def definitions():
    defs = {}
    for name, s in SOUNDS.items():
        d = {"category": s["cat"]}
        if s["mind"]:
            d["min_distance"] = float(s["mind"])
        d["max_distance"] = float(s["dist"])
        d["sounds"] = [{"name": f"{SND_REL}/{file_name(name, v)}", "volume": s["vol"]} for v in range(s["variants"])]
        defs[f"{NS}.{name}"] = d
    return {"format_version": "1.14.0", "sound_definitions": defs}


def _build_one(job):
    name, v = job
    write_ogg(os.path.join(SND_DIR, file_name(name, v) + ".ogg"), render(name, v))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in argv
    want_preview = "--preview" in argv
    names = [a for a in argv if not a.startswith("--")]
    unknown = [n for n in names if n not in SOUNDS]
    if unknown:
        print(f"  unknown sound(s): {', '.join(unknown)}")
        return 1
    if not shutil.which("ffmpeg"):
        print("  ffmpeg が無いので効果音の生成を飛ばします（既存の .ogg を使用）")
        write_json(DEFS_PATH, definitions())
        return 0
    os.makedirs(SND_DIR, exist_ok=True)
    h = src_hash()
    try:
        with open(STAMP, encoding="utf-8") as fh:
            stale = json.load(fh).get("src") != h
    except (OSError, ValueError):
        stale = True
    keep = set()
    jobs = []
    for name, s in SOUNDS.items():
        for v in range(s["variants"]):
            path = os.path.join(SND_DIR, file_name(name, v) + ".ogg")
            keep.add(os.path.basename(path))
            if force or stale or name in names or not os.path.exists(path):
                if names and name not in names and os.path.exists(path) and not force:
                    continue
                jobs.append((name, v))
    n_jobs = max(1, int(os.environ.get("ASTRO_JOBS", min(2, os.cpu_count() or 1))))
    if n_jobs > 1 and len(jobs) > 4:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(n_jobs) as ex:
            list(ex.map(_build_one, jobs, chunksize=2))
    else:
        for job in jobs:
            _build_one(job)
    made = len(jobs)
    for f in os.listdir(SND_DIR):                              # 一覧から消えた音を掃除
        if f.endswith(".ogg") and f not in keep:
            os.remove(os.path.join(SND_DIR, f))
    write_json(DEFS_PATH, definitions())
    if not names:
        os.makedirs(SCRATCH, exist_ok=True)
        with open(STAMP, "w", encoding="utf-8") as fh:
            json.dump({"src": h}, fh)
    total = sum(os.path.getsize(os.path.join(SND_DIR, f)) for f in keep)
    nfiles = len(keep)
    print(f"  sounds: {len(SOUNDS)} ids / {nfiles} files ({total / 1024:.0f} KB), rendered {made}")
    if want_preview:
        preview()
    return 0


# ===========================================================================
#  プレビュー（波形とスペクトログラムの一覧）
# ===========================================================================
def _cmap(v):
    """0..1 → magma 風の色。"""
    stops = np.array([[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66],
                      [245, 125, 21], [250, 193, 39], [252, 255, 164]], float)
    x = np.clip(v, 0, 1) * (len(stops) - 1)
    i = np.minimum(x.astype(int), len(stops) - 2)
    fr = (x - i)[..., None]
    return (stops[i] * (1 - fr) + stops[i + 1] * fr).astype(np.uint8)


def stats(x):
    pk = float(np.max(np.abs(x))) if len(x) else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    return dict(dur=len(x) / SR, peak_db=20 * np.log10(max(pk, 1e-9)), rms_db=20 * np.log10(max(rms, 1e-9)),
                dc=float(np.mean(x)) if len(x) else 0.0,
                edge=float(max(abs(x[0]), abs(x[-1]))) if len(x) else 0.0)


def preview(out=None):
    from PIL import Image, ImageDraw, ImageFont
    out = out or os.path.join(SCRATCH, "sounds.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        font = ImageFont.load_default(size=12)
    except TypeError:
        font = ImageFont.load_default()
    pxs = 120                      # 1 秒あたりの幅
    cw, wave_h, spec_h, lab_h = 460, 34, 84, 28
    ch = lab_h + wave_h + spec_h + 8
    cols = 3
    names = list(SOUNDS)
    rows = (len(names) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw, rows * ch), (16, 16, 20))
    dr = ImageDraw.Draw(img)
    fmin, fmax = 40.0, NYQ
    rowf = np.geomspace(fmax, fmin, spec_h)
    problems = []
    report = []
    for k, name in enumerate(names):
        cx, cy = (k % cols) * cw, (k // cols) * ch
        s = SOUNDS[name]
        sts = []
        for v in range(s["variants"]):
            path = os.path.join(SND_DIR, file_name(name, v) + ".ogg")
            x = decode(path)
            st = stats(x)
            sts.append(st)
            if st["peak_db"] > -0.1:
                problems.append(f"{name}_{v}: clipping {st['peak_db']:.2f} dB")
            if st["rms_db"] < -45:
                problems.append(f"{name}_{v}: nearly silent (rms {st['rms_db']:.1f} dB)")
            if abs(st["dc"]) > 0.002:
                problems.append(f"{name}_{v}: DC {st['dc']:.4f}")
            if v == 0:
                x0 = x
        report.append((name, sts))
        st = sts[0]
        lab = f"{name}  x{s['variants']}  " + "/".join(f"{q['dur']:.2f}" for q in sts) + "s"
        lab2 = f"pk {st['peak_db']:.1f}dB  rms {st['rms_db']:.1f}dB  {s['cat']}"
        dr.text((cx + 4, cy + 1), lab, fill=(230, 230, 240), font=font)
        dr.text((cx + 4, cy + 14), lab2, fill=(150, 160, 180), font=font)
        w = min(cw - 8, int(len(x0) / SR * pxs) + 1)
        # 波形
        y0 = cy + lab_h
        per = max(1, len(x0) // w)
        for i in range(w):
            seg = x0[i * per:(i + 1) * per]
            if not len(seg):
                break
            lo, hi = float(seg.min()), float(seg.max())
            col = (255, 70, 70) if max(abs(lo), abs(hi)) > 0.99 else (110, 220, 160)
            dr.line([(cx + 4 + i, y0 + wave_h / 2 - hi * wave_h / 2), (cx + 4 + i, y0 + wave_h / 2 - lo * wave_h / 2)], fill=col)
        # スペクトログラム（対数周波数）
        nfft, hop = 1024, 256
        if len(x0) < nfft:
            x0 = np.concatenate([x0, np.zeros(nfft - len(x0))])
        nfr = 1 + (len(x0) - nfft) // hop
        idx = hop * np.arange(nfr)[:, None] + np.arange(nfft)[None, :]
        S = np.abs(np.fft.rfft(x0[idx] * np.hanning(nfft), axis=1))
        fb = np.fft.rfftfreq(nfft, 1 / SR)
        Sl = np.stack([np.interp(rowf, fb, fr_) for fr_ in S], axis=1)          # (rows, frames)
        cols_px = np.linspace(0, nfr - 1, w).astype(int)
        Sd = 20 * np.log10(Sl[:, cols_px] + 1e-9)
        Sd = (Sd - (Sd.max() - 80)) / 80
        im = Image.fromarray(_cmap(Sd))
        img.paste(im, (cx + 4, y0 + wave_h + 2))
    img.save(out)
    # 拡大して見やすい分割版も書く
    per_page = cols * 6
    for p in range(0, rows, 6):
        sub = img.crop((0, p * ch, cols * cw, min(rows, p + 6) * ch))
        sub.save(out.replace(".png", f"_{p // 6 + 1}.png"))
    print(f"  preview: {out}")
    for name, sts in report:
        print(f"    {name:16s} " + "  ".join(f"{q['dur']:.2f}s pk{q['peak_db']:+.1f} rms{q['rms_db']:+.1f}" for q in sts))
    if problems:
        print("  problems:")
        for p in problems:
            print("    " + p)
    else:
        print("  problems: none")
    del per_page
    return problems


if __name__ == "__main__":
    sys.exit(main())
