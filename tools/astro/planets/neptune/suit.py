# -*- coding: utf-8 -*-
"""海王星 — 深淵機装 トリトン（Triton Frame）。深海の騎士（v1.1: 7 頭身・細かい部品）。

藍（plate2）を主に、紺碧（plate）は重ねた上板と鱗に。縁取りは金ではなく真珠色の銀（pearl）。
白い波頭のヒレ（fin）は「曲がった条（すじ）を細かい節で繋いだ」扇で作る（ray_fin）。発光は生物発光の水色。
frame7 の暗い機械の骨格（細身 bulk 0.92）の上に:

  兜     藍の小さなドーム・額の三叉の冠（返しの付いた三本の穂先。飾り）・頭頂から後ろへ流れる背ビレの鶏冠・
         後ろへ流れる耳ビレ・こめかみの鰓のスリット・鋭く吊り上がった二つの目・鰓の格子の面頬・鱗のしころ
  胴     逆三角形の藍の胸・左右に三枚重ねの鰓の胸板（間から水色の光）・中央の竜骨・暗斑の海王星の星核と
         逆回り（逆行）の嵐の羽根（fx_spin_storm）・菱形の鱗を重ねた細い腹・襟・脇の鰓の排気口
  背中   水流タービン（真珠の輪の吸気口と回る羽根 fx_spin_turbine）・肩甲骨から外上へ反る白い背ビレ（飾り）・
         下後ろへ向けた双発スラスター・背骨の小ビレ・蛇腹のホース
  腰     三叉の紋の留め金・細い前垂れ・鱗の草摺と白いヒレ先・後ろ垂れ・二股に分かれた尾ビレのマント（空中で開く）
  腕     藍の二の腕・真珠の腕輪と宝玉・肘の棘・肘の外のピストン・鱗の篭手と前腕の白いヒレ・指の甲当て
  肩     丸い貝殻の肩当て（藍の殻 + 紺碧の外の段 + 真珠の縁 + 紋章）と後ろのヒレ
  脚     縁取りの腿当て（型番）・帆立貝の膝当てと外のピストン・菱形の鱗の脛当て・ふくらはぎの鰓の排気口と白いヒレ・
         舳先のように尖ったサバトンと踵の噴射口・足首の外の小ビレ

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）から取る。
右側だけ作り `_r` を付ける → 左は自動で鏡映。回転（統合版の rotation）: rx 正 = 上端が前へ /
ry 正 = 正面が右（-X）を向く（+X の端が前へ）/ rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。

この惑星だけの形の道具（共通部分には無い）: ray_fin（曲がった条の扇・ヒレ）、scale_patch（傾いた板の面に
菱形の鱗を段違いに貼る）。v1 の fin3 / fan_fin / diamond / scales はナノウェポンが使うので残す。
"""
from __future__ import annotations

import math

import numpy as np

from astro_common import FACE_AXES, cube_rot, mat_cube, surface
from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, layered_plate,  # noqa: F401
                        line_on, mirror_x, octa, piston, polyline, rbox, ring, rivets, sensor,
                        stick, taper, vents)
from hd_space import rot

TRIM_W = 0.24          # 真珠の縁取りの幅
FIN = ["fin", "fin_m"]  # ヒレの条（白と淡い水色を交互に。ナノウェポンも使う）
LEAD = ["pearl", "fin", "fin", "fin", "fin"]   # 前縁の条だけ真珠、残りは白（間に fin_web の膜）
LX = A.LEG_X           # 脚の軸 -2.15
HZ = A.HEAD_Z          # 頭の中心の奥行き -0.25

# 配色（astro_data の neptune: plate 紺碧 / plate2 藍 / glow 水色 / accent 白）
AZURE = (36, 92, 214)
INDIGO = (36, 48, 148)
ABYSS = (12, 16, 40)
AQUA = (79, 227, 255)
FOAM = (234, 244, 255)
PEARL = (200, 224, 238)


# ===========================================================================
#  形の道具（このスーツとナノウェポンで使う）
# ===========================================================================
def _v(p):
    return np.asarray(p, float)


def _unit(v):
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else v


def ray_fin(bone, roots, tips, thick, styles, seg=0.9, w0=0.75, w1=0.45, bend=0.0,
            bend_dir=None, tip_style=None, lead=None, lead_w=0.3, normal=None, extend=0.1,
            web=None, web_seg=None, web_t=0.84, web_k=0.55, **kw):
    """ヒレ（扇）: 根元 roots[i] から先 tips[i] へ伸びる条を、曲がった（2 次ベジエ）細い節の列で作る。
    条の幅は根元 w0 → 先 w1 に細る。節の長さは seg 以下（seg ≤ 0.9 なら「細かい部品」）。
    web に塗りを渡すと、隣り合う条の間に膜（条より薄い板）を張る。膜は条の先 web_t までで止まり、
    条の先が波頭のように飛び出す。膜の節は web_seg（省略で seg の 1.6 倍）。
    bend: 条の長さに対する曲がりの大きさ。bend_dir（ワールドの向き）の方へ反る（省略で面の中の垂直）。
    styles: 条ごとに交互に塗る / tip_style: 先の節の塗り / lead: 前縁（条 0）に沿う縁取りの塗り。
    すべての条は 1 枚の平面（normal。省略で点から求める）の上に置く。戻り値はキューブのリスト。"""
    R0 = [_v(p) for p in roots]
    T0 = [_v(p) for p in tips]
    n = len(T0)
    if len(R0) == 1:
        R0 = R0 * n
    elif len(R0) == 2 and n > 2:
        R0 = [R0[0] + (R0[1] - R0[0]) * (i / (n - 1)) for i in range(n)]
    if normal is None:
        d0 = T0[0] - R0[0]
        cands = [np.cross(d0, R0[-1] - R0[0]), np.cross(d0, T0[-1] - R0[-1])]
        N = max(cands, key=lambda v: float(np.linalg.norm(v)))
    else:
        N = _v(normal)
    N = _unit(N)
    out = []

    def ctrl(P0, P2):
        d = P2 - P0
        L = float(np.linalg.norm(d))
        if bend_dir is not None:
            b = _v(bend_dir)
            b = b - N * float(np.dot(b, N))
            b = b - _unit(d) * float(np.dot(b, _unit(d)))
            off = _unit(b) * bend * L if np.linalg.norm(b) > 1e-6 else np.zeros(3)
        else:
            off = _unit(np.cross(N, d)) * bend * L
        return (P0 + P2) / 2 + off, L

    def bez(P0, C, P2, t):
        return (1 - t) ** 2 * P0 + 2 * (1 - t) * t * C + t * t * P2

    def curve(P0, P2, step):
        C, L = ctrl(P0, P2)
        approx = L * (1.0 + 2.6 * bend * bend)       # 弧長を粗く見積もって節の数を決める
        k = max(1, int(math.ceil(approx / step - 1e-6)))
        return [bez(P0, C, P2, t) for t in np.linspace(0, 1, k + 1)]

    def frame(a, b):
        dd = b - a
        ln = float(np.linalg.norm(dd))
        dz = dd / ln
        Nn = _unit(N - dz * float(np.dot(N, dz)))
        wv = _unit(np.cross(Nn, dz))
        return np.column_stack([Nn, wv, np.cross(Nn, wv)]), ln

    def segs(pts, wa, wb, thick_, sty, tip):
        res = []
        k = len(pts) - 1
        for j in range(k):
            a, b = pts[j], pts[j + 1]
            if float(np.linalg.norm(b - a)) < 1e-4:
                continue
            R, ln = frame(a, b)
            w = wa + (wb - wa) * (j + 0.5) / k
            st = tip if (tip and j == k - 1) else sty
            res.append(mat_cube(bone, (a + b) / 2, (thick_, max(0.15, w), ln + extend), st, R, **kw))
        return res

    for i in range(n):
        st = styles[i % len(styles)] if isinstance(styles, (list, tuple)) else styles
        tp = None
        if tip_style:
            tp = tip_style[i % len(tip_style)] if isinstance(tip_style, (list, tuple)) else tip_style
        out += segs(curve(R0[i], T0[i], seg), w0, w1, thick, st, tp)
    if web and n > 1:
        ws = web_seg or seg * 1.6
        for i in range(n - 1):
            Ca, _La = ctrl(R0[i], T0[i])
            Cb, _Lb = ctrl(R0[i + 1], T0[i + 1])
            mid_len = float(np.linalg.norm((T0[i] + T0[i + 1]) / 2 - (R0[i] + R0[i + 1]) / 2))
            k = max(1, int(math.ceil(mid_len * web_t / ws - 1e-6)))
            ts = np.linspace(0.0, web_t, k + 1)
            for j in range(k):
                pa0, pb0 = bez(R0[i], Ca, T0[i], ts[j]), bez(R0[i + 1], Cb, T0[i + 1], ts[j])
                pa1, pb1 = bez(R0[i], Ca, T0[i], ts[j + 1]), bez(R0[i + 1], Cb, T0[i + 1], ts[j + 1])
                a, b = (pa0 + pb0) / 2, (pa1 + pb1) / 2
                if float(np.linalg.norm(b - a)) < 1e-4:
                    continue
                R, ln = frame(a, b)
                w = (float(np.linalg.norm(pa0 - pb0)) + float(np.linalg.norm(pa1 - pb1))) / 2 + 0.12
                out.append(mat_cube(bone, (a + b) / 2, (max(0.15, thick * web_k), w, ln + 0.06),
                                    web, R, **kw))
    if lead:
        # 前縁: 条 0 の外側の縁に沿う細い縁取り（少し厚い）
        side = (R0[0] - R0[1]) + (T0[0] - T0[1]) if n > 1 else np.cross(N, T0[0] - R0[0])
        side = side - N * float(np.dot(side, N))
        side = _unit(side)
        pts = [p + side * max(0.0, (w0 - lead_w) / 2 * 0.8) for p in curve(R0[0], T0[0], seg)]
        out += segs(pts, lead_w, max(0.15, lead_w * 0.7), thick + 0.14, lead, None)
    return out


def scale_patch(bone, c, face, cols, d=0.8, t=0.28, styles=("plate",), b0=0.12, b1=0.88,
                lift=14.0, sink=0.06, a_mid=0.5, **kw):
    """傾いた板 c の面 face に、菱形の鱗を段違いに貼る（上の段の下端が下の段に重なる）。
    cols: 段ごとの個数（上から）。d: 菱形の対角線（隣の鱗との間隔）。lift: 鱗の下端を面から起こす角度。
    段の高さは b0..b1（面の 0..1）に均等に並べる。戻り値はキューブのリスト。"""
    ia, ib, inn, sg = FACE_AXES[face]
    sa = c.size[ia] + 2 * c.inflate
    ea, eb, en = np.zeros(3), np.zeros(3), np.zeros(3)
    ea[ia], eb[ib], en[inn] = 1.0, 1.0, float(sg)
    M = np.column_stack([ea, eb, en])
    if np.linalg.det(M) < 0:
        M[:, 0] *= -1
    th = math.radians(-lift)
    Rx = np.array([[1, 0, 0], [0, math.cos(th), -math.sin(th)], [0, math.sin(th), math.cos(th)]])
    q = math.radians(45)
    Rz = np.array([[math.cos(q), -math.sin(q), 0], [math.sin(q), math.cos(q), 0], [0, 0, 1.0]])
    R = cube_rot(c) @ M @ Rx @ Rz
    side = d / math.sqrt(2) * 1.04
    rows = len(cols)
    out = []
    for r, nc in enumerate(cols):
        b = b1 - (b1 - b0) * (r / max(1, rows - 1)) if rows > 1 else (b0 + b1) / 2
        for i in range(nc):
            a = a_mid + (i - (nc - 1) / 2) * d / sa
            p, nn = surface(c, face, a, b)
            cen = p + nn * (t / 2 - sink + side * 0.35 * abs(math.sin(th)))
            st = styles[(r + i) % len(styles)]
            out.append(mat_cube(bone, cen, (side, side, t), st, R, **kw))
    return out


# ---- v1 の道具（ナノウェポンが使う） ----------------------------------------
def fin3(bone, A_, B, C, thick, layer, style, overlap=0.15, styles=None, **kw):
    """三角形 ABC を、辺 A→B に平行な細い板（ヒレの条）を C へ向かって重ねて埋める。"""
    A_, B, C = _v(A_), _v(B), _v(C)
    e = B - A_
    L = float(np.linalg.norm(e))
    e /= L
    N = np.cross(B - A_, C - A_)
    N /= np.linalg.norm(N)
    n = np.cross(N, e)
    cu, cv = float(np.dot(C - A_, e)), float(np.dot(C - A_, n))
    if cv < 0:
        n, cv = -n, -cv
    R = np.column_stack([N, n, np.cross(N, n)])
    out = []
    k = int(math.ceil(cv / layer - 1e-6))
    h = cv / k
    for i in range(k):
        d = h * (i + 0.5)
        s = d / cv
        u0, u1 = sorted((s * cu, L + s * (cu - L)))
        ln = u1 - u0 + overlap
        if ln < 0.2:
            continue
        cen = A_ + e * ((u0 + u1) / 2) + n * d
        st = styles[i % len(styles)] if styles else style
        out.append(mat_cube(bone, cen, (thick, h * 1.06, ln), st, R, **kw))
    return out


def fan_fin(bone, base0, base1, edge, thick, style, width=None, styles=None, taper_k=0.7,
            tip_style=None, **kw):
    """（v1）ヒレ: 付け根 base0→base1 から外縁の点列 edge へ放射状に伸びる条の板（2 段で細る）。"""
    b0, b1 = _v(base0), _v(base1)
    E = [_v(p) for p in edge]
    n = len(E)
    N = np.cross(b1 - b0, E[0] - b0)
    if np.linalg.norm(N) < 1e-6:
        N = np.cross(b1 - b0, E[-1] - b0)
    N /= np.linalg.norm(N)
    out = []
    for i, P in enumerate(E):
        root = b0 + (b1 - b0) * (i / max(1, n - 1))
        d = P - root
        L = float(np.linalg.norm(d))
        if L < 0.2:
            continue
        dz = d / L
        wv = np.cross(N, dz)
        R = np.column_stack([N, wv, np.cross(N, wv)])
        if width is None:
            sp = float(np.linalg.norm(b1 - b0)) / max(1, n - 1)
            nb = float(np.linalg.norm(E[min(n - 1, i + 1)] - E[max(0, i - 1)])) / 2
            w = max(0.5, (sp + nb) * 0.75)
        else:
            w = width[i] if isinstance(width, (list, tuple)) else width
        st = styles[i % len(styles)] if styles else style
        for k, (t0, t1, ww) in enumerate(((0.0, 0.55, w), (0.5, 1.0, w * taper_k))):
            c = root + d * ((t0 + t1) / 2)
            sk = (tip_style[i % len(tip_style)] if isinstance(tip_style, (list, tuple))
                  else tip_style) if (k == 1 and tip_style) else st
            out.append(mat_cube(bone, c, (thick, ww, L * (t1 - t0) + 0.1), sk, R, **kw))
    return out


def diamond(bone, centre, d, t, style, tilt=0.0, yaw=0.0, **kw):
    """対角線 d の菱形の板（厚み t）。tilt は上端を前へ倒す角度（負で下端が前 = 鱗の重なり）。"""
    s = d / math.sqrt(2)
    R = rot(tilt, yaw, 0) @ rot(0, 0, 45)
    return mat_cube(bone, centre, (s, s, t), style, R, **kw)


def scales(bone, cx, y0, z, rows, d, widths, style, t=0.5, tilt=-16.0, styles=None, yaw=0.0):
    """（v1）菱形の鱗を段にして並べる。widths は段ごとの幅（個数を決める）。"""
    out = []
    for r in range(rows):
        y = y0 - r * d * 0.55
        w = widths[r] if isinstance(widths, (list, tuple)) else widths
        n = max(1, int(round(w / d)))
        if r % 2 == 1:
            n = max(1, n - 1)
        x0 = cx - (n - 1) * d / 2
        for i in range(n):
            st = styles[(r + i) % len(styles)] if styles else style
            out.append(diamond(bone, (x0 + i * d, y, z - r * 0.02), d, t, st, tilt=tilt, yaw=yaw))
    return out


# ===========================================================================
#  塗り（astro_paint.suit_styles("neptune") への上書き・追加）
# ===========================================================================
_PEARL = {"kind": "trim", "base": PEARL, "light": (255, 255, 255), "dark": (96, 132, 176),
          "line": (36, 52, 96)}
SUIT_STYLES = {
    "plate": {"base": AZURE, "light": (120, 170, 245), "dark": (18, 52, 140),
              "line": (10, 30, 92)},
    "plate_b": {"base": (26, 68, 170), "light": (90, 140, 230), "dark": (14, 40, 112),
                "line": (8, 24, 80)},
    "plate2": {"base": INDIGO, "light": (92, 116, 218), "dark": (18, 24, 86),
               "line": (8, 10, 44), "groove": (16, 20, 70)},
    "plate2_b": {"base": (26, 34, 112), "light": (70, 88, 180), "dark": (14, 18, 64),
                 "line": (6, 8, 32)},
    # 白い波頭のヒレ（条の筋）
    "fin": {"kind": "armor", "base": FOAM, "light": (255, 255, 255), "dark": (176, 204, 238),
            "line": (120, 160, 220), "panel": 0, "bolts": False, "outline_k": 0.35,
            "bevel_lo": 0.92, "unlit": True},
    "fin_m": {"kind": "armor", "base": (190, 222, 250), "light": (236, 248, 255),
              "dark": (140, 186, 236), "line": (110, 150, 214), "panel": 0, "bolts": False,
              "sheen": False, "outline_k": 0.3, "bevel_lo": 0.92, "unlit": True},
    # ヒレの膜（条の間。淡い水色で、白い条が浮いて見える）
    "fin_web": {"kind": "armor", "base": (150, 196, 242), "light": (214, 238, 255),
                "dark": (96, 146, 214), "line": (70, 112, 186), "panel": 0, "bolts": False,
                "sheen": False, "outline_k": 0.25, "bevel_lo": 0.94, "unlit": True},
    "pearl": dict(_PEARL),
    "gold": dict(_PEARL),
    "silver": dict(_PEARL, bevel=False),
    "rivet": {"kind": "trim", "base": (214, 232, 246), "light": (255, 255, 255),
              "dark": (110, 140, 184), "line": (30, 44, 86), "bevel": False},
    "chrome": {"base": (170, 200, 236), "line": (30, 44, 90)},
    "steel": {"kind": "chrome", "base": (110, 128, 170), "light": (200, 220, 246),
              "line": (24, 30, 60)},
    "frame": {"base": (26, 32, 64), "light": (70, 86, 140), "line": (8, 10, 24)},
    "frame_lt": {"kind": "frame", "base": (52, 64, 112), "light": (120, 140, 200),
                 "line": (10, 12, 32)},
    "dark": {"base": (14, 18, 44), "line": (4, 6, 16)},
    "inner": {"base": (16, 20, 48), "glow": AQUA},
    "visor": {"glow": (110, 240, 255), "light": (230, 255, 255), "deep": (10, 70, 140),
              "emit": 18},
    "glow": {"glow": AQUA, "light": (220, 252, 255)},
    "glow_soft": {"glow": AQUA, "light": (220, 252, 255)},
    "vent": {"base": (22, 28, 60), "glow": AQUA, "deep": (8, 40, 110)},
    "grille": {"kind": "vent", "base": (30, 40, 90), "glow": (30, 50, 110), "deep": (8, 12, 30),
               "slat": 2},
    "gill": {"kind": "vent", "base": (20, 26, 62), "glow": (90, 236, 255), "deep": (6, 40, 120),
             "slat": 2},
    "thruster": {"glow": (110, 236, 255), "light": (240, 255, 255), "deep": (14, 60, 170)},
    "flame": {"glow": (90, 220, 255), "light": (230, 255, 255), "deep": (20, 70, 200)},
    "flame_core": {"kind": "flame", "glow": (200, 250, 255), "light": (255, 255, 255),
                   "deep": (90, 190, 255), "bevel": False, "outline": False},
    "core": {"halo": AQUA, "bezel": (10, 14, 36), "emit": 40},
    "gem": {"glow": (90, 240, 255), "deep": (10, 40, 120)},
    # 尾ビレのマント: 紺碧の膜（条の筋）と、上の段の布
    "tail": {"kind": "armor", "base": (44, 104, 222), "light": (120, 170, 245),
             "dark": (22, 60, 160), "line": (12, 32, 96), "panel": 0, "bolts": False,
             "outline_k": 0.45},
    "tail_b": {"kind": "armor", "base": (34, 82, 196), "light": (100, 150, 236),
               "dark": (18, 48, 140), "line": (10, 28, 90), "panel": 0, "bolts": False,
               "sheen": False, "outline_k": 0.45},
    "cape_top": {"kind": "cloth", "base": (40, 96, 214), "shadow": (20, 52, 150),
                 "hem": PEARL, "cloud": False, "outline": True, "line": (10, 14, 50),
                 "outline_k": 0.6, "fold": 7.0},
    "serial": {"text": "TR-08", "under": {"kind": "armor", "base": INDIGO, "panel": 0,
                                          "line": (8, 10, 40)},
               "ink": (150, 236, 255)},
    "hazard": {"c1": AQUA, "c2": ABYSS},
    "face": {"kind": "armor", "base": (60, 76, 150), "panel": 0, "line": (12, 16, 50),
             "light": (120, 140, 210)},
    "emblem": {"under": {"kind": "armor", "base": INDIGO, "panel": 0, "line": (8, 10, 40)},
               "color": AQUA},
}

# ===========================================================================
#  部位アニメ（Molang）
#  回る物は v.astro_spin（空中・疾走で速くなる累積の時間）× 角速度。揺れは q.anim_time（12 秒でループ
#  → 周波数は 30°/秒の倍数）か v.astro_t。v.astro_air / v.astro_run は振れ幅にだけ掛ける。
#  `_r` は左へ自動で鏡映（尾ビレは左右で位相をずらすため `_l` も書く）
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # 大暗斑の嵐の羽根は逆向き（逆行）に、背中の水流タービンは順方向に回る
        "fx_spin_storm": {"rotation": [0, 0, "-v.astro_spin * 90.0"]},
        "fx_spin_turbine": {"rotation": [0, 0, "v.astro_spin * 240.0"]},
        "extra_tail_r": {"rotation": ["5.0 + math.sin(q.anim_time * 90.0) * 2.5", 0,
                                      "math.sin(q.anim_time * 60.0) * 1.5"]},
        "extra_tail2_r": {"rotation": ["4.0 + math.sin(q.anim_time * 90.0 - 70.0) * 4.0", 0,
                                       "math.sin(q.anim_time * 60.0 - 50.0) * 2.0"]},
        "extra_tail_l": {"rotation": ["5.0 + math.sin(q.anim_time * 90.0 + 50.0) * 2.5", 0,
                                      "-math.sin(q.anim_time * 60.0 + 40.0) * 1.5"]},
        "extra_tail2_l": {"rotation": ["4.0 + math.sin(q.anim_time * 90.0 - 20.0) * 4.0", 0,
                                       "-math.sin(q.anim_time * 60.0 - 10.0) * 2.0"]},
        # ヒレがゆっくり水を掻く
        "back_dorsal_r": {"rotation": [0, "math.sin(q.anim_time * 60.0) * 2.0", 0]},
        "arms_fin_r": {"rotation": [0, 0, "math.sin(q.anim_time * 90.0) * 2.0"]},
        "legs_calf_fin_r": {"rotation": [0, 0, "math.sin(q.anim_time * 90.0 + 90.0) * 2.0"]},
    },
    "thrust": {
        # 空中では尾ビレが二股に大きく開き、スラスターの炎の通り道を空ける。背ビレも外へ張る
        "extra_tail_r": {"rotation": ["v.astro_air * 10.0", 0, "v.astro_air * 13.0"]},
        "extra_tail2_r": {"rotation": [
            "v.astro_air * (4.0 + math.sin(v.astro_t * 720.0) * 6.0)", 0, "v.astro_air * 7.0"]},
        "back_dorsal_r": {"rotation": [0, 0, "-v.astro_air * 10.0"]},
        "arms_fin_r": {"rotation": [0, 0, "-v.astro_air * 8.0"]},
    },
    "sprint": {
        "extra_tail_r": {"rotation": ["v.astro_run * 26.0", 0, "-v.astro_run * 4.0"]},
        "extra_tail2_r": {"rotation": [
            "v.astro_run * (12.0 + math.sin(v.astro_t * 900.0) * 5.0)", 0, 0]},
        "back_dorsal_r": {"rotation": ["v.astro_run * 8.0", 0, 0]},
    },
}


# ===========================================================================
def build_suit(s: Suit):
    s.frame7(bulk=0.92, skip=("foot", "head", "spine", "cables"))   # 足はサバトン・頭は兜・背骨は背中の装甲で包む
    boots(s)
    legs(s)
    waist(s)
    tail_cape(s)
    torso(s)
    back(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)


# ---------------------------------------------------------------------------
#  サバトン（舳先のように尖ったつま先・踵の噴射口・足首の外の小ビレ）
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (LX, 0.16, -1.0), (2.8, 0.32, 5.7), "dark")                            # 靴底
    shell = chamfer(b, (LX, 1.02, -0.5), (2.75, 1.45, 3.9), "plate2", cut=0.36, axis="z")
    line_on(b, shell[0], "west", (0.1, 0.42), (0.88, 0.42), 0.18, 0.16, "glow")
    rivets(b, shell[0], "west", 2, edge="top", margin=0.3, span=(0.35, 0.75))
    # 甲（紺碧）+ 真珠の縁 + 鱗
    ins = rbox(b, (LX, 1.92, -1.75), (2.2, 0.5, 1.9), "plate", rot=(-30, 0, 0))
    stick(b, ins, "up", 0.5, 0.07, (2.05, 0.22, 0.16), "pearl", sink=0.05)
    # 舳先: 左右の板が前で合わさって尖る（真珠の稜）
    pr = rbox(b, (LX - 0.56, 0.8, -3.0), (1.3, 0.95, 1.7), "plate2", rot=(-8, 32, 0))
    pe = stick(b, pr, "up", 0.85, 0.5, (0.22, 1.6, 0.16), "pearl", sink=0.05)
    mirror_x(b, pr, pe, about=LX)
    toe = rbox(b, (LX, 1.08, -2.62), (2.2, 0.7, 1.0), "plate", rot=(-22, 0, 0))     # つま先の板
    stick(b, toe, "north", 0.5, 0.5, (0.42, 0.42, 0.16), "gem", spin=45, sink=0.04)
    cbox(b, (LX, 0.6, -3.62), (1.1, 0.34, 0.34), "dark")                            # 関節
    rbox(b, (LX, 0.56, -3.9), (0.74, 0.6, 0.74), "pearl", rot=(0, 45, 0))           # 尖り
    # 踵（藍）と噴射口
    cbox(b, (LX, 1.0, 1.25), (2.45, 1.4, 0.95), "plate2_b")
    octa(b, (LX, 0.72, 1.9), 1.15, 0.5, "frame", axis="z")
    cbox(b, (LX, 0.72, 2.18), (0.85, 0.85, 0.16), "thruster")
    # 足首の外の小ビレ（後ろ上へ）
    ray_fin(b, [(LX - 1.32, 1.85, 1.1), (LX - 1.32, 1.05, 1.5)],
            [(LX - 1.42, 3.0, 2.6), (LX - 1.42, 1.9, 3.05)],
            0.26, ["pearl", "fin"], seg=1.25, w0=0.6, w1=0.42, bend=0.08, bend_dir=(0, 1, 0),
            web="fin_web", web_seg=3.0, web_t=0.8)


# ---------------------------------------------------------------------------
#  脚（腿・帆立貝の膝・鱗の脛・ふくらはぎのヒレ）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前の藍の下板 + 紺碧の上板（真珠の縁・水色の流れの線・鱗）、外の藍の板（型番）、後ろの板
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.75, -1.8), (2.8, 4.3, 0.55), "plate2", top="plate",
                       rot=(-3, 0, 0), inset=0.3, trim="pearl", trim_edge="bottom",
                       rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(t, fr["top"], "north", (0.78, 0.1), (0.64, 0.45), 0.18, 0.16, "glow")
    line_on(t, fr["top"], "north", (0.64, 0.45), (0.8, 0.82), 0.18, 0.16, "glow")
    side = rbox(t, (LX - 1.76, 11.35, 0.05), (0.48, 3.2, 2.8), "plate2", rot=(0, 0, -3),
                decals={"west": {"decal": "serial", "text": "TR-08", "ink": (150, 236, 255)}})
    rivets(t, side, "west", 2, edge="bottom", margin=0.3)
    cbox(t, (LX - 1.62, 9.62, 0.05), (0.42, 0.42, 2.7), "pearl")
    rbox(t, (LX, 11.6, 1.72), (2.1, 3.3, 0.4), "plate2_b", rot=(4, 0, 0))
    sensor(t, (LX + 0.3, 13.45, -2.15), 0.28, "glow", "dark")
    # 膝: 帆立貝の膝当て（藍の殻・放射状の紺碧の肋・真珠の珠・蝶番）と外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    chamfer(k, (LX, 8.5, -1.85), (2.2, 2.1, 0.62), "plate2", cut=0.3, axis="z")
    H = np.array((LX, 7.5, -2.28))
    for ang in (-58, -29, 0, 29, 58):
        dv = np.array((-math.sin(math.radians(ang)), math.cos(math.radians(ang)), -0.08))
        beam(k, H + dv * 0.42, H + dv * 1.36, 0.36, 0.28, "plate", extend=0.04)
    octa(k, tuple(H), 0.72, 0.3, "pearl", axis="z")                                  # 蝶番
    rbox(k, (LX, 7.5, -2.46), (0.36, 0.36, 0.18), "gem", rot=(0, 0, 45))
    piston(k, (LX - 1.58, 10.9, 0.55), (LX - 1.48, 6.3, 0.45), r=0.25, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 藍の前板に菱形の鱗（紺碧）・真珠の稜、両脇の板、ふくらはぎの鰓の排気口
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    # 前は二枚の板が中央の稜で前へ合わさる船底（V）の形。両方に菱形の鱗、稜は真珠
    front = rbox(g, (LX - 0.64, 4.75, -1.36), (1.42, 5.1, 0.48), "plate2", rot=(4, 20, 0))
    ftr = stick(g, front, "north", 0.5, 0.965, (1.3, TRIM_W, 0.16), "pearl", sink=0.05)
    fsc = scale_patch(g, front, "north", [2, 1, 2, 1], d=0.66, t=0.22,
                      styles=("plate", "plate", "plate_b"), b0=0.2, b1=0.84)
    mirror_x(g, front, ftr, fsc, about=LX)
    rbox(g, (LX, 4.75, -1.66), (0.32, 4.9, 0.32), "pearl", rot=(4, 45, 0))           # 稜
    sd = rbox(g, (LX - 1.45, 4.85, -0.15), (0.45, 4.9, 2.7), "plate", rot=(0, 0, -4))
    sdl = line_on(g, sd, "west", (0.15, 0.2), (0.85, 0.7), 0.18, 0.16, "glow")
    mirror_x(g, sd, about=LX)
    rivets(g, sd, "west", 2, edge="bottom", margin=0.3)
    calf = rbox(g, (LX, 6.15, 1.62), (2.3, 2.5, 0.45), "plate2_b", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.2, 0.2, 0.8, 0.8), style="gill")
    octa(g, (LX, 2.9, 0.15), 2.55, 0.3, "pearl", axis="y")                           # 足首の輪
    # ふくらはぎの白いヒレ（外。後ろ上へ反る）
    fn = s.part("legs", "calf_fin_r", g, pivot=(LX - 1.7, 5.6, 0.9), rotation=(0, 0, -12))
    xf = LX - 1.85
    ray_fin(fn, [(xf, 7.2, 0.3), (xf, 3.8, 1.2)],
            [(xf, 8.9, 2.9), (xf, 7.9, 3.8), (xf, 6.4, 4.1), (xf, 4.8, 3.4)],
            0.3, LEAD, seg=1.6, w0=0.55, w1=0.4, bend=0.1, bend_dir=(0, -1, 0),
            web="fin_web", web_seg=3.0, web_t=0.86)


# ---------------------------------------------------------------------------
#  腰（ベルト・三叉の留め金・前垂れ・腰の脇の板・後ろ垂れ・鱗の草摺）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    belt = chamfer(w, (0, 16.95, 0.12), (6.6, 0.9, 4.4), "frame", cut=0.4, axis="y")
    stick(w, belt[0], "north", 0.5, 0.86, (5.2, 0.2, 0.16), "pearl", sink=0.05)
    stick(w, belt[0], "north", 0.5, 0.3, (4.6, 0.2, 0.16), "glow_soft", sink=0.05)
    bl = rivets(w, belt[0], "north", 1, edge="bottom", margin=0.45, span=(0.12, 0.12))
    mirror_x(w, bl)
    # 留め金: 真珠の八角 → 宝玉 → 小さな三叉の紋
    octa(w, (0, 16.95, -2.36), 1.55, 0.36, "pearl", axis="z")
    rbox(w, (0, 16.82, -2.6), (0.55, 0.55, 0.2), "gem", rot=(0, 0, 45))
    beam(w, (0, 16.95, -2.66), (0, 17.6, -2.66), 0.18, 0.16, "pearl")
    pg = polyline(w, [(-0.18, 16.98, -2.66), (-0.42, 17.22, -2.66), (-0.4, 17.52, -2.66)],
                  0.16, 0.16, "pearl", overlap=0.1)
    mirror_x(w, pg)
    # 前垂れ（細い藍の板。下が尖る。腿の前を隠さない幅）
    fp = rbox(w, (0, 15.3, -2.08), (1.7, 2.3, 0.45), "plate2", rot=(-8, 0, 0))
    rbox(w, (0, 14.2, -2.16), (1.05, 1.05, 0.4), "plate2", rot=(-8, 0, 45))
    line_on(w, fp, "north", (0.5, 0.2), (0.5, 0.88), 0.2, 0.16, "glow")
    fe = line_on(w, fp, "north", (0.06, 0.95), (0.06, 0.12), 0.18, 0.16, "pearl")
    mirror_x(w, fe)
    # 腰の脇の紺碧の板（股関節の前を覆う）+ 真珠の下縁 + リベット
    hp = rbox(w, (-2.35, 15.75, -2.0), (2.1, 1.5, 0.45), "plate", rot=(-8, 14, 4))
    hpt = stick(w, hp, "north", 0.5, 0.1, (1.9, 0.2, 0.16), "pearl", sink=0.05)
    hpr = rivets(w, hp, "north", 1, edge="top", margin=0.3, span=(0.7, 0.7))
    mirror_x(w, hp, hpt, hpr)
    # 後ろ垂れ（鱗）
    rs = rbox(w, (0, 15.1, 2.42), (4.2, 2.6, 0.45), "plate2", rot=(14, 0, 0))
    scale_patch(w, rs, "south", [3, 2], d=0.9, t=0.22, styles=("plate", "plate_b"), b0=0.3,
                b1=0.72)
    # 草摺（腰の横。付け根で外へ開く。藍の下板 + 紺碧の上板 + 真珠の縁 + 鱗 + 白いヒレ先）
    ts = s.part("waist", "tasset_r", w, pivot=(-3.35, 16.6, 0.0), rotation=(0, 0, 8))
    base = layered_plate(ts, (-3.62, 15.15, 0.0), (0.45, 2.8, 3.4), "plate2", top="plate",
                         face="west", inset=0.34, trim="pearl", trim_edge="bottom",
                         rivet="rivet", n_rivets=3, rivet_edge="top")
    scale_patch(ts, base["top"], "west", [2, 1], d=0.78, t=0.2, styles=("plate2", "plate2_b"),
                b0=0.32, b1=0.6)
    cbox(ts, (-3.42, 16.3, 0.0), (0.5, 0.55, 1.6), "dark")                          # 蝶番


# ---------------------------------------------------------------------------
#  尾ビレのマント（ベルトの後ろから二股に垂れる。上下 2 段で揺れ、空中で開く）
# ---------------------------------------------------------------------------
def tail_cape(s):
    tp = s.part("extra", "tail_r", "body", pivot=(-0.55, 17.0, 2.78), rotation=(6, 0, 5))
    cbox(tp, (-0.6, 16.95, 2.78), (1.0, 0.75, 0.55), "pearl")                       # 留め具
    rbox(tp, (-0.6, 16.95, 3.1), (0.42, 0.42, 0.2), "gem", rot=(0, 0, 45))
    up = rbox(tp, (-1.0, 15.25, 2.92), (1.55, 3.0, 0.3), "cape_top", rot=(0, 0, 8))
    line_on(tp, up, "south", (0.08, 0.9), (0.08, 0.06), 0.18, 0.16, "glow_soft", sink=0.06)
    lo = s.part("extra", "tail2_r", tp, pivot=(-1.25, 13.7, 2.95), rotation=(4, 0, 6))
    # 下の段: 尾ビレ（上の縁から下・外へ広がる条。外の条が長く、先は泡の白 → 二股の尾）
    ray_fin(lo, [(-0.55, 13.85, 2.95), (-2.05, 13.65, 2.95)],
            [(-1.0, 9.8, 2.95), (-2.1, 8.0, 2.95), (-3.2, 6.2, 2.95), (-4.25, 4.4, 2.95)],
            0.32, ["tail", "tail", "tail", "pearl"], seg=2.0, w0=0.6, w1=0.42, bend=0.07,
            bend_dir=(-1, 0, 0), tip_style=FIN, normal=(0, 0, 1), web="tail_b", web_seg=3.2,
            web_t=0.88)


# ---------------------------------------------------------------------------
#  胴（胸郭・鰓の胸板・竜骨・星核と嵐の羽根・襟・脇の鰓・鱗の腹）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.2, 0.0), (9.0, 3.5, 5.0), "plate2", cut=0.8, axis="y")       # 上が広い
    chamfer(c, (0, 21.65, -0.05), (7.0, 2.3, 4.6), "plate2_b", cut=0.6, axis="y")
    sl = rbox(c, (-3.85, 22.15, 0.0), (0.5, 2.9, 4.0), "plate2", rot=(0, 0, -24))   # 脇の斜面
    mirror_x(c, sl)
    # 鰓の胸板: 三枚が外下へ流れて重なる（紺碧 + 真珠の下縁 + 内の端のリベット + 間から水色の光）
    for k in range(3):
        y = 25.15 - k * 1.0
        wd = 3.5 - k * 0.25
        xin = -0.95 - k * 0.35
        z = -2.68 + k * 0.06
        r_ = (-10, 16, 12 + 4 * k)
        cx = xin - wd / 2
        pl = rbox(c, (cx, y, z), (wd, 0.95, 0.42), "plate", rot=r_)
        tr = stick(c, pl, "north", 0.5, 0.1, (wd - 0.2, 0.2, 0.16), "pearl", sink=0.05)
        rv = rivets(c, pl, "north", 1, edge="right", margin=0.26, span=(0.5, 0.5), size=0.22)
        mirror_x(c, pl, tr, rv)
    gb = rbox(c, (-2.75, 23.95, -2.42), (2.9, 2.9, 0.3), "glow", rot=(-10, 16, 16))   # 鰓の間の光
    mirror_x(c, gb)
    # 中央の竜骨（藍 + 真珠の稜）が星核へ降りる
    kl = rbox(c, (0, 24.55, -2.72), (1.15, 2.6, 0.5), "plate2", rot=(-8, 0, 0))
    stick(c, kl, "north", 0.5, 0.55, (0.26, 2.2, 0.16), "pearl", sink=0.06)
    sensor(c, (0, 25.95, -2.62), 0.24, "glow", "dark")
    # 星核: 黒い菱形の台 → 真珠の八角の枠 → 海王星 → 脈打つ光の輪 → 逆回りの嵐の羽根
    C = (0.0, 22.35)
    rbox(c, (C[0], C[1], -2.6), (2.3, 2.3, 0.45), "dark", rot=(0, 0, 45))
    octa(c, (C[0], C[1], -2.86), 2.0, 0.34, "pearl", axis="z")
    cbox(c, (C[0], C[1], -3.0), (1.4, 1.4, 0.5), "core")
    gl_ = s.fx("glow", "core", c, pivot=(C[0], C[1], -3.2))
    ring(gl_, (C[0], C[1], -3.2), 1.1, 8, (0, 0.22, 0.22), "glow_soft", axis="z")
    sp = s.fx("spin", "storm", c, pivot=(C[0], C[1], -3.45))
    for i in range(6):
        a = math.radians(i * 60)
        pts = [(C[0] - math.sin(a + dt) * r, C[1] + math.cos(a + dt) * r, -3.45)
               for r, dt in ((1.28, 0.0), (1.56, 0.3), (1.8, 0.66))]
        polyline(sp, pts, [0.26, 0.22], [0.22, 0.2], "glow" if i % 2 == 0 else "pearl",
                 overlap=0.12)
    # 襟（首の両脇に立つ藍の板 + 紺碧の上板 + 真珠の縁）と前の小板
    col = rbox(c, (-1.75, 26.2, 0.35), (1.4, 1.1, 3.6), "plate2", rot=(0, 0, -24))
    colt = stick(c, col, "up", 0.5, 0.5, (1.05, 3.3, 0.2), "plate", sink=0.06)
    colg = stick(c, col, "west", 0.5, 0.06, (3.4, TRIM_W, 0.16), "pearl", sink=0.05)
    cf = rbox(c, (-0.95, 25.95, -1.95), (1.55, 0.9, 0.45), "plate", rot=(-20, 30, -10))
    cfr = rivets(c, cf, "north", 1, line=((0.7, 0.5), (0.7, 0.5)), size=0.22)
    mirror_x(c, col, colt, colg, cf, cfr)
    # 肩の付け根（肩当ての下）と脇の鰓の排気口（真珠の枠）
    yk = rbox(c, (-3.95, 25.95, 0.0), (2.0, 0.55, 3.5), "plate2_b", rot=(0, 0, -8))
    sv = cbox(c, (-4.4, 23.7, 0.35), (0.4, 2.0, 2.4), "plate")
    svv = vents(c, sv, "west", 3, box=(0.2, 0.22, 0.8, 0.78), axis="v", style="gill")
    mirror_x(c, yk, sv, svv)
    rivets(c, up[1], "south", 4, edge="top", margin=0.35, span=(0.12, 0.88))
    # 腹: 暗い下地に菱形の鱗（下ほど細い）、脇の斜めの板、背の腰板
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    bp = rbox(ab, (0, 18.75, -1.82), (3.7, 3.3, 0.3), "frame", rot=(-4, 0, 0))
    scale_patch(ab, bp, "north", [4, 3, 3, 2], d=0.86, t=0.26,
                styles=("plate", "plate", "plate_b"), b0=0.1, b1=0.9)
    ob = rbox(ab, (-2.28, 18.7, -1.25), (0.8, 3.0, 0.4), "plate2", rot=(0, 34, -6))
    obt = stick(ab, ob, "north", 0.1, 0.5, (0.18, 2.8, 0.16), "pearl", sink=0.05)
    mirror_x(ab, ob, obt)
    lb = cbox(ab, (0, 18.9, 2.08), (2.2, 2.6, 0.45), "plate2_b")
    vents(ab, lb, "south", 3, box=(0.2, 0.25, 0.8, 0.75))


# ---------------------------------------------------------------------------
#  背中（バックパック・水流タービン・背ビレ・双発スラスター・背骨の小ビレ・ホース）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    pk = chamfer(bk, (0, 22.5, 3.3), (4.4, 5.0, 1.6), "plate2", cut=0.5, axis="z")
    rbox(bk, (0, 25.1, 3.0), (3.8, 0.8, 1.8), "plate", rot=(20, 0, 0))               # 上の蓋
    rivets(bk, pk[0], "south", 4, edge="border", margin=0.24, size=0.22)
    sensor(bk, (0, 24.55, 4.18), 0.26, "glow", "dark", facing=1)
    # 水流タービン（真珠の輪の吸気口・暗い奥・ボルトの輪・回る羽根）
    T = (0.0, 22.35)
    octa(bk, (T[0], T[1], 4.12), 2.75, 0.3, "dark", axis="z")
    ring(bk, (T[0], T[1], 4.22), 1.5, 10, (0, 0.34, 0.36), "pearl", axis="z")
    ring(bk, (T[0], T[1], 4.12), 1.92, 6, (0.22, 0.22, 0.2), "rivet", axis="z", phase=30.0)
    tb = s.fx("spin", "turbine", bk, pivot=(T[0], T[1], 4.42))
    for i in range(7):
        a = math.radians(i * 360 / 7)
        p0 = (-math.sin(a) * 0.38, T[1] + math.cos(a) * 0.38, 4.42)
        p1 = (-math.sin(a + 0.35) * 1.26, T[1] + math.cos(a + 0.35) * 1.26, 4.42)
        beam(tb, p0, p1, 0.42, 0.16, "plate" if i % 2 else "plate_b", roll=28)
    octa(tb, (T[0], T[1], 4.5), 0.66, 0.3, "glow", axis="z")
    cbox(tb, (T[0], T[1], 4.66), (0.3, 0.3, 0.16), "pearl")
    # 脇の排気スリット・ホース（バックパックの下から腰の両脇へ垂れる蛇腹）
    hs = cable(bk, [(-1.6, 20.1, 3.4), (-2.9, 17.6, 2.3)], 0.28, "dark", sag=0.3,
               rib="frame_lt", rib_every=2)
    mirror_x(bk, hs)
    # スラスター（右。下後ろへ向ける）: 藍の胴・真珠の帯・広がったベル・光る縁の輪・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.5, 20.4, 3.6), rotation=(22, 0, -10))
    octa(th, (-1.5, 19.5, 3.6), 1.45, 1.8, "plate2", axis="y")
    octa(th, (-1.5, 20.2, 3.6), 1.65, 0.3, "pearl", axis="y")
    octa(th, (-1.5, 18.25, 3.6), 1.85, 0.9, "frame", axis="y")
    ring(th, (-1.5, 17.8, 3.6), 0.74, 6, (0, 0.24, 0.24), "glow", axis="y")
    cbox(th, (-1.5, 17.78, 3.6), (1.25, 0.16, 1.25), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.5, 17.72, 3.6))
    taper(fx, (-1.5, 17.72, 3.6), (-1.5, 11.8, 3.6), 1.45, 0.32, 3, "flame")
    taper(fx, (-1.5, 17.68, 3.6), (-1.5, 14.4, 3.6), 0.7, 0.2, 2, "flame_core", round_=False)
    # 背ビレ（肩甲骨の上から外上・後ろへ反る白い扇。飾り = 計測しない）
    bf = s.part("back", "dorsal_r", bk, pivot=(-1.95, 24.0, 3.9), rotation=(-8, -26, -20),
                ornament=True)
    xb = -1.95
    rbox(bf, (xb, 23.9, 4.15), (0.55, 2.6, 0.9), "plate2", rot=(-18, 0, 0))         # 付け根の装甲
    beam(bf, (xb - 0.3, 24.9, 4.0), (xb - 0.3, 22.9, 4.6), 0.18, 0.3, "glow")
    ray_fin(bf, [(xb, 24.95, 3.95), (xb, 22.7, 4.35)],
            [(xb, 29.3, 5.6), (xb, 28.3, 7.3), (xb, 26.5, 8.3), (xb, 24.3, 7.9)],
            0.34, LEAD, seg=1.9, w0=0.6, w1=0.42, web="fin_web", web_seg=2.6, web_t=0.86,
            bend=0.08, bend_dir=(0, -1, 0.4), normal=(1, 0, 0))


# ---------------------------------------------------------------------------
#  腕（二の腕・肘の棘・肘のピストン・鱗の篭手・前腕のヒレ）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.3, 21.3, 0.0), (0.45, 3.1, 2.4), "plate2", rot=(0, 0, 3))
    line_on(ua, op, "west", (0.5, 0.1), (0.5, 0.9), 0.18, 0.16, "glow")
    rivets(ua, op, "west", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))
    upf = rbox(ua, (X + 0.05, 21.4, -1.36), (2.1, 2.8, 0.42), "plate2", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.5, (0.55, 2.3, 0.16), "plate", sink=0.06)
    sensor(ua, (X + 0.05, 22.5, -1.64), 0.22, "glow", "dark")
    rbox(ua, (X + 0.05, 21.7, 1.34), (1.9, 2.3, 0.4), "plate2_b", rot=(3, 0, 0))
    octa(ua, (X, 19.75, 0.02), 2.8, 0.3, "pearl", axis="y")                         # 腕輪
    rbox(ua, (X, 19.75, -1.48), (0.36, 0.36, 0.18), "gem", rot=(0, 0, 45))
    rbox(ua, (X - 1.46, 19.75, 0.02), (0.18, 0.36, 0.36), "gem", rot=(45, 0, 0))
    # 肘当て（後ろ）と後ろへ伸びる棘、外の油圧シリンダー
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    ex = A.ELBOW[0]
    cop = chamfer(el, (ex, 18.55, 1.6), (2.0, 1.8, 0.55), "plate", cut=0.28, axis="z")
    rivets(el, cop[0], "south", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))
    taper(el, (ex, 18.3, 1.85), (ex + 0.05, 17.2, 3.0), 0.5, 0.18, 2, "pearl", round_=False)
    piston(el, (X - 0.98, 20.3, 1.1), (A.FOREARM_X - 1.1, 16.6, 1.15), r=0.21,
           style="frame", rod_style="chrome", cap_style="dark")
    # 篭手: 手首へ向かって開く藍 + 外の紺碧の板（鱗）+ 前の板（水色の線）+ 真珠の袖口
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    chamfer(fa, (FX_, 17.15, 0.0), (2.8, 1.9, 2.9), "plate2", cut=0.4, axis="y")
    lo = chamfer(fa, (FX_ - 0.04, 15.7, 0.0), (3.0, 1.75, 3.1), "plate2", cut=0.42, axis="y")
    ob = rbox(fa, (FX_ - 1.66, 16.3, 0.0), (0.42, 3.1, 2.6), "plate", rot=(0, 0, 5))
    scale_patch(fa, ob, "west", [2, 1, 2], d=0.8, t=0.2, styles=("plate2", "plate2_b"),
                b0=0.2, b1=0.72)
    rivets(fa, ob, "west", 2, edge="top", margin=0.24, size=0.22)
    fv = rbox(fa, (FX_ - 0.02, 16.45, -1.6), (1.9, 2.2, 0.35), "plate", rot=(-5, 0, 0))
    line_on(fa, fv, "north", (0.3, 0.12), (0.55, 0.55), 0.16, 0.16, "glow")
    line_on(fa, fv, "north", (0.55, 0.55), (0.45, 0.9), 0.16, 0.16, "glow")
    chamfer(fa, (FX_ - 0.04, 14.72, 0.0), (3.06, 0.34, 3.2), "pearl", cut=0.4, axis="y")
    sensor(fa, (FX_ + 0.05, 15.5, 1.68), 0.24, "glow", "dark", facing=1)
    _ = lo
    # 前腕の白いヒレ（外。後ろ上へ反る）
    af = s.part("arms", "fin_r", fa, pivot=(FX_ - 1.85, 16.5, 0.6), rotation=(0, 0, -8))
    xf = FX_ - 1.95
    ray_fin(af, [(xf, 17.7, 0.25), (xf, 15.2, 0.95)],
            [(xf, 19.4, 2.6), (xf, 18.6, 3.45), (xf, 17.3, 3.85), (xf, 15.9, 3.45)],
            0.28, LEAD, seg=1.5, w0=0.5, w1=0.38, bend=0.08, bend_dir=(0, -1, 0),
            web="fin_web", web_seg=3.0, web_t=0.86)


def hands(s):
    """手の甲の紺碧の板と宝玉、指の甲当て（4 本の基節 + 真珠の鋲）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.42, 13.62, 0.0), (0.36, 1.7, 2.3), "plate", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.6, 0.6, 0.2), "gem", spin=45, sink=0.05)
    stick(h, hb, "west", 0.5, 0.94, (2.1, 0.2, 0.16), "pearl", sink=0.05)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        n = (-0.81, -0.58, 0.0)
        o = 0.34
        q0 = (p0[0] + n[0] * o, p0[1] + n[1] * o, zf)
        q1 = (p1[0] + n[0] * o, p1[1] + n[1] * o, zf)
        beam(h, q0, q1, 0.56, 0.22, "plate2")
    rbox(h, (-5.62, 13.55, -1.72), (0.62, 0.9, 0.22), "plate2", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（丸い貝殻の肩当て: 藍の殻 → 紺碧の外の段 → 真珠の縁・紋章・後ろのヒレ）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    C = (-6.6, 24.3, 0.0)
    ring(p, C, 1.8, 5, (0, 0.62, 4.4), "plate2", axis="z", a0=-20, a1=115)
    ring(p, (C[0], C[1], -2.25), 1.82, 4, (0, 0.72, 0.2), "pearl", axis="z", a0=-20, a1=115)
    ring(p, (C[0] - 0.1, C[1] - 0.05, 0.0), 2.28, 3, (0, 0.45, 3.6), "plate", axis="z",
         a0=40, a1=118)
    # 外の紋章板（藍・水色の紋章）と真珠の縁・リベット
    em = rbox(p, (-8.72, 22.95, 0.0), (0.42, 1.6, 3.0), "plate2", rot=(0, 0, 16),
              decals={"west": {"decal": "emblem", "color": AQUA}})
    stick(p, em, "west", 0.5, 0.07, (2.8, TRIM_W, 0.16), "pearl", sink=0.05)
    rivets(p, em, "west", 3, edge="top", margin=0.22, size=0.2)
    sensor(p, (-7.3, 24.5, -2.42), 0.24, "glow", "dark")


# ---------------------------------------------------------------------------
#  兜（ドーム・額・眉・こめかみの鰓・頬当て・耳・面頬・しころ・三叉の冠・鶏冠・耳ビレ）とバイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hz = HZ
    hm = s.part("helmet", "dome", "head")
    cbox(hm, (0, 29.3, hz + 0.3), (3.8, 3.4, 4.2), "dark")                           # 内側を塞ぐ
    bevel(hm, (0, 30.55, hz + 0.35), (4.4, 2.2, 4.7), "plate2", cut=0.6, axis="z")
    crown = chamfer(hm, (0, 31.68, hz + 0.5), (3.4, 0.7, 4.2), "plate2", cut=0.22, axis="z")
    cbox(hm, (0, 32.1, hz + 0.5), (0.6, 0.3, 4.0), "pearl")                          # 中央の稜
    gl = stick(hm, crown[0], "up", 0.24, 0.5, (0.2, 3.6, 0.16), "glow", sink=0.05)
    mirror_x(hm, gl)
    fh = rbox(hm, (0, 30.75, hz - 2.2), (3.9, 1.2, 0.45), "plate", rot=(-24, 0, 0))  # 額の斜面
    stick(hm, fh, "north", 0.5, 0.1, (3.7, 0.2, 0.16), "pearl", sink=0.05)
    br = rbox(hm, (-1.0, 30.05, hz - 2.45), (2.0, 0.42, 0.42), "plate2", rot=(-8, 8, 12))
    sd = cbox(hm, (-2.1, 29.05, hz + 0.55), (0.42, 2.3, 3.6), "plate2")             # こめかみ
    sdv = vents(hm, sd, "west", 3, box=(0.1, 0.25, 0.5, 0.75), axis="v", style="gill")
    ck = rbox(hm, (-1.72, 28.35, hz - 1.2), (0.48, 2.0, 2.3), "plate", rot=(0, 20, -10))
    ckg = stick(hm, ck, "west", 0.06, 0.5, (0.22, 1.8, 0.16), "pearl", sink=0.05)
    ear = octa(hm, (-2.36, 29.15, hz + 0.7), 1.3, 0.32, "pearl", axis="x")         # 耳
    eg = cbox(hm, (-2.55, 29.15, hz + 0.7), (0.16, 0.5, 0.5), "glow")
    mirror_x(hm, br, sd, sdv, ck, ckg, ear, eg)
    # 面: 暗い顔の板・鰓の格子の V の面頬・尖った顎・真珠の鼻筋
    cbox(hm, (0, 29.0, hz - 2.08), (2.9, 2.2, 0.3), "dark")
    fc = rbox(hm, (-0.62, 28.42, hz - 2.25), (1.25, 1.2, 0.42), "face", rot=(8, 26, 0))
    fcv = vents(hm, fc, "north", 2, box=(0.18, 0.2, 0.82, 0.8), axis="v", w=0.2, style="grille")
    ch = rbox(hm, (-0.42, 27.75, hz - 1.98), (0.95, 0.7, 0.45), "face", rot=(0, 26, -22))
    mirror_x(hm, fc, fcv, ch)
    cbox(hm, (0, 28.45, hz - 2.5), (0.28, 1.2, 0.28), "pearl")
    # 後頭部（排気口・鱗）としころ
    bh = cbox(hm, (0, 29.1, hz + 2.55), (3.9, 2.4, 0.45), "plate2")
    vents(hm, bh, "south", 2, box=(0.3, 0.6, 0.7, 0.85), w=0.2, style="grille")
    scale_patch(hm, bh, "south", [3, 2], d=0.8, t=0.18, styles=("plate", "plate_b"), b0=0.16,
                b1=0.42)
    rbox(hm, (0, 28.05, hz + 2.62), (3.6, 0.75, 0.45), "plate2_b", rot=(22, 0, 0))
    rbox(hm, (0, 27.6, hz + 2.75), (3.1, 0.6, 0.42), "plate", rot=(32, 0, 0))
    # 背ビレの鶏冠（頭頂の中央を前から後ろへ。白い条・真珠の前縁。飾り）
    cr = s.part("helmet", "crest", "head", pivot=(0, 32.1, hz + 0.5), ornament=True)
    cbox(cr, (0, 32.3, hz + 0.9), (0.4, 0.2, 3.0), "glow")
    ray_fin(cr, [(0, 32.15, hz - 0.7), (0, 32.15, hz + 2.2)],
            [(0, 34.1, hz + 1.5), (0, 33.95, hz + 2.7), (0, 33.4, hz + 3.7), (0, 32.55, hz + 4.2)],
            0.32, LEAD, seg=0.9, w0=0.5, w1=0.38, bend=0.1, bend_dir=(0, 0, 1),
            normal=(1, 0, 0), web="fin_web", web_seg=3.0, web_t=0.84)
    # 三叉の冠（額の上: 中央の高い穂先と、外へ開いて先が内へ返る左右の穂先。飾り）
    tz = hz - 2.62
    tc = s.part("helmet", "trident", "head", pivot=(0, 30.8, tz), ornament=True)
    bar = polyline(tc, [(0, 30.78, tz), (-0.6, 30.86, tz), (-1.25, 31.25, tz)], [0.34, 0.3],
                   [0.32, 0.3], "pearl", overlap=0.12)
    mirror_x(tc, bar)
    octa(tc, (0, 30.8, tz - 0.02), 0.9, 0.3, "pearl", axis="z")
    rbox(tc, (0, 30.8, tz - 0.2), (0.5, 0.5, 0.2), "gem", rot=(0, 0, 45))
    taper(tc, (0, 31.1, tz), (0, 33.9, tz + 0.12), 0.42, 0.2, 3, "pearl", round_=False)
    rbox(tc, (0, 33.05, tz + 0.08), (0.62, 0.62, 0.22), "pearl", rot=(0, 0, 45))  # 返し
    rbox(tc, (0, 33.05, tz - 0.06), (0.3, 0.3, 0.16), "glow", rot=(0, 0, 45))
    cbox(tc, (0, 32.0, tz - 0.14), (0.16, 1.2, 0.16), "glow")
    side = polyline(tc, [(-1.2, 31.15, tz), (-1.45, 31.9, tz + 0.05), (-1.36, 32.65, tz + 0.1),
                         (-1.05, 33.1, tz + 0.12)], [0.32, 0.28, 0.24], [0.3, 0.26, 0.22],
                    "pearl", overlap=0.14)
    sb = rbox(tc, (-1.43, 32.45, tz + 0.08), (0.42, 0.42, 0.2), "pearl", rot=(0, 0, 45))
    sg = cbox(tc, (-1.42, 31.75, tz - 0.12), (0.16, 0.7, 0.16), "glow")
    mirror_x(tc, side, sb, sg)
    # 耳ビレ（側頭から後ろ上へ流れる。飾り）
    ef = s.part("helmet", "ear_fin_r", "head", pivot=(-2.4, 29.3, hz + 0.7), rotation=(0, 0, -16),
                ornament=True)
    ray_fin(ef, [(-2.5, 29.85, hz + 0.45), (-2.5, 28.75, hz + 1.1)],
            [(-2.5, 31.05, hz + 2.95), (-2.5, 30.15, hz + 3.5), (-2.5, 29.15, hz + 3.3)],
            0.28, LEAD, seg=0.9, w0=0.5, w1=0.36, bend=0.08, bend_dir=(0, 1, 0),
            normal=(1, 0, 0), web="fin_web", web_seg=3.0, web_t=0.84)
    # バイザー: 暗い帯の上に、鋭く吊り上がった二つの目と真珠の鼻筋
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 29.5, hz - 2.3), (3.6, 0.72, 0.3), "dark")
    cbox(vz, (0, 29.35, hz - 2.5), (0.26, 0.9, 0.22), "pearl")
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.5, hz - 2.48))
    eye = rbox(fg, (-0.9, 29.52, hz - 2.48), (1.3, 0.32, 0.18), "visor", rot=(0, 8, 13))
    mirror_x(fg, eye)
