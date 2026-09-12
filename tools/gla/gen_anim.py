# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — アニメーション (企画書 §07 / §08)。

企画書の「滑らかさはキーフレームの総数ではなく、重心・間・速度変化・つながりで
作る」を素直に実装する。だから:

* 移動系はキーフレームを並べず、Molang の振動で作る。30fps でも 60fps でも
  同じポーズが読める。
* 技はすべて spec.py の windup / active / recover から長さを起こす。
  数字がダメージ判定と同じ場所から来るので、見た目と判定がずれない。
* 形態ごとに重心・振り幅・周波数を変える。左右反転や色違いで水増ししない
  （企画書 §07 制作単位）。
* 看板演出（ニカの浮遊・大爆笑）は spec.SHOWPIECE の表をそのまま時間軸にする。

技ごとの専用クリップは `player.playAnimation()` からの再生を想定した「best effort」
で、これが動かなくてもアタッチャブル側の汎用の振りと VFX で技は成立する。
実機で確認するまで「対応済み」とは書かない（企画書 §01 完成の判定）。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import spec                                             # noqa: E402

RP = os.path.join(ROOT, spec.RP_DIR)
NS = spec.NS

# ---------------------------------------------------------------------------
#  Molang の土台（怪獣8号側と同じ定数を使う。どちらも公式の標準値）
# ---------------------------------------------------------------------------
LIMB = "query.modified_distance_moved * 38.17"
SPD = "query.modified_move_speed"
T = "query.anim_time"


def swing(amp, phase=0, speed=1.0, scale=SPD):
    ph = f" + {phase}" if phase else ""
    return f"math.cos({LIMB} * {speed}{ph}) * {amp} * {scale}"


def bob(amp, hz=62, phase=0):
    ph = f" + {phase}" if phase else ""
    return f"math.cos({T} * {hz}{ph}) * {amp}"


def off(base, expr):
    """Molang 式に定数を足す。bob()/swing() は文字列を返すので + は使えない。"""
    if not base:
        return expr
    return f"{base:g} + {expr}"


def rot(x=0, y=0, z=0):
    return {"rotation": [x, y, z]}


def pos(x=0, y=0, z=0):
    return {"position": [x, y, z]}


def rp(r, p):
    return {"rotation": list(r), "position": list(p)}


def tkey(t: float) -> str:
    """Bedrock のキー時刻は秒の文字列。0.0 は "0" にする。"""
    return f"{round(t, 4):g}"


def kf(*pairs):
    """kf((0, [0,0,0]), (0.2, [-40,0,0])) -> {"0": [...], "0.2": [...]}"""
    return {tkey(t): list(v) for t, v in pairs}


def clip(bones, length=None, loop=True):
    d = {"loop": loop, "bones": bones}
    if length:
        d["animation_length"] = round(length, 3)
    return d


A: dict = {}


# ---------------------------------------------------------------------------
#  形態ごとの「動きの性格」
#  企画書 §04 の役割をそのまま数値にしたもの。ここを変えると全クリップが変わる。
# ---------------------------------------------------------------------------
CHARACTER = {
    "normal": dict(
        lean=0, arm=46, leg=44, hz=62, bounce=0.10, stance=2.0, speed=1.00,
        wrist=12, loose=1.00,
        note="軽快な重心移動。腕は大きく、着地は軽い。"),
    "gear2": dict(
        lean=9, arm=30, leg=52, hz=92, bounce=0.06, stance=1.4, speed=1.45,
        wrist=8, loose=0.70,
        note="前傾。歩幅は狭く回転を上げる。腕は畳んで予備動作を短く見せる。"),
    "gear3": dict(
        lean=2, arm=38, leg=40, hz=54, bounce=0.14, stance=2.6, speed=0.88,
        wrist=16, loose=1.15,
        note="前腕が重い。振り始めが遅れて、止まるときに引きずる。"),
    "gear4_bound": dict(
        lean=-4, arm=52, leg=38, hz=48, bounce=0.30, stance=3.2, speed=0.94,
        wrist=20, loose=1.35,
        note="弾む重心。上下動を大きく、接地の間を長く取る。"),
    "gear4_snake": dict(
        lean=6, arm=62, leg=46, hz=70, bounce=0.08, stance=1.8, speed=1.20,
        wrist=26, loose=1.50,
        note="長い腕がうねる。肩と手首の位相をずらして軌道を曲げて見せる。"),
    "gear5": dict(
        lean=-2, arm=58, leg=50, hz=44, bounce=0.26, stance=2.8, speed=1.05,
        wrist=30, loose=1.80,
        note="ゴムの弾性。全部が少し遅れて追従し、戻りが行き過ぎる。"),
}

#  補助パーツの遅れ。本体と同時に全部動かさず、僅かに遅れて追従させる
#  （企画書 §07 表情・補助）。
FOLLOW_PHASE = 46


def secondary(c: dict, form: str) -> dict:
    """髪・帯・雲など、本体に遅れて付いてくるもの。"""
    hz = c["hz"]
    out = {
        "hair": rot(bob(2.6 * c["loose"], hz, FOLLOW_PHASE),
                    bob(1.6 * c["loose"], hz * 0.6, FOLLOW_PHASE), 0),
    }
    if form == "gear5":
        # 雲は4つとも別々の速さで巡らせる。同じ動きに見せない。
        for i in range(4):
            out[f"cloud{i}"] = {
                "rotation": [bob(5.0, 26 + i * 5, i * 90),
                             bob(360 if i % 2 == 0 else -360, 7 + i, i * 60), 0],
                "position": [bob(0.6, 21 + i * 4, i * 70),
                             bob(0.5, 18 + i * 3, i * 120), 0],
            }
        out["brow"] = rot(bob(1.2, 30), 0, 0)
        out["mouth"] = {"scale": [1.0, f"1.0 + {bob(0.06, 40)}", 1.0]}
    if form == "gear2":
        out["chest"] = rot(bob(1.4, hz, 30), 0, 0)
    return out


# ---------------------------------------------------------------------------
#  移動 (待機 / 歩行 / 走行 / 左右移動 / 空中 / 着地 / しゃがみ)
# ---------------------------------------------------------------------------
def idle_clip(form: str) -> dict:
    c = CHARACTER[form]
    hz = c["hz"]
    b = c["bounce"]
    bones = {
        "body": {"rotation": [off(c["lean"], bob(0.8, hz)), 0, bob(0.6, hz // 2)],
                 "position": [0, bob(b, hz, 90), 0]},
        "chest": rot(bob(1.0, hz, 40), 0, 0),
        "neck": rot(bob(0.7, hz, 80), bob(1.8, hz // 3), 0),
        "head": rot(bob(0.9, hz, 90), bob(2.4, hz // 3, 20), 0),
        "rightArm": rot(bob(2.2, hz - 4), 0, f"-3 - {bob(1.3, hz - 4)}"),
        "leftArm": rot(bob(2.2, hz - 4, 180), 0, f"3 + {bob(1.3, hz - 4, 180)}"),
        "rightForearm": rot(bob(1.8 * c["loose"], hz - 4, 40), 0, 0),
        "leftForearm": rot(bob(1.8 * c["loose"], hz - 4, 220), 0, 0),
        "rightHand": rot(bob(c["wrist"] * 0.16, hz - 4, 70), 0, 0),
        "leftHand": rot(bob(c["wrist"] * 0.16, hz - 4, 250), 0, 0),
    }
    bones.update(secondary(c, form))
    return clip(bones)


def _gait(form: str, run: bool) -> dict:
    c = CHARACTER[form]
    k = 1.0 if not run else 1.45
    arm = c["arm"] * (0.7 if not run else 1.0)
    leg = c["leg"] * (0.7 if not run else 1.0)
    lean = c["lean"] + (0 if not run else 8)
    sp = c["speed"] * (1.0 if not run else 1.15)
    bones = {
        "body": {"rotation": [off(lean, swing(2.4 * k, 0, sp * 2)), swing(4.0, 90, sp), 0],
                 "position": [0, swing(0.8 * k, 90, sp * 2, scale=SPD), 0]},
        "chest": rot(swing(2.0, 180, sp * 2), swing(5.0, 270, sp), 0),
        "head": rot(swing(2.6, 180, sp * 2), swing(4.0, 90, sp), 0),
        "rightArm": rot(swing(arm, 180, sp), 0, -3),
        "leftArm": rot(swing(arm, 0, sp), 0, 3),
        "rightForearm": rot(f"-{abs(arm) * 0.34:.1f} + {swing(arm * 0.30, 180, sp)}", 0, 0),
        "leftForearm": rot(f"-{abs(arm) * 0.34:.1f} + {swing(arm * 0.30, 0, sp)}", 0, 0),
        "rightLeg": rot(swing(leg, 0, sp), 0, 0),
        "leftLeg": rot(swing(leg, 180, sp), 0, 0),
        "rightShin": rot(f"{leg * 0.45:.1f} + {swing(leg * 0.45, 90, sp)}", 0, 0),
        "leftShin": rot(f"{leg * 0.45:.1f} + {swing(leg * 0.45, 270, sp)}", 0, 0),
        "rightFoot": rot(swing(leg * 0.30, 270, sp), 0, 0),
        "leftFoot": rot(swing(leg * 0.30, 90, sp), 0, 0),
    }
    bones.update(secondary(c, form))
    return clip(bones)


def strafe_clip(form: str) -> dict:
    """左右移動。進行方向と体のねじれが合っているかを見る用 (企画書 §07)。"""
    c = CHARACTER[form]
    sp = c["speed"]
    bones = {
        "body": {"rotation": [c["lean"], swing(9.0, 0, sp), swing(3.0, 90, sp)],
                 "position": [swing(0.5, 90, sp * 2, scale=SPD), 0, 0]},
        "head": rot(0, swing(-12.0, 0, sp), 0),
        "rightLeg": rot(swing(c["leg"] * 0.5, 0, sp), 0, swing(5.0, 0, sp)),
        "leftLeg": rot(swing(c["leg"] * 0.5, 180, sp), 0, swing(5.0, 180, sp)),
        "rightArm": rot(swing(c["arm"] * 0.35, 180, sp), 0, -6),
        "leftArm": rot(swing(c["arm"] * 0.35, 0, sp), 0, 6),
    }
    bones.update(secondary(c, form))
    return clip(bones)


def air_clip(form: str) -> dict:
    c = CHARACTER[form]
    hz = c["hz"]
    bones = {
        "body": rot(off(c["lean"] - 6, bob(2.0, hz * 0.7)), 0, bob(1.6, hz * 0.5)),
        "rightArm": rot(off(-52, bob(5.0, hz * 0.7)), 0, -16),
        "leftArm": rot(off(-52, bob(5.0, hz * 0.7, 180)), 0, 16),
        "rightForearm": rot(-24, 0, 0),
        "leftForearm": rot(-24, 0, 0),
        "rightLeg": rot(off(16, bob(4.0, hz * 0.6)), 0, 0),
        "leftLeg": rot(off(-10, bob(4.0, hz * 0.6, 180)), 0, 0),
        "rightShin": rot(28, 0, 0),
        "leftShin": rot(12, 0, 0),
        "head": rot(bob(2.4, hz * 0.7, 40), 0, 0),
    }
    bones.update(secondary(c, form))
    return clip(bones)


def land_clip(form: str) -> dict:
    """着地。止まるときの重心を見せる (企画書 §07 見るポイント)。"""
    c = CHARACTER[form]
    d = 0.42 * (1.0 + c["bounce"])
    return clip({
        "body": {"rotation": kf((0, [c["lean"] - 4, 0, 0]),
                                (d * 0.30, [c["lean"] + 16, 0, 0]),
                                (d * 0.62, [c["lean"] - 3, 0, 0]),
                                (d, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0.6, 0]), (d * 0.30, [0, -1.6, 0]),
                                (d * 0.62, [0, 0.3, 0]), (d, [0, 0, 0]))},
        "rightLeg": {"rotation": kf((0, [-14, 0, 0]), (d * 0.30, [26, 0, 0]),
                                    (d, [0, 0, 0]))},
        "leftLeg": {"rotation": kf((0, [-14, 0, 0]), (d * 0.30, [26, 0, 0]),
                                   (d, [0, 0, 0]))},
        "rightShin": {"rotation": kf((0, [10, 0, 0]), (d * 0.30, [-42, 0, 0]),
                                     (d, [0, 0, 0]))},
        "leftShin": {"rotation": kf((0, [10, 0, 0]), (d * 0.30, [-42, 0, 0]),
                                    (d, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [-40, 0, -10]), (d * 0.30, [18, 0, -22]),
                                    (d, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [-40, 0, 10]), (d * 0.30, [18, 0, 22]),
                                   (d, [0, 0, 3]))},
        "hair": {"rotation": kf((0, [-8, 0, 0]), (d * 0.42, [14, 0, 0]),
                                (d, [0, 0, 0]))},
    }, length=d, loop=False)


def crouch_clip(form: str) -> dict:
    c = CHARACTER[form]
    hz = c["hz"]
    bones = {
        "body": {"rotation": [off(c["lean"] + 26, bob(0.6, hz * 0.6)), 0, 0],
                 "position": [0, -3.4, 1.2]},
        "chest": rot(-8, 0, 0),
        "head": rot(off(-18, bob(0.8, hz * 0.6)), bob(2.0, hz * 0.3), 0),
        "rightArm": rot(-14, 0, -8),
        "leftArm": rot(-14, 0, 8),
        "rightLeg": rot(-26, 0, 0),
        "leftLeg": rot(-26, 0, 0),
        "rightShin": rot(42, 0, 0),
        "leftShin": rot(42, 0, 0),
        "rightFoot": rot(-16, 0, 0),
        "leftFoot": rot(-16, 0, 0),
    }
    bones.update(secondary(c, form))
    return clip(bones)


def hurt_clip(form: str) -> dict:
    c = CHARACTER[form]
    d = 0.36
    return clip({
        "body": {"rotation": kf((0, [c["lean"], 0, 0]), (0.08, [c["lean"] - 18, 6, 0]),
                                (0.22, [c["lean"] + 5, -2, 0]), (d, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0, 0]), (0.08, [0, 0, 1.6]), (d, [0, 0, 0]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (0.08, [-22, -10, 0]),
                                (d, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (0.08, [-30, 0, -24]),
                                    (d, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (0.08, [-30, 0, 24]),
                                   (d, [0, 0, 3]))},
    }, length=d, loop=False)


# ---------------------------------------------------------------------------
#  形態の登場演出。ギア5だけは企画書 §08 の 4.5 秒をそのまま起こす。
# ---------------------------------------------------------------------------
def arrival_clip(form: str) -> dict:
    """変身直後の専用ポーズ。ギア5以外は短い決めポーズで、次の待機へ繋ぐ。"""
    c = CHARACTER[form]
    d = 0.9
    return clip({
        "body": {"rotation": kf((0, [c["lean"] + 18, 0, 0]),
                                (0.22, [c["lean"] - 12, 0, 0]),
                                (0.55, [c["lean"] + 4, 0, 0]),
                                (d, [c["lean"], 0, 0])),
                 "position": kf((0, [0, -1.4, 0]), (0.22, [0, 0.9, 0]),
                                (d, [0, 0, 0]))},
        "chest": {"rotation": kf((0, [12, 0, 0]), (0.26, [-10, 0, 0]),
                                 (d, [0, 0, 0]))},
        "head": {"rotation": kf((0, [16, 0, 0]), (0.30, [-14, 0, 0]),
                                (0.62, [4, 0, 0]), (d, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [24, 0, -4]), (0.26, [-64, 0, -30]),
                                    (0.60, [-8, 0, -6]), (d, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [24, 0, 4]), (0.26, [-64, 0, 30]),
                                   (0.60, [-8, 0, 6]), (d, [0, 0, 3]))},
        "rightForearm": {"rotation": kf((0, [0, 0, 0]), (0.26, [-46, 0, 0]),
                                        (d, [0, 0, 0]))},
        "leftForearm": {"rotation": kf((0, [0, 0, 0]), (0.26, [-46, 0, 0]),
                                       (d, [0, 0, 0]))},
        "hair": {"rotation": kf((0, [18, 0, 0]), (0.34, [-16, 0, 0]),
                                (0.70, [6, 0, 0]), (d, [0, 0, 0]))},
    }, length=d, loop=False)


def nika_showpiece() -> dict:
    """看板演出 — ニカ変身後の浮遊・大爆笑 (企画書 §08)。

    spec.SHOWPIECE の各段の開始 tick をそのままキー時刻にする。表と実装が
    ずれないので、秒数を直す作業が1か所で済む。
    浮遊は「見た目の root を上げる」だけ。プレイヤーの実座標は動かさない。
    """
    t = [s["t"] / 20.0 for s in spec.SHOWPIECE]
    end = spec.SHOWPIECE_TICKS / 20.0
    lift = spec.SHOWPIECE_LIFT * 16.0          # ブロック -> モデル単位

    body_rot = kf(
        (t[0], [6, 0, 0]),           # 息を吸って丸める
        (t[1], [14, 0, 0]),
        (t[2], [-4, 0, 0]),          # 胸・肩・頭の順に持ち上がる
        (t[3], [-26, 0, 0]),         # 背を反らす
        (t[4], [-34, 0, 0]),         # 大爆笑
        (t[4] + 0.7, [-24, 0, 0]),
        (t[5], [-12, 0, 0]),
        (end, [0, 0, 0]),
    )
    body_pos = kf(
        (t[0], [0, 0, 0]), (t[1], [0, -0.8, 0]), (t[2], [0, 0.4, 0]),
        (t[3], [0, lift * 0.7, 0]), (t[4], [0, lift, 0]),
        (t[4] + 0.7, [0, lift * 0.92, 0]), (t[5], [0, lift * 0.45, 0]),
        (end, [0, 0, 0]),
    )
    return clip({
        "body": {"rotation": body_rot, "position": body_pos},
        "chest": {"rotation": kf((t[0], [10, 0, 0]), (t[1], [-6, 0, 0]),
                                 (t[2], [-12, 0, 0]), (t[4], [-18, 0, 0]),
                                 (t[4] + 0.5, [-8, 0, 0]), (end, [0, 0, 0]))},
        "head": {"rotation": kf((t[0], [12, 0, 0]), (t[1], [-4, 0, 0]),
                                (t[2], [-16, 0, 0]), (t[3], [-30, 0, 0]),
                                (t[4], [-38, 0, 0]), (t[4] + 0.6, [-26, 0, 0]),
                                (t[4] + 1.1, [-36, 0, 0]), (end, [0, 0, 0]))},
        # 腕は腹と顔へ
        "rightArm": {"rotation": kf((t[0], [8, 0, -4]), (t[2], [-30, 0, -18]),
                                    (t[4], [64, -22, -30]),
                                    (t[4] + 0.6, [52, -18, -26]),
                                    (t[5], [10, 0, -8]), (end, [0, 0, -3]))},
        "leftArm": {"rotation": kf((t[0], [8, 0, 4]), (t[2], [-30, 0, 18]),
                                   (t[4], [70, 26, 34]),
                                   (t[4] + 0.6, [58, 20, 28]),
                                   (t[5], [10, 0, 8]), (end, [0, 0, 3]))},
        "rightForearm": {"rotation": kf((t[0], [0, 0, 0]), (t[4], [-72, 0, 0]),
                                        (end, [0, 0, 0]))},
        "leftForearm": {"rotation": kf((t[0], [0, 0, 0]), (t[4], [-76, 0, 0]),
                                       (end, [0, 0, 0]))},
        # 膝を上げる
        "rightLeg": {"rotation": kf((t[0], [0, 0, 0]), (t[3], [-46, 0, 0]),
                                    (t[4], [-58, 0, 0]), (t[5], [-18, 0, 0]),
                                    (end, [0, 0, 0]))},
        "leftLeg": {"rotation": kf((t[0], [0, 0, 0]), (t[3], [-34, 0, 0]),
                                   (t[4], [-44, 0, 0]), (t[5], [-12, 0, 0]),
                                   (end, [0, 0, 0]))},
        "rightShin": {"rotation": kf((t[3], [64, 0, 0]), (t[4], [78, 0, 0]),
                                     (end, [0, 0, 0]))},
        "leftShin": {"rotation": kf((t[3], [48, 0, 0]), (t[4], [60, 0, 0]),
                                    (end, [0, 0, 0]))},
        # 笑顔 → 大笑い。口は縦に伸ばし、眉は上げる。
        "mouth": {"scale": kf((t[0], [1, 1, 1]), (t[2], [1.15, 1.4, 1]),
                              (t[4], [1.35, 2.6, 1.1]),
                              (t[4] + 0.35, [1.30, 2.1, 1.1]),
                              (t[4] + 0.8, [1.35, 2.6, 1.1]),
                              (t[5], [1.15, 1.4, 1]), (end, [1, 1, 1]))},
        "brow": {"rotation": kf((t[0], [6, 0, 0]), (t[2], [-10, 0, 0]),
                                (t[4], [-16, 0, 0]), (end, [0, 0, 0]))},
        # 髪と雲は本体に遅れて追従する
        "hair": {"rotation": kf((t[0], [10, 0, 0]), (t[1] + 0.1, [16, 0, 0]),
                                (t[2] + 0.1, [-10, 0, 0]),
                                (t[3] + 0.1, [-22, 0, 0]),
                                (t[4] + 0.2, [-14, 0, 0]),
                                (t[5] + 0.1, [8, 0, 0]), (end, [0, 0, 0]))},
        **{f"cloud{i}": {
            "rotation": kf((t[2], [0, 0, 0]), (t[4], [0, 180 * (1 if i % 2 else -1), 0]),
                           (end, [0, 360 * (1 if i % 2 else -1), 0])),
            "scale": kf((t[0], [0.2, 0.2, 0.2]), (t[2], [0.6, 0.6, 0.6]),
                        (t[3], [1.0, 1.0, 1.0]), (end, [1.0, 1.0, 1.0])),
        } for i in range(4)},
    }, length=end, loop=False)


def nika_showpiece_short() -> dict:
    """「演出短縮」を選んだときの版。決めの2段だけ残して 1.7 秒に畳む。"""
    end = spec.SHOWPIECE_SHORT_TICKS / 20.0
    lift = spec.SHOWPIECE_LIFT * 16.0
    return clip({
        "body": {"rotation": kf((0, [10, 0, 0]), (end * 0.35, [-26, 0, 0]),
                                (end * 0.75, [-16, 0, 0]), (end, [0, 0, 0])),
                 "position": kf((0, [0, 0, 0]), (end * 0.35, [0, lift, 0]),
                                (end, [0, 0, 0]))},
        "head": {"rotation": kf((0, [8, 0, 0]), (end * 0.35, [-34, 0, 0]),
                                (end, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [6, 0, -4]), (end * 0.40, [58, -18, -26]),
                                    (end, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [6, 0, 4]), (end * 0.40, [62, 22, 30]),
                                   (end, [0, 0, 3]))},
        "mouth": {"scale": kf((0, [1, 1, 1]), (end * 0.40, [1.32, 2.3, 1.1]),
                              (end, [1, 1, 1]))},
        "brow": {"rotation": kf((0, [4, 0, 0]), (end * 0.40, [-14, 0, 0]),
                                (end, [0, 0, 0]))},
    }, length=end, loop=False)


# ---------------------------------------------------------------------------
#  変身と解除（形態に依らない共通クリップ）
# ---------------------------------------------------------------------------
def transform_in() -> dict:
    return clip({
        "body": {"rotation": kf((0, [0, 0, 0]), (0.18, [16, 0, 0]),
                                (0.46, [-14, 0, 0]), (0.8, [0, 0, 0])),
                 "position": kf((0, [0, 0, 0]), (0.18, [0, -1.8, 0]),
                                (0.46, [0, 1.2, 0]), (0.8, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (0.18, [30, 0, -18]),
                                    (0.46, [-58, 0, -34]), (0.8, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (0.18, [30, 0, 18]),
                                   (0.46, [-58, 0, 34]), (0.8, [0, 0, 3]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (0.18, [18, 0, 0]),
                                (0.46, [-22, 0, 0]), (0.8, [0, 0, 0]))},
    }, length=0.8, loop=False)


def revert_out() -> dict:
    return clip({
        "body": {"rotation": kf((0, [0, 0, 0]), (0.16, [-10, 0, 0]),
                                (0.44, [14, 0, 0]), (0.7, [0, 0, 0])),
                 "position": kf((0, [0, 0, 0]), (0.44, [0, -1.2, 0]),
                                (0.7, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (0.44, [22, 0, -8]),
                                    (0.7, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (0.44, [22, 0, 8]),
                                   (0.7, [0, 0, 3]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (0.44, [16, 0, 0]),
                                (0.7, [0, 0, 0]))},
    }, length=0.7, loop=False)


# ---------------------------------------------------------------------------
#  技 — spec.py の windup / active / recover から起こす
#  企画書 §07「1技の時間設計例」: 沈む → 肩・胴・腕の順に加速 → 命中 → 反動と戻り
# ---------------------------------------------------------------------------
#  shape ごとの「構え」。同じ直線技でも、伸ばす／押す／薙ぐで別の骨が動く。
def _line(c, t0, t1, t2, t3, sgn=-1):
    """伸ばす単拳。肩→胴→腕の順に遅れて加速させる。"""
    a, b = ("right", "left") if sgn < 0 else ("left", "right")
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] + 10, -sgn * 16, 0]),
                                (t1, [c["lean"] - 6, sgn * 22, 0]),
                                (t2, [c["lean"] - 2, sgn * 12, 0]),
                                (t3, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0, 0]), (t0, [0, -1.0, 0.8]),
                                (t1, [0, 0.4, -1.6]), (t3, [0, 0, 0]))},
        "chest": {"rotation": kf((0, [0, 0, 0]), (t0, [6, -sgn * 10, 0]),
                                 (t1, [-8, sgn * 14, 0]), (t3, [0, 0, 0]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [8, -sgn * 12, 0]),
                                (t1, [-6, sgn * 8, 0]), (t3, [0, 0, 0]))},
        f"{a}Arm": {"rotation": kf((0, [0, 0, -sgn * -3]),
                                   (t0, [58, sgn * 14, sgn * 18]),
                                   (t1, [-96, 0, sgn * 4]),
                                   (t2, [-84, 0, sgn * 4]),
                                   (t3, [0, 0, sgn * 3]))},
        f"{a}Forearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-64, 0, 0]),
                                       (t1, [4, 0, 0]), (t3, [0, 0, 0]))},
        f"{a}Hand": {"rotation": kf((0, [0, 0, 0]), (t0, [-18, 0, 0]),
                                    (t1, [8, 0, 0]), (t3, [0, 0, 0]))},
        f"{b}Arm": {"rotation": kf((0, [0, 0, sgn * -3]), (t0, [-26, 0, sgn * -16]),
                                   (t1, [22, 0, sgn * -22]), (t3, [0, 0, sgn * -3]))},
    }


def _cone(c, t0, t1, t2, t3):
    """両手の押し出し。溜めがある分だけ胴を大きく沈める。"""
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] + 18, 0, 0]),
                                (t1, [c["lean"] - 12, 0, 0]),
                                (t3, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0, 0]), (t0, [0, -2.2, 1.4]),
                                (t1, [0, 0.6, -2.0]), (t3, [0, 0, 0]))},
        "chest": {"rotation": kf((0, [0, 0, 0]), (t0, [14, 0, 0]),
                                 (t1, [-14, 0, 0]), (t3, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (t0, [44, 22, -28]),
                                    (t1, [-88, 6, -10]), (t2, [-78, 6, -10]),
                                    (t3, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (t0, [44, -22, 28]),
                                   (t1, [-88, -6, 10]), (t2, [-78, -6, 10]),
                                   (t3, [0, 0, 3]))},
        "rightForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-72, 0, 0]),
                                        (t1, [2, 0, 0]), (t3, [0, 0, 0]))},
        "leftForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-72, 0, 0]),
                                       (t1, [2, 0, 0]), (t3, [0, 0, 0]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [14, 0, 0]),
                                (t1, [-10, 0, 0]), (t3, [0, 0, 0]))},
    }


def _arc(c, t0, t1, t2, t3):
    """薙ぎ／曲がる軌道。腰の回転を主役にして、腕はその後を追う。"""
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] + 6, -46, 0]),
                                (t1, [c["lean"], 52, 0]),
                                (t2, [c["lean"], 34, 0]),
                                (t3, [c["lean"], 0, 0]))},
        "chest": {"rotation": kf((0, [0, 0, 0]), (t0, [0, -24, 0]),
                                 (t1, [0, 30, 0]), (t3, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (t0, [10, -58, -54]),
                                    (t1, [-62, 44, -18]), (t2, [-40, 30, -14]),
                                    (t3, [0, 0, -3]))},
        "rightForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-44, 0, 0]),
                                        (t1, [-6, 0, 0]), (t3, [0, 0, 0]))},
        "rightHand": {"rotation": kf((0, [0, 0, 0]), (t0, [0, -26, 0]),
                                     (t1, [0, 22, 0]), (t3, [0, 0, 0]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (t0, [-20, 0, 34]),
                                   (t1, [26, 0, 16]), (t3, [0, 0, 3]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [0, -30, 0]),
                                (t1, [0, 26, 0]), (t3, [0, 0, 0]))},
    }


def _slam(c, t0, t1, t2, t3):
    """振り下ろし／打ち上げ。上に大きく振りかぶってから落とす。"""
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] - 24, 0, 0]),
                                (t1, [c["lean"] + 34, 0, 0]),
                                (t2, [c["lean"] + 22, 0, 0]),
                                (t3, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0, 0]), (t0, [0, 1.8, 0]),
                                (t1, [0, -2.6, 0]), (t3, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (t0, [-168, 0, -16]),
                                    (t1, [42, 0, -6]), (t2, [30, 0, -6]),
                                    (t3, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (t0, [-168, 0, 16]),
                                   (t1, [42, 0, 6]), (t2, [30, 0, 6]),
                                   (t3, [0, 0, 3]))},
        "rightForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-38, 0, 0]),
                                        (t1, [6, 0, 0]), (t3, [0, 0, 0]))},
        "leftForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-38, 0, 0]),
                                       (t1, [6, 0, 0]), (t3, [0, 0, 0]))},
        "rightLeg": {"rotation": kf((0, [0, 0, 0]), (t1, [-22, 0, 0]),
                                    (t3, [0, 0, 0]))},
        "leftLeg": {"rotation": kf((0, [0, 0, 0]), (t1, [14, 0, 0]),
                                   (t3, [0, 0, 0]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [-26, 0, 0]),
                                (t1, [26, 0, 0]), (t3, [0, 0, 0]))},
    }


def _radial(c, t0, t1, t2, t3):
    """全方位。体を縮めてから一気に開く。"""
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] + 28, 0, 0]),
                                (t1, [c["lean"] - 22, 0, 0]),
                                (t3, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0, 0]), (t0, [0, -2.6, 0]),
                                (t1, [0, 2.0, 0]), (t3, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (t0, [64, 0, -46]),
                                    (t1, [-24, 0, -86]), (t2, [-16, 0, -74]),
                                    (t3, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (t0, [64, 0, 46]),
                                   (t1, [-24, 0, 86]), (t2, [-16, 0, 74]),
                                   (t3, [0, 0, 3]))},
        "rightForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-84, 0, 0]),
                                        (t1, [0, 0, 0]), (t3, [0, 0, 0]))},
        "leftForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-84, 0, 0]),
                                       (t1, [0, 0, 0]), (t3, [0, 0, 0]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [24, 0, 0]),
                                (t1, [-26, 0, 0]), (t3, [0, 0, 0]))},
    }


def _dash(c, t0, t1, t2, t3):
    """自分が飛ぶ技。溜めで沈み、射出で伸び切る。"""
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] + 30, 0, 0]),
                                (t1, [c["lean"] + 4, 0, 0]),
                                (t2, [c["lean"] + 12, 0, 0]),
                                (t3, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0, 0]), (t0, [0, -2.8, 1.6]),
                                (t1, [0, 0.8, -2.4]), (t3, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (t0, [40, 0, -12]),
                                    (t1, [-30, 0, -8]), (t3, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (t0, [40, 0, 12]),
                                   (t1, [-30, 0, 8]), (t3, [0, 0, 3]))},
        "rightLeg": {"rotation": kf((0, [0, 0, 0]), (t0, [-52, 0, 0]),
                                    (t1, [24, 0, 0]), (t3, [0, 0, 0]))},
        "leftLeg": {"rotation": kf((0, [0, 0, 0]), (t0, [-32, 0, 0]),
                                   (t1, [-14, 0, 0]), (t3, [0, 0, 0]))},
        "rightShin": {"rotation": kf((0, [0, 0, 0]), (t0, [76, 0, 0]),
                                     (t1, [10, 0, 0]), (t3, [0, 0, 0]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [18, 0, 0]),
                                (t1, [-12, 0, 0]), (t3, [0, 0, 0]))},
    }


def _throw(c, t0, t1, t2, t3):
    """投擲。掴んで振りかぶり、放して残心。"""
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] + 6, -34, 0]),
                                (t1, [c["lean"] - 8, 40, 0]),
                                (t3, [c["lean"], 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (t0, [-142, -16, -24]),
                                    (t1, [-34, 12, -6]), (t2, [4, 8, -4]),
                                    (t3, [0, 0, -3]))},
        "rightForearm": {"rotation": kf((0, [0, 0, 0]), (t0, [-76, 0, 0]),
                                        (t1, [-8, 0, 0]), (t3, [0, 0, 0]))},
        "rightHand": {"rotation": kf((0, [0, 0, 0]), (t0, [-30, 0, 0]),
                                     (t1, [26, 0, 0]), (t3, [0, 0, 0]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (t0, [-58, 0, 30]),
                                   (t1, [18, 0, 12]), (t3, [0, 0, 3]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [-14, -20, 0]),
                                (t1, [6, 18, 0]), (t3, [0, 0, 0]))},
    }


def _brace(c, t0, t1, t2, t3):
    """自己強化・区域技。攻撃ではないので、踏みしめて構えるだけにする。"""
    return {
        "body": {"rotation": kf((0, [c["lean"], 0, 0]),
                                (t0, [c["lean"] + 20, 0, 0]),
                                (t1, [c["lean"] - 14, 0, 0]),
                                (t2, [c["lean"] - 6, 0, 0]),
                                (t3, [c["lean"], 0, 0])),
                 "position": kf((0, [0, 0, 0]), (t0, [0, -2.0, 0]),
                                (t1, [0, 1.0, 0]), (t3, [0, 0, 0]))},
        "rightArm": {"rotation": kf((0, [0, 0, -3]), (t0, [28, 0, -34]),
                                    (t1, [-14, 0, -52]), (t3, [0, 0, -3]))},
        "leftArm": {"rotation": kf((0, [0, 0, 3]), (t0, [28, 0, 34]),
                                   (t1, [-14, 0, 52]), (t3, [0, 0, 3]))},
        "rightLeg": {"rotation": kf((0, [0, 0, 0]), (t0, [-18, 0, 0]),
                                    (t3, [0, 0, 0]))},
        "leftLeg": {"rotation": kf((0, [0, 0, 0]), (t0, [-18, 0, 0]),
                                   (t3, [0, 0, 0]))},
        "head": {"rotation": kf((0, [0, 0, 0]), (t0, [16, 0, 0]),
                                (t1, [-20, 0, 0]), (t3, [0, 0, 0]))},
    }


SHAPE_POSE = {
    "line": _line,
    "slam": _slam,
    "cone": _cone,
    "arc": _arc,
    "sphere": _radial,
    "zone": _brace,
    "self": _brace,
    "dash": _dash,
    "projectile": _throw,
    "delayed": _slam,
}

#  shape が slam でなくても振り下ろしで見せたい技。
#  地面のゴム化は区域技だが、動作としては踏み下ろしたい。
SLAM_SLUGS = {"rubber_ground"}


def tech_clip(t: spec.Tech) -> dict:
    """技1つぶんのクリップ。時間は判定と同じ spec の値から起こす。"""
    c = CHARACTER[t.form]
    w, a, r = t.windup / 20.0, t.active / 20.0, t.recover / 20.0
    total = w + a + r
    # 沈む → 加速 → 命中 → 反動と戻り
    t0 = max(0.04, w * 0.80)          # 溜め切り
    t1 = w + a * 0.28                 # 命中の瞬間
    t2 = w + a                        # 有効時間の終わり
    t3 = total
    pose = _slam if t.slug in SLAM_SLUGS else SHAPE_POSE[t.shape]
    bones = pose(c, t0, t1, t2, t3)
    if t.hits > 1:
        # 連打は腕を往復させる。単発と見分けが付くように回数だけ刻む。
        step = max(0.05, (a) / max(1, t.hits))
        frames = [(0, [0, 0, -3])]
        for i in range(min(t.hits, 10)):
            frames.append((w + step * i, [-96 if i % 2 == 0 else -70, 0, -4]))
            frames.append((w + step * (i + 0.5), [-44, 0, -6]))
        frames.append((t3, [0, 0, -3]))
        bones["rightArm"] = {"rotation": kf(*frames)}
        bones["leftArm"] = {"rotation": kf(
            *[(ft, [v[0] if i % 2 else v[0] * 0.5, -v[1], -v[2]])
              for i, (ft, v) in enumerate(frames)])}
    if t.form == "gear3":
        # 技中だけ前腕と拳を膨らませる（企画書 §04 技中の部位変形）
        for bone, peak in (("rightForearm", 2.6), ("rightHand", 3.0)):
            bones.setdefault(bone, {})["scale"] = kf(
                (0, [1, 1, 1]), (t0, [peak * 0.5, peak * 0.5, peak * 0.5]),
                (t1, [peak, peak, peak]), (t2, [peak * 0.8, peak * 0.8, peak * 0.8]),
                (t3, [1, 1, 1]))
    return clip(bones, length=total, loop=False)


# ---------------------------------------------------------------------------
#  組み立て
# ---------------------------------------------------------------------------
def build() -> None:
    for form in spec.FORM_ORDER:
        p = f"animation.{NS}.{form}."
        A[p + "idle"] = idle_clip(form)
        A[p + "walk"] = _gait(form, run=False)
        A[p + "run"] = _gait(form, run=True)
        A[p + "strafe"] = strafe_clip(form)
        A[p + "air"] = air_clip(form)
        A[p + "land"] = land_clip(form)
        A[p + "crouch"] = crouch_clip(form)
        A[p + "hurt"] = hurt_clip(form)
        A[p + "laugh"] = (nika_showpiece() if form == "gear5"
                          else arrival_clip(form))
    A[f"animation.{NS}.gear5.laugh_short"] = nika_showpiece_short()
    A[f"animation.{NS}.form.transform_in"] = transform_in()
    A[f"animation.{NS}.form.revert"] = revert_out()
    for t in spec.TECHS:
        A[t.anim_id] = tech_clip(t)


def state(animations=None, transitions=None, blend=None):
    d = {}
    if animations:
        d["animations"] = animations
    if transitions:
        d["transitions"] = transitions
    if blend is not None:
        d["blend_transition"] = blend
    return d


#  アタッチャブルの animation controller。
#  企画書 §07「コントローラの分離」— 優先順位は 復旧・解除 ＞ 変身 ＞ 攻撃 ＞
#  移動 ＞ 待機。ここで観測できるのは組み込みのクエリだけなので、移動系の
#  出し分けだけを担当し、技ごとの専用クリップはスクリプト側から再生する。
CONTROLLERS = {
    f"controller.animation.{NS}.form": {
        "initial_state": "idle",
        "states": {
            "idle": state(["idle"], [
                {"crouch": "query.is_sneaking"},
                {"air": "!query.is_on_ground"},
                {"move": f"{SPD} > 0.02"},
            ], blend=0.25),
            "move": state(["walk"], [
                {"crouch": "query.is_sneaking"},
                {"air": "!query.is_on_ground"},
                {"run": f"{SPD} > 0.14"},
                {"idle": f"{SPD} <= 0.02"},
            ], blend=0.2),
            "run": state(["run"], [
                {"crouch": "query.is_sneaking"},
                {"air": "!query.is_on_ground"},
                {"move": f"{SPD} <= 0.14"},
            ], blend=0.2),
            "air": state(["air"], [
                {"land": "query.is_on_ground"},
            ], blend=0.15),
            "land": state(["land"], [
                {"air": "!query.is_on_ground"},
                {"idle": "query.all_animations_finished"},
            ], blend=0.15),
            "crouch": state(["crouch"], [
                {"air": "!query.is_on_ground"},
                {"idle": "!query.is_sneaking"},
            ], blend=0.25),
        },
    },
}


def main() -> None:
    build()
    os.makedirs(os.path.join(RP, "animations"), exist_ok=True)
    os.makedirs(os.path.join(RP, "animation_controllers"), exist_ok=True)
    with open(os.path.join(RP, "animations", f"{NS}.animation.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format_version": "1.8.0", "animations": A}, fh, indent=2,
                  ensure_ascii=False)
        fh.write("\n")
    with open(os.path.join(RP, "animation_controllers",
                           f"{NS}.animation_controllers.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format_version": "1.10.0",
                   "animation_controllers": CONTROLLERS}, fh, indent=2,
                  ensure_ascii=False)
        fh.write("\n")
    one_shot = sum(1 for v in A.values() if v["loop"] is False)
    print(f"animations: {len(A)} clips ({one_shot} one-shot), "
          f"{len(CONTROLLERS)} controllers")


if __name__ == "__main__":
    main()
