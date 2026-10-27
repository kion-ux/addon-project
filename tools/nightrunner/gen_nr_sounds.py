# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 効果音の合成（numpy + ffmpeg/libvorbis）。

素材音源は一切使わず、物理に寄せた合成だけで全部の効果音を作る（DESIGN.md §9）:

* 声: 声門パルス（Rosenberg 形・ジッタ・シマー・二重声・声門の擦れ）→ 声道のフォルマント
  （時変の縦続共鳴を STFT で掛ける）→ 息・泡・ゆがみ。spec の VOICE_VOCAB（f0 範囲・母音・雑音・
  ざらつき・層）から nr.z.<voice>.<idle|alert|attack|hurt|death> を機械的に作る。
* ゴア: 肉の打撃（低い胴鳴り + 平手の破裂 + 湿った共鳴の掃引）、骨（微小な破断の群れ + 乾いた共鳴）、
  裂ける（粒状の繊維の破断）、血（泡の共鳴 Minnaert・飛沫・拍動する噴出）。
* 武器（風切りの帯域掃引・金属のモード合成）、銃（衝撃波 + 胴 + 街の残響）、爆発、電気、火、UV の唸り、
  パルクールの足音と衣擦れ、UI、追跡の警告音、心音、夜の号笛。

出力: packs/nightrunner_RP/sounds/nr/<分類>/<名前>_<n>.ogg（モノラル 22.05 / 44.1 kHz。正規化・無音の
切り詰め。ループ用は端を重ねてつなぎ目を消す）と、断片 sound_definitions / sounds_json（DESIGN.md §1）。
ID は nr_registry.all_sound_ids(spec) の全部と、ゾンビの足音 nr.zstep.*（登録簿の「増やすのは自由」）。

キャッシュ: tools/nightrunner/.cache/sounds/<内容ハッシュ>.ogg（DSP の核・レシピのソース・引数・
ffmpeg の版から計算）。並列: ProcessPoolExecutor（CPU 数）。決定的（乱数は ID と変種から seed）。

    python3 tools/nightrunner/gen_nr_sounds.py                    # 全部（キャッシュが効く）
    python3 tools/nightrunner/gen_nr_sounds.py --sheet            # + スペクトログラムの一覧画像
    python3 tools/nightrunner/gen_nr_sounds.py --only 'nr.gore.*' --force --sheet

レシピの約束: レシピ（r_*）は「楽器」（この下の DSP の核と部品）だけを呼ぶ。別のレシピを呼ぶときは
キャッシュの鍵に呼ばれた側のソースも入る（_recipe_src）。
"""
from __future__ import annotations

import argparse
import fnmatch
import functools
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nr_common import PREVIEW, RP, SCRATCH, frag, stable_hash, write_json  # noqa: E402

GEN = "gen_nr_sounds"
OUT = os.path.join(RP, "sounds", "nr")
CACHE = os.path.join(HERE, ".cache", "sounds")
SHEET = os.path.join(SCRATCH, "sounds_spectrograms.png")
REPORT = os.path.join(SCRATCH, "sounds_report.json")
ENC_Q = {44100: "3", 22050: "4"}          # libvorbis の品質（-q:a）
SIZE_LIMIT_MB = 25.0

# =====================================================================
#  DSP の核（numpy だけ。1 サンプルずつの Python ループは使わない）
# =====================================================================
SR = 44100
R = np.random.default_rng(1)


def setup(sr: int, seed: int) -> None:
    """ジョブごとに標本化周波数と乱数を決める（決定的）。"""
    global SR, R
    SR = int(sr)
    R = np.random.default_rng(seed)


def ns(d) -> int:
    return max(1, int(round(float(d) * SR)))


def tax(d):
    return np.arange(ns(d)) / SR


def silence(d):
    return np.zeros(ns(d))


def white(d):
    return R.standard_normal(ns(d))


def _nfft(n) -> int:
    return 1 << max(4, int(n - 1).bit_length())


def nrm(x, peak=1.0):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return x * (peak / m) if m > 1e-12 else x


def colored(d, slope=-3.0, fmin=20.0):
    """傾き slope dB/oct のノイズ（-3 ピンク / -6 ブラウン / +3 青）。分散 1。"""
    n = ns(d)
    m = _nfft(n)
    spec = np.fft.rfft(R.standard_normal(m))
    f = np.maximum(np.fft.rfftfreq(m, 1.0 / SR), fmin)
    spec *= (f / 1000.0) ** (slope / 6.0206)
    y = np.fft.irfft(spec, m)[:n]
    return y / (np.std(y) + 1e-12)


def pink(d):
    return colored(d, -3.0)


def brown(d):
    return colored(d, -6.0)


# ---------------------------------------------------------------- 包絡
def env_pts(d, pts, shape="lin"):
    """[(秒, 値), ...] を結ぶ包絡。shape: lin（直線）/ cos（滑らか）/ db（値を dB で結ぶ）。"""
    t = tax(d)
    ts = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    if shape == "db":
        return 10.0 ** (np.interp(t, ts, 20.0 * np.log10(np.maximum(vs, 1e-6))) / 20.0)
    if shape == "cos" and len(ts) > 1:
        i = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2)
        u = np.clip((t - ts[i]) / np.maximum(ts[i + 1] - ts[i], 1e-9), 0.0, 1.0)
        return vs[i] + (vs[i + 1] - vs[i]) * (0.5 - 0.5 * np.cos(np.pi * u))
    return np.interp(t, ts, vs)


def perc(d, a=0.001, tau=0.1, p=1.0):
    """打撃の包絡: a 秒で立ち上がり、時定数 tau で減衰（p > 1 で終わりが急、< 1 で尾が長い）。"""
    t = tax(d)
    return np.clip(t / max(a, 1e-5), 0.0, 1.0) * np.exp(-(np.maximum(t - a, 0.0) / tau) ** p)


def bell(d, peak=0.5, pw=1.0):
    """0 → 1 → 0 の山（peak は頂点の相対位置、pw で尖らせる）。"""
    u = np.linspace(0.0, 1.0, ns(d))
    up = 0.5 - 0.5 * np.cos(np.pi * np.clip(u / max(peak, 1e-4), 0, 1))
    dn = 0.5 - 0.5 * np.cos(np.pi * np.clip((1.0 - u) / max(1.0 - peak, 1e-4), 0, 1))
    return np.where(u < peak, up, dn) ** pw


def lfn(d, rate, lo=-1.0, hi=1.0):
    """rate Hz で値が変わる滑らかな乱数（コサイン補間）。ゆらぎ・乱流・震え。"""
    n = ns(d)
    k = int(np.ceil(n / SR * rate)) + 3
    v = R.uniform(lo, hi, k)
    x = np.arange(n) / SR * rate
    i = x.astype(int)
    u = 0.5 - 0.5 * np.cos(np.pi * (x - i))
    return v[i] * (1.0 - u) + v[i + 1] * u


def at(arr, tc):
    """標本の配列 arr を時刻 tc（任意の形）で読む（tvf の中で包絡を使う）。"""
    return np.interp(tc, np.arange(len(arr)) / SR, arr)


# ---------------------------------------------------------------- フィルタ
def _minphase(mag):
    """振幅特性から最小位相の伝達関数（ケプストラム法）。
    振幅の床を -60 dB にする（深すぎる谷はケプストラムが折り返して、音の終わりに薄い塊が出る）。"""
    m = 2 * (len(mag) - 1)
    c = np.fft.irfft(np.log(np.maximum(mag, 1e-3)), m)
    c[1:m // 2] *= 2.0
    c[m // 2 + 1:] = 0.0
    return np.exp(np.fft.rfft(c, m))


def filt(x, *gains, tail=0.0):
    """静的なフィルタ（gains = 周波数 Hz → 振幅 の関数。掛け合わせる）。最小位相なので打撃の頭がにじまない。
    tail 秒だけ後ろへ鳴り続ける（共鳴の余韻）。"""
    n = len(x)
    m = n + (ns(tail) if tail > 0 else 0)
    size = _nfft(m + 64)
    f = np.fft.rfftfreq(size, 1.0 / SR)
    mag = np.ones_like(f)
    for g in gains:
        mag = mag * g(f)
    return np.fft.irfft(np.fft.rfft(x, size) * _minphase(mag), size)[:m]


def g_lp(fc, o=2):
    return lambda f: 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * o))


def g_hp(fc, o=2):
    return lambda f: 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-3)) ** (2 * o))


def g_bp(fc, q=1.0):
    return lambda f: 1.0 / np.sqrt(1.0 + (q * (f / fc - fc / np.maximum(f, 1e-3))) ** 2)


def g_pk(fc, q, db):
    k = 10.0 ** (db / 20.0) - 1.0
    return lambda f: 1.0 + k * g_bp(fc, q)(f) ** 2


def g_tilt(db_oct, f0=1000.0):
    return lambda f: (np.maximum(f, 20.0) / f0) ** (db_oct / 6.0206)


def lp(x, fc, o=2, tail=0.0):
    return filt(x, g_lp(fc, o), tail=tail)


def hp(x, fc, o=2):
    return filt(x, g_hp(fc, o))


def bp(x, fc, q=1.0, tail=0.0):
    return filt(x, g_bp(fc, q), tail=tail)


def tvf(x, gfn, win=1024, tail=0.0):
    """時変フィルタ（STFT・ゼロ位相・重ね合わせ）。gfn(tc (T,1) 秒, f (1,F) Hz) -> 振幅 (T,F)。
    掃引する帯域・声道のフォルマント・周波数で違う減衰に使う。"""
    n = len(x)
    hop = win // 4
    out_n = n + (ns(tail) if tail > 0 else 0)
    xp = np.concatenate([np.zeros(win), x, np.zeros(out_n - n + 2 * win)])
    nfr = (len(xp) - win) // hop + 1
    idx = hop * np.arange(nfr)[:, None] + np.arange(win)[None, :]
    w = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(win) / win)
    size = 2 * win
    frames = np.zeros((nfr, size))
    frames[:, win // 2: win // 2 + win] = xp[idx] * w
    spec = np.fft.rfft(frames, axis=1)
    f = np.fft.rfftfreq(size, 1.0 / SR)[None, :]
    tc = ((hop * np.arange(nfr) + win / 2.0 - win) / SR)[:, None]
    y = np.fft.irfft(spec * np.asarray(gfn(tc, f), float), size, axis=1)
    seg = size // hop
    yr = y.reshape(nfr, seg, hop)
    acc = np.zeros((nfr + seg, hop))
    for k in range(seg):
        acc[k:k + nfr] += yr[:, k, :]
    acc = acc.reshape(-1)
    s = win + win // 2
    return acc[s:s + out_n] / 2.0


def conv(x, h):
    n = len(x) + len(h) - 1
    m = _nfft(n)
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(h, m), m)[:n]


# ---------------------------------------------------------------- 混ぜる・形を変える
def put(buf, x, t0=0.0, g=1.0):
    """buf の t0 秒の所に x を足す（はみ出しは切る）。"""
    i = max(0, int(round(t0 * SR)))
    j = min(len(buf), i + len(x))
    if j > i:
        buf[i:j] += g * x[:j - i]
    return buf


def fit(x, d):
    n = ns(d)
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros(n - len(x))])


def mix(*xs):
    n = max(len(x) for x in xs)
    out = np.zeros(n)
    for x in xs:
        out[:len(x)] += x
    return out


def sat(x, drive=2.0):
    """柔らかい飽和（tanh）。ピークで正規化してから掛ける。"""
    return np.tanh(drive * nrm(x)) / np.tanh(drive)


def asat(x, drive=2.0, bias=0.25):
    """非対称の飽和（偶数次の倍音が出る。荒れた声・壊れたスピーカー）。"""
    z = np.tanh(drive * (nrm(x) + bias)) - np.tanh(drive * bias)
    return z - np.mean(z)


def ringmod(x, f, depth=1.0):
    t = np.arange(len(x)) / SR
    return x * (1.0 - depth + depth * np.sin(2 * np.pi * f * t))


def resample(x, ratio):
    """帯域制限の再標本化（ratio > 1 で短く高く）。"""
    n = len(x)
    m = max(8, int(round(n / ratio)))
    spec = np.fft.rfft(x)
    out = np.zeros(m // 2 + 1, complex)
    k = min(len(spec), len(out))
    out[:k] = spec[:k]
    return np.fft.irfft(out, m) * (m / n)


def varispeed(x, rate):
    """再生速度 rate（標本ごとの配列）で読む。ピッチの滑り・ドップラー。"""
    pos = np.cumsum(np.asarray(rate, float))
    pos = pos[pos < len(x) - 1]
    return np.interp(pos, np.arange(len(x)), x)


def sine(d, f, ph=0.0):
    """周波数 f（数か配列）の正弦。位相は積分で連続。"""
    f = np.broadcast_to(np.asarray(f, float), (ns(d),))
    return np.sin(2.0 * np.pi * np.cumsum(f) / SR + ph)


def osc(d, f, harm=12, tilt=1.0, odd=False):
    """帯域制限の加算合成の鋸波/矩形波（ブザー・警報・金管の和音）。"""
    f = np.broadcast_to(np.asarray(f, float), (ns(d),))
    ph = 2.0 * np.pi * np.cumsum(f) / SR
    y = np.zeros(len(f))
    for k in range(1, harm + 1):
        if odd and k % 2 == 0:
            continue
        y += np.where(k * f < SR * 0.45, np.sin(k * ph), 0.0) / k ** tilt
    return y


def modes(d, freqs, taus, amps, phases=None):
    """減衰する正弦の和（モード合成。金属・木・骨・ガラスの響き）。"""
    t = tax(d)
    y = np.zeros(len(t))
    for i, (f, tau, a) in enumerate(zip(freqs, taus, amps)):
        if f <= 0 or f >= SR * 0.46:
            continue
        p = phases[i] if phases is not None else R.uniform(0, 2 * np.pi)
        y += a * np.exp(-t / tau) * np.sin(2 * np.pi * f * t + p)
    return y


# ---------------------------------------------------------------- 残響
def reverb_ir(rt60=0.8, damp=1.0, pre=0.006, er=6, er_span=0.04, fd=2500.0):
    """残響の応答: 周波数ごとに減衰の速さが違う雑音の尾（高い音ほど早く消える）+ 初期反射。エネルギー 1。"""
    d = rt60 * 1.15 + pre
    tail = white(d) * (np.arange(ns(d)) >= ns(pre))

    def g(tc, f):
        rt = rt60 / (1.0 + damp * (f / fd) ** 1.3)
        return np.exp(-6.91 * np.maximum(tc - pre, 0.0) / rt)
    ir = tvf(tail, g, win=512)
    for _ in range(er):
        k = ns(pre + R.uniform(0.002, er_span))
        if k < len(ir):
            ir[k] += R.uniform(-1.0, 1.0) * 6.0 * np.sqrt(np.mean(ir[:ns(0.05)] ** 2) + 1e-12)
    ir[:ns(pre)] = 0.0
    return ir / (np.sqrt(np.sum(ir ** 2)) + 1e-12)


def room(x, rt60=0.6, wet=0.25, damp=1.0, pre=0.008, fd=2500.0):
    """x に残響を足す（長さは尾の分だけ伸びる）。"""
    w = conv(x, reverb_ir(rt60, damp, pre, fd=fd))
    out = w * wet * np.sqrt(np.sum(x ** 2) / (np.sum(w ** 2) + 1e-12)) * 0.6
    out[:len(x)] += x
    return out


def echoes(x, taps, fc=2500.0):
    """離れた壁からのはね返り（遅れ秒, 大きさ）。遅いものほど高域が落ちる。"""
    end = max(t for t, _ in taps) + 0.05
    out = np.concatenate([x, np.zeros(ns(end))])
    for t, g in taps:
        put(out, lp(x, fc / (1.0 + 2.0 * t), 2), t, g)
    return out


# ---------------------------------------------------------------- 仕上げ
def loopify(x, xf):
    """末尾 xf 秒を先頭に重ねて（等パワー）ループのつなぎ目を消す。長さは len(x) - xf。"""
    k = ns(xf)
    body = x[:-k].copy()
    u = np.linspace(0.0, 1.0, k)
    body[:k] = x[:k] * np.sin(0.5 * np.pi * u) + x[-k:] * np.cos(0.5 * np.pi * u)
    return body


def finish(x, loop=False, cls="fx", lowcut=25.0):
    """直流と超低域を切り、無音を詰め、正規化して、音量の分類ごとの上限（瞬時 RMS）に収める。"""
    x = np.nan_to_num(np.asarray(x, float), nan=0.0, posinf=0.0, neginf=0.0)
    if lowcut:
        x = hp(x, lowcut, 2)
    x = x - np.mean(x)
    pk = float(np.max(np.abs(x))) or 1.0
    if not loop:
        env = np.abs(x)
        on = np.nonzero(env > pk * 10 ** (-48 / 20))[0]
        start = max(0, (on[0] if len(on) else 0) - ns(0.0015))
        k = ns(0.01)
        sm = np.convolve(env, np.ones(k) / k, mode="same")
        live = np.nonzero(sm > pk * 10 ** (-62 / 20))[0]
        end = min(len(x), (live[-1] if len(live) else len(x) - 1) + ns(0.01))
        x = x[start:end]
    x = nrm(x, 0.891)
    win = ns(0.25)
    if len(x) > win:
        c = np.cumsum(np.concatenate([[0.0], x ** 2]))
        mom = float(np.sqrt(np.max(c[win:] - c[:-win]) / win))
    else:
        mom = float(np.sqrt(np.mean(x ** 2)))
    cap = 10 ** (CAP_DB.get(cls, -12.0) / 20)
    if mom > cap:
        x *= cap / mom
    fi, fo = (0.02, 0.02) if loop else (0.0008, min(0.03, 0.15 * len(x) / SR))
    a, b = ns(fi), ns(fo)
    if len(x) > a + b + 2:
        x[:a] *= np.linspace(0.0, 1.0, a)
        x[-b:] *= np.linspace(1.0, 0.0, b) ** 2
    return x


# 音量の分類ごとの上限（最も大きい 0.25 秒の RMS、dBFS）。打撃はピークで決まるので実質この上限には当たらない
CAP_DB = {"fx": -11.0, "loud": -9.0, "voice": -14.0, "loop": -20.0, "ui": -19.0, "soft": -21.0}


# =====================================================================
#  楽器（音の部品）— 肉・骨・液体・繊維・風・金属・木・機構
# =====================================================================
def impulses(d, rate, sigma=0.8):
    """rate（数か標本ごとの配列, 回/秒）で起きる点の列。大きさは対数正規、符号はランダム。"""
    n = ns(d)
    r = np.broadcast_to(np.asarray(rate, float), (n,))
    hit = R.random(n) < r / SR
    return np.where(hit, np.exp(R.normal(0.0, sigma, n)) * R.choice([-1.0, 1.0], n), 0.0)


def thud(d=0.35, f0=95.0, f1=48.0, tau=0.07, drop=0.03, click=0.25, body=0.6, nf=700.0):
    """重い物が当たる低音: 下がる正弦（胴鳴り）+ 低域の雑音の塊 + 当たりの粒。"""
    t = tax(d)
    tone = sine(d, f1 + (f0 - f1) * np.exp(-t / drop)) * perc(d, 0.0015, tau)
    nz = nrm(lp(white(d), nf, 2) * perc(d, 0.001, tau * 0.45))
    ck = nrm(hp(white(d), 1800.0) * perc(d, 0.0002, 0.003))
    return tone + body * nz + click * ck


def slap(d=0.07, fc=1600.0, q=0.7, tau=0.01):
    """皮膚・平らな物の破裂的な当たり（中域の雑音の一瞬）。"""
    return nrm(bp(white(d), fc, q) * perc(d, 0.0003, tau))


def bubble(f0, amp=1.0, rise=0.5):
    """泡 1 つ（Minnaert 共鳴: 減衰しながら上へ滑る正弦）。"""
    tau = 6.0 / f0 + 0.002
    d = min(0.15, 5.0 * tau)
    f = f0 * (1.0 + rise * tax(d) / d)
    return amp * sine(d, f) * perc(d, 0.0004, tau)


def bubbles(d, rate, lo=300.0, hi=2000.0, rise=0.5, start=0.0):
    """泡の群れ（ポアソン過程）。ごぼごぼ・血の泡・酸の泡立ち。"""
    out = silence(d)
    for _ in range(R.poisson(rate * max(d - start, 0.0))):
        f0 = lo * (hi / lo) ** R.random()
        put(out, bubble(f0, (lo / f0) ** 0.4 * R.uniform(0.3, 1.0), rise * R.uniform(0.4, 1.6)),
            R.uniform(start, d))
    return out


def squelch(d=0.3, lo=220.0, hi=1500.0, q=5.0, rate=12.0, grit=0.5, bub=8.0):
    """ぐちゃっ: 粘る雑音を共鳴の強い帯域で掃く（湿った口の母音の動き）+ 泡。包絡は呼ぶ側で掛ける。"""
    src = pink(d) * (1.0 - grit + grit * np.abs(lfn(d, 90.0)) ** 2) + 0.6 * grit * impulses(d, 400.0, 0.6)
    cv = lfn(d, rate)

    def g(tc, f):
        c = lo * (hi / lo) ** (0.5 + 0.5 * at(cv, tc))
        return g_bp(c, q)(f) + 0.35 * g_bp(c * 2.6, q * 0.8)(f)
    y = nrm(tvf(src, g, win=512))
    if bub:
        y = y + 0.45 * nrm(bubbles(d, bub, lo * 1.2, hi * 1.3))
    return y


def droplet(size=1.0):
    """血の粒が落ちる音（小さな湿った当たり + 時々泡）。size が大きいほど低く長い。"""
    d = 0.025 * size + 0.012
    x = nrm(bp(white(d), R.uniform(1200, 4800) / size ** 0.5, 1.3) * perc(d, 0.0002, 0.003 * size + 0.001))
    if R.random() < 0.45:
        x = mix(x, 0.6 * bubble(R.uniform(900, 3000) / size ** 0.3, 1.0, 0.7))
    return nrm(x)


def splatter(d, n, spread, size=1.0, start=0.0):
    """飛び散った血・肉片が周りに落ちる（start から指数分布の時刻に n 粒）。"""
    out = silence(d)
    for _ in range(n):
        ti = start + R.exponential(spread)
        if ti < d - 0.06:
            s = size * R.uniform(0.5, 1.6)
            put(out, droplet(s), ti, R.uniform(0.2, 1.0) * s ** 0.5)
    return out


def crack(d=0.15, n=6, span=0.03, lo=900.0, hi=5000.0, low=0.4, tone=1.0):
    """骨・木の破断: 微小なパチッの群れ（span 秒に n 個）を乾いた共鳴（短いモード）に通す + 胴の低音。"""
    clicks = silence(d)
    ts = np.sort(np.concatenate([[0.0], np.abs(R.normal(0.0, span, max(n - 1, 0)))]))
    for i, ti in enumerate(ts):
        g = bp(white(0.003), R.uniform(lo, hi), 1.0) * perc(0.003, 0.00005, 0.0006)
        put(clicks, nrm(g), ti, 1.0 if i == 0 else R.uniform(0.25, 0.9))
    k = 7
    ir = modes(0.06, R.uniform(lo * 0.5, hi * 0.6, k), R.uniform(0.002, 0.011, k), R.uniform(0.3, 1.0, k))
    ir = nrm(ir) * tone
    ir[0] += 1.6
    y = nrm(conv(clicks, ir)[:len(clicks)])
    if low:
        y = y + low * nrm(thud(d, 170.0, 85.0, 0.022, click=0.0, body=0.3))
    return y


def tear(d=0.4, rate_peak=600.0, rate_base=40.0, lo=500.0, hi=4500.0, peak=0.6, q=2.5, stretch=0.4):
    """繊維がちぎれる: 密度が変わる粒（帯域を跳ぶ共鳴）+ 張った筋の擦れ。"""
    imp = impulses(d, rate_base + (rate_peak - rate_base) * bell(d, peak, 1.5), 0.9)
    cv = lfn(d, 150.0)

    def g(tc, f):
        return g_bp(lo * (hi / lo) ** (0.5 + 0.5 * at(cv, tc)), q)(f)
    y = nrm(tvf(imp, g, win=256))
    if stretch:
        st = bp(pink(d), 1300.0, 1.1) * (0.5 + 0.5 * lfn(d, 45.0)) ** 2 * bell(d, peak, 1.0)
        y = y + stretch * nrm(st)
    return y


def whoosh(d=0.3, lo=300.0, hi=2800.0, peak=0.5, q=1.5, power=2.0, tone=0.0, src=None):
    """風切り: 速さの山に合わせて帯域の中心と大きさを動かす雑音（tone > 0 で笛のような細い成分）。"""
    v = bell(d, peak, 1.0)
    x = pink(d) if src is None else src

    def g(tc, f):
        vv = at(v, tc)
        c = lo + (hi - lo) * vv
        return g_bp(c, q)(f) * (0.25 + 0.75 * vv) + tone * g_bp(c * 1.6, 14.0)(f)
    return nrm(tvf(x, g, win=512) * v ** power)


METAL = {
    "bar": (1.0, 2.756, 5.404, 8.933, 13.344, 19.93),
    "plate": (1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501, 3.6, 4.06, 4.15, 4.63, 5.2, 5.9),
    "pipe": (1.0, 2.32, 4.25, 6.63, 9.38, 12.5),
    "blade": (1.0, 2.76, 3.8, 5.40, 6.9, 8.93, 13.3),
    "bell": (0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166, 5.433),
    "glass": (1.0, 2.32, 2.89, 4.25, 5.21, 6.67, 7.8, 9.1),
    "wood": (1.0, 2.48, 3.95, 5.6, 7.7, 9.9, 12.4),
}


def metal(d, f0, kind="plate", tau=0.5, bright=0.5, hard=1.0, detune=0.003, n=None, contact=0.35):
    """金属の打撃（モード合成）: 比 kind の部分音を少しずつずらして重ね（うなり）、高い部分音ほど早く消す。
    hard = 当たりの硬さ（接触の雑音の短さ・明るさ）。"""
    ratios = METAL[kind][:n] if n else METAL[kind]
    fr, ta, am = [], [], []
    for k, r in enumerate(ratios):
        f = f0 * r * (1.0 + R.normal(0.0, 0.006))
        for s in (1.0, 1.0 + detune * R.uniform(0.5, 1.5)):
            fr.append(f * s)
            ta.append(tau * (f0 / f) ** 0.55 * R.uniform(0.7, 1.2))
            am.append((1.0 / (k + 1)) ** (1.0 - bright) * R.uniform(0.5, 1.0))
    ir = modes(d, fr, ta, am)
    cd = 0.0012 / hard
    exc = hp(white(cd + 0.002), 300.0 * hard) * perc(cd + 0.002, 0.0001, cd * 0.4)
    out = nrm(conv(nrm(exc), ir)[:ns(d)])
    if contact:
        out = mix(out, contact * hard * nrm(hp(white(0.02), 2500.0) * perc(0.02, 0.0001, 0.002)))
    return out


def wood(d=0.25, f0=180.0, tau=0.035, bright=0.4, knock=0.6):
    """木の打撃（減衰の速いモード + 乾いたノック）。"""
    out = metal(d, f0, "wood", tau, bright, hard=0.7, detune=0.01, contact=0.0)
    return out + knock * nrm(bp(white(d), 900.0, 0.8) * perc(d, 0.0003, 0.006))


def mclick(d=0.05, f0=2800.0, tau=0.006, hard=1.0, n=5):
    """機械の小さな金属音（ばね・爪・掛け金・引き金）。"""
    fr = f0 * np.array([1.0, 1.73, 2.41, 3.37, 4.6])[:n] * R.uniform(0.95, 1.05, n)
    ir = modes(d, fr, tau * R.uniform(0.5, 1.2, n), R.uniform(0.4, 1.0, n))
    exc = nrm(hp(white(0.002), 800.0 * hard) * perc(0.002, 0.00005, 0.0004))
    return nrm(conv(exc, ir)[:ns(d)] + 0.4 * hard * fit(exc, d))


def mslide(d=0.12, lo=1400.0, hi=5000.0, rough=0.6, peak=0.4):
    """金属が擦れて滑る（スライド・ボルト・弾倉・ポンプ）。"""
    x = 0.3 * white(d) + impulses(d, 3000.0 * rough, 0.5)
    return nrm(filt(x, g_hp(lo), g_lp(hi)) * bell(d, peak))


def cloth(d=0.3, rate=220.0, lo=900.0, hi=6500.0, peak=0.4):
    """衣擦れ: 細かい摩擦の粒（パチパチした雑音）を帯域で整える。"""
    b = bell(d, peak)
    x = 0.5 * pink(d) * b + impulses(d, rate * b + 5.0, 0.6)
    return nrm(filt(x, g_hp(lo), g_lp(hi)) * b)


def grit(d=0.08, rate=900.0, lo=2200.0, hi=9000.0):
    """砂利・砂・瓦礫の粒のじゃり（踏む・擦る・落ちる）。"""
    x = impulses(d, rate * perc(d, 0.002, d * 0.35), 0.9)
    return nrm(filt(x, g_hp(lo), g_lp(hi), g_bp((lo * hi) ** 0.5, 0.5)))


def friedlander(d=0.01, T=0.0012, b=1.4):
    """爆風・銃口の圧力波（正の急峻な山のあとに長い負圧）。"""
    t = tax(d)
    return (1.0 - t / T) * np.exp(-b * t / T)


# =====================================================================
#  声（声門パルス → 声道のフォルマント）
# =====================================================================
# 母音のフォルマント（男性の平均, Hz）と帯域幅。scream = 叫びで大きく開いた口、growl = 喉を詰めた唸り
VOWELS = {
    "a": ((730, 1090, 2440, 3400, 4500), (90, 110, 170, 250, 300)),
    "o": ((570, 840, 2410, 3300, 4400), (80, 100, 160, 250, 300)),
    "u": ((330, 870, 2250, 3300, 4300), (70, 100, 140, 250, 300)),
    "e": ((530, 1840, 2480, 3500, 4500), (80, 120, 170, 250, 300)),
    "i": ((290, 2250, 3000, 3700, 4600), (60, 100, 160, 250, 300)),
    "ae": ((660, 1720, 2410, 3400, 4500), (90, 120, 170, 250, 300)),
    "schwa": ((500, 1500, 2500, 3500, 4500), (80, 110, 160, 250, 300)),
    "scream": ((960, 1420, 2700, 3700, 4700), (130, 150, 200, 280, 330)),
    "growl": ((430, 1000, 2300, 3200, 4200), (120, 150, 210, 290, 330)),
}


def glottal(f0, oq=0.6, jitter=0.012, shimmer=0.08, rough=0.0, breath=0.2, creak=0.0, osr=2):
    """声門の音源（体積流の微分 = 唇の放射込み）。f0 は標本ごとの Hz の配列。
    oq: 声門が開いている割合（0.4 押しつぶした叫び〜0.8 息もれのうめき。配列可）。
    jitter / shimmer: 周期ごとの高さ / 大きさの乱れ。rough: 二重声（周期ごとの強弱の交代 = 下の倍音）と脱落。
    creak: ボーカルフライ（不規則に長い周期）。breath: 声門の息（開きに合わせて脈打つ雑音）。
    rough・creak・jitter は配列でも良い（周期の始まりの値を使う）。2 倍の速さで作って帯域制限で戻す。"""
    n = len(f0)
    m = n * osr
    sro = SR * osr
    fo = np.interp(np.arange(m) / osr, np.arange(n), f0)
    ph0 = np.cumsum(fo) / sro
    K = int(ph0[-1]) + 4
    st = np.minimum(np.searchsorted(ph0, np.arange(K)), m - 1) // osr

    def per(a):
        return np.broadcast_to(np.asarray(a, float), (n,))[st]
    rg, ck, jt = per(rough), per(creak), per(jitter)
    fry = np.where(R.random(K) < 0.5 * ck, R.uniform(0.3, 0.7, K), 1.0)
    k0 = np.minimum(ph0.astype(int), K - 1)
    fj = fo * (1.0 + R.standard_normal(K) * jt)[k0] * fry[k0]
    ph = np.cumsum(fj) / sro
    k = np.minimum(ph.astype(int), K - 1)
    p = ph - np.floor(ph)
    amp = np.exp(R.standard_normal(K) * shimmer)
    alt = np.where(np.arange(K) % 2 == 0, 1.0, -1.0) * R.uniform(0.4, 1.0, K)
    amp = amp * np.clip(1.0 + 0.75 * rg * alt, 0.05, None)
    amp = amp * np.where(R.random(K) < 0.1 * rg + 0.25 * ck, R.uniform(0.05, 0.4, K), 1.0)
    oqs = np.broadcast_to(np.asarray(oq, float), (n,))[np.minimum(np.arange(m) // osr, n - 1)]
    tp, te = oqs * 0.62, oqs
    g = np.where(p < tp, 0.5 - 0.5 * np.cos(np.pi * p / tp),
                 np.where(p < te, np.cos(0.5 * np.pi * (p - tp) / np.maximum(te - tp, 1e-3)), 0.0)) * amp[k]
    dg = np.diff(g, prepend=0.0) * (sro / np.maximum(fj, 20.0))
    asp = hp(R.standard_normal(m) * (0.25 + g), 400.0)
    x = dg / (np.sqrt(np.mean(dg ** 2)) + 1e-9) + 1.4 * breath * asp / (np.sqrt(np.mean(asp ** 2)) + 1e-9)
    return resample(x, osr)[:n]


def tract(exc, keys, k=1.0, bw=1.0, tilt=-6.0, extra=None, wobble=0.03):
    """声道: 母音の列 keys = [(秒, 母音名), ...] のフォルマントを時間で補間（対数）して掛ける。
    各フォルマントは平らな土台の上の山（ローレンツ形、高さ F/B）。縦続の 5 本だけだと高い極が欠けて
    8 kHz より上が無くなるので、代わりに F1 より上を tilt dB/oct で落とす（-6 で普通の声、-3 で叫び）。
    k = 声道の短さの倍率（大きい生き物ほど小さい）、bw = 帯域幅の倍率（湿った・壊れた喉は広い）、
    extra(tc, f) = 追加の共鳴（喉の袋）。"""
    d = len(exc) / SR
    tk = np.array([t for t, _ in keys], float)
    fl = np.log(np.array([VOWELS[vw][0] for _, vw in keys], float))
    bv = np.array([VOWELS[vw][1] for _, vw in keys], float)
    wob = [lfn(d, 2.0 + 0.7 * i) * wobble for i in range(5)]

    def g(tc, f):
        T = tc[:, 0]
        G = np.ones((len(T), f.shape[1]))
        f1 = None
        for i in range(5):
            Fi = (np.exp(np.interp(T, tk, fl[:, i])) * k * (1.0 + at(wob[i], T)))[:, None]
            Bi = (np.interp(T, tk, bv[:, i]) * bw * (0.6 + 0.4 * k))[:, None]
            f1 = Fi if i == 0 else f1
            G *= 1.0 + (Fi / Bi - 1.0) / (1.0 + ((f - Fi) / (0.5 * Bi)) ** 2)
        G *= np.maximum(f / (0.8 * f1), 1.0) ** (tilt / 6.0206)
        if extra is not None:
            G *= extra(tc, f)
        return G
    return tvf(exc, g, win=1024 if SR > 30000 else 512)


def vtk(P) -> float:
    """声の f0 範囲から声道の長さの倍率（大きい生き物ほど低いフォルマント）。"""
    if not P.get("f0"):
        return 1.0
    lo, hi = P["f0"]
    return float(np.clip((np.sqrt(lo * hi) / 120.0) ** 0.22, 0.78, 1.3))


def utter(P, d, u, vowels, amp, oq=0.65, rough=None, breath=None, creak=0.0, drive=0.0, tilt=-6.0, bw=1.3,
          growl=0.0, k=None, jitter=0.012, shimmer=0.08, fshift=1.0):
    """VOICE_VOCAB の 1 項目 P で 1 回の発声。u = f0 の位置の [(秒, 値)]（0 = 下限・1 = 上限、外へ出ても良い）、
    vowels = [(秒, 母音)]、amp = [(秒, 大きさ)]。growl = 偽声帯の唸り（f0/2 の振幅変調）。
    P の extra のうち音源に効くもの（tremolo / vibrato / bubbles / subbass / sac_resonance）はここで掛ける。"""
    lo, hi = P["f0"]
    ex = P.get("extra", ())
    t = tax(d)
    f0 = lo * (hi / lo) ** env_pts(d, u, "cos") * fshift
    a = env_pts(d, amp, "cos")
    rough = P["rough"] if rough is None else rough
    breath = P["noise"] if breath is None else breath
    if "tremolo" in ex:
        tr = np.sin(2 * np.pi * (6.0 + 0.4 * lfn(d, 0.8)) * t + R.uniform(0, 6.28))
        f0 = f0 * (1.0 + 0.03 * tr)
        a = a * (1.0 + 0.4 * tr)
    if "vibrato" in ex:
        f0 = f0 * (1.0 + (0.04 + 0.02 * lfn(d, 0.6)) * np.sin(2 * np.pi * np.cumsum(5.3 + 0.8 * lfn(d, 0.5)) / SR))
    if "bubbles" in ex:
        f0 = f0 * (1.0 + 0.05 * lfn(d, 26.0))
        a = a * (1.0 - 0.55 * np.abs(lfn(d, 21.0)))
    f0 = f0 * (1.0 + 0.012 * lfn(d, 5.0) + 0.008 * lfn(d, 13.0))
    if growl:
        a = a * (1.0 - growl * (0.5 + 0.5 * np.sin(np.pi * np.cumsum(f0) / SR * (1.0 + 0.1 * lfn(d, 9.0)))))
    exc = glottal(f0, oq, jitter, shimmer, rough, breath, creak) * a
    extra = None
    if "sac_resonance" in ex:
        fs = 300.0 * (1.0 + 0.15 * lfn(d, 1.5))
        extra = lambda tc, f: g_pk(at(fs, tc), 3.0, 16.0)(f)  # noqa: E731
    y = tract(exc, vowels, vtk(P) if k is None else k, bw, tilt, extra)
    if "subbass" in ex:
        sb = (sine(d, f0 * 0.5) + 0.6 * sine(d, f0)) * a
        y = y + 0.8 * sb * np.sqrt(np.mean(y ** 2)) / (np.sqrt(np.mean(sb ** 2)) + 1e-9)
    y = filt(y, g_hp(lo * 0.9, 1))
    if drive:
        y = asat(y, drive, 0.15)
    return y


def whisper(d, vowels, amp, k=1.0, bw=1.9, fric=0.0, fric_fc=5200.0, rasp=0.0):
    """ささやき・息の声（雑音を母音の形に）。fric = 歯の擦れ（す・し）、rasp = 低い不規則なきしみ。"""
    a = env_pts(d, amp, "cos")
    src = white(d)
    if rasp:
        src = src + rasp * 3.0 * impulses(d, 45.0 + 25.0 * lfn(d, 3.0), 0.5)
    y = nrm(tract(src * a, vowels, k, bw, tilt=-3.0, wobble=0.05))
    if fric:
        s = filt(white(d), g_bp(fric_fc, 1.4), g_hp(2500.0)) * a
        y = y + fric * nrm(s)
    return y


def tongue_click(f=2600.0, q=5.0, amp=1.0):
    """舌打ち・歯の当たり（鋭い粒を細い共鳴に通す）。"""
    x = np.zeros(ns(0.03))
    x[0] = 1.0
    return amp * nrm(filt(x, g_bp(f, q), g_hp(700.0)))


def rattle(d, lo=120.0, hi=520.0, rate=45.0):
    """喉の奥の痰・血の泡の音（死前喘鳴）。"""
    return nrm(bubbles(d, rate, lo, hi, 0.4) + 0.4 * lp(impulses(d, 30.0, 0.5), 900.0))


# =====================================================================
#  楽器 — 火・電気・唸り・銃・爆発・足音・人の息と声・電子音
# =====================================================================
def crackles(d, rate, lo=1500.0, hi=7000.0, sigma=1.1, ring=0.002):
    """はぜる音（大小のパチッ。木の繊維の短い共鳴を通す）。rate は数か標本ごとの配列。"""
    imp = impulses(d, rate, sigma)
    ir = modes(0.02, R.uniform(lo, hi, 5), R.uniform(ring * 0.5, ring * 1.5, 5), R.uniform(0.3, 1.0, 5))
    ir = nrm(ir)
    ir[0] += 2.0
    return nrm(conv(imp, ir)[:ns(d)])


def fire_bed(d, crackle=0.6, roar=1.0, hiss=0.25):
    """燃え続ける火: 低い乱流の轟き + 大小のはぜる音 + 高いしゅー。"""
    r = lp(brown(d), 420.0, 2) * (0.6 + 0.4 * lfn(d, 5.0)) * (0.75 + 0.25 * lfn(d, 17.0))
    h = hp(white(d), 3500.0) * (0.5 + 0.5 * lfn(d, 3.0))
    c = crackles(d, 20.0 * crackle + 2.0, 1200.0, 6500.0)
    pops = crackles(d, 1.5 * crackle + 0.3, 300.0, 1500.0, 0.6, 0.006)
    return roar * nrm(r) + 0.5 * hiss * nrm(h) + 0.8 * crackle * c + 0.6 * crackle * pops


def arc(d, lo=60.0, hi=500.0, gate=0.6, snap=1.0):
    """放電: 速さが乱れるパルス列（ブーン〜ジジジ）を断続させ、高域のバチッを重ねる。"""
    r = lo * (hi / lo) ** (0.5 + 0.5 * lfn(d, 30.0))
    ph = np.cumsum(r) / SR
    pul = np.zeros(ns(d))
    idx = np.nonzero(np.diff(np.floor(ph), prepend=0.0) > 0)[0]
    pul[idx] = np.exp(R.normal(0.0, 0.5, len(idx))) * R.choice([-1.0, 1.0], len(idx))
    g = (lfn(d, 38.0) > (0.0 - gate)).astype(float)
    k = ns(0.0015)
    g = np.convolve(g, np.ones(k) / k, mode="same")
    buzz = filt(pul, g_hp(250.0), g_pk(2600.0, 1.2, 8.0))
    sn = filt(impulses(d, 700.0 * snap, 1.2), g_hp(1800.0))
    return nrm(nrm(buzz) * g + 0.55 * nrm(sn) * g)


def hum(d, f=60.0, n=30, even=1.0, buzz=0.25, wob=0.2):
    """交流の唸り（電源の 2 倍の周波数の倍音）。d を 1/(2f) の整数倍にすると繰り返しの位相がそろう。
    buzz = 磁歪のビリつき（尖った倍音）、wob = ゆっくりした大きさの揺れ。"""
    t = tax(d)
    y = np.zeros(len(t))
    for k in range(1, n + 1):
        fk = 2.0 * f * k
        if fk > SR * 0.45:
            break
        y += (1.0 / k ** 1.1) * (1.0 if k % 2 else even) * R.uniform(0.5, 1.0) * np.sin(2 * np.pi * fk * t + R.uniform(0, 6.3))
    y = nrm(y)
    y = y + buzz * nrm(np.sign(y) * np.abs(y) ** 0.25)
    return nrm(y) * (1.0 - wob + wob * (0.5 + 0.5 * np.cos(2 * np.pi * t / d * 2.0)))


def gunshot(d=1.6, size=1.0, body_f=110.0, crack=1.0, tail=1.0, bright=1.0, rt=1.4, drive=3.0):
    """銃声: 銃口の圧力波（鋭い山と負圧）+ 燃焼ガスの胴（明るさが落ちていく雑音の塊）+ 低い衝撃
    + 街の残響とはね返り（建物の壁の遅れ）。"""
    out = silence(0.4)
    put(out, nrm(hp(friedlander(0.02, 0.0009 * size, 1.4), 90.0)), 0.0, 1.0 * crack)
    db = 0.3 * size
    cut = np.geomspace(7500.0 * bright, 700.0, ns(db))
    body = tvf(white(db) * perc(db, 0.0004, 0.026 * size), lambda tc, f: g_lp(at(cut, tc), 2)(f), win=256)
    put(out, nrm(body), 0.0, 0.85)
    put(out, thud(0.3 * size, body_f * 1.6, body_f * 0.55, 0.05 * size, drop=0.012, click=0.0, body=0.4, nf=600),
        0.0, 0.75)
    x = sat(out, drive)
    taps = [(R.uniform(0.11, 0.16), 0.3), (R.uniform(0.26, 0.33), 0.18), (R.uniform(0.44, 0.52), 0.1)]
    w = echoes(room(x, rt, 0.5 * tail, damp=1.6, fd=1600.0), taps, 2000.0)
    return fit(w, d)


def explosion(d=4.0, size=1.0, debris=1.0, glass=0.0, fire=0.5, metal_amt=0.0):
    """爆発: 圧力の山 + 重低音（下がる正弦）+ 乱流の轟音（暗くなっていく）+ 火の玉のはぜ
    + 降ってくる瓦礫・ガラス・金属片 + 長く暗い残響。"""
    out = silence(d)
    put(out, nrm(hp(friedlander(0.06, 0.004 * size, 1.2), 35.0)), 0.0, 1.0)
    put(out, thud(min(d, 2.2 * size), 72.0, 26.0, 0.45 * size, drop=0.15, click=0.0, body=0.6, nf=160), 0.0, 1.0)
    dr = min(d, 3.0 * size)
    nz = (0.5 * brown(dr) + 0.5 * pink(dr)) * (0.65 + 0.35 * lfn(dr, 9.0)) * (0.8 + 0.2 * lfn(dr, 23.0))
    e = env_pts(dr, [(0, 0.0), (0.004, 1.0), (0.15, 0.8), (0.6 * size, 0.3), (dr, 0.0)], "cos")
    cut = 220.0 + 3800.0 * np.exp(-tax(dr) / (0.35 * size))
    put(out, nrm(tvf(nz * e, lambda tc, f: g_lp(at(cut, tc), 2)(f))), 0.0, 0.95)
    if fire:
        put(out, crackles(1.4, 70.0 * fire + 5.0, 900.0, 6000.0) * perc(1.4, 0.05, 0.45), 0.03, 0.3 * fire)
    for _ in range(int(16 * debris)):
        t = 0.25 + R.exponential(0.55 * size)
        if t < d - 0.3:
            kind = R.random()
            if kind < 0.5:
                put(out, grit(0.12, 1800.0, 1500.0, 8000.0), t, R.uniform(0.05, 0.2))
            elif kind < 0.8:
                put(out, thud(0.15, 220.0, 110.0, 0.02, click=0.4, body=0.5, nf=2500.0), t, R.uniform(0.05, 0.18))
            else:
                put(out, wood(0.12, R.uniform(300, 700), 0.015, 0.4, 0.8), t, R.uniform(0.05, 0.15))
    for _ in range(int(10 * glass)):
        t = 0.2 + R.exponential(0.4)
        if t < d - 0.3:
            put(out, metal(0.25, R.uniform(2500, 5000), "glass", 0.05, 0.6, 1.5, n=5), t, R.uniform(0.04, 0.15))
    for _ in range(int(6 * metal_amt)):
        t = 0.3 + R.exponential(0.7)
        if t < d - 0.4:
            put(out, metal(0.6, R.uniform(500, 1400), "plate", 0.25, 0.5, 1.2), t, R.uniform(0.05, 0.15))
    x = sat(out, 2.5)
    return fit(room(x, 2.2 * size, 0.45, damp=2.5, fd=1100.0), d)


def footstep(weight=1.0, scuff=0.5, gravel=0.4, toe=True):
    """足音: 踵（低い当たり）+ 靴底の平手 + つま先の 2 打目 + 砂利のじゃり + 擦り。"""
    out = silence(0.3)
    put(out, thud(0.12, 150.0 / weight ** 0.5, 75.0, 0.018 * weight, drop=0.01, click=0.4, body=0.9, nf=1500.0), 0.0, 1.0)
    put(out, slap(0.05, 1300.0, 0.6, 0.007), 0.002, 0.5)
    tt = R.uniform(0.03, 0.06)
    if toe:
        put(out, thud(0.08, 190.0, 100.0, 0.012, click=0.3, body=0.6, nf=2000.0), tt, 0.45)
    if gravel:
        put(out, grit(0.09, 1400.0), 0.0, gravel)
    if scuff:
        put(out, nrm(filt(white(0.09), g_bp(2200.0, 0.8)) * bell(0.09, 0.3)), tt * 0.5, 0.4 * scuff)
    return out


PLAYER_VOICE = dict(f0=(100.0, 170.0), vowel="a", noise=0.45, rough=0.15, extra=())


def effort(d=0.25, kind="hup", amp=1.0):
    """生存者（プレイヤー）の短い息み声: hup（跳ぶ）/ ugh（重い着地・被弾）/ hah（蹴り）。"""
    u = {"hup": [(0, 0.5), (0.3 * d, 0.7), (d, 0.4)], "ugh": [(0, 0.6), (0.2 * d, 0.45), (d, 0.1)],
         "hah": [(0, 0.8), (0.25 * d, 0.95), (d, 0.5)]}[kind]
    vw = {"hup": [(0, "schwa"), (d, "u")], "ugh": [(0, "schwa"), (0.3 * d, "a"), (d, "schwa")],
          "hah": [(0, "a"), (d, "ae")]}[kind]
    y = utter(PLAYER_VOICE, d, u, vw, [(0, 0), (0.015, 1), (0.5 * d, 0.7), (d, 0)], oq=0.5, breath=0.6,
              tilt=-5, drive=1.3)
    return amp * nrm(y)


def pant(d=2.0, rate=2.2, k=1.0):
    """息切れ（吸う・吐くの繰り返し。吐く方が強く、だんだん落ち着く）。"""
    out = silence(d)
    t, i = 0.0, 0
    per = 1.0 / rate
    while t < d - 0.15:
        ex_d = per * R.uniform(0.5, 0.6)
        in_d = per - ex_d
        put(out, whisper(ex_d, [(0, "a"), (ex_d, "schwa")], [(0, 0), (0.15 * ex_d, 1), (ex_d, 0)], k, 1.6),
            t, R.uniform(0.75, 1.0) * (1.0 - 0.3 * t / d))
        put(out, whisper(in_d, [(0, "o"), (in_d, "i")], [(0, 0), (0.7 * in_d, 1), (in_d, 0)], k, 2.0, fric=0.2),
            t + ex_d, 0.5 * (1.0 - 0.3 * t / d))
        t += per * R.uniform(0.92, 1.08) * (1.0 + 0.25 * t / d)
        i += 1
    return out


def tone(d, f, a=0.002, tau=0.2, harm=(1.0,), inh=0.0):
    """減衰する音色（倍音の大きさ harm、inh で少し伸びる倍音 = 金属っぽさ）。"""
    t = tax(d)
    y = np.zeros(len(t))
    for k, h in enumerate(harm, 1):
        fk = f * k * (1.0 + inh * k * k)
        if fk < SR * 0.45:
            y += h * np.sin(2 * np.pi * fk * t) * np.exp(-t * k ** 0.5 / tau)
    return y * np.clip(t / a, 0, 1)


def fmbell(d, f, ratio=3.5, index=2.5, tau=0.6):
    """FM の鐘（明るい打撃が丸くなっていく）。"""
    t = tax(d)
    ii = index * np.exp(-t / (tau * 0.4))
    return np.sin(2 * np.pi * f * t + ii * np.sin(2 * np.pi * f * ratio * t)) * np.exp(-t / tau) * np.clip(t / 0.001, 0, 1)


def beep(d, f, a=0.003, r=0.02, sq=0.3):
    """電子音（少し矩形寄りの正弦）。"""
    y = sine(d, f) + sq * sine(d, 3 * f) / 3 + 0.5 * sq * sine(d, 5 * f) / 5
    e = np.minimum(np.clip(tax(d) / a, 0, 1), np.clip((d - tax(d)) / r, 0, 1))
    return nrm(y * e)


def horn(d, f, harm=26, bright=0.9, vib=0.004):
    """金管・号笛の音色（帯域制限の鋸波を口の共鳴で整える）。"""
    t = tax(d)
    ff = f * (1.0 + vib * np.sin(2 * np.pi * 4.8 * t) + 0.003 * lfn(d, 2.0))
    y = osc(d, ff, harm, bright)
    return filt(y, g_pk(700.0, 1.2, 8.0), g_pk(1500.0, 1.5, 4.0), g_lp(3500.0, 2))


#@@ RECIPES ここより上が「DSP の核と楽器」（変えると全部のキャッシュが切れる）。下はレシピ（r_*(v) -> 波形）
# =====================================================================
#  ゴア（nr.gore.*）
# =====================================================================
def r_slash_flesh(v):
    """刃が肉を裂く: 刃の最後の風切り → 皮を切る「シュッ」→ 繊維が裂ける粒 → 湿った共鳴 → 血の粒。"""
    out = silence(0.6)
    put(out, whoosh(0.09, 1500, 6000, 0.85, 1.2), 0.0, 0.22)
    put(out, nrm(hp(white(0.05), 2600) * perc(0.05, 0.0003, 0.007)), 0.08, 0.9)
    put(out, tear(0.17, 900 + 150 * v, 80, 700, 5200, 0.25, 2.0, 0.3), 0.085, 0.6)
    put(out, nrm(squelch(0.24, 300, 1700, 4.5, 18) * perc(0.24, 0.004, 0.06)), 0.09, 0.55)
    put(out, thud(0.15, 125, 62, 0.03, click=0.0, body=0.4), 0.08, 0.32)
    put(out, splatter(0.45, 9 + 2 * v, 0.08, 0.7), 0.12, 0.35)
    return out


def r_blunt_flesh(v):
    """鈍器が肉を潰す: 低い胴鳴り + 平手の破裂 + ぐちゃっと潰れる共鳴 + 少しの飛沫。"""
    out = silence(0.55)
    put(out, thud(0.38, 115 + 18 * v, 50, 0.06, click=0.35, body=0.9, nf=900), 0.0, 1.0)
    put(out, slap(0.06, 1300 + 200 * v, 0.7, 0.012), 0.0, 0.7)
    put(out, nrm(squelch(0.26, 200, 1100, 5, 10) * perc(0.26, 0.006, 0.07)), 0.004, 0.5)
    put(out, splatter(0.45, 5, 0.06, 0.8), 0.03, 0.22)
    return sat(out, 1.6)


def r_pierce_flesh(v):
    """刺さる・弾が入る: 鋭い先端の粒 → 詰まった「ずぶっ」（高めの短い胴鳴り）→ 吸い込む湿った音。"""
    out = silence(0.45)
    put(out, nrm(hp(white(0.006), 3000) * perc(0.006, 0.0001, 0.0012)), 0.0, 0.8)
    put(out, thud(0.2, 230 - 20 * v, 105, 0.028, click=0.5, body=0.5, nf=1600), 0.001, 0.9)
    sq = squelch(0.16, 500, 1900, 7, 25, 0.3, 4) * env_pts(0.16, [(0, 0), (0.01, 1), (0.16, 0)])
    put(out, nrm(sq), 0.01, 0.55)
    put(out, splatter(0.35, 4 + v, 0.05, 0.6), 0.02, 0.2)
    return out


def r_bone_crack(v):
    """骨が折れる: 乾いたパチッの群れ（セロリを折るような繊維）+ 胴の低音 + 湿った肉。"""
    out = silence(0.4)
    put(out, crack(0.3, 5 + 2 * v, 0.014 + 0.004 * v, 1000, 5500, 0.5), 0.0, 1.0)
    put(out, tear(0.08, 1800, 300, 1500, 7000, 0.15, 1.5, 0.0), 0.002, 0.35)
    put(out, nrm(squelch(0.14, 400, 1500, 4, 20, 0.4, 0) * perc(0.14, 0.003, 0.03)), 0.006, 0.18)
    return out


def r_bone_crunch(v):
    """骨が砕ける: 長く続く破断の群れ + 擦れ合う骨の砕け + 潰れる肉。"""
    out = silence(0.7)
    put(out, crack(0.5, 14 + 3 * v, 0.06, 700, 4200, 0.6), 0.0, 1.0)
    put(out, tear(0.35, 2500, 200, 400, 2600, 0.3, 1.8, 0.0), 0.01, 0.55)
    put(out, nrm(squelch(0.4, 180, 1000, 5, 9) * perc(0.4, 0.01, 0.12)), 0.01, 0.4)
    put(out, thud(0.3, 100, 45, 0.05, click=0.2, body=0.7), 0.0, 0.55)
    return sat(out, 1.4)


def r_sever(v):
    """四肢がちぎれる: 引き伸ばされる筋（密度が上がる裂け）→ 大きな裂けと関節の「ぼきっ」→ 血の噴き出し。"""
    d = 1.15
    out = silence(d)
    t_rip = 0.22 + 0.04 * v
    put(out, tear(t_rip + 0.04, 320, 30, 400, 3000, 0.95, 2.0, 0.6), 0.0, 0.45)
    put(out, tear(0.2, 1700, 250, 600, 6500, 0.18, 1.6, 0.5), t_rip, 0.95)
    put(out, crack(0.2, 4, 0.01, 700, 3500, 0.7), t_rip + 0.01, 0.8)
    put(out, thud(0.25, 140, 60, 0.04, click=0.3, body=0.5), t_rip, 0.5)
    sp = (hp(white(0.6), 900) * (0.5 + 0.5 * lfn(0.6, 35.0)) ** 2 + 0.5 * bubbles(0.6, 40, 500, 2200)) \
        * env_pts(0.6, [(0, 0), (0.02, 1), (0.25, 0.6), (0.6, 0)])
    put(out, nrm(bp(sp, 2400, 0.6)), t_rip + 0.02, 0.45)
    put(out, splatter(d - t_rip, 18, 0.15, 1.0), t_rip + 0.03, 0.45)
    return out


def r_decap(v):
    """首が飛ぶ: 首に食い込む刃 → 背骨の砕け → 裂け → 噴水のように噴く血と喉の泡。"""
    d = 1.5
    out = silence(d)
    put(out, thud(0.3, 130, 55, 0.05, click=0.7, body=0.8, nf=1400), 0.0, 0.9)
    put(out, nrm(hp(white(0.04), 2000) * perc(0.04, 0.0002, 0.006)), 0.0, 0.7)
    put(out, crack(0.35, 10 + 2 * v, 0.03, 800, 4000, 0.4), 0.004, 0.9)
    put(out, tear(0.25, 2000, 300, 500, 5000, 0.25, 1.8, 0.5), 0.03, 0.7)
    sp = (bp(white(1.1), 2200, 0.5) * (0.4 + 0.6 * np.abs(lfn(1.1, 25.0)))
          * (0.55 + 0.45 * np.cos(2 * np.pi * 2.6 * tax(1.1)) ** 8))
    put(out, nrm(sp * env_pts(1.1, [(0, 0), (0.03, 1), (0.7, 0.5), (1.1, 0)])), 0.06, 0.5)
    put(out, bubbles(1.2, 55, 160, 900, 0.8), 0.2, 0.5)
    put(out, splatter(1.3, 24, 0.25, 1.1), 0.08, 0.45)
    return sat(out, 1.3)


def r_head_pop(v):
    """頭が弾ける: 圧で割れる頭蓋（低い破裂 + 破断の群れ）→ 湿った爆ぜ → 降ってくる血と肉片。"""
    d = 1.5
    out = silence(d)
    put(out, thud(0.45, 95, 38, 0.09, click=1.0, body=1.0, nf=2600), 0.0, 1.0)
    put(out, crack(0.3, 12 + 3 * v, 0.02, 700, 4500, 0.3), 0.0, 0.9)
    wet = squelch(0.3, 300, 3000, 2.2, 30, 0.6, 20) * perc(0.3, 0.002, 0.07)
    put(out, nrm(wet), 0.003, 0.9)
    put(out, nrm(bp(white(0.12), 1500, 0.4) * perc(0.12, 0.0005, 0.03)), 0.0, 0.7)
    put(out, splatter(d, 34, 0.28, 1.2, 0.12), 0.0, 0.55)
    for _ in range(4 + v):
        t = R.uniform(0.3, 1.0)
        put(out, thud(0.15, 160, 80, 0.02, click=0.1, body=0.5), t, R.uniform(0.15, 0.35))
        put(out, slap(0.05, R.uniform(900, 1600), 0.8, 0.01), t, R.uniform(0.1, 0.3))
    return sat(out, 2.0)


def r_splat(v):
    """血肉が叩きつけられる: 湿った塊の当たり + 平手 + 広がる飛沫。"""
    out = silence(0.65)
    put(out, thud(0.25, 115, 55, 0.04, click=0.2, body=0.7), 0.0, 0.8)
    put(out, slap(0.08, 1000 + 250 * v, 0.6, 0.015), 0.0, 0.85)
    put(out, nrm(squelch(0.2, 250, 1600, 4, 22, 0.5, 15) * perc(0.2, 0.002, 0.05)), 0.002, 0.6)
    put(out, splatter(0.6, 14 + 3 * v, 0.07, 0.9), 0.01, 0.5)
    return out


def r_squish(v):
    """ぐちゃっと潰れる: ゆっくり押し潰される粘る肉（共鳴の掃引）と泡。"""
    d = 0.55 + 0.1 * v
    sq = squelch(d, 170, 1300, 6, 9 + 3 * v, 0.6, 25)
    e = env_pts(d, [(0, 0), (0.03, 1), (0.18, 0.7), (0.3, 0.9), (d, 0)], "cos")
    out = nrm(sq * e)
    put(out, thud(0.2, 90, 50, 0.05, click=0.0, body=0.5), 0.0, 0.35)
    return out


def r_spurt(v):
    """血が噴く: 心拍に合わせて脈打つ噴出（帯域の雑音の揺らぎ）+ 喉の泡 + 地面に落ちる飛沫。"""
    d = 1.35
    t = tax(d)
    hr = 2.3 + 0.3 * v
    pulse = np.maximum(np.sin(2 * np.pi * hr * t + 0.4), 0.0) ** 2.5 * np.exp(-t / 0.9) * 0.8 + np.exp(-t / 0.08)
    spray = bp(white(d), 2600, 0.6) * (0.45 + 0.55 * np.abs(lfn(d, 40.0)))
    out = nrm(spray * pulse)
    out += 0.5 * nrm(bubbles(d, 50, 400, 1800, 0.8) * (0.3 + pulse))
    out += 0.35 * splatter(d, 26, 0.35, 0.8, 0.05)
    return out


def r_gut_spill(v):
    """内臓がこぼれる: 重なり合う滑る湿った塊（低い共鳴の掃引）+ 重い「べちゃ」+ 泡。"""
    d = 1.7
    out = silence(d)
    for i in range(4):
        dd = R.uniform(0.35, 0.65)
        sq = squelch(dd, 140, 900, 6, 7, 0.6, 10) * bell(dd, R.uniform(0.3, 0.6), 1.5)
        put(out, nrm(sq), 0.08 + i * 0.28 + R.uniform(0, 0.08), R.uniform(0.5, 0.9))
    for _ in range(3):
        t = R.uniform(0.2, 1.2)
        put(out, thud(0.3, 85, 45, 0.06, click=0.05, body=0.8), t, 0.7)
        put(out, slap(0.07, 700, 0.7, 0.02), t, 0.5)
    out += 0.4 * nrm(bubbles(d, 30, 200, 900, 0.6))
    return out


def r_gib_land(v):
    """ちぎれた部位が落ちる: 大きさの違う湿った塊の当たり（4 種類）。"""
    s = (0.75, 1.0, 1.3, 0.9)[v % 4]
    out = silence(0.45)
    put(out, thud(0.28, 140 / s, 62 / s, 0.032 * s, click=0.15, body=0.7), 0.0, 1.0)
    put(out, slap(0.06, 1300 / s ** 0.5, 0.7, 0.01 * s), 0.0, 0.6)
    put(out, nrm(squelch(0.12 * s, 300, 1500, 4, 25, 0.5, 10) * perc(0.12 * s, 0.002, 0.03 * s)), 0.003, 0.35)
    put(out, splatter(0.4, 3 + v, 0.04, 0.6), 0.01, 0.2)
    return out


def r_body_fall(v):
    """体が倒れる: 膝 → 胴の重い低音 → 頭がぶつかる → 腕が遅れて落ちる。衣擦れと床の砂。"""
    d = 1.3
    out = silence(d)
    tb = 0.14 + 0.04 * v
    put(out, cloth(0.45, 260, 700, 5000, 0.5), 0.0, 0.35)
    put(out, thud(0.2, 140, 70, 0.025, click=0.2, body=0.6), 0.0, 0.45)
    put(out, thud(0.6, 78, 36, 0.12, drop=0.05, click=0.3, body=1.0, nf=500), tb, 1.0)
    put(out, grit(0.12, 1200), tb, 0.25)
    put(out, nrm(squelch(0.15, 200, 800, 4, 12, 0.5, 0) * perc(0.15, 0.004, 0.04)), tb, 0.25)
    put(out, wood(0.12, 420, 0.012, 0.3, 0.8), tb + 0.07, 0.35)
    put(out, thud(0.2, 150, 75, 0.02, click=0.2, body=0.5), tb + 0.24 + 0.05 * v, 0.4)
    put(out, slap(0.05, 1100, 0.7, 0.01), tb + 0.24 + 0.05 * v, 0.25)
    return sat(out, 1.3)


def r_drip(v):
    """血が滴る: 水たまりへ落ちる一滴（ぽちゃ = 上へ滑る泡の共鳴 + 小さな当たり）。"""
    out = silence(0.3)
    f0 = (1100, 1450, 900, 1700)[v % 4]
    put(out, nrm(hp(white(0.004), 2500) * perc(0.004, 0.0001, 0.0008)), 0.0, 0.3)
    put(out, bubble(f0, 1.0, 0.9), 0.002, 1.0)
    if v % 2:
        put(out, bubble(f0 * 1.4, 0.4, 0.9), 0.09, 1.0)
    return out


def r_burst(v):
    """体が破裂する: 皮が張り詰めるきしみ → 大きな湿った破裂 → ガスの噴出 → 降る肉片と内臓。"""
    d = 2.0
    out = silence(d)
    put(out, tear(0.3, 200, 20, 250, 1500, 0.95, 4.0, 0.8), 0.0, 0.3)
    t0 = 0.28
    put(out, thud(0.6, 75, 32, 0.14, click=1.0, body=1.0, nf=1800), t0, 1.0)
    put(out, nrm(bp(white(0.25), 1200, 0.4) * perc(0.25, 0.001, 0.06)), t0, 0.8)
    put(out, nrm(squelch(0.4, 200, 2400, 2.5, 25, 0.6, 30) * perc(0.4, 0.002, 0.1)), t0 + 0.002, 0.9)
    put(out, nrm(hp(white(0.9), 1500) * perc(0.9, 0.01, 0.25)), t0 + 0.01, 0.35)
    put(out, splatter(d - t0, 40, 0.35, 1.3), t0 + 0.08, 0.6)
    for _ in range(5):
        t = t0 + R.uniform(0.35, 1.2)
        put(out, thud(0.2, 120, 60, 0.03, click=0.1, body=0.6), t, R.uniform(0.2, 0.4))
        put(out, slap(0.05, R.uniform(800, 1500), 0.8, 0.012), t, R.uniform(0.15, 0.35))
    return sat(out, 1.8)


def r_chop(v):
    """重い刃が肉と骨に食い込む: 刃の「どすっ」（短い金属の鳴り）+ 肉の胴鳴り + 骨の破断 + 湿り。"""
    out = silence(0.75)
    put(out, nrm(hp(white(0.03), 1800) * perc(0.03, 0.0002, 0.004)), 0.0, 0.8)
    put(out, metal(0.25, 820 + 90 * v, "blade", 0.06, 0.3, 0.8, contact=0.0), 0.0, 0.18)
    put(out, thud(0.35, 115, 52, 0.055, click=0.4, body=0.9), 0.0, 1.0)
    put(out, crack(0.22, 6 + v, 0.012, 900, 4500, 0.4), 0.004, 0.75)
    put(out, nrm(squelch(0.25, 220, 1400, 5, 14) * perc(0.25, 0.004, 0.07)), 0.006, 0.5)
    put(out, splatter(0.6, 10, 0.09, 0.9), 0.02, 0.35)
    return sat(out, 1.6)


def r_smash(v):
    """重い打撃が肉と骨を叩き潰す: とても低い衝撃 + 砕ける骨の群れ + 潰れて飛び散る肉。"""
    out = silence(0.95)
    put(out, thud(0.55, 85, 36, 0.11, click=0.5, body=1.0, nf=600), 0.0, 1.0)
    put(out, crack(0.35, 14 + 2 * v, 0.045, 700, 4000, 0.0), 0.002, 0.8)
    put(out, nrm(squelch(0.3, 180, 1300, 4, 16, 0.6, 20) * perc(0.3, 0.003, 0.08)), 0.003, 0.65)
    put(out, splatter(0.8, 20, 0.12, 1.0), 0.02, 0.45)
    put(out, grit(0.1, 1500, 1500, 7000), 0.0, 0.25)
    return sat(out, 2.4)


# =====================================================================
#  ゾンビの声（nr.z.<voice>.<idle|alert|attack|hurt|death>）— VOICE_VOCAB から機械的に
# =====================================================================
VOICE_N = {"idle": 3, "alert": 3, "attack": 3, "hurt": 3, "death": 2}


def _inhale(d=0.16, k=1.0, amp=0.5):
    """息を吸う「ひっ」（高めの擦れ、だんだん強く）。"""
    return amp * whisper(d, [(0, "i"), (d, "schwa")], [(0, 0), (0.8 * d, 1), (d, 0)], k, 2.2, fric=0.3)


def _plan(event, P, v):
    """発声の段取り: [(開始秒, 長さ, u, 母音, 大きさ, utter の引数), ...] と全体の長さ。"""
    lo, hi = P["f0"]
    ex, rg, nz = P.get("extra", ()), P["rough"], P["noise"]
    high = lo >= 300
    main = P["vowel"] if P["vowel"] in VOWELS else "a"
    opn = "scream" if high else ("a" if main in ("o", "u") else main)
    segs, t = [], 0.0
    if event == "idle":
        if "hiccup" in ex:                                 # しゃくり上げる泣き: 短い音節と吸う息
            for i in range(R.integers(4, 7)):
                d = R.uniform(0.16, 0.34)
                pk = R.uniform(0.5, 0.95)
                segs.append((t, d, [(0, pk - 0.25), (0.3 * d, pk), (d, pk - 0.4)],
                             [(0, "schwa"), (0.4 * d, ("a", "i", "e")[i % 3])],
                             [(0, 0), (0.15 * d, 1), (0.6 * d, 0.7), (d, 0)], dict(oq=0.6, tilt=-6, gain=R.uniform(0.6, 1))))
                t += d + R.uniform(0.05, 0.14)
            d = R.uniform(0.7, 1.0)                        # 崩れてうめきに
            segs.append((t, d, [(0, 0.3), (0.3 * d, 0.35), (d, -0.2)], [(0, "a"), (d, "o")],
                         [(0, 0), (0.15 * d, 1), (d, 0)], dict(oq=0.7, creak=0.3, tilt=-7)))
            return segs, t + d
        d = R.uniform(1.2, 2.0) if high else R.uniform(1.7, 2.7)
        m = R.uniform(0.3, 0.6)
        u = [(0, R.uniform(0.05, 0.3)), (0.3 * d, m + 0.15), (0.65 * d, m), (d, R.uniform(-0.25, 0.05))]
        if "rise" in ex:
            u = [(0, -0.05), (0.2 * d, 0.1), (0.75 * d, 0.85), (d, 0.6)]
        vw = [(0, "u"), (0.25 * d, main), (0.7 * d, opn if v % 2 else main), (d, "o" if main != "o" else "u")]
        amp = [(0, 0), (0.22 * d, 1), (0.5 * d, 0.75 + 0.25 * R.random()), (0.8 * d, 0.6), (d, 0)]
        creak = np.clip(0.04 + 0.6 * (tax(d) / d) ** 3, 0, 0.7) * (0.4 + rg)
        segs.append((0.0, d, u, vw, amp, dict(oq=0.7, creak=creak, tilt=-7, bw=1.4)))
        t = d
        if v % 3 == 2 and not high:                       # 息を継いで短い二度目のうめき
            t += R.uniform(0.25, 0.4)
            d2 = R.uniform(0.7, 1.1)
            segs.append((t, d2, [(0, m), (0.3 * d2, m + 0.1), (d2, -0.2)], [(0, "schwa"), (0.3 * d2, main), (d2, "u")],
                         [(0, 0), (0.25 * d2, 0.8), (d2, 0)], dict(oq=0.72, creak=0.25 * (0.4 + rg), tilt=-8, bw=1.4)))
            t += d2
        return segs, t
    if event == "alert":
        d = R.uniform(0.8, 1.3)
        u = [(0, 0.45), (0.06, 0.9), (0.35 * d, 1.05), (0.75 * d, 0.85), (d, 0.4)]
        if "rise" in ex:
            u = [(0, 0.1), (0.5 * d, 0.8), (0.85 * d, 1.1), (d, 0.9)]
        vw = [(0, "schwa"), (0.07, opn), (0.8 * d, opn), (d, main)]
        amp = [(0, 0), (0.03, 1), (0.5 * d, 0.95), (0.85 * d, 0.6), (d, 0)]
        segs.append((0.0, d, u, vw, amp, dict(oq=0.45, rough=min(1.0, rg * 1.15), tilt=-4, bw=1.2, drive=2.2,
                                               growl=0.25 * rg)))
        return segs, d
    if event == "attack":
        d = R.uniform(0.4, 0.75)
        u = [(0, 0.55), (0.04, 0.85), (0.5 * d, 0.75), (d, 0.4)]
        vw = [(0, "growl"), (0.08, opn), (0.7 * d, "growl"), (d, "growl")]
        amp = [(0, 0), (0.015, 1), (0.55 * d, 0.9), (d, 0)]
        segs.append((0.0, d, u, vw, amp, dict(oq=0.4, rough=min(1.0, rg + 0.25), breath=nz + 0.1, tilt=-3.5,
                                               bw=1.5, drive=3.5, growl=0.55, jitter=0.03)))
        return segs, d
    if event == "hurt":
        d = R.uniform(0.22, 0.42)
        u = [(0, 0.75), (0.025, 1.05), (0.4 * d, 0.7), (d, 0.25)]
        vw = [(0, "scream" if high else ("e", "a", "schwa", "u")[v % 4]), (d, "schwa")]
        amp = [(0, 0), (0.01, 1), (0.35 * d, 0.75), (0.8 * d, 0.3), (d, 0)]
        segs.append((0.0, d, u, vw, amp, dict(oq=0.5, breath=nz + 0.1, tilt=-5, drive=1.8)))
        return segs, d
    # death: 長く落ちていくうめき → 擦れ → 喉の泡
    d = R.uniform(1.7, 2.6)
    u = [(0, 0.8), (0.12 * d, 0.95), (0.55 * d, 0.35), (0.85 * d, 0.0), (d, -0.45)]
    vw = [(0, opn), (0.4 * d, main), (0.8 * d, "o"), (d, "u")]
    amp = [(0, 0), (0.04, 1), (0.45 * d, 0.75), (0.8 * d, 0.35), (d, 0)]
    creak = np.clip((tax(d) / d - 0.3) * 1.2, 0.0, 0.9)
    segs.append((0.0, d, u, vw, amp, dict(oq=0.6, rough=min(1.0, rg + 0.15), creak=creak, tilt=-6, bw=1.5,
                                           drive=1.4)))
    return segs, d


def _voiced(event, P, v):
    """声帯のある声: 段取りを（choir4 なら少しずつずらした 4 層で）鳴らす。growl_layer は低い唸りを重ねる。"""
    ex = P.get("extra", ())
    segs, total = _plan(event, P, v)
    layers = ((1.0, 0.0, 1.0, 1.0),)
    if "choir4" in ex:
        layers = ((1.0, 0.0, 1.0, 1.0), (0.955, 0.027, 0.8, 0.96), (1.05, 0.052, 0.7, 1.04), (0.91, 0.083, 0.6, 0.93))
    out = silence(total + 0.2)
    k0 = vtk(P)
    for fs, dl, g, kk in layers:
        for t0, d, u, vw, amp, kw in segs:
            kw = dict(kw)
            gain = kw.pop("gain", 1.0)
            y = utter(P, d, u, vw, amp, fshift=fs, k=k0 * kk, **kw)
            put(out, nrm(y), t0 + dl, g * gain)
    if "growl_layer" in ex and event != "hurt":
        PG = dict(f0=(62.0, 135.0), vowel="o", noise=0.5, rough=1.0, extra=())
        for t0, d, u, vw, amp, kw in segs:
            y = utter(PG, d, [(0, 0.4), (0.5 * d, 0.7), (d, 0.3)], [(0, "growl"), (d, "growl")], amp, oq=0.45,
                      growl=0.8, drive=3.0, tilt=-5, bw=1.6, k=0.85)
            put(out, nrm(y), t0, 0.55)
    if "hiccup" in ex and event == "idle":                 # 音節の合間のしゃくり上げる吸う息
        for (t0, d, *_r), (t1, *_q) in zip(segs, segs[1:]):
            gap = t1 - (t0 + d)
            if gap > 0.04:
                put(out, _inhale(min(0.09, gap), k0, 0.5), t0 + d, 1.0)
    if event == "alert" and v % 2 == 0 and "hiccup" not in ex:
        out = np.concatenate([_inhale(0.14, k0, 0.35), out])
    return out


def _noise_voice(event, P, v):
    """声帯の無い声（hiss / click / whisper_rasp）。"""
    ex, vowel = P.get("extra", ()), P["vowel"]
    if vowel == "s":                                       # 威嚇の息（す・しゃー）
        if event == "idle":
            out = silence(2.6)
            t = 0.0
            for i in range(2):
                d = R.uniform(0.7, 1.1)
                put(out, whisper(d, [(0, "schwa"), (d, "u")], [(0, 0), (0.3 * d, 1), (0.7 * d, 0.8), (d, 0)],
                                 1.0, 2.0, fric=1.3, fric_fc=R.uniform(4200, 5600)), t, 1.0 - 0.3 * i)
                t += d + R.uniform(0.2, 0.35)
            return out[:ns(min(t + 0.1, 2.6))]
        d = {"alert": 0.75, "attack": 0.45, "hurt": 0.25, "death": 1.8}[event]
        e = {"alert": [(0, 0), (0.02, 1), (0.6 * d, 0.8), (d, 0)], "attack": [(0, 0), (0.01, 1), (d, 0)],
             "hurt": [(0, 0), (0.005, 1), (d, 0)], "death": [(0, 0), (0.05, 1), (0.5 * d, 0.5), (d, 0)]}[event]
        y = whisper(d, [(0, "a"), (d, "schwa")], e, 1.0, 1.8, fric=1.6 if event != "death" else 1.0,
                    fric_fc=6000 if event == "alert" else 5000, rasp=0.3 if event in ("attack", "death") else 0.0)
        if event == "attack":
            y = asat(y, 2.5)
            y = mix(y, 0.4 * splatter(d, 6, 0.05, 0.4))
        if event == "death":
            y = mix(y, 0.5 * np.concatenate([np.zeros(ns(d * 0.5)), rattle(d * 0.5) * bell(d * 0.5, 0.4)]))
        return y
    if vowel == "k":                                       # 暗闇を探る舌打ち（反響定位）
        if event == "idle":
            out = silence(2.4)
            t = 0.1
            for _ in range(3):
                n = R.integers(4, 9)
                rate = R.uniform(7, 13)
                for j in range(n):
                    put(out, tongue_click(R.uniform(2300, 3400), R.uniform(6, 10)), t + j / rate, R.uniform(0.6, 1.0))
                t += n / rate + R.uniform(0.25, 0.45)
            put(out, whisper(2.2, [(0, "u"), (2.2, "schwa")], [(0, 0), (1.0, 1), (2.2, 0)], 1.0, 2.0), 0.0, 0.18)
            return out
        d = {"alert": 1.0, "attack": 0.55, "hurt": 0.3, "death": 1.6}[event]
        out = silence(d)
        if event in ("alert", "attack"):                   # 速まって「ジジジ」と鳴る連続の舌打ち
            ph = np.cumsum(np.geomspace(8.0, 70.0 if event == "alert" else 90.0, ns(d))) / SR
            for i in np.nonzero(np.diff(np.floor(ph)) > 0)[0]:
                put(out, tongue_click(R.uniform(2400, 3600), 8.0), i / SR, R.uniform(0.6, 1.0))
            out = out + 0.6 * nrm(whisper(d, [(0, "a"), (d, "schwa")], [(0, 0), (0.7 * d, 1), (d, 0)], 1.0, 1.8,
                                          fric=1.0))
        elif event == "hurt":
            for j in range(3):
                put(out, tongue_click(R.uniform(1800, 2800), 5.0), j * R.uniform(0.04, 0.08), 1.0)
            out = out + 0.7 * nrm(whisper(d, [(0, "i"), (d, "schwa")], [(0, 0), (0.02, 1), (d, 0)], 1.1, 2.0))
        else:
            t = 0.0
            for j in range(9):
                put(out, tongue_click(R.uniform(2000, 3000), 6.0), t, 1.0 - j * 0.1)
                t += 0.08 + j * 0.03
            out = mix(out, 0.4 * np.concatenate([np.zeros(ns(d - 0.8)), rattle(0.8) * bell(0.8, 0.3)]))
        return out
    # whisper_rasp: ささやきの詠唱（0.5 Hz の律動で強まる）
    if event == "idle":
        d = R.uniform(2.6, 3.2)
        out = silence(d + 0.2)
        t, i = 0.0, 0
        while t < d - 0.2:
            ds = R.uniform(0.18, 0.3)
            acc = 0.55 + 0.45 * np.cos(2 * np.pi * 0.5 * t) ** 2
            vw = ("a", "o", "i", "u", "e")[(i + v) % 5]
            put(out, whisper(ds, [(0, "schwa"), (0.35 * ds, vw), (ds, vw)], [(0, 0), (0.25 * ds, 1), (ds, 0)],
                             1.0, 1.7, fric=0.5 if i % 3 == 0 else 0.15, rasp=0.5), t, acc)
            t += ds + R.uniform(0.02, 0.08)
            i += 1
        return out
    d = {"alert": 1.0, "attack": 0.55, "hurt": 0.3, "death": 2.0}[event]
    e = {"alert": [(0, 0), (0.05, 1), (0.7 * d, 0.8), (d, 0)], "attack": [(0, 0), (0.02, 1), (d, 0)],
         "hurt": [(0, 0), (0.01, 1), (d, 0)], "death": [(0, 0), (0.1, 1), (0.6 * d, 0.5), (d, 0)]}[event]
    y = whisper(d, [(0, "schwa"), (0.2 * d, "a"), (d, "o")], e, 1.0, 1.8, fric=0.6, rasp=0.8)
    if event == "attack":
        y = asat(y, 2.5)
    if event == "death":
        y = mix(y, 0.5 * np.concatenate([np.zeros(ns(d * 0.5)), rattle(d * 0.5) * bell(d * 0.5, 0.4)]))
    return y


def _voice_post(y, event, P, v):
    """音源の後に掛ける層（こもり・はぜ・呼吸器・舌打ち・吐き戻し・電子音・反響・火・羽音・リング変調）。"""
    ex = P.get("extra", ())
    d = len(y) / SR
    t = tax(d)
    k = ns(0.02)
    envl = np.convolve(np.abs(y), np.ones(k) / k, mode="same")
    envl = envl / (envl.max() + 1e-9)
    if "lowpass" in ex:
        y = lp(y, 1100.0 if "bubbles" in ex else 1500.0, 2)
    if "bubbles" in ex:
        y = nrm(y) + 0.35 * nrm(bubbles(d, 45, 180, 1100, 0.6) * (0.25 + envl))
    if "crackle" in ex:
        cr = filt(impulses(d, 90.0 * (0.3 + envl), 1.0), g_hp(1500.0), g_lp(7000.0))
        y = nrm(y) + 0.3 * nrm(cr)
    if "respirator" in ex:
        y = lp(y, 2200.0, 1)
        hs = filt(white(d), g_bp(3800.0, 1.6)) * (0.3 + 0.7 * envl)
        y = nrm(y) + 0.22 * nrm(hs)
        if event == "idle":                                # 吸う息で弁が鳴る
            tail = whisper(0.6, [(0, "u"), (0.6, "u")], [(0, 0), (0.5, 1), (0.6, 0)], 1.0, 2.0, fric=1.2,
                           fric_fc=3600.0)
            y = np.concatenate([y, 0.45 * nrm(tail)])
            put(y, mclick(0.03, 2400.0, 0.004), d, 0.2)
    if "clicks" in ex and P["vowel"] != "k":
        n = {"idle": 4, "alert": 3, "attack": 2, "hurt": 1, "death": 2}[event]
        if P["vowel"] == "i":                              # chitter: 声帯のある声に毎秒 18 回の歯鳴り
            ph = np.cumsum(18.0 * (1.0 + 0.25 * lfn(d, 3.0))) / SR       # 毎秒 18 回の歯鳴り
            for i in np.nonzero(np.diff(np.floor(ph)) > 0)[0]:
                put(y, tongue_click(R.uniform(2800, 4200), 7.0), i / SR, 0.35 * R.uniform(0.5, 1.0) * (0.3 + envl[i]))
        else:
            for _ in range(n):
                put(y, tongue_click(R.uniform(2000, 3200), 6.0), R.uniform(0, max(d - 0.05, 0.01)), 0.5)
    if "splatter" in ex and event in ("idle", "attack", "death"):
        tl = 0.5
        sp = silence(tl)
        put(sp, nrm(squelch(0.3, 250, 1600, 3.5, 20, 0.6, 25) * perc(0.3, 0.01, 0.08)), 0.0, 1.0)
        sp = sp + 0.6 * splatter(tl, 14, 0.08, 0.9)
        y = np.concatenate([nrm(y), np.zeros(ns(0.05))])
        y = mix(y, np.concatenate([np.zeros(max(len(y) - ns(0.25), 0)), 0.6 * nrm(sp)]))
    if "beep_rise" in ex:
        bp_ = silence(d)
        if event == "death":
            for i in range(5):
                put(bp_, sine(0.06, 2900.0) * perc(0.06, 0.003, 0.03), 0.1 + i * 0.18, 1.0)
            put(bp_, sine(max(d - 1.1, 0.2), 2900.0) * env_pts(max(d - 1.1, 0.2), [(0, 0), (0.01, 1), (0.6, 1), (max(d - 1.1, 0.2), 0)]),
                1.05, 1.0)
        else:
            ph = np.cumsum(np.geomspace(2.5, 9.0, ns(d))) / SR
            for i in np.nonzero(np.diff(np.floor(ph)) > 0)[0]:
                put(bp_, sine(0.05, 3100.0) * perc(0.05, 0.002, 0.02), i / SR, 1.0)
        y = nrm(y) + 0.25 * bp_
    if "fire" in ex:
        fb = fire_bed(d, 0.5)
        y = nrm(y) + 0.3 * nrm(fb)
    if "buzz" in ex:
        f = 205.0 * (1.0 + 0.04 * lfn(d, 2.0))
        bz = filt(osc(d, f, 30, 0.8) * (0.6 + 0.4 * np.sin(2 * np.pi * 37.0 * t)), g_bp(1100.0, 0.7))
        y = nrm(y) + 0.35 * nrm(bz) * (0.3 + 0.7 * envl)
    if "ringmod" in ex:
        fr = 260.0 + 220.0 * (0.5 + 0.5 * lfn(d, 1.3))
        y = 0.4 * nrm(y) + 0.6 * nrm(y * np.sin(2 * np.pi * np.cumsum(fr) / SR))
    y = nrm(y)
    if "echo" in ex:
        y = room(echoes(y, [(0.11, 0.38), (0.23, 0.24), (0.41, 0.13)]), 1.1, 0.3)
    else:
        y = room(y, 0.32, 0.12)
    return y


def r_voice(key, event, P, v):
    """ゾンビの声の 1 変種。P = VOICE_VOCAB[key]。"""
    y = _voiced(event, P, v) if P.get("f0") else _noise_voice(event, P, v)
    return _voice_post(y, event, P, v)


# =====================================================================
#  武器（nr.w.*）
# =====================================================================
def r_swing_light(v):
    """軽い風切り（ナイフ・鉈・パイプ）: 速い帯域の掃引 + 刃の細い笛。"""
    d = 0.24 + 0.03 * (v % 3)
    return whoosh(d, 600 + 120 * v, 4200 + 300 * v, R.uniform(0.45, 0.6), 1.6, 2.0, tone=0.25)


def r_swing_heavy(v):
    """重い風切り（両手斧・大槌）: 低く長い掃引 + 空気を押す低い「ぶおん」。"""
    d = 0.45 + 0.05 * v
    w = whoosh(d, 170, 1500, 0.55, 1.2, 1.6, tone=0.1)
    vb = bell(d, 0.55)
    low = tvf(white(d), lambda tc, f: g_lp(120.0 + 260.0 * at(vb, tc), 2)(f)) * vb ** 2
    return mix(w, 0.7 * nrm(low))


def r_hit_metal(v):
    """金属音（武器が金属・壁の鉄に当たる）: 打撃の粒 + 板・管・棒の響き（うなり付き）+ 細かいびびり。"""
    kind = ("plate", "pipe", "bar", "plate")[v % 4]
    out = metal(1.0, R.uniform(380, 900), kind, R.uniform(0.25, 0.45), 0.55, 1.3)
    out = mix(out, 0.25 * nrm(hp(white(0.05), 3000) * perc(0.05, 0.0002, 0.008)))
    return out


def r_hit_wood(v):
    """木の打撃音（木の板・柄・バリケード）。"""
    out = silence(0.45)
    put(out, wood(0.4, R.uniform(140, 260), R.uniform(0.03, 0.05), 0.45, 0.8), 0.0, 1.0)
    put(out, thud(0.2, 160, 90, 0.025, click=0.3, body=0.4), 0.0, 0.5)
    put(out, crackles(0.15, 200, 1500, 5000) * perc(0.15, 0.001, 0.03), 0.003, 0.15)
    return out


def r_break(v):
    """武器が壊れる: 木の柄が裂ける（破断の群れ + 繊維）+ 刃の金属が折れる響き + 落ちる破片。"""
    out = silence(1.2)
    put(out, crack(0.4, 22, 0.06, 700, 5200, 0.5), 0.0, 1.0)
    put(out, tear(0.25, 1500, 200, 800, 6000, 0.2, 2.0, 0.2), 0.01, 0.5)
    put(out, metal(0.8, R.uniform(1500, 2400), "blade", 0.25, 0.6, 1.6), 0.0, 0.55)
    for _ in range(4):
        t = R.uniform(0.25, 0.75)
        put(out, metal(0.3, R.uniform(1800, 4000), "bar", 0.06, 0.5, 1.4, n=4), t, R.uniform(0.12, 0.3))
        put(out, wood(0.12, R.uniform(400, 800), 0.012, 0.4, 0.8), t + R.uniform(0.02, 0.1), R.uniform(0.1, 0.25))
    return out


def _stickslip(d, r0, r1, body=(300.0, 1500.0), jit=0.2):
    """きしみ（摩擦の引っかかりの列: 速さ r0 → r1 回/秒）を胴の共鳴に通す（弓・扉・縄・腱）。"""
    rate = np.geomspace(r0, r1, ns(d)) * (1.0 + jit * lfn(d, 12.0))
    ph = np.cumsum(rate) / SR
    pul = np.zeros(ns(d))
    idx = np.nonzero(np.diff(np.floor(ph), prepend=0.0) > 0)[0]
    pul[idx] = np.exp(R.normal(0.0, 0.35, len(idx)))
    k = 6
    ir = modes(0.05, R.uniform(body[0], body[1], k), R.uniform(0.004, 0.015, k), R.uniform(0.4, 1.0, k))
    return nrm(conv(pul, ir)[:ns(d)])


def _string(d, f0, tau=0.15, n=14, drop=0.0, bright=0.6):
    """弦のはじき（倍音ごとに速く消える）。"""
    t = tax(d)
    y = np.zeros(len(t))
    f = f0 * (1.0 - drop * (1.0 - np.exp(-t / 0.05)))
    ph = 2 * np.pi * np.cumsum(f) / SR
    for k in range(1, n + 1):
        if k * f0 < SR * 0.45:
            y += np.sin(k * ph) * np.exp(-t * k ** 0.7 / tau) / k ** (1.0 - bright * 0.5)
    return nrm(y)


def r_bow_draw(v):
    """弓を引く: 弦と弓のきしみ（速まる摩擦）+ 張力の低い唸り + 腕の衣擦れ。"""
    d = 0.75
    out = 0.8 * _stickslip(d, 22, 65, (250, 1300)) * env_pts(d, [(0, 0), (0.1, 0.6), (0.6, 1), (d, 0)])
    out = out + 0.35 * cloth(d, 160, 800, 5000, 0.3)
    out = out + 0.2 * nrm(lp(white(d), 400) * bell(d, 0.7))
    return out


def r_bow_release(v):
    """弓を放つ: 弦の「びん」+ 矢の「ひゅっ」+ 弓の腕の鈍い当たり。"""
    out = silence(0.65)
    put(out, _string(0.5, R.uniform(95, 130), 0.14, 14, 0.06), 0.0, 0.8)
    put(out, nrm(hp(white(0.01), 1500) * perc(0.01, 0.0002, 0.002)), 0.0, 0.6)
    put(out, whoosh(0.18, 2500, 600, 0.15, 1.8, 2.0, tone=0.2), 0.0, 0.6)
    put(out, thud(0.15, 180, 100, 0.02, click=0.2, body=0.3), 0.0, 0.4)
    return out


def r_crossbow_shot(v):
    """クロスボウを撃つ: 引き金の掛け金 + 重い弦の叩き + 太矢の風切り + 台座の「どん」。"""
    out = silence(0.75)
    put(out, mclick(0.04, 2600, 0.004), 0.0, 0.5)
    put(out, _string(0.4, R.uniform(150, 190), 0.07, 12, 0.08, 0.9), 0.008, 1.0)
    put(out, thud(0.25, 150, 70, 0.03, click=0.8, body=0.5, nf=2500), 0.008, 0.9)
    put(out, whoosh(0.25, 3000, 500, 0.12, 2.0, 2.2, tone=0.3), 0.01, 0.55)
    put(out, metal(0.3, 900, "bar", 0.05, 0.4, 1.0, n=4), 0.01, 0.2)
    return sat(out, 1.6)


def r_crossbow_reload(v):
    """クロスボウの装填: 巻き上げのラチェット（速まるカチカチ）+ 張っていく弦のきしみ + 掛け金の「がちん」。"""
    d = 1.4
    out = silence(d)
    ph = np.cumsum(np.geomspace(7.0, 13.0, ns(1.0))) / SR
    for i in np.nonzero(np.diff(np.floor(ph)) > 0)[0]:
        put(out, mclick(0.04, R.uniform(2200, 3000), 0.005), 0.05 + i / SR, R.uniform(0.4, 0.6))
    put(out, 0.5 * _stickslip(1.0, 18, 45, (300, 1400)), 0.05, 0.4)
    put(out, mclick(0.08, 1700, 0.012, 1.2), 1.15, 1.0)
    put(out, thud(0.12, 220, 120, 0.02, click=0.5, body=0.4), 1.15, 0.5)
    return out


def r_gun(v, size, body_f, crack_amt, tail, bright, rt, d, mech, drive=3.0, extra=""):
    """銃の共通（下の各レシピから呼ぶ）。"""
    out = gunshot(d, size, body_f, crack_amt, tail, bright, rt, drive)
    if mech:
        put(out, mclick(0.05, R.uniform(2000, 2800), 0.006, 1.2), R.uniform(0.018, 0.03), 0.18 * mech)
        put(out, mclick(0.05, R.uniform(1600, 2200), 0.008, 1.0), R.uniform(0.045, 0.07), 0.12 * mech)
    if extra == "shell":
        t = R.uniform(0.35, 0.55)
        for j in range(3):
            put(out, metal(0.12, R.uniform(3500, 5200), "bar", 0.03, 0.5, 1.5, n=4), t + j * R.uniform(0.05, 0.1), 0.04 / (j + 1))
    if extra == "ring":
        put(out, metal(0.6, R.uniform(1100, 1400), "bar", 0.15, 0.4, 1.2), 0.002, 0.05)
    if extra == "supersonic":
        put(out, nrm(hp(friedlander(0.004, 0.0003, 1.2), 1500)), 0.0, 0.7)
    return out


def r_pistol(v):
    """拳銃: 乾いた鋭い破裂 + 中くらいの胴 + スライドの金属音 + 薬莢の落ちる音 + 街の残響。"""
    return r_gun(v, 0.8, 130, 1.0, 0.9, 1.0, 1.2, 1.4, 1.0, 3.0, "shell")


def r_revolver(v):
    """リボルバー: 重く太い破裂 + シリンダーの金属の鳴り + 長めの残響。"""
    return r_gun(v, 1.15, 105, 1.1, 1.0, 0.9, 1.5, 1.8, 0.4, 3.2, "ring")


def r_shotgun(v):
    """散弾銃: 胸に響く低い爆音 + 太い胴 + 長い街の残響。"""
    return r_gun(v, 1.6, 78, 0.9, 1.2, 0.75, 1.9, 2.2, 0.0, 3.6)


def r_rifle(v):
    """ライフル: 超音速の鋭い破裂 + 遠くまで転がる長い残響。"""
    return r_gun(v, 1.3, 95, 1.4, 1.35, 1.2, 2.2, 2.4, 0.0, 3.2, "supersonic")


def r_smg(v):
    """短機関銃（連射用に短い）: 軽い破裂 + ボルトの往復の音 + 短い残響。"""
    return r_gun(v, 0.75, 140, 0.9, 0.55, 1.1, 0.6, 0.7, 1.3, 3.0)


def r_reload(v):
    """弾倉の交換: 弾倉を外す掛け金 → 抜ける擦れ → 差し込む「かちっ」→ スライドを引いて放す。"""
    d = 1.35
    out = silence(d)
    put(out, mclick(0.05, 2200, 0.006), 0.0, 0.6)
    put(out, mslide(0.14, 1200, 4500, 0.5), 0.04, 0.4)
    put(out, mslide(0.12, 1200, 4500, 0.5), 0.55, 0.35)
    put(out, mclick(0.07, 1600, 0.01, 1.2), 0.67, 1.0)
    put(out, thud(0.1, 260, 150, 0.015, click=0.4, body=0.3), 0.67, 0.4)
    put(out, mslide(0.09, 1800, 6000, 0.8), 0.95, 0.5)
    put(out, mclick(0.06, 2500, 0.006, 1.3), 1.04, 0.8)
    put(out, mclick(0.08, 1900, 0.01, 1.5), 1.16, 1.0)
    return out


def r_pump(v):
    """ポンプの往復: 引く擦れ + 「がしゃ」→ 押す擦れ + 「がちゃ」。"""
    out = silence(0.55)
    put(out, mslide(0.11, 900, 4000, 0.7), 0.0, 0.6)
    put(out, mclick(0.08, 1500, 0.012, 1.2), 0.1, 1.0)
    put(out, thud(0.1, 240, 140, 0.015, click=0.3, body=0.3), 0.1, 0.4)
    put(out, mslide(0.1, 900, 4000, 0.7), 0.2, 0.55)
    put(out, mclick(0.08, 1700, 0.01, 1.3), 0.3, 1.0)
    return out


def r_empty_click(v):
    """弾切れ: 撃鉄が空を叩く乾いた小さな音。"""
    out = silence(0.12)
    put(out, mclick(0.08, R.uniform(2800, 3600), 0.004, 1.4), 0.0, 1.0)
    put(out, mclick(0.05, R.uniform(1500, 2000), 0.006, 0.8), 0.012, 0.3)
    return out


def r_throw(v):
    """投げる: 腕の風切り + 服の擦れ。"""
    out = silence(0.4)
    put(out, cloth(0.25, 260, 900, 6000, 0.6), 0.0, 0.4)
    put(out, whoosh(0.3, 350, 2600, 0.45, 1.4, 2.0), 0.03, 1.0)
    return out


def r_knife_stick(v):
    """投げナイフが刺さる: 「とすっ」+ 柄のびよーんという震え（振幅の揺れる刃の鳴り）。"""
    out = silence(0.7)
    put(out, thud(0.2, 270, 140, 0.02, click=0.7, body=0.4, nf=2500), 0.0, 1.0)
    put(out, wood(0.15, 380, 0.015, 0.4, 0.6), 0.0, 0.4)
    q = metal(0.6, R.uniform(330, 450), "blade", 0.25, 0.3, 0.6, contact=0.0)
    q = q * (0.55 + 0.45 * np.cos(2 * np.pi * R.uniform(24, 34) * tax(0.6)))
    put(out, q, 0.003, 0.35)
    return out


def r_reload_revolver(v):
    """シリンダーを振り出して 1 発ずつ込める: 振り出し → 空薬莢が落ちる → 3 発込める → 回して閉じる。"""
    d = 2.3
    out = silence(d)
    put(out, mclick(0.06, 2000, 0.008, 1.2), 0.0, 0.8)
    put(out, mslide(0.08, 1500, 5000, 0.6), 0.15, 0.3)
    for j in range(6):
        t = R.uniform(0.3, 0.65)
        put(out, metal(0.15, R.uniform(3200, 5200), "bar", 0.035, 0.5, 1.5, n=4), t, R.uniform(0.08, 0.2))
    for t in (0.85, 1.12, 1.38):
        put(out, mslide(0.06, 2000, 6000, 0.4), t, 0.3)
        put(out, mclick(0.04, R.uniform(2600, 3200), 0.004), t + 0.055, 0.5)
    for j in range(7):
        put(out, mclick(0.03, 3000, 0.003), 1.62 + j * 0.03, 0.25)
    put(out, mclick(0.08, 1700, 0.01, 1.5), 1.9, 1.0)
    return out


def r_reload_shell(v):
    """散弾を 1 発込める: 薬室へ押し込む擦れ + 「かちっ」+ ばねの小さな鳴り。"""
    out = silence(0.4)
    put(out, mslide(0.09, 900, 3500, 0.5), 0.0, 0.5)
    put(out, mclick(0.05, R.uniform(1800, 2300), 0.006, 1.0), 0.085, 0.9)
    put(out, metal(0.15, R.uniform(700, 900), "bar", 0.03, 0.3, 0.8, n=3), 0.09, 0.15)
    return out


def r_bolt_cycle(v):
    """ボルトを引いて戻す: 起こす「かち」→ 引く擦れ → 薬莢 → 押す擦れ → 倒す「がち」。"""
    out = silence(0.75)
    put(out, mclick(0.05, 2200, 0.006, 1.1), 0.0, 0.7)
    put(out, mslide(0.12, 1000, 4500, 0.6), 0.05, 0.6)
    put(out, metal(0.15, 4300, "bar", 0.03, 0.5, 1.4, n=4), 0.22, 0.1)
    put(out, mslide(0.11, 1000, 4500, 0.6), 0.33, 0.6)
    put(out, mclick(0.08, 1600, 0.01, 1.4), 0.46, 1.0)
    return out


def r_mod_fire(v):
    """火炎の改造が燃え上がる: 「ぼっ」と開く炎（暗い所から明るくなる雑音）+ はぜる火。"""
    d = 0.9
    cut = np.geomspace(300.0, 4000.0, ns(d))
    w = tvf(pink(d), lambda tc, f: g_lp(at(cut, tc), 2)(f)) * env_pts(d, [(0, 0), (0.08, 1), (0.3, 0.7), (d, 0)])
    out = nrm(w) + 0.5 * fire_bed(d, 1.0, 0.6) * env_pts(d, [(0, 0), (0.1, 1), (d, 0)])
    put(out, thud(0.3, 80, 45, 0.08, click=0.0, body=0.5, nf=300), 0.0, 0.6)
    return out


def r_mod_shock(v):
    """感電の改造の放電: 鋭い「バチッ」と短いジジジ + 低いビリつきの胴（飽和で詰めて聞こえる大きさに）。"""
    d = 0.5
    out = arc(d, 90, 900, 0.8, 1.6) * perc(d, 0.002, 0.15)
    put(out, nrm(lp(arc(d, 50, 150, 0.95, 0.0), 2500)) * perc(d, 0.003, 0.12), 0.0, 0.6)
    put(out, nrm(hp(white(0.01), 2000) * perc(0.01, 0.0001, 0.002)), 0.0, 0.8)
    return sat(out, 2.5)


def r_mod_bleed(v):
    """出血の改造で血が噴く: 短い噴出 + 飛沫。"""
    d = 0.7
    sp = bp(white(d), 2600, 0.6) * (0.4 + 0.6 * np.abs(lfn(d, 40.0))) * perc(d, 0.005, 0.18)
    return nrm(sp) + 0.5 * nrm(bubbles(d, 50, 500, 2000)) * perc(d, 0.01, 0.2) + 0.4 * splatter(d, 12, 0.1, 0.8)


def r_mod_toxic(v):
    """毒の改造の霧が噴く: しゅっという噴射 + 泡立つ液。"""
    d = 0.8
    hs = filt(white(d), g_bp(4500, 1.0), g_hp(1500)) * env_pts(d, [(0, 0), (0.02, 1), (0.3, 0.5), (d, 0)])
    return nrm(hs) + 0.4 * nrm(bubbles(d, 60, 600, 2500)) * perc(d, 0.02, 0.3)


def r_mod_uv(v):
    """UV の改造が焼く唸り: 一瞬高まる電気の唸り + 焼けるじゅっ。"""
    d = 0.8
    h = hum(d, 60.0 + 10.0 * v, 30, 0.8, 0.5) * env_pts(d, [(0, 0), (0.05, 1), (0.4, 0.6), (d, 0)])
    sz = crackles(d, 400, 2500, 9000, 0.7) * perc(d, 0.02, 0.25)
    return nrm(h) + 0.5 * sz + 0.3 * nrm(hp(white(d), 3000)) * perc(d, 0.01, 0.2)


def r_mod_impact(v):
    """衝撃の改造の小さな破裂: 圧の「ぼん」+ 砂ぼこり。"""
    out = silence(0.8)
    put(out, nrm(hp(friedlander(0.02, 0.0015, 1.3), 60)), 0.0, 1.0)
    put(out, thud(0.4, 110, 45, 0.07, click=0.3, body=0.8), 0.0, 0.9)
    put(out, grit(0.2, 1500, 1500, 8000), 0.01, 0.3)
    return room(sat(out, 2.0), 0.6, 0.2)


# =====================================================================
#  レシピの下請け（ループ・火・噴気・怪物の声）
# =====================================================================
def _looped(d, xf, gen):
    """ループ用: gen(d + xf) を作り、末尾 xf 秒を頭に重ねて継ぎ目の無い d 秒の輪にする（不規則な成分用）。
    周期 d の成分（唸り・モーター）は重ねると +3 dB の山になるので、呼ぶ側で輪にした後に足す。"""
    return loopify(gen(d + xf), xf)


def _fwoom(d=0.5, lo=250.0, hi=3500.0, a=0.1):
    """火が回る「ぼっ」: 暗い所から明るく開く雑音（低域通過の掃引）。"""
    cut = np.geomspace(lo, hi, ns(d))
    w = tvf(pink(d), lambda tc, f: g_lp(at(cut, tc), 2)(f)) * env_pts(d, [(0, 0), (a, 1), (d, 0)], "cos")
    return nrm(w)


def _hiss(d, fc=4000.0, q=1.0, lo=1200.0, hi=11000.0, turb=0.25, rate=18.0):
    """噴き出すガス・湯気: 帯域で整えた雑音を乱流で揺らす（包絡は呼ぶ側で掛ける）。"""
    return nrm(filt(white(d), g_hp(lo), g_pk(fc, q, 8.0), g_lp(hi)) * (1.0 - turb + turb * lfn(d, rate)))


def _sweep(d, lo, hi, q=1.2, src=None):
    """帯域の中心が lo → hi へ滑る雑音（上がる・下がる気配、風）。"""
    c = np.geomspace(lo, hi, ns(d))
    return nrm(tvf(pink(d) if src is None else src, lambda tc, f: g_bp(at(c, tc), q)(f)))


def _burst(d=0.02, T=0.0015, fc=60.0):
    """破裂・発射の圧の山（Friedlander 波の高域だけ）。"""
    return nrm(hp(friedlander(d, T, 1.3), fc))


# 怪物の声の型（VOICE_VOCAB と同じ形。能力・ボスの音で使う）
MONSTER = {
    "growl": dict(f0=(70.0, 230.0), vowel="a", noise=0.5, rough=0.6, extra=()),
    "screech": dict(f0=(480.0, 1500.0), vowel="scream", noise=0.35, rough=0.5, extra=()),
    "howl": dict(f0=(220.0, 750.0), vowel="o", noise=0.2, rough=0.35, extra=("sac_resonance",)),
    "giant": dict(f0=(42.0, 140.0), vowel="a", noise=0.45, rough=0.85, extra=("subbass",)),
    "chant": dict(f0=(62.0, 100.0), vowel="o", noise=0.25, rough=0.3, extra=("tremolo",)),
}


def _cry(kind, d, u, vowels, amp=None, **kw):
    """怪物の声 1 回（MONSTER の型で utter を呼ぶ短縮）。amp を省くと速く立ち上がってゆっくり消える。"""
    amp = amp or [(0, 0), (0.06 * d, 1), (0.7 * d, 0.8), (d, 0)]
    return nrm(utter(MONSTER[kind], d, u, vowels, amp, **kw))


# =====================================================================
#  爆発・属性（nr.fx.*）
# =====================================================================
def r_explosion(v):
    """爆発: 圧の山・重低音・暗くなっていく轟音・降る瓦礫（変種ごとに ガラス / 金属 / 火 の多さを変える）。"""
    glass, metal_amt, fire = ((0.2, 0.0, 0.5), (1.0, 0.0, 0.4), (0.2, 1.0, 0.9))[v % 3]
    return explosion(4.0, 1.0 + 0.08 * v, 1.0, glass, fire, metal_amt)


def r_explosion_big(v):
    """大爆発（プロパンボンベ）: ボンベが裂ける一瞬の噴出 → 巨大な爆発 → 火の玉の轟き → 長い残響と瓦礫の雨。"""
    d = 6.0
    out = silence(d)
    pre = 0.09 + 0.03 * v
    put(out, _hiss(pre, 4200, 2.0, 1800) * env_pts(pre, [(0, 0), (0.01, 0.6), (pre, 1.0)]), 0.0, 0.35)
    put(out, metal(0.5, 380 + 60 * v, "pipe", 0.2, 0.6, 1.5), pre - 0.01, 0.3)
    put(out, explosion(d - pre, 1.6, 1.4, 0.6, 1.0, 1.0), pre, 1.0)
    rd = 3.0
    put(out, nrm(lp(brown(rd), 300.0)) * env_pts(rd, [(0, 0), (0.2, 1), (1.4, 0.6), (rd, 0)], "cos"), pre + 0.1, 0.45)
    put(out, fire_bed(rd, 0.8, 0.0, 0.2) * env_pts(rd, [(0, 0), (0.3, 1), (rd, 0)]), pre + 0.3, 0.25)
    return out


def r_fire_ignite(v):
    """着火: ガスに火が回る「ぼっ」（暗い所から明るく開く雑音と低い胴）→ はぜながら落ち着く炎。"""
    d = 1.3
    out = silence(d)
    a = 0.1 + 0.03 * v
    put(out, _fwoom(0.5, 250, 3500, a), 0.0, 1.0)
    put(out, thud(0.4, 70, 38, 0.12, click=0.0, body=0.7, nf=250), a * 0.6, 0.7)
    fd = d - 0.12
    put(out, fire_bed(fd, 0.9, 0.7, 0.3) * env_pts(fd, [(0, 0), (0.15, 1), (fd, 0)]), 0.12, 0.45)
    return out


def r_fire_loop(v):
    """燃え続ける炎（ループ 2.05 秒。スクリプトが 2 秒ごとに鳴らし直すので少し重なる）。"""
    return _looped(2.05, 0.25, lambda d: fire_bed(d, 0.7 + 0.2 * v, 1.0, 0.3))


def r_electric_zap(v):
    """放電: 空気が裂ける鋭い「バチッ」+ 乱れたパルス列のジジジ + オゾンのしゅー。"""
    d = 0.35 + 0.08 * v
    out = silence(d + 0.05)
    put(out, nrm(hp(white(0.012), 1500) * perc(0.012, 0.0001, 0.0025)), 0.0, 1.0)
    put(out, arc(d, 80 + 20 * v, 1200, 0.9, 1.5) * perc(d, 0.002, d * 0.35, 1.5), 0.002, 0.8)
    put(out, nrm(lp(arc(d, 50, 160, 0.95, 0.0), 2500)) * perc(d, 0.003, d * 0.4, 1.5), 0.002, 0.6)
    put(out, nrm(hp(white(d), 4000)) * perc(d, 0.01, d * 0.5), 0.0, 0.15)
    return sat(out, 2.8)


def r_electric_buzz(v):
    """通電の唸り（ループ 2 秒）: 60 Hz の唸りと磁歪のビリつき（周期的）+ 時々走る小さな放電。"""
    d = 2.0
    h = hum(d, 60.0, 30, 0.9, 0.6, 0.15)
    sp = _looped(d, 0.2, lambda dd: arc(dd, 70, 700, -0.35 + 0.15 * v, 0.8))
    return nrm(h) + 0.3 * sp


def r_toxic_hiss(v):
    """毒ガスの噴出: 高圧のしゅーっ（乱流で揺れる明るい雑音）+ 噴き出しの湿った頭 + 弱まっていく尾。"""
    d = 1.6 + 0.2 * v
    out = _hiss(d, 3800 + 500 * v, 1.2, 1200, 9000) * env_pts(d, [(0, 0), (0.015, 1), (0.25, 0.75), (d, 0)], "cos")
    put(out, nrm(bubbles(0.3, 70, 300, 1400)) * perc(0.3, 0.005, 0.08), 0.0, 0.35)
    put(out, nrm(lp(pink(0.25), 500)) * perc(0.25, 0.004, 0.06), 0.0, 0.5)
    return out


def r_acid_sizzle(v):
    """酸で溶ける: 細かくはぜる泡（揚げ物のような密なパチパチ）+ しゅー + 泡の破裂。"""
    d = 1.8
    e = env_pts(d, [(0, 0), (0.05, 1), (0.6, 0.8), (d, 0)], "cos")
    cr = crackles(d, 900 * e + 20, 2500, 9500, 0.9, 0.0008)
    hs = filt(white(d), g_hp(3000), g_lp(11000)) * e * (0.7 + 0.3 * lfn(d, 9.0))
    b = bubbles(d, 120, 900, 3500, 0.7) * e
    return nrm(cr) + 0.35 * nrm(hs) + 0.4 * nrm(b)


def r_uv_hum(v):
    """UV ライトの唸り（ループ 3.05 秒。スクリプトが 3 秒ごとに鳴らし直す）: 安定器の 120 Hz の唸り
    + 管の高いうなり（周期的）+ かすかなチリチリ（輪にする）。"""
    d = 3.05
    h = nrm(hum(d, 60.0, 36, 0.7, 0.3, 0.1)) + 0.05 * sine(d, 7200.0 + 120.0 * v)
    fz = _looped(d, 0.25, lambda dd: crackles(dd, 18, 4000, 10000, 0.7, 0.001))
    return nrm(h) + 0.12 * fz


def r_uv_burn(v):
    """UV で焼ける: 肉が焼けるじゅっ（密なはぜ）+ 湯気のしゅー + 皮膚がはじける小さなパチッ + 光の唸り。"""
    d = 1.2
    e = env_pts(d, [(0, 0), (0.02, 1), (0.35, 0.7), (d, 0)], "cos")
    cr = crackles(d, 1400 * e + 30, 2000, 9000, 1.0, 0.0006)
    pops = crackles(d, 25 * e + 2, 600, 2500, 0.8, 0.003)
    st = _hiss(d, 5500, 1.0, 2500) * e
    h = hum(d, 60, 20, 0.8, 0.4) * env_pts(d, [(0, 0), (0.03, 1), (d, 0)])
    return nrm(cr) + 0.5 * nrm(pops) + 0.4 * st + 0.25 * nrm(h)


def r_glass_break(v):
    """ガラスが割れる: 割れの鋭い破裂（高域の破断の群れ）→ 大小の破片の鳴り（ガラスのモード）が散らばって落ちる。"""
    d = 1.4
    out = silence(d)
    put(out, crack(0.12, 12, 0.012, 2500, 9000, 0.15), 0.0, 1.0)
    put(out, metal(0.6, R.uniform(1800, 2600), "glass", 0.25, 0.6, 2.0, n=6), 0.0, 0.5)
    for _ in range(26 + 4 * v):
        t = R.exponential(0.25)
        if t < d - 0.2:
            put(out, metal(0.3, R.uniform(2500, 7000), "glass", R.uniform(0.03, 0.1), 0.7, 2.0, n=4, contact=0.5),
                t, R.uniform(0.05, 0.3) * np.exp(-t / 0.6))
    put(out, grit(0.4, 2500, 3000, 12000) * perc(0.4, 0.005, 0.15), 0.01, 0.25)
    return out


def r_metal_clang(v):
    """金属が鳴る: 重い金属の板・管・棒を叩いた響き（うなりのあるモード）+ 当たりの低い胴。"""
    kind = ("plate", "pipe", "bar", "plate")[v % 4]
    f0 = (310, 520, 410, 240)[v % 4]
    out = metal(1.6, f0, kind, 0.7, 0.55, 1.2)
    put(out, thud(0.2, 160, 90, 0.03, click=0.3, body=0.5, nf=1500), 0.0, 0.4)
    return out


def r_gas_hiss(v):
    """ボンベ・ガス管から漏れるガスの噴出（ループ 2 秒）: 細い穴の高い噴流 + 笛のような細い成分 + 乱流のゆらぎ。"""
    def gen(d):
        jet = _hiss(d, 5200 + 700 * v, 1.5, 1500, 12000, 0.2, 15.0)
        wh = filt(white(d), g_bp(2900 + 400 * v, 25.0)) * (0.6 + 0.4 * lfn(d, 3.0))
        return jet + 0.25 * nrm(wh)
    return _looped(2.0, 0.25, gen)


# =====================================================================
#  罠・世界（nr.trap.* / nr.world.*）
# =====================================================================
def r_trap_spike(v):
    """スパイク: 掛け金が外れる「かちっ」→ ばねで突き出す金属の擦れ → 杭が止まる硬い金属の当たり。"""
    out = silence(0.7)
    put(out, mclick(0.05, 2400, 0.008, 1.3), 0.0, 0.5)
    put(out, mslide(0.07, 1500, 7000, 0.8, 0.3), 0.02, 0.6)
    put(out, metal(0.5, R.uniform(700, 900), "bar", 0.18, 0.5, 1.6), 0.085, 0.8)
    put(out, thud(0.2, 170, 80, 0.03, click=0.5, body=0.6, nf=1800), 0.085, 0.6)
    for j in range(3):
        put(out, metal(0.25, R.uniform(1500, 2600), "bar", 0.07, 0.5, 1.4, n=4), 0.09 + 0.006 * j, 0.25)
    return out


def r_trap_beartrap(v):
    """トラバサミ: 強いばねが弾けるきしみ → 顎がかみ合う重い金属の「がしゃん」→ 鎖のじゃらつき。"""
    out = silence(0.9)
    put(out, mclick(0.04, 1800, 0.01, 1.5), 0.0, 0.4)
    put(out, _stickslip(0.03, 900, 3000, (1200, 4000)), 0.0, 0.2)
    put(out, metal(0.7, R.uniform(480, 620), "bar", 0.25, 0.55, 1.8), 0.025, 1.0)
    put(out, thud(0.25, 140, 70, 0.04, click=0.6, body=0.7, nf=2000), 0.025, 0.7)
    for _ in range(8):
        put(out, mclick(0.06, R.uniform(2200, 4200), 0.012, 1.0), 0.06 + R.exponential(0.12), R.uniform(0.1, 0.3))
    return out


def r_trap_electric(v):
    """電気トラップ: 変圧器が唸り上がる → 大きな放電の連続（バチバチ）→ 唸りが落ちる。"""
    d = 1.3
    e = env_pts(d, [(0, 0), (0.06, 1), (0.8, 0.8), (d, 0)], "cos")
    out = 0.4 * nrm(hum(d, 60, 30, 1.0, 0.7, 0.1) * e)
    put(out, arc(d - 0.05, 60, 1500, 0.9, 2.0) * e[:ns(d - 0.05)], 0.05, 1.0)
    put(out, nrm(hp(white(0.015), 1200) * perc(0.015, 0.0001, 0.003)), 0.05, 1.0)
    return sat(out, 2.0)


def r_trap_alarm(v):
    """車のアラーム（ループ 2 秒）: 小さなスピーカーの矩形寄りの音。0 = 上がる掃引の繰り返し、1 = 高低 2 音の交互。
    1 周期を並べて作るので継ぎ目は周期の境目と同じ（輪にする重ねは要らない）。"""
    seg_d, n = (0.5, 4) if v == 0 else (0.25, 8)
    t = tax(seg_d)
    if v == 0:
        f = 900.0 * 2.0 ** (1.1 * t / seg_d)
    else:
        f = np.where(t < seg_d / 2, 1450.0, 1080.0)
    edge = np.clip(np.minimum(t, seg_d - t) / 0.003, 0, 1)
    if v:
        edge = edge * np.clip(np.abs(t - seg_d / 2) / 0.003, 0, 1)
    seg = osc(seg_d, f, 9, 1.0, odd=True) * edge
    # 前後に 2 周期ずつ余分に並べて、スピーカーと屋外の響きを掛けてから真ん中の n 周期を取る（定常の輪）
    x = np.tile(seg, n + 4)
    x = asat(filt(x, g_pk(2800, 2.0, 10), g_hp(600), g_lp(6500)), 2.0, 0.1)
    x = room(x, 0.45, 0.15, damp=1.5)
    k = len(seg)
    return x[2 * k: (2 + n) * k]


def r_trap_click(v):
    """仕掛けの作動音: 掛け金が外れる「かちっ」と、ばねが張る小さな金属音。"""
    out = silence(0.18)
    put(out, mclick(0.05, 2600 + 300 * v, 0.006, 1.3), 0.0, 1.0)
    put(out, mclick(0.06, 1700 + 200 * v, 0.012, 1.0), 0.035 + 0.01 * v, 0.6)
    put(out, nrm(bp(white(0.03), 3500, 2) * perc(0.03, 0.0005, 0.006)), 0.034, 0.2)
    return out


def r_trap_gas_burst(v):
    """ガス管が裂けて火を噴く: 金属の裂ける破裂 → 高圧の噴出 → 引火の「ぼわっ」→ 噴き続ける炎の轟き。"""
    d = 2.4
    out = silence(d)
    put(out, _burst(0.03, 0.002, 80), 0.0, 0.8)
    put(out, metal(0.6, 260 + 40 * v, "pipe", 0.25, 0.5, 1.4), 0.0, 0.5)
    put(out, tear(0.12, 2500, 400, 1500, 7000, 0.2, 2.0, 0.0), 0.0, 0.5)
    jd = d - 0.05
    put(out, _hiss(jd, 3000, 1.0, 900, 9000, 0.2, 20) * env_pts(jd, [(0, 0), (0.01, 1), (jd, 0.3)]), 0.03, 0.45)
    ig = 0.18 + 0.05 * v
    fd = d - ig
    put(out, _fwoom(0.4, 250, 3000, 0.08), ig, 0.9)
    put(out, thud(0.4, 75, 40, 0.1, click=0.0, body=0.7, nf=250), ig, 0.6)
    fe = env_pts(fd, [(0, 0), (0.1, 1), (fd, 0)])
    put(out, nrm(lp(brown(fd), 600) * (0.7 + 0.3 * lfn(fd, 8))) * fe, ig, 0.6)
    put(out, fire_bed(fd, 0.9, 0.4, 0.4) * fe, ig, 0.35)
    return sat(out, 1.6)


def r_trap_uv_burst(v):
    """UV トラップが一斉に点く: 継電器の「がちゃん」の連なり → 安定器の点灯 → 立ち上がる強い唸りと管のうなり。"""
    d = 1.6
    out = silence(d)
    t = 0.02
    for _ in range(4):
        put(out, mclick(0.06, R.uniform(1200, 1900), 0.01, 1.2), t, 0.6)
        put(out, thud(0.08, 220, 120, 0.01, click=0.3, body=0.4, nf=2000), t, 0.3)
        t += R.uniform(0.03, 0.06)
    hd = d - 0.2
    e = env_pts(hd, [(0, 0), (0.15, 1.2), (0.4, 1.0), (hd, 0)], "cos")
    put(out, nrm(hum(hd, 60, 36, 0.7, 0.5, 0.1)) * e, 0.18, 0.6)
    put(out, sine(hd, 7200.0) * e, 0.18, 0.04)
    put(out, crackles(0.6, 300, 3000, 10000, 0.8, 0.0005) * perc(0.6, 0.01, 0.2), 0.2, 0.3)
    return out


def r_trap_rope_snap(v):
    """吊り縄が切れる: 張った縄のきしみ → 繊維が一気にちぎれる → 鋭い破断と、縄の端が鞭のように走る風切り。"""
    out = silence(0.8)
    put(out, _stickslip(0.18, 60, 140, (250, 900)) * env_pts(0.18, [(0, 0), (0.12, 1), (0.18, 0.6)]), 0.0, 0.4)
    put(out, tear(0.12, 2600, 400, 400, 3500, 0.5, 1.5, 0.0), 0.15, 0.8)
    put(out, nrm(hp(white(0.02), 1200) * perc(0.02, 0.0002, 0.004)), 0.26, 1.0)
    put(out, thud(0.15, 200, 110, 0.02, click=0.5, body=0.4, nf=2500), 0.26, 0.4)
    put(out, whoosh(0.35, 500, 3500, 0.25, 1.4, 2.0), 0.27, 0.5)
    return out


def r_trap_wire(v):
    """有刺鉄線が服と肉を引っかく: 棘が布を裂く粒 + 鉄線の擦れ + ばねのように揺れる鉄線の鳴り。"""
    out = silence(0.6)
    put(out, tear(0.3, 1800, 200, 1500, 7000, 0.4, 2.0, 0.3), 0.0, 0.6)
    put(out, mslide(0.25, 2500, 9000, 0.9, 0.35), 0.0, 0.4)
    put(out, metal(0.5, R.uniform(900, 1300), "bar", 0.15, 0.4, 0.8, contact=0.0), 0.03, 0.35)
    put(out, cloth(0.25, 400, 1200, 7000, 0.4), 0.02, 0.4)
    return out


def r_barricade_hit(v):
    """バリケードを叩く: 板の低い木の鳴り + 板・釘のがたつき + 落ちる埃。"""
    out = silence(0.8)
    put(out, wood(0.4, R.uniform(95, 140), 0.06, 0.4, 0.8), 0.0, 1.0)
    put(out, wood(0.25, R.uniform(220, 320), 0.03, 0.5, 0.9), 0.0, 0.7)
    put(out, thud(0.35, 120, 55, 0.05, click=0.4, body=0.8, nf=900), 0.0, 0.6)
    for _ in range(6):
        put(out, wood(0.12, R.uniform(300, 700), 0.015, 0.5, 0.6), 0.015 + R.exponential(0.05), R.uniform(0.2, 0.4))
    put(out, mclick(0.05, R.uniform(1800, 2600), 0.01, 0.8), 0.01, 0.15)
    put(out, grit(0.25, 700, 2500, 9000) * perc(0.25, 0.02, 0.1), 0.04, 0.12)
    return sat(out, 1.5)


def r_door(v):
    """扉: 取っ手の掛け金 + 蝶番のきしみ（摩擦の引っかかりの列）+ 閉まる時の木の胴鳴り（変種 1 は開けるだけ）。"""
    out = silence(1.1)
    put(out, mclick(0.06, 1500 + 200 * v, 0.012, 1.0), 0.0, 0.5)
    put(out, _stickslip(0.6, 35 + 10 * v, 160 + 30 * v, (500, 1600), 0.3) * bell(0.6, 0.5, 1.5), 0.06, 0.5)
    if v != 1:
        put(out, wood(0.5, 85 + 10 * v, 0.08, 0.35, 0.7), 0.7, 0.9)
        put(out, thud(0.4, 110, 50, 0.06, click=0.3, body=0.8, nf=800), 0.7, 0.7)
        put(out, mclick(0.05, 2000, 0.01, 1.2), 0.71, 0.4)
    return room(out, 0.5, 0.2)


# =====================================================================
#  パルクール（nr.pk.*）
# =====================================================================
def r_step_run(v):
    """走る足音（舗装。変種で擦れと砂利の多さを変える）。"""
    return footstep(1.0, 0.35 + 0.1 * (v % 2), 0.2 + 0.12 * v, True)


def r_jump(v):
    """跳ぶ: 踏み切りの靴底の擦れ・砂利 + 衣擦れの風 + 短い息み声（変種 2 は声なし）。"""
    out = silence(0.45)
    put(out, footstep(0.9, 0.8, 0.3, False), 0.0, 0.8)
    put(out, cloth(0.25, 350, 900, 6000, 0.35), 0.02, 0.4)
    put(out, whoosh(0.3, 300, 1800, 0.4, 1.2, 2.0), 0.03, 0.25)
    if v != 2:
        put(out, effort(0.2, "hup"), 0.03, 0.45)
    return out


def r_land_soft(v):
    """軽い着地: 両足がほぼ同時に着く 2 打 + 靴底の擦れ + 衣擦れ。"""
    out = silence(0.4)
    put(out, footstep(1.1, 0.5, 0.3, False), 0.0, 1.0)
    put(out, footstep(1.0, 0.3, 0.2, True), R.uniform(0.02, 0.04), 0.7)
    put(out, cloth(0.2, 300, 900, 5000, 0.3), 0.0, 0.25)
    return out


def r_land_hard(v):
    """重い着地: 体重の乗った低い当たり + 両足の平手 + 散る砂利 + 衣擦れ + 「うっ」。"""
    out = silence(0.7)
    put(out, thud(0.45, 120, 42, 0.07, drop=0.02, click=0.5, body=1.0, nf=900), 0.0, 1.0)
    put(out, footstep(1.6, 0.8, 0.6, False), 0.0, 0.8)
    put(out, footstep(1.4, 0.5, 0.4, True), 0.018, 0.6)
    put(out, grit(0.3, 1200, 1500, 8000) * perc(0.3, 0.005, 0.12), 0.01, 0.35)
    put(out, cloth(0.3, 400, 700, 5000, 0.2), 0.0, 0.3)
    put(out, effort(0.28, "ugh"), 0.03, 0.5)
    return sat(out, 1.4)


def r_roll(v):
    """受け身: 肩 → 背中 → 腰と順に転がる鈍い当たり + 長い衣擦れ + 足で立ち上がる。"""
    out = silence(0.85)
    put(out, cloth(0.6, 500, 500, 5000, 0.45), 0.02, 0.7)
    for j, (t, w) in enumerate(((0.0, 1.0), (0.14, 0.8), (0.27, 0.7))):
        put(out, thud(0.2, 140 - 15 * j, 60, 0.03, click=0.2, body=0.8, nf=800), t + R.uniform(0.0, 0.015), w)
    put(out, grit(0.4, 600, 1500, 7000) * bell(0.4, 0.4), 0.05, 0.25)
    put(out, footstep(1.0, 0.6, 0.3, True), 0.5 + 0.03 * v, 0.7)
    if v == 1:
        put(out, effort(0.18, "hup", 0.4), 0.0, 0.3)
    return out


def r_vault(v):
    """乗り越え: 手のひらが縁を叩く平手 + 体が越える衣擦れの風 + 向こう側への着地。"""
    out = silence(0.65)
    put(out, slap(0.06, 1400, 0.8, 0.01), 0.0, 0.9)
    put(out, thud(0.15, 200, 110, 0.02, click=0.3, body=0.5, nf=1500), 0.0, 0.5)
    put(out, grit(0.1, 900, 2000, 8000), 0.005, 0.2)
    put(out, whoosh(0.3, 250, 1600, 0.5, 1.2, 2.0), 0.05, 0.4)
    put(out, cloth(0.25, 300, 900, 6000, 0.5), 0.06, 0.4)
    put(out, footstep(1.1, 0.5, 0.3, True), 0.36 + 0.03 * v, 0.8)
    return out


def r_grab(v):
    """縁をつかむ: 両手が縁を叩いて握る平手 2 つ + 指のじゃり + 体重が掛かる衣擦れと小さな息み。"""
    out = silence(0.4)
    put(out, slap(0.05, 1500, 0.8, 0.009), 0.0, 1.0)
    put(out, slap(0.05, 1300, 0.8, 0.009), R.uniform(0.015, 0.035), 0.8)
    put(out, thud(0.12, 210, 120, 0.015, click=0.2, body=0.4, nf=1500), 0.0, 0.4)
    put(out, grit(0.12, 700, 2500, 9000), 0.01, 0.3)
    put(out, cloth(0.2, 300, 900, 5000, 0.3), 0.03, 0.35)
    put(out, effort(0.15, "ugh", 0.5), 0.04, 0.25)
    return out


def r_climb(v):
    """よじ登る: 手の平手 + 靴が壁を擦り上げる + 体を引き上げる衣擦れと息み + 縁に足を掛ける。"""
    out = silence(0.75)
    put(out, slap(0.05, 1400, 0.8, 0.01), 0.0, 0.7)
    sc = filt(white(0.3), g_bp(1800, 0.7)) * bell(0.3, 0.3) * (0.6 + 0.4 * lfn(0.3, 40))
    put(out, nrm(sc), 0.05, 0.45)
    put(out, grit(0.3, 500, 1500, 7000) * bell(0.3, 0.3), 0.05, 0.25)
    put(out, cloth(0.45, 350, 800, 5500, 0.5), 0.1, 0.5)
    put(out, effort(0.3, "hup", 0.6), 0.12, 0.4)
    put(out, footstep(0.9, 0.4, 0.2, False), 0.55, 0.6)
    return out


def r_wallrun(v):
    """壁を走る: 壁を蹴る速い 3 歩（擦れの多い靴底）+ 体の風切り。"""
    out = silence(0.6)
    t = 0.0
    for j in range(3):
        put(out, footstep(0.9, 0.9, 0.25, False), t, 0.9 - 0.1 * j)
        t += R.uniform(0.13, 0.16)
    put(out, whoosh(0.55, 300, 2000, 0.5, 1.2, 1.5), 0.0, 0.35)
    return out


def r_slide(v):
    """スライディング: 腰が着く当たり → 布と靴底がコンクリートを擦る長いざらつき（摩擦で弱まる）。"""
    out = silence(1.0)
    put(out, thud(0.2, 130, 60, 0.03, click=0.3, body=0.8, nf=900), 0.0, 0.7)
    sd = 0.9
    e = env_pts(sd, [(0, 0), (0.02, 1), (0.5, 0.65), (sd, 0)], "cos")
    src = white(sd) * (0.7 + 0.3 * lfn(sd, 60)) + impulses(sd, 1500 * e + 20, 0.6)
    put(out, nrm(filt(src, g_bp(1500 + 200 * v, 0.6), g_lp(7000)) * e), 0.01, 0.75)
    put(out, grit(0.7, 1200, 1500, 8000) * e[:ns(0.7)], 0.01, 0.35)
    put(out, cloth(0.8, 500, 600, 5000, 0.2), 0.0, 0.4)
    return out


def r_dropkick(v):
    """ドロップキック: 「はっ」の気合 + 体ごと飛ぶ風切り → 両足が当たる重い打撃（胴鳴り + 平手 2 つ）。"""
    out = silence(0.8)
    put(out, effort(0.25, "hah"), 0.0, 0.6)
    put(out, whoosh(0.3, 250, 2200, 0.7, 1.3, 2.0), 0.0, 0.55)
    t = 0.2
    put(out, thud(0.4, 110, 45, 0.06, click=0.6, body=1.0, nf=1200), t, 1.0)
    put(out, slap(0.07, 1200, 0.7, 0.012), t, 0.8)
    put(out, slap(0.07, 1000, 0.7, 0.012), t + 0.012, 0.6)
    return sat(out, 1.6)


def r_grapple_fire(v):
    """フックの発射: 圧縮ガスの「ぱしゅっ」+ 繰り出されるワイヤーの唸りとがたつき + 遠くでフックが刺さる金属音。"""
    out = silence(0.75)
    put(out, _burst(0.02, 0.0012, 300), 0.0, 0.7)
    put(out, _hiss(0.15, 5000, 1.2, 2000) * perc(0.15, 0.002, 0.04), 0.0, 0.6)
    wd = 0.4
    f = 900 * np.geomspace(1.3, 0.8, ns(wd))
    wire = 0.5 * nrm(osc(wd, f, 8, 1.2)) + nrm(filt(white(wd) + impulses(wd, 150, 0.5), g_bp(3000, 1.0)))
    put(out, nrm(wire) * env_pts(wd, [(0, 0), (0.02, 1), (wd, 0)]), 0.02, 0.35)
    th = 0.42 + 0.03 * v
    put(out, metal(0.3, R.uniform(1400, 1900), "bar", 0.08, 0.5, 1.5), th, 0.4)
    put(out, thud(0.1, 250, 150, 0.01, click=0.4, body=0.4, nf=2000), th, 0.3)
    return out


def r_grapple_reel(v):
    """巻き取り（ループ 1 秒）: モーターの唸り（倍音の多い一定の音）と爪車のカリカリ（周期的）+ ワイヤーの擦れ（輪にする）。"""
    d = 1.0
    f = 220.0 + 40.0 * v                        # f·d が整数なので 1 秒で位相が戻る
    mot = filt(osc(d, f, 14, 1.0), g_pk(1800, 1.5, 6), g_lp(5000))
    clk = silence(d)
    for j in range(30):                          # 30 回/秒の爪（最後の尾も 1 秒の中で消える）
        put(clk, mclick(0.02, 3200 + R.uniform(-200, 200), 0.003, 1.0), j / 30.0, R.uniform(0.6, 1.0))
    wire = _looped(d, 0.2, lambda dd: filt(white(dd), g_bp(2500, 0.8)) * (0.7 + 0.3 * lfn(dd, 20)))
    return nrm(mot) * 0.6 + 0.5 * nrm(clk) + 0.3 * nrm(wire)


def r_glider_open(v):
    """グライダーを開く: 骨組みが伸びる金属の「しゃきん」+ 布が風をはらむ「ばさっ」+ はためき。"""
    out = silence(0.8)
    put(out, mslide(0.1, 1800, 7000, 0.7, 0.4), 0.0, 0.4)
    put(out, mclick(0.05, 2400, 0.008, 1.2), 0.1, 0.5)
    put(out, nrm(filt(pink(0.25), g_bp(350, 0.8), g_lp(2500)) * perc(0.25, 0.006, 0.05)), 0.11, 1.0)
    put(out, cloth(0.3, 600, 400, 5000, 0.2), 0.11, 0.5)
    fl = filt(pink(0.5), g_bp(500, 0.7)) * np.sin(np.pi * (12 + 2 * v) * tax(0.5)) ** 2 * env_pts(0.5, [(0, 1), (0.5, 0)])
    put(out, nrm(fl), 0.2, 0.35)
    return out


def r_glider_wind(v):
    """滑空の風（ループ 2.5 秒）: 体と布を過ぎる風（ゆっくり揺れる帯域の雑音）+ 布のはためき。"""
    def gen(d):
        c = 650.0 * (1.0 + 0.35 * lfn(d, 0.7)) * (1.0 + 0.1 * v)
        w = tvf(pink(d), lambda tc, f: g_bp(at(c, tc), 0.7)(f), win=512) * (0.7 + 0.3 * lfn(d, 1.3))
        fl = filt(white(d), g_bp(320, 1.0)) * (0.5 + 0.5 * lfn(d, 14.0)) ** 2
        return nrm(w) + 0.25 * nrm(fl) + 0.2 * nrm(lp(brown(d), 160))
    return _looped(2.5, 0.3, gen)


def r_breath(v):
    """息切れ: 荒い吸う・吐くの繰り返し（だんだん落ち着く）。"""
    return pant(2.4, 2.3 + 0.2 * v, 1.0 + 0.04 * v)


# =====================================================================
#  ゾンビの足音（nr.zstep.<種類>。sounds.json の step が使う）
# =====================================================================
def r_zstep(kind, v):
    """ゾンビの足音: shuffle 引きずる擦り足 / run 裸足まじりの速い一歩 / heavy 重い一歩 / giant 地響き /
    crawl 手と膝 / claw 爪がコンクリートを叩く / stalk 忍び足。"""
    out = silence(0.9 if kind == "giant" else 0.45)
    if kind == "shuffle":
        sd = 0.28
        put(out, nrm(filt(white(sd) * (0.6 + 0.4 * lfn(sd, 50)), g_bp(1300, 0.6)) * bell(sd, 0.6, 1.5)), 0.0, 0.5)
        put(out, grit(sd, 400, 1500, 7000) * bell(sd, 0.6), 0.0, 0.3)
        put(out, footstep(0.9, 0.2, 0.2, False), sd * 0.75, 0.8)
    elif kind == "run":
        put(out, footstep(1.1, 0.4, 0.3, True), 0.0, 1.0)
        put(out, slap(0.05, 1100, 0.8, 0.01), 0.002, 0.5)
    elif kind == "heavy":
        put(out, thud(0.35, 95, 40, 0.07, drop=0.02, click=0.4, body=1.0, nf=800), 0.0, 0.8)
        put(out, footstep(1.6, 0.4, 0.5, False), 0.0, 0.9)
        put(out, slap(0.06, 900, 0.7, 0.012), 0.002, 0.4)
        put(out, grit(0.15, 900, 1200, 7000), 0.005, 0.3)
    elif kind == "giant":
        put(out, thud(0.8, 62, 26, 0.18, drop=0.04, click=0.3, body=1.0, nf=400), 0.0, 1.0)
        put(out, crack(0.3, 12, 0.05, 300, 2200, 0.5), 0.003, 0.45)
        put(out, grit(0.4, 1500, 1000, 7000), 0.01, 0.45)
        for _ in range(4):
            put(out, thud(0.1, R.uniform(250, 400), 150, 0.012, click=0.5, body=0.4, nf=2500), 0.05 + R.exponential(0.12),
                R.uniform(0.05, 0.15))
        out = room(sat(out, 1.8), 0.9, 0.25, damp=2.0, fd=1000)
    elif kind == "crawl":
        put(out, slap(0.06, 1000, 0.8, 0.012), 0.0, 0.8)
        put(out, thud(0.2, 140, 70, 0.03, click=0.2, body=0.7), 0.05, 0.6)
        put(out, cloth(0.3, 400, 500, 4500, 0.5), 0.0, 0.5)
        put(out, grit(0.25, 400, 1500, 7000) * bell(0.25, 0.5), 0.02, 0.3)
    elif kind == "claw":
        for j in range(3):
            put(out, tongue_click(R.uniform(2600, 4200), 6.0), 0.012 * j + R.uniform(0, 0.006), 0.8 - 0.15 * j)
        put(out, thud(0.12, 180, 100, 0.02, click=0.1, body=0.5, nf=1200), 0.005, 0.25)
    else:  # stalk
        put(out, lp(footstep(0.8, 0.2, 0.1, False), 1800), 0.0, 1.0)
        put(out, cloth(0.2, 200, 700, 4000, 0.4), 0.0, 0.3)
    return out


# =====================================================================
#  プレイヤーの状態（nr.pl.*）
# =====================================================================
def r_heartbeat(v):
    """心音（免疫低下）: 「どくん」= 胸の中のこもった低い 2 拍（lub は強く dub は短く）。飽和で倍音を足し
    小さなスピーカーでも聞こえるようにする。"""
    out = silence(0.75)
    put(out, thud(0.25, 62, 38, 0.06, drop=0.01, click=0.0, body=1.0, nf=150), 0.0, 1.0)
    put(out, thud(0.2, 75, 45, 0.045, drop=0.01, click=0.0, body=1.0, nf=180), 0.24 + 0.02 * v, 0.7)
    return sat(lp(out, 350, 2), 3.0)


def r_immunity_warn(v):
    """免疫の警告: 低い不協和の脈打つ音（短二度でぶつかる 2 音のうなり）+ 耳鳴り + 心音の一打。"""
    d = 1.4
    t = tax(d)
    e = env_pts(d, [(0, 0), (0.05, 1), (0.9, 0.7), (d, 0)], "cos")
    a = osc(d, 110.0 * (1 + 0.06 * v), 16, 1.2) + osc(d, 116.5 * (1 + 0.06 * v), 16, 1.2)
    pulse = 0.55 + 0.45 * np.cos(np.pi * 4.0 * t) ** 2
    out = nrm(lp(a, 1200) * e * pulse)
    put(out, sine(d, 3100.0 + 300 * v) * env_pts(d, [(0, 0), (0.3, 1), (d, 0)]), 0.0, 0.08)
    put(out, thud(0.3, 60, 35, 0.07, click=0.0, body=1.0, nf=150), 0.0, 0.8)
    return out


def r_immunity_restore(v):
    """免疫の回復: 上がっていく明るい鐘の分散和音 + 吸い込む息のような上がる風 + ほっとする柔らかな和音。"""
    d = 1.6
    out = silence(d)
    notes = (523.25, 659.25, 783.99, 1046.5) if v == 0 else (587.33, 739.99, 880.0, 1174.66)
    for j, f in enumerate(notes):
        put(out, fmbell(1.0, f, 2.0, 1.2, 0.5), 0.08 * j, 0.35)
    put(out, _sweep(1.0, 400, 4000, 1.2) * bell(1.0, 0.7), 0.0, 0.25)
    pad = sum(osc(d, ff / 2, 6, 1.5) for ff in notes[:3])
    put(out, nrm(lp(pad, 2000)) * env_pts(d, [(0, 0), (0.3, 1), (d, 0)], "cos"), 0.0, 0.25)
    return out


def r_pl_hurt(v):
    """被弾: 体に入る鈍い当たり + 「うっ」「ぐっ」と詰まる声。"""
    out = silence(0.5)
    put(out, thud(0.25, 130, 60, 0.04, click=0.3, body=0.8, nf=900), 0.0, 0.6)
    put(out, slap(0.05, 1200, 0.7, 0.01), 0.0, 0.3)
    put(out, effort(0.22 + 0.04 * v, "ugh"), 0.01, 1.0)
    return out


def r_heal(v):
    """回復: 柔らかく上がる鐘の 2 音 + 安堵の吐息。"""
    out = silence(1.1)
    put(out, fmbell(0.8, 660 + 40 * v, 2.0, 1.0, 0.4), 0.0, 0.4)
    put(out, fmbell(0.8, 990 + 60 * v, 2.0, 1.0, 0.4), 0.12, 0.35)
    put(out, whisper(0.6, [(0, "a"), (0.6, "schwa")], [(0, 0), (0.1, 1), (0.6, 0)], 1.0, 1.6), 0.15, 0.4)
    return out


def r_levelup(v):
    """スキルポイント獲得: 明るく駆け上がる分散和音（鐘 + 金管）+ きらめき + 低い支え。"""
    out = silence(1.8)
    base = 392.0 if v == 0 else 440.0
    for j, r in enumerate((1.0, 1.25, 1.5, 2.0)):
        put(out, fmbell(1.2, base * r, 3.0, 1.5, 0.6), 0.09 * j, 0.3)
        put(out, horn(0.9, base * r / 2, 18, 1.0) * perc(0.9, 0.01, 0.4), 0.09 * j, 0.06)
    put(out, crackles(1.2, 40, 4000, 10000, 0.6, 0.004) * env_pts(1.2, [(0, 0), (0.2, 1), (1.2, 0)]), 0.3, 0.15)
    put(out, thud(0.6, 70, 50, 0.2, click=0.0, body=0.6, nf=200), 0.27, 0.3)
    return room(out, 1.0, 0.25)


def r_grabbed(v):
    """掴まれた: 腕を掴む湿った平手と服が引かれる衣擦れ + 息をのむ声と詰まる声 + 心臓が跳ねる低音。"""
    out = silence(0.8)
    put(out, slap(0.06, 1100, 0.8, 0.012), 0.0, 0.9)
    put(out, cloth(0.3, 600, 500, 5000, 0.2), 0.0, 0.6)
    put(out, whisper(0.3, [(0, "a"), (0.3, "o")], [(0, 0), (0.05, 1), (0.3, 0)], 1.0, 1.5), 0.04, 0.5)
    put(out, effort(0.25, "ugh", 0.8), 0.1, 0.5)
    put(out, thud(0.4, 70, 38, 0.1, click=0.0, body=1.0, nf=200), 0.0, 0.6)
    return out


# =====================================================================
#  夜と追跡（nr.chase.* / nr.night.start / nr.day.start）
# =====================================================================
def r_chase_start(v):
    """追跡開始: 重低音の一撃 + ぶつかり合う金管の不協和音（強く入って長く残る）+ 金属を弓で擦る高い軋み + 残響。"""
    d = 3.0
    out = silence(d)
    put(out, thud(1.2, 70, 30, 0.35, click=0.0, body=1.0, nf=200), 0.0, 1.0)
    root = 98.0 * (1.06 if v else 1.0)
    hd = 2.2
    he = env_pts(hd, [(0, 0.001), (0.02, 1), (0.4, 0.55), (hd, 0.001)], "db")
    br = sum(horn(hd, root * r, 26, 1.0, 0.003) for r in (1.0, 1.06, 1.414, 1.5, 2.12))
    put(out, nrm(br) * he, 0.0, 0.8)
    sq = _stickslip(1.4, 900, 1250, (2500, 6000), 0.15) * env_pts(1.4, [(0, 0), (0.1, 1), (1.4, 0)], "cos")
    put(out, sq, 0.05, 0.25)
    return fit(room(sat(out, 1.6), 1.8, 0.35, damp=1.8, fd=1500), d)


def r_chase_level_up(v):
    """追跡レベル上昇: 速く駆け上がる上昇音（金管のグリッサンド + 雑音の掃引）→ 強い一撃。"""
    d = 1.6
    out = silence(d)
    rd = 0.6
    f = np.geomspace(150, 600, ns(rd)) * (1.0 + 0.06 * v)
    re = env_pts(rd, [(0, 0.02), (rd, 1)], "db")
    put(out, nrm(lp(osc(rd, f, 20, 1.0), 4000)) * re, 0.0, 0.45)
    put(out, _sweep(rd, 300, 5000, 1.0) * re, 0.0, 0.4)
    put(out, thud(0.8, 75, 32, 0.25, click=0.2, body=1.0, nf=300), rd, 1.0)
    hd = 0.9
    br = sum(horn(hd, 196.0 * (1.0 + 0.06 * v) * r, 26, 1.0, 0.003) for r in (1.0, 1.06, 1.5))
    put(out, nrm(br) * perc(hd, 0.01, 0.35), rd, 0.7)
    return fit(room(sat(out, 1.6), 1.2, 0.3), d)


def r_chase_end(v):
    """追跡を振り切った: 張り詰めた不協和がほどけて下がり、柔らかな長三和音へ落ち着く + 静かに引いていく風。"""
    d = 2.6
    out = silence(d)
    root = 130.81 if v == 0 else 146.83
    e1 = env_pts(1.0, [(0, 0), (0.05, 1), (1.0, 0)], "cos")
    put(out, nrm(lp(osc(1.0, root * 1.06, 10, 1.4) + osc(1.0, root * 1.414, 10, 1.4), 2500)) * e1, 0.0, 0.4)
    e2 = env_pts(d - 0.5, [(0, 0), (0.4, 1), (d - 0.5, 0)], "cos")
    pad = sum(osc(d - 0.5, root * r, 10, 1.6) for r in (1.0, 1.26, 1.5, 2.0))
    put(out, nrm(lp(pad, 1800)) * e2, 0.5, 0.5)
    put(out, _sweep(d, 3000, 300, 1.0) * env_pts(d, [(0, 0), (0.3, 1), (d, 0)], "cos"), 0.0, 0.2)
    return room(out, 1.4, 0.3)


def r_night_start(v):
    """夜が来る: 街に響く巨大な号笛（低い金管の 2 音。ゆっくり立ち上がり、少し持ち上がって、下がりながら消える）
    + 建物のはね返り。"""
    d, hd = 7.0, 5.0
    scoop = env_pts(hd, [(0, 0.94), (0.6, 1.0), (3.8, 1.0), (hd, 0.9)], "cos")
    e = env_pts(hd, [(0, 0), (0.7, 1), (3.6, 0.9), (hd, 0)], "cos")
    f1, f2 = (110.0, 138.6) if v == 0 else (98.0, 123.5)
    y = nrm(horn(hd, f1 * scoop, 30, 0.9, 0.003) + 0.8 * horn(hd, f2 * scoop, 30, 0.9, 0.003)) * e
    y = y + 0.25 * nrm(lp(brown(hd), 120)) * e
    out = silence(d)
    put(out, y, 0.0, 1.0)
    out = echoes(room(out, 2.5, 0.4, damp=2.0, fd=1500), [(0.35, 0.35), (0.8, 0.22), (1.4, 0.12)], 1500)
    return fit(out, d)


def r_day_start(v):
    """夜明け: 遠くで鳴る鐘 2 打（長く残る部分音）+ 明るい長和音の柔らかな広がり + 澄んだ風。"""
    d = 5.0
    out = silence(d)
    f0 = 220.0 + 30.0 * v
    put(out, metal(3.5, f0, "bell", 1.8, 0.4, 0.8), 0.0, 0.6)
    put(out, metal(3.5, f0, "bell", 1.8, 0.4, 0.8), 1.3, 0.5)
    pad = sum(osc(d, f0 * r, 8, 1.6) for r in (1.0, 1.26, 1.5))
    put(out, nrm(lp(pad, 1600)) * env_pts(d, [(0, 0), (1.2, 1), (d, 0)], "cos"), 0.0, 0.3)
    put(out, _sweep(d, 600, 2500, 0.8) * env_pts(d, [(0, 0), (1.5, 1), (d, 0)], "cos"), 0.0, 0.12)
    return fit(room(out, 2.2, 0.35, damp=1.5), d)


# =====================================================================
#  UI・道具（nr.ui.*）
# =====================================================================
def r_ui_click(v):
    """クリック: 小さく硬い機械の「かちっ」+ ごく短い電子音。"""
    out = silence(0.08)
    put(out, mclick(0.04, 3200 + 400 * v, 0.004, 1.2), 0.0, 1.0)
    put(out, beep(0.03, 1800 + 200 * v, 0.001, 0.02, 0.2), 0.0, 0.25)
    return out


def r_ui_open(v):
    """端末を開く: 上がる起動音 2 つ + ブラウン管のような低い唸りの立ち上がり + 静電気のさざめき。"""
    out = silence(0.6)
    put(out, beep(0.07, 880 * (1 + 0.12 * v), 0.002, 0.03), 0.0, 0.5)
    put(out, beep(0.09, 1320 * (1 + 0.12 * v), 0.002, 0.04), 0.07, 0.5)
    put(out, nrm(hum(0.5, 60, 20, 0.6, 0.3, 0.0)) * env_pts(0.5, [(0, 0), (0.05, 1), (0.5, 0)]), 0.0, 0.25)
    put(out, nrm(hp(white(0.3), 3000)) * perc(0.3, 0.005, 0.08), 0.0, 0.15)
    return out


def r_ui_craft(v):
    """クラフト: 部品を組む金属の 2 打 + ねじのラチェット + できあがりの明るい「きん」。"""
    out = silence(0.95)
    put(out, metal(0.2, R.uniform(900, 1300), "bar", 0.06, 0.5, 1.5), 0.0, 0.6)
    put(out, metal(0.2, R.uniform(1100, 1500), "bar", 0.06, 0.5, 1.5), 0.12, 0.5)
    for j in range(5):
        put(out, mclick(0.02, 3000, 0.003, 1.0), 0.25 + 0.03 * j, 0.35)
    put(out, fmbell(0.5, 1568.0 + 100 * v, 2.0, 1.5, 0.3), 0.45, 0.5)
    return out


def r_ui_error(v):
    """エラー: 低いブザーの下がる 2 音。"""
    out = silence(0.4)
    for j, f in enumerate((220.0, 185.0)):
        bd = 0.13
        e = np.minimum(np.clip(tax(bd) / 0.003, 0, 1), np.clip((bd - tax(bd)) / 0.02, 0, 1))
        put(out, nrm(lp(osc(bd, f * (1 + 0.05 * v), 12, 1.0, True), 3000)) * e, 0.16 * j, 0.8)
    return out


def r_ui_combo(v):
    """ゴアコンボ: 低い一撃 + 段（変種）ごとに上がる金属の「ぴん」+ ざらつき。"""
    out = silence(0.6)
    put(out, thud(0.3, 90, 45, 0.06, click=0.3, body=0.9, nf=600), 0.0, 0.8)
    f = 880.0 * 2 ** (v * 4 / 12)
    put(out, fmbell(0.5, f, 3.0, 2.0, 0.25), 0.0, 0.5)
    put(out, fmbell(0.4, f * 1.5, 3.0, 2.0, 0.2), 0.05, 0.3)
    return sat(out, 1.5)


def r_ui_headshot(v):
    """ヘッドショット: 鋭く高い金属の「きん」+ 短い低音 + 骨のぱきっ。"""
    out = silence(0.6)
    put(out, metal(0.5, 2300 + 200 * v, "bell", 0.25, 0.6, 1.8), 0.0, 0.6)
    put(out, thud(0.2, 100, 50, 0.04, click=0.4, body=0.8, nf=800), 0.0, 0.6)
    put(out, crack(0.1, 4, 0.008, 1500, 6000, 0.2), 0.0, 0.4)
    return out


def r_ui_kill(v):
    """撃破: 重く短い低音 + 下がる短い音 + ざらついた砕け。"""
    out = silence(0.6)
    put(out, thud(0.4, 85, 38, 0.08, click=0.5, body=1.0, nf=500), 0.0, 0.8)
    f = np.geomspace(700 + 80 * v, 260, ns(0.25))
    put(out, nrm(osc(0.25, f, 10, 1.3)) * perc(0.25, 0.003, 0.09), 0.0, 0.6)
    put(out, crack(0.15, 6, 0.02, 800, 4000, 0.3), 0.0, 0.5)
    return sat(out, 1.6)


def r_ui_bandage(v):
    """包帯を巻く: 腕に巻きつける衣擦れの繰り返し + 最後に端をちぎる。"""
    out = silence(1.5)
    for j in range(3):
        put(out, cloth(0.3, 300, 900, 6000, 0.5), 0.05 + 0.33 * j + R.uniform(-0.02, 0.02), 0.7)
    put(out, tear(0.18, 1800, 300, 1200, 7000, 0.3, 1.8, 0.0), 1.12, 0.6)
    return out


def r_ui_medkit(v):
    """救急キット: 掛け金 2 つの「ぱちん」+ 蓋が開くプラスチックの響き + 中身をあさる音 + 包帯の衣擦れ。"""
    out = silence(1.6)
    put(out, mclick(0.05, 2100, 0.008, 1.3), 0.0, 0.7)
    put(out, mclick(0.05, 2000, 0.008, 1.3), 0.11, 0.7)
    put(out, wood(0.15, 420, 0.02, 0.6, 0.4), 0.22, 0.4)
    for _ in range(6):
        put(out, mclick(0.04, R.uniform(1500, 3500), 0.004, 0.6), 0.35 + R.uniform(0, 0.5), R.uniform(0.15, 0.3))
    put(out, cloth(0.4, 300, 900, 6000, 0.5), 0.6, 0.6)
    put(out, cloth(0.35, 300, 900, 6000, 0.5), 1.05, 0.5)
    return out


def r_ui_inject(v):
    """注射を打つ: キャップを外す「ぽん」+ 押し当てて作動する「かしゅっ」（空気の抜ける鋭い音）+ 小さく吸う息。"""
    out = silence(0.9)
    put(out, nrm(bp(white(0.03), 900, 2.0) * perc(0.03, 0.001, 0.008)), 0.0, 0.4)
    put(out, mclick(0.05, 2600, 0.006, 1.4), 0.25, 0.7)
    put(out, _hiss(0.35, 6000, 1.5, 2500) * env_pts(0.35, [(0, 0), (0.005, 1), (0.08, 0.6), (0.35, 0)]), 0.255, 0.8)
    put(out, whisper(0.35, [(0, "i"), (0.35, "a")], [(0, 0), (0.25, 1), (0.35, 0)], 1.0, 2.0, fric=0.3), 0.45, 0.3)
    return out


def r_ui_eat(v):
    """食べる: かじる「ぱり」+ 噛むたびの湿った音とくぐもった砕け（3 回）+ 飲み込む。"""
    out = silence(1.2)
    put(out, crack(0.1, 6, 0.015, 1500, 6000, 0.3), 0.0, 0.6)
    for j in range(3):
        t = 0.2 + 0.24 * j + R.uniform(-0.02, 0.02)
        put(out, lp(crack(0.08, 4, 0.02, 600, 2500, 0.4), 2500), t, 0.45)
        put(out, nrm(squelch(0.12, 300, 1200, 4, 15, 0.3, 3)) * perc(0.12, 0.004, 0.04), t + 0.01, 0.3)
    put(out, thud(0.15, 160, 90, 0.03, click=0.0, body=0.5, nf=400), 0.98, 0.35)
    return out


def r_ui_drink(v):
    """缶を開けて飲む: プルタブの「かしゅっ」と炭酸のしゅわ → ごくっごくっ（喉の詰まり + 液の泡）。"""
    out = silence(1.6)
    put(out, mclick(0.03, 2200, 0.005, 1.2), 0.0, 0.5)
    put(out, nrm(filt(white(0.4), g_hp(3000))) * env_pts(0.4, [(0, 0), (0.003, 1), (0.05, 0.4), (0.4, 0)]), 0.01, 0.6)
    put(out, bubbles(0.5, 200, 2500, 7000, 0.5) * perc(0.5, 0.01, 0.2), 0.03, 0.3)
    for j in range(2 + v % 2):
        t = 0.6 + 0.3 * j
        put(out, thud(0.18, 180, 110, 0.035, click=0.1, body=0.7, nf=500), t, 0.5)
        put(out, bubbles(0.15, 60, 250, 800, 0.4), t, 0.4)
    return out


def r_ui_pills(v):
    """錠剤の瓶を振る: プラスチックの瓶の中で錠剤がぶつかる細かい硬い粒（振るたびの塊）。"""
    out = silence(0.8)
    for j in range(2 + v % 2):
        t0 = 0.05 + 0.22 * j
        for _ in range(25):
            put(out, mclick(0.015, R.uniform(2500, 6000), 0.0015, 0.8, 3), t0 + abs(R.normal(0.04, 0.025)),
                R.uniform(0.1, 0.6))
        put(out, wood(0.06, 600, 0.01, 0.6, 0.3), t0, 0.15)
    return out


def r_ui_repair(v):
    """テープを巻いて武器を直す: ダクトテープを引き出すバリバリ（粘着がはがれる密な粒）× 2 + 巻きつける擦れ + ちぎる。"""
    out = silence(1.4)
    for j in range(2):
        t = 0.05 + 0.5 * j
        tp = impulses(0.35, 1800 * bell(0.35, 0.4) + 50, 0.7)
        put(out, nrm(filt(tp, g_bp(2500, 0.6), g_hp(600))), t, 0.7)
        put(out, cloth(0.25, 300, 900, 5000, 0.5), t + 0.3, 0.4)
    put(out, tear(0.12, 2500, 300, 1500, 7000, 0.2, 1.5, 0.0), 1.15, 0.6)
    return out


def r_ui_lockpick(v):
    """鍵穴を探るピック: 細い金属の擦れ + ピンが跳ねる小さな「ちっ」の不規則な列。"""
    d = 0.55
    out = silence(d)
    put(out, mslide(0.4, 3000, 10000, 0.5, 0.4), 0.0, 0.2)
    t = 0.03
    while t < d - 0.05:
        put(out, mclick(0.03, R.uniform(3500, 6000), 0.003, 1.0, 4), t, R.uniform(0.3, 0.8))
        t += R.uniform(0.05, 0.12)
    return out


def r_ui_uv_on(v):
    """UV ライトが点く: スイッチの「かちっ」+ 安定器が上がる高い唸り（掃引）+ 唸りの立ち上がり。"""
    out = silence(0.7)
    put(out, mclick(0.04, 2300, 0.006, 1.2), 0.0, 0.8)
    f = np.geomspace(1800, 6500 + 400 * v, ns(0.4))
    put(out, sine(0.4, f) * env_pts(0.4, [(0, 0), (0.05, 1), (0.4, 0.2)]), 0.02, 0.12)
    put(out, nrm(hum(0.6, 60, 30, 0.7, 0.4, 0.0)) * env_pts(0.6, [(0, 0), (0.08, 1), (0.6, 0)]), 0.03, 0.5)
    return out


def r_ui_zoom(v):
    """双眼鏡のピント: 細かく刻んだつまみの歯車のカリカリ（間隔が少しずつ開く）+ 筒が擦れる小さな音。"""
    out = silence(0.5)
    for j in range(9 + v):
        put(out, mclick(0.02, R.uniform(3800, 4400), 0.002, 0.8, 3), 0.02 + j * (0.03 + 0.002 * j), 0.6)
    put(out, mslide(0.35, 1500, 6000, 0.3, 0.5), 0.02, 0.2)
    return out


# =====================================================================
#  ボス（nr.boss.*。22.05 kHz）
# =====================================================================
def r_boss_intro(v):
    """ボスの出現: 暗く膨らむ低音の気配（雑音と金管の和音のクレッシェンド）→ 地響きの一撃 → 巨体の咆哮 → 長い残響。"""
    d = 5.0
    out = silence(d)
    sw = 1.3
    se = env_pts(sw, [(0, 0.01), (sw, 1)], "db")
    put(out, _sweep(sw, 120, 1500, 0.8, brown(sw) + 0.3 * pink(sw)) * se, 0.0, 0.5)
    ch = sum(horn(sw, f * (1 + 0.05 * v), 20, 1.1, 0.002) for f in (55.0, 58.3, 82.4))
    put(out, nrm(ch) * se, 0.0, 0.4)
    put(out, thud(1.5, 60, 26, 0.4, click=0.2, body=1.0, nf=200), sw, 1.0)
    put(out, _burst(0.05, 0.004, 30), sw, 0.7)
    rd = 2.6
    put(out, _cry("giant", rd, [(0, 0.3), (0.3, 0.8), (1.6, 0.7), (rd, 0.2)], [(0, "growl"), (0.4, "a"), (rd, "o")],
                  [(0, 0), (0.15, 1), (1.8, 0.8), (rd, 0)], oq=0.45, drive=2.5, tilt=-4, growl=0.6, k=0.8), sw + 0.1, 0.9)
    return fit(room(sat(out, 1.8), 2.4, 0.4, damp=2.0, fd=1200), d)


def r_boss_phase(v):
    """ボスの段階移行: 衝撃波（圧の山 + 下がる重低音 + 押し寄せる風）+ 怒りの咆哮 + 不協和の金管の一撃。"""
    d = 3.2
    out = silence(d)
    put(out, _burst(0.05, 0.003, 30), 0.0, 0.8)
    put(out, thud(1.0, 65, 28, 0.3, click=0.0, body=1.0, nf=200), 0.0, 1.0)
    put(out, whoosh(0.9, 150, 1200, 0.15, 0.9, 1.5), 0.0, 0.6)
    put(out, _cry("giant", 2.2, [(0, 0.5), (0.25, 1.0), (1.6, 0.8), (2.2, 0.3)], [(0, "growl"), (0.25, "a"), (2.2, "o")],
                  oq=0.42, drive=3.0, tilt=-4, growl=0.7, k=0.8), 0.15, 0.9)
    br = sum(horn(1.5, 73.4 * (1 + 0.06 * v) * r, 22, 1.0, 0.003) for r in (1.0, 1.06, 1.414))
    put(out, nrm(br) * perc(1.5, 0.01, 0.5), 0.0, 0.4)
    return fit(room(sat(out, 1.8), 2.0, 0.35, damp=2.0, fd=1300), d)


def r_boss_death(v):
    """ボス撃破: 下がっていく断末魔 → 巨体が崩れる重い地響きと破裂する肉 → 解決する低い和音と長い残響。"""
    d = 5.5
    out = silence(d)
    put(out, _cry("giant", 2.0, [(0, 0.9), (0.4, 1.0), (2.0, -0.3)], [(0, "a"), (0.5, "o"), (2.0, "u")],
                  [(0, 0), (0.1, 1), (1.4, 0.7), (2.0, 0)], oq=0.45, drive=2.5, tilt=-4, growl=0.5, k=0.8), 0.0, 0.9)
    t = 1.8
    put(out, thud(1.4, 55, 24, 0.4, drop=0.05, click=0.4, body=1.0, nf=300), t, 1.0)
    put(out, nrm(squelch(0.6, 150, 900, 5, 10, 0.6, 10)) * perc(0.6, 0.01, 0.2), t, 0.5)
    put(out, splatter(1.2, 20, 0.3, 1.3), t + 0.05, 0.35)
    put(out, grit(0.8, 1500, 800, 6000), t, 0.3)
    root = 65.4 * (1 + 0.06 * v)
    pd = d - t - 0.3
    pad = sum(osc(pd, root * r, 14, 1.4) for r in (1.0, 1.5, 2.0, 2.52))
    put(out, nrm(lp(pad, 1500)) * env_pts(pd, [(0, 0), (0.8, 1), (pd, 0)], "cos"), t + 0.3, 0.4)
    return fit(room(sat(out, 1.6), 2.5, 0.4, damp=2.0, fd=1200), d)


# =====================================================================
#  特殊能力（nr.ab.<ability>。spec の ABILITY_VOCAB の fx に合わせる。能力の発動時に鳴る）
# =====================================================================
# 能力の音の表の設定（build_table が使う）: 変種 3 つ / 22.05 kHz（声が主）/ 届く距離 / 音量の分類 / ループ
AB_N3 = {"acid_spit", "ambush_strike", "ankle_grab", "armor_shed", "ash_puff", "blade_dash", "bone_plate",
         "ceiling_ambush", "debris_throw", "dodge", "flee_bolt", "grab_throw_player", "ground_pound", "keep_distance",
         "parkour_chase", "pounce_pin", "pustule_pop", "sac_rupture", "shield_block", "tool_wield", "uv_weak",
         "wall_climb"}
AB_22K = {"boss_phases", "chase_call", "enrage_unarmored", "frenzy", "howl_alarm", "keen_scream", "reanimate",
          "summon_volatiles"}
AB_DIST = {"chase_call": 96, "howl_alarm": 96, "summon_volatiles": 96, "keen_scream": 64, "boss_phases": 96,
           "ground_pound": 64, "detonate": 48, "tank_burst": 64, "gas_cloud_death": 48, "rage_charge": 48,
           "enrage_unarmored": 64, "pustule_pop": 16, "toxic_trail": 16, "keep_distance": 16, "dodge": 16}
AB_CLS = {"ground_pound": "loud", "boss_phases": "loud", "chase_call": "loud", "howl_alarm": "loud",
          "keen_scream": "loud", "tank_burst": "loud", "gas_cloud_death": "loud", "frenzy": "voice",
          "enrage_unarmored": "voice", "reanimate": "voice", "summon_volatiles": "voice", "ember_aura": "loop",
          "toxic_trail": "soft"}
AB_LOOP = {"ember_aura"}


def r_ab_acid_puddle(v):
    """酸だまり: 泡立つ水たまり（大小の泡の破裂）+ じゅうじゅう溶けるはぜ + しゅー。"""
    d = 1.8
    e = env_pts(d, [(0, 0), (0.1, 1), (1.2, 0.8), (d, 0)], "cos")
    out = nrm(bubbles(d, 45, 250, 1200, 0.6) * e)
    out += 0.45 * nrm(crackles(d, 500 * e + 10, 2500, 9000, 0.9, 0.0008))
    out += 0.25 * nrm(filt(white(d), g_hp(3500)) * e * (0.7 + 0.3 * lfn(d, 6)))
    put(out, nrm(squelch(0.3, 200, 900, 4, 10)) * perc(0.3, 0.01, 0.1), 0.0, 0.4)
    return out


def r_ab_acid_spit(v):
    """酸を吐く: 袋が膨らむごぼごぼ（上がっていく泡と喉）→ 「ぺっ」と吐く湿った破裂 + 飛んでいく液の風切り。"""
    out = silence(1.0)
    wd = 0.45
    up = env_pts(wd, [(0, 0), (wd, 1)], "cos")
    put(out, nrm(bubbles(wd, 60, 150, 600, 0.9)) * up, 0.0, 0.5)
    put(out, _cry("growl", wd, [(0, 0.1), (wd, 0.5)], [(0, "u"), (wd, "o")], breath=0.8) * up, 0.0, 0.35)
    put(out, nrm(squelch(0.15, 400, 2200, 5, 25, 0.6, 6)) * perc(0.15, 0.002, 0.04), wd, 1.0)
    put(out, slap(0.05, 1800, 0.7, 0.008), wd, 0.6)
    put(out, whoosh(0.35, 800, 3500, 0.3, 1.2, 2.0), wd + 0.02, 0.4)
    put(out, splatter(0.3, 6, 0.06, 0.6), wd + 0.02, 0.25)
    return out


def r_ab_ambush_strike(v):
    """透明からの不意打ち: 吸い込まれるように膨らむ気配 → 鋭い風切り → 噛みつくような唸り。"""
    out = silence(0.8)
    sw = 0.3
    put(out, nrm(filt(pink(sw), g_bp(1500, 0.7))) * env_pts(sw, [(0, 0.01), (sw, 1)], "db"), 0.0, 0.45)
    put(out, whoosh(0.18, 600, 5000, 0.6, 1.3, 2.0), sw - 0.04, 0.8)
    put(out, _cry("growl", 0.4, [(0, 0.7), (0.4, 0.4)], [(0, "a"), (0.4, "growl")], oq=0.45, drive=2.0, growl=0.4), sw, 0.6)
    return out


def r_ab_ankle_grab(v):
    """足首を掴む: 瓦礫の陰から伸びる腕の擦れ → 足首を握る湿った平手と服の引かれる音 → 低い唸り。"""
    out = silence(0.8)
    put(out, grit(0.12, 600, 1500, 7000), 0.0, 0.3)
    put(out, cloth(0.15, 400, 800, 5000, 0.5), 0.0, 0.4)
    put(out, slap(0.06, 1000, 0.8, 0.012), 0.1, 1.0)
    put(out, nrm(squelch(0.12, 250, 900, 4, 12, 0.4, 2)) * perc(0.12, 0.003, 0.04), 0.1, 0.35)
    put(out, cloth(0.25, 700, 600, 5000, 0.2), 0.11, 0.5)
    put(out, _cry("growl", 0.5, [(0, 0.4), (0.5, 0.2)], [(0, "growl"), (0.5, "u")], oq=0.5, drive=1.5, growl=0.5), 0.14, 0.5)
    return out


def r_ab_armor_shed(v):
    """装甲が外れる: 留め具がちぎれる金属のきしみと破断 + 火花 → 板が落ちて跳ねる金属音。"""
    out = silence(1.2)
    put(out, _stickslip(0.12, 400, 1500, (1500, 5000), 0.3), 0.0, 0.5)
    put(out, nrm(hp(white(0.02), 1500) * perc(0.02, 0.0002, 0.004)), 0.12, 0.8)
    put(out, crackles(0.25, 150, 3000, 10000, 1.0, 0.0006) * perc(0.25, 0.002, 0.07), 0.12, 0.4)
    t, f0 = 0.35, R.uniform(320, 480)
    for j in range(3):
        put(out, metal(0.6, f0 * R.uniform(0.97, 1.03), "plate", 0.35 / (j + 1), 0.5, 1.2), t, 0.8 / (j + 1) ** 0.8)
        t += 0.17 / (j + 1) ** 0.6
    return out


def r_ab_ash_puff(v):
    """灰の雲: 乾いた体が崩れる砂のさらさらと乾いた破断 + 粉が吹き出す柔らかい「ぼふっ」。"""
    out = silence(0.9)
    put(out, nrm(filt(pink(0.35), g_bp(400, 0.6), g_lp(2500)) * perc(0.35, 0.01, 0.1)), 0.0, 0.9)
    e = env_pts(0.7, [(0, 0), (0.05, 1), (0.7, 0)])
    put(out, grit(0.7, 2500, 1500, 9000) * e, 0.0, 0.45)
    put(out, nrm(filt(white(0.7), g_hp(2500))) * e, 0.02, 0.25)
    put(out, crack(0.2, 8, 0.1, 1200, 5000, 0.1), 0.0, 0.3)
    return out


def r_ab_blade_dash(v):
    """刃の突進: かがむ足の擦れ → 一直線に駆ける強い風切り + 刃の金属の鳴り + 通り過ぎる斬撃の風。"""
    out = silence(0.9)
    put(out, grit(0.12, 1000, 1500, 7000), 0.0, 0.4)
    put(out, footstep(1.2, 0.9, 0.4, False), 0.0, 0.5)
    put(out, whoosh(0.45, 400, 4500, 0.35, 1.3, 1.5, 0.15), 0.12, 0.9)
    put(out, metal(0.6, R.uniform(1800, 2400), "blade", 0.25, 0.5, 1.0, contact=0.0), 0.15, 0.25)
    put(out, whoosh(0.15, 1500, 7000, 0.7, 1.5, 2.0), 0.4, 0.6)
    return out


def r_ab_bone_plate(v):
    """骨の兜が弾く: 硬く乾いた骨の当たり（短いモード + 破断の粒）+ 弾かれる刃の「きん」+ 飛ぶ骨片。"""
    out = silence(0.5)
    put(out, metal(0.25, R.uniform(700, 900), "wood", 0.04, 0.6, 1.5), 0.0, 1.0)
    put(out, crack(0.12, 4, 0.008, 1500, 6000, 0.3), 0.0, 0.6)
    put(out, metal(0.4, R.uniform(2600, 3200), "blade", 0.12, 0.5, 1.5, contact=0.0), 0.002, 0.25)
    for _ in range(4):
        put(out, wood(0.06, R.uniform(1500, 3000), 0.008, 0.6, 0.6), 0.05 + R.exponential(0.06), 0.15)
    return sat(out, 2.0)


def r_ab_boss_phases(v):
    """段階移行の咆哮: 衝撃波（圧の山 + 下がる重低音 + 押し寄せる風）+ 長い咆哮 + 残る耳鳴り。"""
    d = 2.8
    out = silence(d)
    put(out, _burst(0.05, 0.003, 30), 0.0, 0.8)
    put(out, thud(1.0, 65, 28, 0.3, click=0.0, body=1.0, nf=200), 0.0, 0.9)
    put(out, whoosh(0.9, 150, 1200, 0.15, 0.9, 1.5), 0.0, 0.6)
    put(out, _cry("giant", 2.4, [(0, 0.4), (0.3, 0.9), (1.8, 0.75), (2.4, 0.3)], [(0, "growl"), (0.3, "a"), (2.4, "o")],
                  oq=0.45, drive=2.5, tilt=-4, growl=0.6), 0.1, 1.0)
    put(out, sine(1.8, 3600.0) * env_pts(1.8, [(0, 0), (0.1, 1), (1.8, 0)]), 0.1, 0.03)
    return fit(room(sat(out, 1.8), 1.8, 0.3, damp=2.0, fd=1400), d)


def r_ab_ceiling_ambush(v):
    """天井から落ちる: ぱらぱら降る砂ぼこり + かすれた息 → 落ちる風切り → 重い着地と唸り。"""
    out = silence(1.2)
    for _ in range(14):
        put(out, grit(0.05, 900, 2500, 9000), R.uniform(0.0, 0.45), R.uniform(0.05, 0.2))
    put(out, whisper(0.45, [(0, "a"), (0.45, "i")], [(0, 0), (0.2, 1), (0.45, 0)], 0.9, 2.2, rasp=0.5), 0.05, 0.35)
    put(out, whoosh(0.3, 200, 1800, 0.7, 1.2, 2.0), 0.45, 0.5)
    put(out, thud(0.45, 110, 45, 0.07, click=0.5, body=1.0, nf=900), 0.72, 1.0)
    put(out, footstep(1.6, 0.6, 0.6, False), 0.72, 0.6)
    put(out, _cry("growl", 0.45, [(0, 0.6), (0.45, 0.3)], [(0, "a"), (0.45, "growl")], oq=0.45, drive=2.2, growl=0.5),
        0.75, 0.6)
    return out


def r_ab_chase_call(v):
    """追跡を呼ぶ金切り声: 遠くまで届く長い叫び（大きく開いた口・ゆがみ）+ 街のはね返り。"""
    d = 2.0
    y = _cry("screech", d, [(0, 0.2), (0.25, 0.85), (1.2, 0.95), (d, 0.5)], [(0, "a"), (0.2, "scream"), (d, "scream")],
             [(0, 0), (0.08, 1), (1.5, 0.85), (d, 0)], oq=0.42, drive=2.5, tilt=-3, k=1.15, fshift=1.0 - 0.08 * v)
    return echoes(room(y, 1.4, 0.3, damp=1.8, fd=1800), [(0.3, 0.3), (0.65, 0.18), (1.1, 0.1)], 1800)


def r_ab_debris_throw(v):
    """瓦礫を投げる: 地面がもぎ取られる砕け（低い破断 + 砂利）+ 力む唸り → 重い風切り。"""
    out = silence(1.6)
    put(out, crack(0.5, 18, 0.3, 300, 2500, 0.8), 0.0, 0.9)
    put(out, grit(0.6, 1500, 800, 7000), 0.02, 0.5)
    put(out, thud(0.4, 90, 40, 0.08, click=0.3, body=0.8), 0.0, 0.6)
    put(out, _cry("growl", 0.7, [(0, 0.3), (0.5, 0.7), (0.7, 0.9)], [(0, "growl"), (0.7, "a")], oq=0.45, drive=2.0, growl=0.5),
        0.2, 0.6)
    put(out, whoosh(0.5, 120, 1200, 0.45, 1.0, 1.5), 0.9, 0.9)
    return out


def r_ab_detonate(v):
    """自爆の秒読み（fuse 1.5 秒）: 速まるビープ（高さも上がる）+ 膨らむ結節の泡立ちと高まる唸り。爆発は別の音。"""
    d = 1.55
    out = silence(d)
    t = 0.0
    while t < d - 0.05:
        u = t / d
        put(out, beep(0.05, 1400.0 * 2 ** (u * 0.8), 0.002, 0.015, 0.5), t, 0.4 + 0.3 * u)
        t += 0.32 * (1.0 - 0.82 * u)
    sw = env_pts(d, [(0, 0.05), (d, 1)], "db")
    put(out, nrm(bubbles(d, 70, 150, 900, 0.8)) * sw, 0.0, 0.35)
    put(out, nrm(lp(osc(d, np.geomspace(90, 260, ns(d)), 12, 1.0), 1500)) * sw, 0.0, 0.3)
    put(out, nrm(squelch(d, 150, 700, 6, 8, 0.5, 0)) * sw, 0.0, 0.2)
    return out


def r_ab_dodge(v):
    """横跳びで避ける: 素早い体の風切り + 足の擦れ + 着地。"""
    out = silence(0.5)
    put(out, whoosh(0.22, 300, 2600, 0.5, 1.3, 2.0), 0.0, 0.8)
    put(out, footstep(1.0, 0.9, 0.4, False), 0.0, 0.5)
    put(out, footstep(1.1, 0.6, 0.4, True), 0.24, 0.7)
    put(out, cloth(0.2, 400, 900, 6000, 0.4), 0.02, 0.35)
    return out


def r_ab_ember_aura(v):
    """火の粉をまとう（ループ 2 秒）: ちりちり燃える細かいはぜと小さな炎のゆらぎ。"""
    return _looped(2.0, 0.25, lambda d: fire_bed(d, 1.3 + 0.2 * v, 0.35, 0.3))


def r_ab_enrage_unarmored(v):
    """怒り狂う: 胸を叩く低い連打 → 長い咆哮（ゆがみ）+ 体から噴く湯気のしゅー。"""
    out = silence(2.4)
    for j in range(3):
        put(out, thud(0.25, 95, 50, 0.05, click=0.3, body=1.0, nf=700), 0.12 * j, 0.6)
    put(out, _cry("giant", 1.9, [(0, 0.4), (0.25, 1.0), (1.4, 0.85), (1.9, 0.4)], [(0, "growl"), (0.25, "a"), (1.9, "o")],
                  oq=0.42, drive=3.0, tilt=-4, growl=0.7, k=0.85), 0.35, 1.0)
    put(out, _hiss(1.6, 5000, 1.0, 2500) * env_pts(1.6, [(0, 0), (0.2, 1), (1.6, 0)], "cos"), 0.6, 0.2)
    return sat(out, 1.5)


def r_ab_fire_trail(v):
    """燃える足跡: 足元で次々に燃え上がる「ぼっ」の連なり + はぜる火。"""
    d = 1.4
    out = silence(d)
    for j in range(3):
        put(out, _fwoom(0.35, 300, 2500, 0.06), 0.3 * j + R.uniform(0, 0.05), 0.7 - 0.1 * j)
    put(out, fire_bed(d, 1.0, 0.5, 0.3) * env_pts(d, [(0, 0), (0.1, 1), (d, 0)]), 0.0, 0.4)
    return out


def r_ab_flashlight_beam(v):
    """懐中電灯が見つけた: 電灯の「かちっ」と電球の小さな唸り + 短い驚きの唸り声。"""
    out = silence(0.9)
    put(out, mclick(0.04, 2400, 0.006, 1.1), 0.0, 0.5)
    put(out, nrm(hum(0.5, 60, 15, 0.6, 0.3, 0.0)) * perc(0.5, 0.01, 0.2), 0.0, 0.12)
    put(out, _cry("growl", 0.55, [(0, 0.5), (0.15, 0.9), (0.55, 0.5)], [(0, "a"), (0.55, "growl")], oq=0.5, drive=1.6,
                  growl=0.3), 0.05, 1.0)
    return out


def r_ab_flee_bolt(v):
    """逃げ出す: 甲高く引きつった短い悲鳴 + 素早い軽い足音の連なり。"""
    out = silence(0.9)
    put(out, _cry("screech", 0.35, [(0, 0.3), (0.1, 0.6), (0.35, 0.2)], [(0, "i"), (0.35, "e")], oq=0.5, drive=1.2, k=1.2,
                  fshift=0.8), 0.0, 0.7)
    t = 0.1
    for j in range(5):
        put(out, footstep(0.8, 0.6, 0.3, j % 2 == 0), t, 0.5)
        t += R.uniform(0.13, 0.16)
    return out


def r_ab_frenzy(v):
    """狂乱: 速く荒い息（喉の擦れ）→ 引き裂くような叫び + 噴き出す湯気。"""
    out = silence(2.1)
    t = 0.0
    for _ in range(4):
        put(out, whisper(0.14, [(0, "a"), (0.14, "schwa")], [(0, 0), (0.02, 1), (0.14, 0)], 0.85, 1.8, rasp=0.8), t, 0.6)
        t += 0.17
    put(out, _cry("growl", 1.3, [(0, 0.6), (0.2, 1.1), (1.0, 1.0), (1.3, 0.5)], [(0, "a"), (0.2, "scream"), (1.3, "a")],
                  oq=0.42, drive=3.0, tilt=-3.5, growl=0.4), 0.68, 1.0)
    put(out, _hiss(1.2, 5000, 1.0, 2500) * env_pts(1.2, [(0, 0), (0.1, 1), (1.2, 0)], "cos"), 0.7, 0.15)
    return out


def r_ab_gas_cloud_death(v):
    """毒袋の破裂: 水っぽい爆音（低い破裂 + ぐちゃっ + 泡）→ 濃いガスが噴き広がるしゅー。"""
    d = 2.3
    out = silence(d)
    put(out, _burst(0.04, 0.003, 40), 0.0, 0.8)
    put(out, thud(0.5, 85, 35, 0.12, click=0.3, body=1.0, nf=500), 0.0, 1.0)
    put(out, nrm(squelch(0.4, 200, 1200, 5, 12, 0.6, 10)) * perc(0.4, 0.005, 0.12), 0.0, 0.8)
    put(out, splatter(1.0, 18, 0.15, 1.0), 0.02, 0.4)
    gd = d - 0.05
    put(out, _hiss(gd, 2500, 0.8, 800, 8000, 0.25, 12) * env_pts(gd, [(0, 0), (0.05, 1), (0.6, 0.6), (gd, 0)], "cos"),
        0.05, 0.5)
    put(out, nrm(lp(brown(gd), 300)) * env_pts(gd, [(0, 0), (0.1, 1), (gd, 0)], "cos"), 0.03, 0.35)
    return sat(out, 1.5)


def r_ab_grab_throw_player(v):
    """掴んで投げる: 掴む重い平手と服の引き → 持ち上げる力みの唸り → 投げ飛ばす大きな風切り。"""
    out = silence(1.4)
    put(out, slap(0.07, 900, 0.8, 0.015), 0.0, 1.0)
    put(out, thud(0.25, 120, 60, 0.04, click=0.3, body=0.8), 0.0, 0.6)
    put(out, cloth(0.35, 700, 600, 5000, 0.3), 0.0, 0.6)
    put(out, _cry("giant", 0.8, [(0, 0.3), (0.6, 0.8), (0.8, 1.0)], [(0, "growl"), (0.8, "a")], oq=0.45, drive=2.0,
                  growl=0.6), 0.2, 0.7)
    put(out, whoosh(0.5, 150, 1500, 0.4, 1.0, 1.5), 0.85, 1.0)
    return out


def r_ab_ground_pound(v):
    """地面を叩く衝撃波: 拳が地面を打つ巨大な低音（圧の山 + 下がる重低音）+ コンクリートの割れ + 跳ねる瓦礫 + 地鳴り。"""
    d = 2.0
    out = silence(d)
    put(out, _burst(0.04, 0.003, 35), 0.0, 0.9)
    put(out, thud(1.2, 70, 26, 0.3, drop=0.05, click=0.6, body=1.0, nf=600), 0.0, 1.0)
    put(out, crack(0.4, 20, 0.12, 400, 3000, 0.8), 0.005, 0.7)
    for _ in range(12):
        t = 0.1 + R.exponential(0.3)
        if t < d - 0.2:
            put(out, thud(0.12, R.uniform(200, 350), 120, 0.015, click=0.5, body=0.5, nf=2500), t, R.uniform(0.05, 0.2))
    put(out, grit(0.6, 2000, 1500, 8000), 0.02, 0.4)
    put(out, nrm(lp(brown(1.6), 150)) * env_pts(1.6, [(0, 0), (0.05, 1), (1.6, 0)], "cos"), 0.0, 0.5)
    return fit(room(sat(out, 2.2), 1.2, 0.3, damp=2.0, fd=1200), d)


def r_ab_heavy_body(v):
    """重い体が受け止める: 分厚い肉に吸われる鈍い「どむっ」+ 動じない低い鼻息。"""
    out = silence(0.8)
    put(out, thud(0.45, 95, 40, 0.09, click=0.2, body=1.0, nf=500), 0.0, 1.0)
    put(out, nrm(squelch(0.2, 150, 700, 4, 8, 0.3, 0)) * perc(0.2, 0.004, 0.06), 0.0, 0.35)
    put(out, whisper(0.4, [(0, "u"), (0.4, "schwa")], [(0, 0), (0.05, 1), (0.4, 0)], 0.75, 2.0, rasp=0.6), 0.12, 0.45)
    return out


def r_ab_hive_summon(v):
    """胞子袋から産み落とす: 袋が裂ける湿った音（粘る裂け + ぐちゃっ）→ 粘液と一緒に落ちる体 + 吹き出す胞子。"""
    out = silence(1.8)
    put(out, tear(0.4, 900, 60, 300, 2500, 0.6, 3.0, 0.5), 0.0, 0.7)
    put(out, nrm(squelch(0.6, 180, 1100, 6, 10, 0.5, 14)) * env_pts(0.6, [(0, 0), (0.1, 1), (0.6, 0)]), 0.1, 0.7)
    put(out, thud(0.4, 110, 50, 0.06, click=0.2, body=0.9, nf=700), 0.55, 0.8)
    put(out, splatter(0.8, 14, 0.12, 1.2), 0.55, 0.4)
    put(out, _hiss(0.8, 4500, 1.0, 2000) * env_pts(0.8, [(0, 0), (0.05, 1), (0.8, 0)], "cos"), 0.15, 0.25)
    return out


def r_ab_howl_alarm(v):
    """喉の袋の遠吠え: 袋が膨らむ低いごぼごぼ → サイレンのように上がる長い遠吠え（喉の袋の共鳴）→ 街のはね返り。"""
    d = 4.6
    out = silence(d)
    inf = 0.8
    put(out, nrm(bubbles(inf, 40, 120, 500, 0.9)) * env_pts(inf, [(0, 0), (inf, 1)], "cos"), 0.0, 0.4)
    put(out, _cry("howl", inf, [(0, -0.2), (inf, 0.0)], [(0, "u"), (inf, "u")], [(0, 0), (inf, 0.5)], breath=0.8), 0.0, 0.4)
    hd = 2.6
    put(out, _cry("howl", hd, [(0, 0.0), (0.9, 0.85), (1.9, 1.0), (hd, 0.6)], [(0, "u"), (0.6, "o"), (1.6, "a"), (hd, "o")],
                  [(0, 0), (0.25, 1), (2.0, 0.9), (hd, 0)], oq=0.55, drive=1.2, tilt=-4.5, fshift=1.0 + 0.07 * v), inf, 1.0)
    return fit(echoes(room(out, 1.6, 0.3, damp=1.8, fd=1600), [(0.4, 0.3), (0.9, 0.18), (1.5, 0.1)], 1600), d)


def r_ab_keen_scream(v):
    """金切り声の衝撃: 突き刺す高い叫び（ゆがみ）+ 空気が揺れる低い圧 + 残る耳鳴り。"""
    out = silence(2.0)
    put(out, _cry("screech", 1.1, [(0, 0.5), (0.1, 1.05), (0.8, 1.0), (1.1, 0.6)], [(0, "e"), (0.1, "scream"), (1.1, "i")],
                  oq=0.4, drive=3.0, tilt=-3, k=1.2, fshift=1.0 + 0.06 * v), 0.0, 1.0)
    put(out, whoosh(0.8, 100, 900, 0.15, 0.8, 1.5), 0.0, 0.5)
    put(out, sine(1.6, 4200.0) * env_pts(1.6, [(0, 0), (0.2, 1), (1.6, 0)], "cos"), 0.3, 0.06)
    return out


def r_ab_keep_distance(v):
    """距離を取る: 後ずさる擦り足 2 歩 + 歯の間から漏れる威嚇の息。"""
    out = silence(0.8)
    put(out, footstep(0.8, 1.0, 0.4, False), 0.0, 0.5)
    put(out, footstep(0.8, 1.0, 0.4, False), 0.26, 0.45)
    put(out, whisper(0.55, [(0, "i"), (0.55, "i")], [(0, 0), (0.1, 1), (0.55, 0)], 1.0, 1.8, fric=0.8, fric_fc=4800,
                     rasp=0.4), 0.05, 0.6)
    return out


def r_ab_long_grab_drag(v):
    """長い腕で掴んで引きずる: 伸びる腕の筋のきしみと風切り → 掴む平手 → 体が地面を引きずられる長い擦れ。"""
    out = silence(1.8)
    put(out, _stickslip(0.3, 50, 120, (200, 700)) * bell(0.3, 0.6), 0.0, 0.3)
    put(out, whoosh(0.3, 300, 2500, 0.6, 1.2, 2.0), 0.0, 0.5)
    put(out, slap(0.07, 1000, 0.8, 0.014), 0.3, 1.0)
    put(out, nrm(squelch(0.15, 250, 900, 4, 12, 0.4, 2)) * perc(0.15, 0.003, 0.05), 0.3, 0.3)
    dd = 1.2
    e = env_pts(dd, [(0, 0), (0.05, 1), (0.9, 0.7), (dd, 0)], "cos")
    put(out, nrm(filt(white(dd) * (0.6 + 0.4 * lfn(dd, 25)), g_bp(900, 0.6), g_lp(5000)) * e), 0.4, 0.6)
    put(out, grit(dd, 800, 1500, 7000) * e, 0.4, 0.3)
    put(out, cloth(dd, 300, 600, 5000, 0.4), 0.4, 0.4)
    return out


def r_ab_long_leap(v):
    """大跳躍: しゃがむ筋のきしみ → 踏み切りの重い当たりと土煙 → 長い風切り → 着地の衝撃。"""
    out = silence(1.4)
    put(out, _stickslip(0.2, 40, 90, (200, 600)), 0.0, 0.2)
    put(out, thud(0.3, 110, 50, 0.05, click=0.5, body=0.9, nf=900), 0.2, 0.8)
    put(out, grit(0.3, 1500, 1500, 8000), 0.2, 0.4)
    put(out, whoosh(0.6, 200, 2200, 0.5, 1.0, 1.5), 0.25, 0.7)
    put(out, thud(0.5, 95, 38, 0.09, click=0.6, body=1.0, nf=900), 0.9, 1.0)
    put(out, grit(0.4, 1500, 1500, 8000), 0.9, 0.4)
    return sat(out, 1.5)


def r_ab_multi_head(v):
    """余分な頭が潰れる: 湿った破裂（頭蓋の破断 + ぐちゃっ）→ 拍動して噴く血と脳 + 残った頭の苦しむ叫び。"""
    out = silence(1.4)
    put(out, crack(0.2, 10, 0.02, 800, 4500, 0.6), 0.0, 0.9)
    put(out, nrm(squelch(0.35, 250, 1500, 5, 14, 0.6, 10)) * perc(0.35, 0.004, 0.1), 0.0, 0.9)
    put(out, thud(0.3, 140, 60, 0.05, click=0.4, body=0.8), 0.0, 0.6)
    sp = bp(white(0.9), 2200, 0.6) * (0.4 + 0.6 * np.abs(lfn(0.9, 25))) * (0.5 + 0.5 * np.cos(2 * np.pi * 3.0 * tax(0.9)) ** 8)
    put(out, nrm(sp) * env_pts(0.9, [(0, 0), (0.03, 1), (0.9, 0)]), 0.05, 0.4)
    put(out, splatter(1.2, 20, 0.2, 1.0), 0.03, 0.4)
    put(out, _cry("growl", 0.9, [(0, 0.8), (0.2, 1.0), (0.9, 0.4)], [(0, "a"), (0.2, "scream"), (0.9, "o")], oq=0.45,
                  drive=2.0), 0.15, 0.6)
    return out


def r_ab_pack_flank(v):
    """群れの回り込み: 短く鋭い合図の吠え声が 3 方向から重なる（高さと間を変えて）。"""
    out = silence(1.3)
    for j in range(3):
        y = _cry("growl", 0.28, [(0, 0.6), (0.06, 1.0), (0.28, 0.5)], [(0, "a"), (0.28, "o")], oq=0.45, drive=2.0,
                 fshift=1.0 + 0.15 * j + 0.05 * v)
        put(out, y, 0.28 * j + R.uniform(0.0, 0.05), 0.8 - 0.15 * j)
    return room(out, 0.7, 0.25)


def r_ab_parkour_chase(v):
    """屋根まで追う乗り越え: 縁を叩く手 + 壁を蹴る足 + 力む唸り + 向こう側への着地。"""
    out = silence(0.8)
    put(out, slap(0.06, 1200, 0.8, 0.012), 0.0, 0.9)
    put(out, footstep(1.2, 0.9, 0.3, False), 0.08, 0.6)
    put(out, _cry("growl", 0.3, [(0, 0.5), (0.3, 0.7)], [(0, "growl"), (0.3, "a")], oq=0.5, drive=1.6), 0.05, 0.45)
    put(out, whoosh(0.25, 300, 1800, 0.5, 1.2, 2.0), 0.15, 0.4)
    put(out, thud(0.3, 120, 50, 0.04, click=0.4, body=0.9, nf=900), 0.42, 0.8)
    return out


def r_ab_play_dead(v):
    """死んだふりから跳ね起きる: 鋭く吸い込む息 → 関節が鳴る骨の連打と服の擦れ → 不意打ちの唸り。"""
    out = silence(1.5)
    put(out, whisper(0.25, [(0, "a"), (0.25, "o")], [(0, 0), (0.18, 1), (0.25, 0)], 0.9, 2.0, fric=0.2, rasp=0.5), 0.0, 0.6)
    for j in range(4):
        put(out, crack(0.08, 3, 0.006, 1200, 5000, 0.3), 0.25 + 0.07 * j + R.uniform(0.0, 0.02), 0.5)
    put(out, cloth(0.4, 500, 600, 5000, 0.3), 0.25, 0.5)
    put(out, footstep(1.3, 0.6, 0.4, False), 0.55, 0.5)
    put(out, _cry("growl", 0.7, [(0, 0.6), (0.1, 1.0), (0.7, 0.5)], [(0, "a"), (0.7, "growl")], oq=0.42, drive=2.5,
                  growl=0.5), 0.6, 0.9)
    return out


def r_ab_pounce_pin(v):
    """跳びかかって押し倒す: 跳ぶ風切り → 体ごとぶつかる重い当たり + 唸り → 噛みつく（骨の砕け + 湿った肉）。"""
    out = silence(1.2)
    put(out, whoosh(0.3, 250, 2200, 0.7, 1.2, 2.0), 0.0, 0.6)
    put(out, thud(0.4, 100, 42, 0.07, click=0.5, body=1.0, nf=900), 0.28, 1.0)
    put(out, cloth(0.3, 600, 600, 5000, 0.2), 0.28, 0.5)
    put(out, _cry("growl", 0.6, [(0, 0.7), (0.6, 0.4)], [(0, "growl"), (0.6, "a")], oq=0.42, drive=2.5, growl=0.6), 0.3, 0.7)
    put(out, crack(0.15, 5, 0.03, 900, 4000, 0.4), 0.75, 0.6)
    put(out, nrm(squelch(0.25, 250, 1300, 5, 15, 0.5, 4)) * perc(0.25, 0.004, 0.08), 0.75, 0.6)
    return out


def r_ab_pustule_pop(v):
    """膿疱が弾ける: 張った膜が破れる鋭い湿った「ぷちゅっ」+ 飛び散る膿。"""
    out = silence(0.6)
    put(out, nrm(hp(white(0.005), 1500) * perc(0.005, 0.0001, 0.001)), 0.0, 0.7)
    put(out, nrm(squelch(0.18, 500, 2500, 6, 30, 0.5, 10)) * perc(0.18, 0.002, 0.05), 0.0, 1.0)
    put(out, bubble(R.uniform(500, 900), 0.6), 0.01, 0.4)
    put(out, splatter(0.4, 8, 0.05, 0.7), 0.02, 0.4)
    return out


def r_ab_rage_charge(v):
    """突進: 吠える溜め → 速まる重い足音（地響き）+ 押しのける風。壁に当たる衝撃は別の音（gore / fx）。"""
    d = 2.2
    out = silence(d)
    put(out, _cry("giant", 0.8, [(0, 0.4), (0.2, 0.9), (0.8, 0.6)], [(0, "growl"), (0.2, "a"), (0.8, "o")], oq=0.42,
                  drive=2.5, growl=0.6), 0.0, 0.9)
    t, per = 0.75, 0.32
    while t < d - 0.3:
        put(out, thud(0.35, 85, 36, 0.07, click=0.4, body=1.0, nf=600), t, 0.8)
        put(out, grit(0.15, 900, 1500, 7000), t, 0.25)
        t += per
        per = max(0.17, per * 0.85)
    put(out, whoosh(1.2, 120, 900, 0.7, 0.9, 1.0), 0.8, 0.4)
    return sat(out, 1.6)


def r_ab_reanimate(v):
    """蘇らせる詠唱: 喉で低く響く唸りの詠唱（母音がゆっくり移る）+ 伸びる菌糸の湿ったきしみ + 漂う胞子のしゅー。"""
    d = 3.2
    out = silence(d)
    put(out, _cry("chant", d, [(0, 0.3), (1.0, 0.5), (2.0, 0.4), (d, 0.2)],
                  [(0, "u"), (0.8, "o"), (1.6, "a"), (2.4, "o"), (d, "u")], [(0, 0), (0.5, 1), (2.6, 0.9), (d, 0)],
                  oq=0.6, rough=0.3, breath=0.35, tilt=-7, fshift=1.0 + 0.06 * v), 0.0, 0.9)
    for j in range(4):
        put(out, _stickslip(0.4, 40, 100, (200, 800)) * bell(0.4, 0.5), 0.4 + 0.6 * j, 0.25)
        put(out, nrm(squelch(0.3, 200, 900, 5, 8, 0.4, 4)) * bell(0.3, 0.5), 0.5 + 0.6 * j, 0.25)
    put(out, nrm(filt(white(d), g_hp(2500)) * env_pts(d, [(0, 0), (0.6, 1), (d, 0)], "cos") * (0.7 + 0.3 * lfn(d, 3))),
        0.0, 0.12)
    return room(out, 1.2, 0.3)


def r_ab_regenerate(v):
    """再生: 断面から伸びる肉の糸（粘る湿ったきしみと逆向きの裂け = 縫い合わさる）+ 泡立つ体液 + 骨が組み直る小さな鳴り。"""
    d = 1.6
    out = silence(d)
    e = env_pts(d, [(0, 0), (0.3, 1), (1.2, 0.8), (d, 0)], "cos")
    put(out, nrm(squelch(d, 150, 900, 6, 6, 0.5, 6) * e), 0.0, 0.7)
    put(out, _stickslip(d, 30, 90, (150, 600), 0.4) * e, 0.0, 0.3)
    put(out, tear(0.6, 500, 40, 400, 2500, 0.9, 2.5, 0.5)[::-1], 0.5, 0.5)
    put(out, bubbles(d, 25, 200, 800, 0.6) * e, 0.0, 0.3)
    for j in range(3):
        put(out, crack(0.06, 2, 0.004, 1500, 5000, 0.2), 0.9 + 0.15 * j, 0.25)
    return out


def r_ab_sac_rupture(v):
    """喉の袋の破裂: 張った袋がはじける湿った破裂（低い胴 + 鋭い膜の裂け）+ 液が噴いて飛び散る。"""
    out = silence(0.9)
    put(out, _burst(0.015, 0.0012, 150), 0.0, 0.8)
    put(out, thud(0.3, 160, 70, 0.04, click=0.3, body=0.7, nf=1200), 0.0, 0.7)
    put(out, nrm(squelch(0.3, 300, 1800, 5, 20, 0.6, 12)) * perc(0.3, 0.003, 0.08), 0.0, 0.9)
    put(out, splatter(0.8, 16, 0.12, 0.9), 0.02, 0.5)
    sp = bp(white(0.4), 2500, 0.6) * (0.4 + 0.6 * np.abs(lfn(0.4, 40))) * perc(0.4, 0.004, 0.12)
    put(out, nrm(sp), 0.01, 0.4)
    return out


def r_ab_shadow_cloak(v):
    """姿が消える: 閉じていく暗い風（下がる帯域）+ 低いささやき + かすかなきらめき。"""
    d = 1.1
    out = _sweep(d, 3000, 250, 1.3) * env_pts(d, [(0, 0), (0.15, 1), (d, 0)], "cos")
    put(out, whisper(0.8, [(0, "a"), (0.8, "u")], [(0, 0), (0.2, 1), (0.8, 0)], 0.85, 2.2, rasp=0.3), 0.1, 0.4)
    put(out, crackles(0.6, 30, 5000, 10000, 0.6, 0.003) * perc(0.6, 0.01, 0.2), 0.05, 0.12)
    return out


def r_ab_shield_block(v):
    """盾で防ぐ: 厚い金属板の鈍い「ごん」（低いモード・短い響き）+ 弾ける火花。"""
    out = silence(0.7)
    put(out, metal(0.6, R.uniform(180, 240), "plate", 0.18, 0.35, 0.9), 0.0, 1.0)
    put(out, thud(0.3, 140, 70, 0.04, click=0.5, body=0.7, nf=1500), 0.0, 0.7)
    put(out, crackles(0.25, 200, 3000, 10000, 1.0, 0.0005) * perc(0.25, 0.001, 0.06), 0.0, 0.35)
    return sat(out, 1.3)


def r_ab_spore_cloud(v):
    """胞子の雲: 袋がしぼんで噴き出す「ぶしゅー」（柔らかい破裂 + 長いしゅー）+ 漂う細かなはぜ。"""
    out = silence(1.7)
    put(out, nrm(filt(pink(0.3), g_bp(350, 0.7)) * perc(0.3, 0.008, 0.08)), 0.0, 0.8)
    hd = 1.6
    put(out, _hiss(hd, 3500, 0.8, 1500, 9000, 0.3, 10) * env_pts(hd, [(0, 0), (0.03, 1), (0.5, 0.6), (hd, 0)], "cos"),
        0.02, 0.55)
    put(out, crackles(hd, 25, 4000, 10000, 0.6, 0.002) * env_pts(hd, [(0, 1), (hd, 0)]), 0.05, 0.12)
    return out


def r_ab_summon_volatiles(v):
    """遠吠えの応答: 遠くの屋上から次々に返ってくる金切り声（遠いほどこもって小さい）。"""
    d = 3.4
    out = silence(d)
    for j in range(4):
        yd = 0.9
        y = _cry("screech", yd, [(0, 0.3), (0.2, 0.9), (yd, 0.4)], [(0, "a"), (0.2, "scream"), (yd, "a")], oq=0.45,
                 drive=2.0, k=1.1, fshift=R.uniform(0.85, 1.1))
        put(out, lp(y, 2500 - 400 * j), 0.15 + 0.6 * j + R.uniform(-0.1, 0.1), 0.8 * 0.75 ** j)
    return fit(echoes(room(out, 2.0, 0.45, damp=2.0, fd=1400), [(0.5, 0.25), (1.1, 0.12)], 1400), d)


def r_ab_tank_burst(v):
    """背中のボンベの破裂: 鋭い破裂音（圧の山 + 裂ける金属）→ 高圧の白い噴気 + 散らばる金属片。"""
    out = silence(1.8)
    put(out, _burst(0.03, 0.0018, 60), 0.0, 1.0)
    put(out, metal(0.6, R.uniform(300, 420), "pipe", 0.2, 0.6, 1.6), 0.0, 0.5)
    put(out, thud(0.4, 100, 45, 0.07, click=0.5, body=0.9), 0.0, 0.7)
    hd = 1.5
    put(out, _hiss(hd, 4500, 1.2, 1500) * env_pts(hd, [(0, 0), (0.01, 1), (0.3, 0.6), (hd, 0)], "cos"), 0.01, 0.6)
    for _ in range(6):
        put(out, metal(0.2, R.uniform(1500, 4000), "bar", 0.05, 0.5, 1.5, n=4), 0.15 + R.exponential(0.2),
            R.uniform(0.05, 0.15))
    return sat(out, 2.0)


def r_ab_tool_wield(v):
    """道具が床に落ちる: 金属の道具が床で跳ねる（だんだん小さく速く）+ 転がる擦れ。"""
    out = silence(0.9)
    t, g = 0.0, 1.0
    f0 = R.uniform(500, 800)
    for j in range(4):
        put(out, metal(0.4, f0 * R.uniform(0.97, 1.03), "bar", 0.15, 0.5, 1.4), t, g)
        put(out, thud(0.1, 250, 140, 0.01, click=0.5, body=0.4, nf=2500), t, 0.4 * g)
        t += 0.16 * 0.65 ** j
        g *= 0.55
    put(out, mslide(0.25, 1500, 6000, 0.7, 0.3), t, 0.15)
    return out


def r_ab_toxic_death_puff(v):
    """防護服から噴くガス: ゴムの裂け目から空気が抜ける震え（ぶるぶる）+ しゅーっと長い噴き出し。"""
    out = silence(1.7)
    fd = 0.6
    fl = filt(white(fd), g_bp(380, 1.2)) * (0.5 + 0.5 * sine(fd, 32 + 8 * lfn(fd, 4))) * env_pts(fd, [(0, 0), (0.03, 1), (fd, 0)])
    put(out, nrm(fl), 0.0, 0.6)
    hd = 1.5
    put(out, _hiss(hd, 3200, 0.9, 1200, 9000, 0.3, 14) * env_pts(hd, [(0, 0), (0.05, 1), (0.6, 0.7), (hd, 0)], "cos"),
        0.05, 0.7)
    return out


def r_ab_toxic_trail(v):
    """毒のもや: 足元にふわっと広がる柔らかなしゅー（低めの帯域）+ かすかな泡。"""
    d = 1.1
    hs = filt(white(d), g_bp(2200, 0.8), g_hp(600)) * env_pts(d, [(0, 0), (0.15, 1), (d, 0)], "cos") * (0.7 + 0.3 * lfn(d, 7))
    return nrm(hs) + 0.25 * nrm(bubbles(d, 20, 400, 1200)) * bell(d, 0.3)


def r_ab_tumor_spawn(v):
    """腫瘍の袋: 落ちて脈打つ湿った鼓動（速まる 3 拍）→ 裂けて粘液と一緒に這い出す。"""
    out = silence(2.0)
    put(out, thud(0.3, 130, 60, 0.04, click=0.2, body=0.8), 0.0, 0.7)
    put(out, splatter(0.3, 6, 0.05, 1.0), 0.0, 0.3)
    t = 0.35
    for j in range(3):
        put(out, thud(0.25, 70, 45, 0.06, click=0.0, body=1.0, nf=300), t, 0.6)
        put(out, nrm(squelch(0.2, 150, 600, 5, 8, 0.4, 3)) * perc(0.2, 0.01, 0.06), t, 0.4)
        t += 0.35 - 0.08 * j
    put(out, tear(0.4, 1200, 80, 300, 2500, 0.6, 3.0, 0.5), t, 0.7)
    put(out, nrm(squelch(0.5, 180, 1000, 6, 12, 0.5, 12)) * perc(0.5, 0.01, 0.15), t + 0.05, 0.7)
    put(out, splatter(0.6, 10, 0.1, 1.2), t + 0.05, 0.35)
    return out


def r_ab_uv_shatter(v):
    """UV を砕く叫び: 金切り声 → ランプのガラスが割れる + 弾ける火花 + 電源が落ちて下がる唸り。"""
    out = silence(2.0)
    put(out, _cry("screech", 1.0, [(0, 0.4), (0.12, 1.0), (1.0, 0.6)], [(0, "a"), (0.12, "scream"), (1.0, "e")], oq=0.4,
                  drive=3.0, k=1.2), 0.0, 0.8)
    for j in range(3):
        t = 0.35 + 0.15 * j
        put(out, crack(0.08, 8, 0.01, 2500, 9000, 0.1), t, 0.6)
        for _ in range(6):
            put(out, metal(0.2, R.uniform(3000, 7000), "glass", 0.05, 0.7, 2.0, n=4), t + R.exponential(0.1),
                R.uniform(0.05, 0.2))
        put(out, arc(0.12, 100, 1500, 0.9, 2.0) * perc(0.12, 0.001, 0.04), t, 0.4)
    h = hum(1.0, 60, 30, 0.8, 0.4, 0.0) * env_pts(1.0, [(0, 1), (1.0, 0)])
    put(out, nrm(varispeed(h, np.geomspace(1.0, 0.5, ns(1.0)))), 0.4, 0.2)
    return out


def r_ab_uv_weak(v):
    """UV で焼かれる: 皮膚が焼けるじゅっ（密なはぜ + 湯気）+ 苦しむ引きつった唸り。"""
    d = 1.2
    e = env_pts(d, [(0, 0), (0.03, 1), (0.6, 0.7), (d, 0)], "cos")
    out = 0.6 * nrm(crackles(d, 1200 * e + 20, 2000, 9000, 1.0, 0.0006)) + 0.3 * nrm(filt(white(d), g_hp(3000)) * e)
    put(out, _cry("growl", 0.8, [(0, 0.6), (0.15, 1.0), (0.8, 0.5)], [(0, "a"), (0.15, "e"), (0.8, "a")], oq=0.45,
                  drive=2.0, fshift=1.3), 0.05, 0.8)
    return out


def r_ab_wall_climb(v):
    """壁を登る: 爪が壁を掻く高い擦れ + 体を引き上げる手足の当たり + 力む息。"""
    out = silence(0.75)
    for j in range(3):
        t = 0.2 * j + R.uniform(0, 0.03)
        sc = filt(white(0.12), g_bp(3500, 1.5)) * (0.5 + 0.5 * np.abs(lfn(0.12, 120))) * perc(0.12, 0.005, 0.05)
        put(out, nrm(sc), t, 0.6)
        put(out, slap(0.05, 1300, 0.8, 0.01), t + 0.02, 0.5)
    put(out, grit(0.5, 600, 2000, 8000) * bell(0.5, 0.3), 0.0, 0.3)
    put(out, whisper(0.5, [(0, "a"), (0.5, "schwa")], [(0, 0), (0.1, 1), (0.5, 0)], 0.85, 2.0, rasp=0.5), 0.1, 0.35)
    return out


# =====================================================================
#  乗り物（nr.veh.*。登録簿に載った ID の名前から型を選ぶ: _veh_kind）
# =====================================================================
VEH_KINDS = (
    ("horn", ("horn", "honk")),
    ("crash", ("crash", "impact", "collide", "collision", "hit", "smash", "wreck")),
    ("skid", ("skid", "brake", "tire", "tyre", "drift", "screech")),
    ("start", ("start", "ignition", "crank")),
    ("stop", ("stop", "off", "shutdown")),
    ("door", ("door", "trunk", "hood")),
    ("engine_high", ("rev", "high", "fast", "drive", "accel", "run", "loop_high")),
    ("engine_idle", ("engine", "idle", "loop", "motor")),
)


def _veh_kind(sid) -> str:
    name = sid.split(".", 2)[-1]
    for kind, words in VEH_KINDS:
        if any(w in name for w in words):
            return kind
    return "crash"


def _engine(d, rpm, cyl=4, load=0.5):
    """エンジン: 点火の脈（毎秒 rpm/60 × cyl/2 回、1 回ごとに強さと間隔が少し乱れる）を排気管の共鳴に通す
    + 吸気の雑音 + 弁のカチカチ。"""
    fire = rpm / 60.0 * cyl / 2.0
    rate = fire * (1.0 + 0.015 * lfn(d, 3.0))
    ph = np.cumsum(rate) / SR
    pul = np.zeros(ns(d))
    idx = np.nonzero(np.diff(np.floor(ph), prepend=0.0) > 0)[0]
    pul[idx] = np.exp(R.normal(0.0, 0.18, len(idx))) * (1.0 + 0.3 * (np.arange(len(idx)) % cyl == 0))
    k = 6
    ir = modes(0.12, R.uniform(70, 420, k) * (1 + load * 0.3), R.uniform(0.008, 0.03, k), R.uniform(0.4, 1.0, k))
    ex = conv(pul, ir)[:ns(d)]
    intake = filt(white(d), g_bp(900 + 1500 * load, 0.8)) * (0.4 + 0.6 * load)
    tick = filt(impulses(d, fire * 2.0, 0.3), g_bp(4500, 2.0))
    return asat(nrm(ex) + 0.18 * nrm(intake) + 0.06 * nrm(tick), 1.5 + load, 0.1)


def r_veh(kind, v):
    """乗り物の音（kind = _veh_kind）。エンジンはループ（2 秒）。"""
    if kind in ("engine_idle", "engine_high"):
        rpm = (850.0 + 60.0 * v) if kind == "engine_idle" else (3200.0 + 300.0 * v)
        return _looped(2.0, 0.25, lambda d: _engine(d, rpm, 4, 0.2 if kind == "engine_idle" else 0.8))
    if kind == "horn":
        d = 0.9
        f1, f2 = (420.0, 500.0) if v % 2 == 0 else (390.0, 470.0)
        y = osc(d, f1, 16, 1.0, odd=True) + osc(d, f2, 16, 1.0, odd=True)
        y = asat(filt(y, g_pk(2200, 2.0, 8), g_hp(300), g_lp(5000)), 2.5, 0.1)
        y = y * np.minimum(np.clip(tax(d) / 0.01, 0, 1), np.clip((d - tax(d)) / 0.03, 0, 1))
        return room(y, 0.6, 0.2)
    if kind == "start":
        d = 2.2
        out = silence(d)
        cr = 1.1
        crank = _engine(cr, 300 + 40 * v, 4, 0.1) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 3.5 * tax(cr))))
        put(out, filt(osc(cr, 160.0, 10, 1.0), g_lp(2000)) * 0.15 + nrm(crank) * 0.8, 0.0, 0.8)
        rpm = np.interp(tax(d - cr), [0, 0.25, d - cr], [600, 2400, 900])
        put(out, _engine(d - cr, float(np.mean(rpm)), 4, 0.6) * env_pts(d - cr, [(0, 0), (0.05, 1), (d - cr, 0.8)]), cr, 1.0)
        return out
    if kind == "stop":
        d = 1.2
        y = _engine(d, 700, 4, 0.2) * env_pts(d, [(0, 1), (0.6, 0.4), (d, 0)], "cos")
        y = varispeed(y, np.geomspace(1.0, 0.45, ns(d)))
        return fit(y, d)
    if kind == "skid":
        d = 1.4
        e = env_pts(d, [(0, 0), (0.05, 1), (1.0, 0.8), (d, 0)], "cos")
        f = (1100.0 + 250.0 * v) * (1.0 + 0.05 * lfn(d, 7.0))
        tonal = osc(d, f, 6, 1.2) * (0.7 + 0.3 * lfn(d, 30.0))
        nz = filt(white(d), g_bp(1800, 1.0))
        return nrm(nrm(tonal) + 0.6 * nrm(nz)) * e
    if kind == "door":
        out = silence(0.8)
        put(out, mclick(0.05, 1800, 0.01, 1.2), 0.0, 0.6)
        put(out, thud(0.4, 120, 55, 0.06, click=0.5, body=0.9, nf=900), 0.02, 1.0)
        put(out, metal(0.5, R.uniform(250, 350), "plate", 0.15, 0.4, 1.0), 0.02, 0.35)
        return room(out, 0.4, 0.15)
    # crash: 板金の潰れ・ガラス・タイヤの擦れ・重い胴
    d = 2.2
    out = silence(d)
    put(out, _burst(0.04, 0.003, 40), 0.0, 0.8)
    put(out, thud(0.8, 80, 32, 0.2, click=0.6, body=1.0, nf=900), 0.0, 1.0)
    for _ in range(6):
        put(out, metal(0.8, R.uniform(150, 600), "plate", 0.4, 0.5, 1.2), R.exponential(0.08), R.uniform(0.2, 0.5))
    put(out, crack(0.4, 30, 0.08, 400, 3000, 0.8), 0.0, 0.6)
    put(out, mslide(0.8, 800, 6000, 0.9, 0.2), 0.05, 0.4)
    for _ in range(14 + 4 * v):
        t = R.exponential(0.25)
        if t < d - 0.3:
            put(out, metal(0.25, R.uniform(2500, 6500), "glass", 0.06, 0.7, 2.0, n=4), t, R.uniform(0.05, 0.25))
    return fit(room(sat(out, 2.0), 1.0, 0.3, damp=1.8, fd=1500), d)


#@@ TABLE
# =====================================================================
#  表（ID → レシピ・変種の数・標本化周波数・分類・距離・音量）
# =====================================================================
SND: dict = {}


def snd(sid, fn, n=3, sr=44100, cat="hostile", dist=32.0, vol=1.0, loop=False, cls="fx", mind=None):
    SND[sid] = dict(fn=fn, n=int(n), sr=int(sr), cat=cat, dist=float(dist), vol=float(vol), loop=bool(loop),
                    cls=cls, mind=mind)


def build_table(S) -> None:
    """全部の ID をレシピに結ぶ（spec の声と能力の語彙もここで展開する）。"""
    SND.clear()
    # ---- ゴア（打った相手の音。hostile）
    snd("nr.gore.slash_flesh", r_slash_flesh, 4, dist=24)
    snd("nr.gore.blunt_flesh", r_blunt_flesh, 4, dist=24)
    snd("nr.gore.pierce_flesh", r_pierce_flesh, 4, dist=24)
    snd("nr.gore.bone_crack", r_bone_crack, 4, dist=24)
    snd("nr.gore.bone_crunch", r_bone_crunch, 3, dist=24)
    snd("nr.gore.sever", r_sever, 3, dist=32)
    snd("nr.gore.decap", r_decap, 3, dist=32)
    snd("nr.gore.head_pop", r_head_pop, 3, dist=40, cls="loud")
    snd("nr.gore.splat", r_splat, 4, dist=20)
    snd("nr.gore.squish", r_squish, 3, dist=16)
    snd("nr.gore.spurt", r_spurt, 3, dist=16, vol=0.8)
    snd("nr.gore.gut_spill", r_gut_spill, 2, dist=16)
    snd("nr.gore.gib_land", r_gib_land, 4, dist=16, vol=0.7)
    snd("nr.gore.body_fall", r_body_fall, 3, dist=24)
    snd("nr.gore.drip", r_drip, 4, dist=8, vol=0.5, cls="soft")
    snd("nr.gore.burst", r_burst, 2, dist=40, cls="loud")
    snd("nr.gore.chop", r_chop, 4, dist=24)
    snd("nr.gore.smash", r_smash, 3, dist=32, cls="loud")
    # ---- ゾンビの声（spec の VOICE_VOCAB から機械的に。22.05 kHz）
    import nr_registry
    far = {"howl", "volatile_screech", "wail", "shriek_high", "roar_giant", "roar_deep", "whimper", "chitter"}
    vdist = {"idle": 24, "alert": 48, "attack": 32, "hurt": 24, "death": 32}
    for key in sorted(S.VOICE_VOCAB):
        P = dict(S.VOICE_VOCAB[key])
        for ev in nr_registry.ZOMBIE_VOICE_EVENTS:
            snd(f"nr.z.{key}.{ev}", functools.partial(r_voice, key, ev, P), VOICE_N[ev], sr=22050,
                dist=vdist[ev] * (2 if key in far and ev != "hurt" else 1), vol=0.85 if ev == "idle" else 1.0,
                cls="voice")
    # ---- 武器（プレイヤーが鳴らす。player）。銃は遠くまで届く
    for sid, fn, n, kw in (
            ("nr.w.swing_light", r_swing_light, 4, dict(dist=16)),
            ("nr.w.swing_heavy", r_swing_heavy, 3, dict(dist=16)),
            ("nr.w.hit_metal", r_hit_metal, 4, dict(dist=24)),
            ("nr.w.hit_wood", r_hit_wood, 3, dict(dist=24)),
            ("nr.w.break", r_break, 2, dict(dist=24)),
            ("nr.w.bow_draw", r_bow_draw, 2, dict(dist=12, vol=0.7)),
            ("nr.w.bow_release", r_bow_release, 3, dict(dist=24)),
            ("nr.w.crossbow_shot", r_crossbow_shot, 3, dict(dist=32)),
            ("nr.w.crossbow_reload", r_crossbow_reload, 2, dict(dist=12, vol=0.7)),
            ("nr.w.pistol", r_pistol, 3, dict(dist=96, cls="loud")),
            ("nr.w.revolver", r_revolver, 3, dict(dist=112, cls="loud")),
            ("nr.w.shotgun", r_shotgun, 3, dict(dist=112, cls="loud")),
            ("nr.w.rifle", r_rifle, 3, dict(dist=128, cls="loud")),
            ("nr.w.smg", r_smg, 4, dict(dist=96, cls="loud")),
            ("nr.w.reload", r_reload, 2, dict(dist=12, vol=0.7)),
            ("nr.w.pump", r_pump, 2, dict(dist=12, vol=0.8)),
            ("nr.w.empty_click", r_empty_click, 3, dict(dist=8, vol=0.6)),
            ("nr.w.throw", r_throw, 3, dict(dist=16)),
            ("nr.w.knife_stick", r_knife_stick, 3, dict(dist=16)),
            ("nr.w.reload_revolver", r_reload_revolver, 2, dict(dist=12, vol=0.7)),
            ("nr.w.reload_shell", r_reload_shell, 3, dict(dist=12, vol=0.7)),
            ("nr.w.bolt_cycle", r_bolt_cycle, 2, dict(dist=12, vol=0.8)),
            ("nr.w.mod_fire", r_mod_fire, 2, dict(dist=24)),
            ("nr.w.mod_shock", r_mod_shock, 3, dict(dist=24)),
            ("nr.w.mod_bleed", r_mod_bleed, 3, dict(dist=16)),
            ("nr.w.mod_toxic", r_mod_toxic, 2, dict(dist=24)),
            ("nr.w.mod_uv", r_mod_uv, 2, dict(dist=24)),
            ("nr.w.mod_impact", r_mod_impact, 3, dict(dist=32))):
        snd(sid, fn, n, cat="player", **kw)
    # ---- 爆発・属性（世界の音。neutral）
    for sid, fn, n, kw in (
            ("nr.fx.explosion", r_explosion, 3, dict(dist=128, cls="loud")),
            ("nr.fx.explosion_big", r_explosion_big, 2, dict(dist=160, cls="loud")),
            ("nr.fx.fire_ignite", r_fire_ignite, 3, dict(dist=24)),
            ("nr.fx.fire_loop", r_fire_loop, 2, dict(dist=20, loop=True, cls="loop")),
            ("nr.fx.electric_zap", r_electric_zap, 4, dict(dist=24)),
            ("nr.fx.electric_buzz", r_electric_buzz, 2, dict(dist=16, loop=True, cls="loop")),
            ("nr.fx.toxic_hiss", r_toxic_hiss, 3, dict(dist=24)),
            ("nr.fx.acid_sizzle", r_acid_sizzle, 3, dict(dist=16)),
            ("nr.fx.uv_hum", r_uv_hum, 2, dict(dist=16, loop=True, cls="loop")),
            ("nr.fx.uv_burn", r_uv_burn, 3, dict(dist=16)),
            ("nr.fx.glass_break", r_glass_break, 4, dict(dist=32)),
            ("nr.fx.metal_clang", r_metal_clang, 4, dict(dist=32)),
            ("nr.fx.gas_hiss", r_gas_hiss, 2, dict(dist=16, loop=True, cls="loop"))):
        snd(sid, fn, n, cat="neutral", **kw)
    # ---- パルクール（プレイヤー自身。player）
    for sid, fn, n, kw in (
            ("nr.pk.step_run", r_step_run, 4, dict(dist=16, vol=0.5)),
            ("nr.pk.jump", r_jump, 3, dict(dist=16, vol=0.7)),
            ("nr.pk.land_soft", r_land_soft, 3, dict(dist=16, vol=0.6)),
            ("nr.pk.land_hard", r_land_hard, 3, dict(dist=24)),
            ("nr.pk.roll", r_roll, 3, dict(dist=16, vol=0.8)),
            ("nr.pk.vault", r_vault, 3, dict(dist=16, vol=0.8)),
            ("nr.pk.grab", r_grab, 3, dict(dist=16, vol=0.8)),
            ("nr.pk.climb", r_climb, 3, dict(dist=16, vol=0.8)),
            ("nr.pk.wallrun", r_wallrun, 3, dict(dist=16, vol=0.7)),
            ("nr.pk.slide", r_slide, 3, dict(dist=16, vol=0.8)),
            ("nr.pk.dropkick", r_dropkick, 3, dict(dist=24)),
            ("nr.pk.grapple_fire", r_grapple_fire, 3, dict(dist=24)),
            ("nr.pk.grapple_reel", r_grapple_reel, 2, dict(dist=16, loop=True, cls="loop")),
            ("nr.pk.glider_open", r_glider_open, 3, dict(dist=16)),
            ("nr.pk.glider_wind", r_glider_wind, 2, dict(dist=12, loop=True, cls="loop")),
            ("nr.pk.breath", r_breath, 3, dict(sr=22050, dist=8, vol=0.6, cls="soft"))):
        snd(sid, fn, n, cat="player", **kw)
    # ---- 罠・世界（block）
    for sid, fn, n, kw in (
            ("nr.trap.spike", r_trap_spike, 3, dict(dist=24)),
            ("nr.trap.beartrap", r_trap_beartrap, 3, dict(dist=24)),
            ("nr.trap.electric", r_trap_electric, 3, dict(dist=24)),
            ("nr.trap.alarm", r_trap_alarm, 2, dict(dist=64, loop=True)),
            ("nr.trap.click", r_trap_click, 3, dict(dist=8, vol=0.7)),
            ("nr.trap.gas_burst", r_trap_gas_burst, 2, dict(dist=48, cls="loud")),
            ("nr.trap.uv_burst", r_trap_uv_burst, 2, dict(dist=24)),
            ("nr.trap.rope_snap", r_trap_rope_snap, 3, dict(dist=24)),
            ("nr.trap.wire", r_trap_wire, 3, dict(dist=16)),
            ("nr.world.barricade_hit", r_barricade_hit, 4, dict(dist=32)),
            ("nr.world.door", r_door, 3, dict(dist=16))):
        snd(sid, fn, n, cat="block", **kw)
    # ---- プレイヤーの状態（player。自分にだけ鳴らす）
    for sid, fn, n, kw in (
            ("nr.pl.heartbeat", r_heartbeat, 2, dict(dist=8)),
            ("nr.pl.immunity_warn", r_immunity_warn, 2, dict(dist=8)),
            ("nr.pl.immunity_restore", r_immunity_restore, 2, dict(dist=8)),
            ("nr.pl.hurt", r_pl_hurt, 4, dict(sr=22050, dist=16)),
            ("nr.pl.heal", r_heal, 3, dict(dist=8, vol=0.8)),
            ("nr.pl.levelup", r_levelup, 2, dict(dist=8)),
            ("nr.pl.grabbed", r_grabbed, 3, dict(dist=16))):
        snd(sid, fn, n, cat="player", **kw)
    # ---- 夜と追跡（警告音は ui = 距離で消えない。号笛と夜明けは ambient、低域だけなので 22.05 kHz）
    snd("nr.chase.start", r_chase_start, 2, cat="ui", dist=16, cls="loud")
    snd("nr.chase.level_up", r_chase_level_up, 2, cat="ui", dist=16)
    snd("nr.chase.end", r_chase_end, 2, cat="ui", dist=16, cls="voice")
    snd("nr.night.start", r_night_start, 2, sr=22050, cat="ambient", dist=64, cls="loud")
    snd("nr.day.start", r_day_start, 2, sr=22050, cat="ambient", dist=64, cls="voice")
    # ---- UI・道具（ui）
    for sid, fn, n in (
            ("nr.ui.click", r_ui_click, 3), ("nr.ui.open", r_ui_open, 2), ("nr.ui.craft", r_ui_craft, 3),
            ("nr.ui.error", r_ui_error, 2), ("nr.ui.combo", r_ui_combo, 3), ("nr.ui.headshot", r_ui_headshot, 2),
            ("nr.ui.kill", r_ui_kill, 3), ("nr.ui.bandage", r_ui_bandage, 3), ("nr.ui.medkit", r_ui_medkit, 2),
            ("nr.ui.inject", r_ui_inject, 3), ("nr.ui.eat", r_ui_eat, 3), ("nr.ui.drink", r_ui_drink, 3),
            ("nr.ui.pills", r_ui_pills, 3), ("nr.ui.repair", r_ui_repair, 3), ("nr.ui.lockpick", r_ui_lockpick, 4),
            ("nr.ui.uv_on", r_ui_uv_on, 2), ("nr.ui.zoom", r_ui_zoom, 3)):
        snd(sid, fn, n, cat="ui", dist=16, cls="ui")
    # ---- ボス（hostile。咆哮が主なので 22.05 kHz）
    snd("nr.boss.intro", r_boss_intro, 2, sr=22050, dist=128, cls="loud")
    snd("nr.boss.phase", r_boss_phase, 2, sr=22050, dist=96, cls="loud")
    snd("nr.boss.death", r_boss_death, 2, sr=22050, dist=128, cls="loud")
    # ---- 特殊能力（spec の ABILITY_VOCAB から。レシピは r_ab_<能力>。声が主なものは 22.05 kHz）
    for key in sorted(S.ABILITY_VOCAB):
        fn = globals().get(f"r_ab_{key}")
        if fn is None:
            continue                     # main が「レシピの無い ID」として止める
        snd(f"nr.ab.{key}", fn, 3 if key in AB_N3 else 2, sr=22050 if key in AB_22K else 44100,
            dist=AB_DIST.get(key, 32), cls=AB_CLS.get(key, "fx"), loop=key in AB_LOOP)
    # ---- ゾンビの足音（この生成器が足す ID。sounds.json の step が使う）
    for kind in ZSTEP_VOL:
        snd(f"nr.zstep.{kind}", functools.partial(r_zstep, kind), 3,
            dist={"giant": 40, "heavy": 24}.get(kind, 16))
    # ---- 乗り物（登録簿に nr.veh.* があれば、名前から型を選んで作る）
    for sid in REG_IDS(S):
        if sid.startswith("nr.veh.") and sid not in SND:
            kind = _veh_kind(sid)
            loop = kind.startswith("engine")
            snd(sid, functools.partial(r_veh, kind), 2 if loop else 3, sr=22050 if loop else 44100, cat="neutral",
                dist={"horn": 64, "crash": 64}.get(kind, 32), loop=loop,
                cls="loop" if loop else ("loud" if kind in ("crash", "horn") else "fx"))
    # @@TABLE_END（ここより上に表を足す）


def all_ids(S) -> list:
    """作る ID の全部（登録簿の全部 + この生成器が足すもの）。"""
    ids = list(dict.fromkeys(REG_IDS(S)))
    return ids + sorted(s for s in SND if s not in set(ids))


def REG_IDS(S):  # noqa: N802
    import nr_registry
    return nr_registry.all_sound_ids(S)


# =====================================================================
#  書き出し（キャッシュ・並列・ffmpeg・統計・断片・掃除・一覧画像）
# =====================================================================
def _spec():
    import nr_spec
    return nr_spec


def _core_src() -> str:
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        return fh.read().split("#@@ RECIPES", 1)[0]


def _code_names(code) -> set:
    """関数が参照する大域名（中の lambda・内側の def も含める）。"""
    names = set(code.co_names)
    for c in code.co_consts:
        if inspect.iscode(c):
            names |= _code_names(c)
    return names


def _recipe_src(fn, seen=None) -> str:
    """キャッシュの鍵に入れるレシピのソース。partial なら引数も。レシピが呼ぶこのファイルの下請け
    （r_* と _* の関数。_plan・_cry・_stickslip など）と、参照する大文字の定数（MONSTER・VOICE_N など）も
    再帰的に入れる（楽器の核は _core_src が受け持つ）。"""
    seen = set() if seen is None else seen
    if isinstance(fn, functools.partial):
        return _recipe_src(fn.func, seen) + repr(fn.args) + repr(sorted(fn.keywords.items()))
    if fn in seen:
        return ""
    seen.add(fn)
    src = inspect.getsource(fn)
    for name in sorted(_code_names(fn.__code__)):
        g = globals().get(name)
        if inspect.isfunction(g) and g.__module__ == fn.__module__ and name.startswith(("r_", "_")):
            src += _recipe_src(g, seen)
        elif name.isupper() and name not in ("SND", "SR", "R") and isinstance(g, (dict, tuple, list, set, int, float, str)):
            text = repr(sorted(g) if isinstance(g, set) else g)
            if " at 0x" not in text and name not in seen:
                seen.add(name)
                src += f"\n{name} = {text}"
    return src


_SRC_MEMO: dict = {}


def _ffmpeg_version() -> str:
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()
        return out[0] if out else "?"
    except OSError:
        return "?"


def job_key(sid, v, core, ffv) -> str:
    e = SND[sid]
    if sid not in _SRC_MEMO:
        _SRC_MEMO[sid] = _recipe_src(e["fn"])
    h = hashlib.sha1()
    for part in (core, _SRC_MEMO[sid], sid, str(v), str(e["sr"]), str(e["loop"]), e["cls"],
                 ENC_Q[e["sr"]], ffv):
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:24]


def render(sid, v):
    """1 つの変種を合成して仕上げる（浮動小数の波形）。"""
    e = SND[sid]
    setup(e["sr"], stable_hash(f"{sid}#{v}"))
    return finish(e["fn"](v), loop=e["loop"], cls=e["cls"])


def encode(x, sr) -> bytes:
    pcm = (np.clip(x, -1.0, 1.0) * 32767.0).round().astype("<i2").tobytes()
    res = subprocess.run(["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
                          "-c:a", "libvorbis", "-q:a", ENC_Q[sr], "-fflags", "+bitexact", "-flags:a", "+bitexact",
                          "-map_metadata", "-1", "-f", "ogg", "pipe:1"], input=pcm, capture_output=True)
    if res.returncode or not res.stdout:
        raise RuntimeError("ffmpeg: " + res.stderr.decode("utf-8", "replace")[:300])
    return res.stdout


def decode(path, sr):
    res = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(sr), "pipe:1"],
                         capture_output=True)
    return np.frombuffer(res.stdout, "<i2").astype(float) / 32768.0


def stats(x, sr) -> dict:
    """ピーク・RMS・最大の瞬時 RMS（0.25 秒）・長さ・スペクトル重心・ループのつなぎ目の段差。"""
    n = len(x)
    db = lambda a: round(20.0 * np.log10(max(float(a), 1e-9)), 1)  # noqa: E731
    pk = np.max(np.abs(x)) if n else 0.0
    rms = np.sqrt(np.mean(x ** 2)) if n else 0.0
    win = int(0.25 * sr)
    if n > win:
        c = np.cumsum(np.concatenate([[0.0], x ** 2]))
        mom = np.sqrt(np.max(c[win:] - c[:-win]) / win)
    else:
        mom = rms
    sp = np.abs(np.fft.rfft(x * np.hanning(n))) ** 2 if n > 16 else np.zeros(2)
    f = np.fft.rfftfreq(max(n, 2), 1.0 / sr)[:len(sp)]
    cen = float(np.sum(f * sp) / (np.sum(sp) + 1e-12))
    return dict(dur=round(n / sr, 3), peak=db(pk), rms=db(rms), mom=db(mom), centroid=int(cen),
                seam=round(float(abs(x[-1] - x[0])) if n else 0.0, 4))


def work(job):
    """並列の 1 仕事: 合成 → ogg → キャッシュ（<鍵>.ogg と統計 <鍵>.json）。"""
    sid, v, key = job
    try:
        x = render(sid, v)
        sr = SND[sid]["sr"]
        data = encode(x, sr)
        st = stats(x, sr)
        tmp = os.path.join(CACHE, f"{key}.tmp{os.getpid()}")
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, os.path.join(CACHE, f"{key}.ogg"))
        with open(os.path.join(CACHE, f"{key}.json"), "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        return sid, v, key, st, None
    except Exception:  # noqa: BLE001
        import traceback
        return sid, v, key, None, traceback.format_exc()


def rel_name(sid, v) -> str:
    """nr.gore.sever の 0 番 → sounds/nr/gore/sever_0（sound_definitions の name）。"""
    parts = sid.split(".")[1:]
    return "sounds/nr/" + "/".join(parts[:-1] + [f"{parts[-1]}_{v}"])


def _same(a, b) -> bool:
    if not os.path.exists(b) or os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def definitions() -> dict:
    out = {}
    for sid, e in SND.items():
        d = {"category": e["cat"], "max_distance": e["dist"]}
        if e["mind"] is not None:
            d["min_distance"] = float(e["mind"])
        d["sounds"] = [{"name": rel_name(sid, v), "volume": e["vol"]} for v in range(e["n"])]
        out[sid] = d
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NIGHT RUNNER の効果音を合成する")
    ap.add_argument("--only", action="append", default=[],
                    help="この ID（fnmatch のパターン可）だけ作る。開発用: 断片・掃除はしない")
    ap.add_argument("--force", action="store_true", help="キャッシュを使わず作り直す（--only と併用可）")
    ap.add_argument("--sheet", action="store_true", help="スペクトログラムの一覧画像も描く（NR_PREVIEW=1 でも）")
    ap.add_argument("--allow-missing", action="store_true", help="登録簿の ID が欠けていても失敗にしない（開発用）")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args(argv)
    t0 = time.time()
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg が無い（効果音を作れない）")
        return 1
    S = _spec()
    build_table(S)
    ids = all_ids(S)
    missing = [s for s in ids if s not in SND]
    if missing:
        print(f"{'WARNING' if args.allow_missing else 'ERROR'}: レシピの無い ID {len(missing)} 件: "
              + ", ".join(missing[:12]) + (" ..." if len(missing) > 12 else ""))
        if not args.allow_missing:
            return 1
    pats = [p for o in args.only for p in o.split(",") if p.strip()]
    sel = [s for s in ids if s in SND and (not pats or any(fnmatch.fnmatchcase(s, p) for p in pats))]
    os.makedirs(CACHE, exist_ok=True)
    core, ffv = _core_src(), _ffmpeg_version()
    jobs, todo = [], []
    for sid in sel:
        for v in range(SND[sid]["n"]):
            key = job_key(sid, v, core, ffv)
            jobs.append((sid, v, key))
            if args.force or not (os.path.exists(os.path.join(CACHE, f"{key}.ogg"))
                                  and os.path.exists(os.path.join(CACHE, f"{key}.json"))):
                todo.append((sid, v, key))
    errors = []
    t1 = time.time()
    if todo:
        # 重い順（長い声・爆発）から投げると最後に一つだけ残りにくい
        todo.sort(key=lambda j: (SND[j[0]]["sr"] == 22050, j[0]))
        if args.jobs > 1 and len(todo) > 1:
            with ProcessPoolExecutor(max_workers=args.jobs) as pool:
                results = list(pool.map(work, todo, chunksize=2))
        else:
            results = [work(j) for j in todo]
        for sid, v, _key, _st, err in results:
            if err:
                errors.append(f"{sid}#{v}:\n{err}")
    t2 = time.time()
    if errors:
        print("ERROR: 合成に失敗:\n" + "\n".join(errors[:5]))
        return 1
    # 書き出し（キャッシュ → RP）
    produced, report, total = set(), {}, 0
    for sid, v, key in jobs:
        src = os.path.join(CACHE, f"{key}.ogg")
        dst = os.path.join(RP, rel_name(sid, v) + ".ogg")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not _same(src, dst):
            shutil.copyfile(src, dst)
        produced.add(os.path.normpath(dst))
        total += os.path.getsize(dst)
        with open(os.path.join(CACHE, f"{key}.json"), encoding="utf-8") as fh:
            report.setdefault(sid, []).append(json.load(fh))
    warns = check_report(report)
    if not pats:
        removed = 0
        for root, _dirs, files in os.walk(OUT, topdown=False):
            for f in files:
                p = os.path.normpath(os.path.join(root, f))
                if f.endswith(".ogg") and p not in produced:
                    os.remove(p)
                    removed += 1
            if root != OUT and not os.listdir(root):
                os.rmdir(root)
        frag("sound_definitions", GEN, definitions())
        frag("sounds_json", GEN, sounds_json(S))
        write_json(REPORT, {"total_bytes": total, "sounds": report})
        if removed:
            print(f"  古い ogg を {removed} 件消した")
    n_files = len(jobs)
    print(f"  sounds: {len(sel)} ID / {n_files} ファイル（新規 {len(todo)}・キャッシュ {n_files - len(todo)}）"
          f" {total / 1048576:.2f} MB  合成 {t2 - t1:.1f}s / 全体 {time.time() - t0:.1f}s")
    for w in warns[:40]:
        print("  WARN", w)
    if total / 1048576 > SIZE_LIMIT_MB and not pats:
        print(f"ERROR: 効果音の合計が {SIZE_LIMIT_MB} MB を超えた")
        return 1
    if args.sheet or PREVIEW:
        draw_sheet(jobs)
    return 0


def check_report(report) -> list:
    """耳の代わりの検査: 無音・割れ・極端な長さ・ループの段差。"""
    out = []
    for sid, sts in report.items():
        e = SND[sid]
        for v, st in enumerate(sts):
            tag = f"{sid}#{v}"
            if st["rms"] < -48:
                out.append(f"{tag}: ほぼ無音（RMS {st['rms']} dBFS）")
            if st["peak"] > -0.5:
                out.append(f"{tag}: ピークが高すぎる（{st['peak']} dBFS）")
            if st["dur"] < 0.03 or st["dur"] > 9.0:
                out.append(f"{tag}: 長さが極端（{st['dur']} 秒）")
            if e["loop"] and st["seam"] > 0.05:
                out.append(f"{tag}: ループのつなぎ目の段差 {st['seam']}")
    return out


# ---------------------------------------------------------------- sounds.json（エンティティの音）
def zstep_kind(z) -> str:
    """ゾンビの足音の種類（nr.zstep.<種類>）。移動の型・体格から。"""
    loco = z.get("locomotion", "shamble")
    if loco == "brute" and z.get("height_cm", 180) >= 260:
        return "giant"
    if loco in ("brute", "waddle") or z.get("bulk", 1.0) >= 1.8:
        return "heavy"
    return {"run": "run", "sprint": "run", "leap": "run", "crawl": "crawl", "knuckle": "crawl",
            "scuttle": "claw", "stalk": "stalk"}.get(loco, "shuffle")


ZSTEP_VOL = {"shuffle": 0.35, "run": 0.45, "heavy": 0.75, "giant": 1.0, "crawl": 0.35, "claw": 0.4, "stalk": 0.25}


def sounds_json(S) -> dict:
    """エンティティの自動の音: ambient → 声の idle、hurt / death → 声、step → 足音、land（跳んだ後の着地）→
    重めの足音、落下 → 体の当たり。voice_pitch は entity の pitch の範囲に掛ける（スクリプトが鳴らす声と同じ移調）。
    nr:gib は land / 落下 → 部位が落ちる音、hurt / death → 潰れる音、step は鳴らさない。"""
    ents = {}
    for z in S.ZOMBIES:
        vp = float(z.get("voice_pitch", 1.0) or 1.0)
        voice = z["voice"]
        kind = zstep_kind(z)
        sp = min(1.15, max(0.7, (178.0 / max(z.get("height_cm", 178), 100)) ** 0.5))
        ents[f"nr:z_{z['key']}"] = {
            "volume": 1.0,
            "pitch": [round(0.93 * vp, 3), round(1.07 * vp, 3)],
            "events": {
                "ambient": {"sound": f"nr.z.{voice}.idle", "volume": 0.9},
                "hurt": {"sound": f"nr.z.{voice}.hurt", "volume": 0.85},
                "death": {"sound": f"nr.z.{voice}.death", "volume": 1.0},
                "step": {"sound": f"nr.zstep.{kind}", "volume": ZSTEP_VOL[kind],
                         "pitch": [round(0.9 * sp, 3), round(1.1 * sp, 3)]},
                "land": {"sound": f"nr.zstep.{kind}", "volume": round(min(1.0, 1.8 * ZSTEP_VOL[kind]), 3),
                         "pitch": [round(0.8 * sp, 3), round(0.95 * sp, 3)]},
                "fall.big": {"sound": "nr.gore.body_fall", "volume": 0.9, "pitch": [0.9, 1.1]},
                "fall.small": {"sound": "nr.pk.land_soft", "volume": 0.6, "pitch": [0.8, 1.0]},
            },
        }
    ents["nr:gib"] = {
        "volume": 1.0,
        "pitch": [0.85, 1.15],
        "events": {
            "hurt": {"sound": "nr.gore.squish", "volume": 0.8},
            "death": {"sound": "nr.gore.splat", "volume": 0.8},
            "step": "",
            "land": {"sound": "nr.gore.gib_land", "volume": 0.9},
            "fall.big": {"sound": "nr.gore.gib_land", "volume": 1.0},
            "fall.small": {"sound": "nr.gore.gib_land", "volume": 0.7},
        },
    }
    return {"entity_sounds": {"entities": ents}}


# ---------------------------------------------------------------- スペクトログラムの一覧
SHEET_IDS = (
    "nr.gore.slash_flesh", "nr.gore.blunt_flesh", "nr.gore.bone_crack", "nr.gore.sever", "nr.gore.head_pop",
    "nr.gore.spurt", "nr.gore.gut_spill", "nr.w.swing_heavy", "nr.w.hit_metal", "nr.w.pistol", "nr.w.shotgun",
    "nr.w.rifle", "nr.w.reload", "nr.fx.explosion", "nr.fx.explosion_big", "nr.fx.electric_zap", "nr.fx.fire_loop",
    "nr.fx.uv_hum", "nr.fx.glass_break", "nr.fx.toxic_hiss", "nr.pk.step_run", "nr.pk.land_hard", "nr.pk.slide",
    "nr.pk.grapple_reel", "nr.pk.glider_wind", "nr.pk.breath", "nr.pl.heartbeat", "nr.pl.immunity_warn",
    "nr.chase.start", "nr.night.start", "nr.ui.click", "nr.ui.headshot", "nr.trap.alarm", "nr.world.barricade_hit",
    "nr.z.groan_male.idle", "nr.z.shriek_high.alert", "nr.z.howl.alert", "nr.z.roar_deep.attack",
    "nr.z.wet_choke.death", "nr.z.volatile_screech.alert", "nr.ab.howl_alarm", "nr.ab.detonate",
    "nr.ab.ground_pound", "nr.ab.reanimate", "nr.ab.sac_rupture", "nr.boss.intro", "nr.zstep.giant",
    "nr.zstep.claw",
)
_LUT_PTS = ((0.0, (0, 0, 4)), (0.15, (31, 12, 72)), (0.3, (85, 15, 109)), (0.45, (136, 34, 106)),
            (0.6, (186, 54, 85)), (0.72, (227, 89, 51)), (0.84, (249, 140, 10)), (0.93, (249, 201, 50)),
            (1.0, (252, 255, 164)))


def _lut():
    xs = np.array([p[0] for p in _LUT_PTS])
    u = np.linspace(0, 1, 256)
    return np.stack([np.interp(u, xs, [p[1][c] for p in _LUT_PTS]) for c in range(3)], 1).astype(np.uint8)


def spectrogram_img(x, sr, w, h):
    """対数周波数（40 Hz〜ナイキスト）× 時間、ピークから -80 dB までを色に。"""
    nwin = 1024 if sr > 30000 else 512
    x = np.concatenate([x, np.zeros(nwin)])
    starts = np.linspace(0, max(len(x) - nwin, 1), w).astype(int)
    win = np.hanning(nwin)
    fr = np.stack([x[s:s + nwin] * win for s in starts])
    mag = np.abs(np.fft.rfft(fr, axis=1))
    freqs = np.fft.rfftfreq(nwin, 1.0 / sr)
    edges = np.geomspace(40.0, sr / 2.0, h + 1)
    rows = []
    for i in range(h):
        lo, hi = np.searchsorted(freqs, edges[i]), np.searchsorted(freqs, edges[i + 1])
        hi = max(hi, lo + 1)
        rows.append(mag[:, lo:hi].max(axis=1))
    m = np.stack(rows[::-1])
    db = 20 * np.log10(m / (m.max() + 1e-12) + 1e-9)
    return (np.clip((db + 80.0) / 80.0, 0, 1) * 255).astype(np.uint8)


def draw_sheet(jobs) -> None:
    from PIL import Image, ImageDraw
    by = {(sid, v): key for sid, v, key in jobs}
    pick = [(sid, by[(sid, 0)]) for sid in SHEET_IDS if (sid, 0) in by]
    if not pick:
        pick = [(sid, key) for sid, v, key in jobs if v == 0][:36]
    cols, cw, ch, lab = 6, 300, 120, 26
    rows = (len(pick) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw, rows * (ch + lab)), (12, 12, 16))
    dr = ImageDraw.Draw(img)
    lut = _lut()
    for i, (sid, key) in enumerate(pick):
        sr = SND[sid]["sr"]
        x = decode(os.path.join(CACHE, f"{key}.ogg"), sr)
        cx, cy = (i % cols) * cw, (i // cols) * (ch + lab)
        img.paste(Image.fromarray(lut[spectrogram_img(x, sr, cw - 4, ch)]), (cx + 2, cy + lab))
        pk = 20 * np.log10(np.max(np.abs(x)) + 1e-9)
        dr.text((cx + 3, cy + 1), sid.replace("nr.", ""), fill=(235, 235, 235))
        dr.text((cx + 3, cy + 13), f"{len(x) / sr:.2f}s  pk {pk:.1f}dB  {sr // 1000}k", fill=(150, 160, 170))
    os.makedirs(os.path.dirname(SHEET), exist_ok=True)
    img.save(SHEET)
    print(f"  一覧画像: {os.path.relpath(SHEET)}（{len(pick)} 個）")


if __name__ == "__main__":
    sys.exit(main())
