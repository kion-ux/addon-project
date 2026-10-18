# -*- coding: utf-8 -*-
"""アストロ・ナノギア — スーツを着て（武器を持った）プレイヤーを描くソフトレンダラ。

変換の規則は hyperdim の hd_space / hd_scene と同じ（Mojang のサンプルから逆算した回転の向き、
X を鏡映した画面）。スーツのトップレベルのボーンはプレイヤーの同名ボーン（姿勢付き）に重ね、
部位ボーンはその子として描く（統合版のアタッチャブルと同じ）。

公開関数（どれも PIL.Image を返す。モジュール化してあるので武器・コア・HUD の担当も足せる）:
  load_suit(key) -> SuitAsset                       生成済みの geo/png/アニメを読む
  pose(name, t=0) -> {bone: {rotation, position}}   プレイヤーの姿勢（stand/walk/hold/air/fp/sneak）
  suit_anim(asset, names, t, env) -> anim           スーツのアニメ（名前のリスト）を t 秒で評価
  assembly_anim(asset, t) / release_anim(asset, t)  組み上がり／解除の途中
  render(asset, pose_, anim, view, size, weapon=None, extra=None, show_player=True)
  render_fp(asset, anim, size, weapon=None)         一人称（fp_hide 後に残る物）
  sheet(tiles, path, cols)                          ラベル付きの並べ図
  VIEWS = {"front","back","left","right","q34","q34l","high","low"}: (yaw, pitch)
weapon / extra は「描き足す物」: {"geo": geo dict または .geo.json, "tex": PIL.Image または png,
  "anim": {bone: {...}}, "bind": "hand"（右手に bind）|"world"}。武器のアタッチャブルは
  hd_scene.weapon_quads と同じ規則で手に付く。
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import astro_common as AC  # noqa: E402
from astro_suit import TOP, suit_world  # noqa: E402
from hd_scene import FACES, SKELETON, skeleton_world  # noqa: E402
from hd_space import FP_ARM_POS, FP_ARM_ROT, FP_EYE, OFF_L, OFF_R, Rx, Ry, mat4, rot  # noqa: E402

VIEWS = {
    "front": (0, -4), "back": (180, -4), "left": (90, -4), "right": (-90, -4),
    "q34": (-34, -10), "q34l": (34, -10), "high": (-28, -38), "low": (-20, 18),
}

# ===========================================================================
#  Molang（プレビュー用の小さな評価器）
# ===========================================================================
_TOK = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|('[^']*')|([A-Za-z_][\w.]*(?:->[A-Za-z_][\w.]*)?)"
                  r"|(\?\?|==|!=|<=|>=|&&|\|\||[-+*/()<>!?:,;=]))")


def _tokens(s):
    pos = 0
    out = []
    s = s.strip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m or m.end() == pos:
            raise ValueError(f"molang: cannot parse at {s[pos:pos + 20]!r}")
        pos = m.end()
        num, st, ident, op = m.groups()
        if num is not None:
            out.append(("n", float(num)))
        elif st is not None:
            out.append(("s", st[1:-1]))
        elif ident is not None:
            out.append(("i", ident))
        else:
            out.append(("o", op))
    out.append(("e", None))
    return out


def _canon(name):
    n = name.lower()
    for a, b in (("query.", "q."), ("variable.", "v."), ("context.", "c."),
                 ("temp.", "t.")):
        if n.startswith(a):
            n = b + n[len(a):]
    return n


_FUN = {
    "math.sin": lambda a: math.sin(math.radians(a)), "math.cos": lambda a: math.cos(math.radians(a)),
    "math.abs": abs, "math.sqrt": lambda a: math.sqrt(max(0, a)), "math.floor": math.floor,
    "math.ceil": math.ceil, "math.round": round, "math.trunc": math.trunc,
    "math.min": min, "math.max": max, "math.pow": pow,
    "math.clamp": lambda v, a, b: max(a, min(b, v)), "math.lerp": lambda a, b, t: a + (b - a) * t,
    "math.mod": lambda a, b: math.fmod(a, b) if b else 0.0,
    "math.atan2": lambda y, x: math.degrees(math.atan2(y, x)),
    "math.asin": lambda a: math.degrees(math.asin(max(-1, min(1, a)))),
    "math.acos": lambda a: math.degrees(math.acos(max(-1, min(1, a)))),
    "math.exp": math.exp, "math.ln": lambda a: math.log(a) if a > 0 else 0.0,
    "math.random": lambda a=0, b=1: (a + b) / 2, "math.random_integer": lambda a, b: (a + b) // 2,
    "math.hermite_blend": lambda t: 3 * t * t - 2 * t * t * t,
    "math.die_roll": lambda n, a, b: n * (a + b) / 2,
}
_BP = {"??": 1, "||": 3, "&&": 4, "==": 5, "!=": 5, "<": 6, ">": 6, "<=": 6, ">=": 6,
       "+": 7, "-": 7, "*": 8, "/": 8}


class Molang:
    """式を評価する。env: {"q.anim_time": 1.2, "v.astro_air": 1, ...}（未知の名前は 0）。"""

    def __init__(self, env=None):
        self.env = {_canon(k): v for k, v in (env or {}).items()}

    def __call__(self, expr):
        if isinstance(expr, (int, float)):
            return float(expr)
        if isinstance(expr, bool):
            return 1.0 if expr else 0.0
        val = 0.0
        for stmt in str(expr).split(";"):
            if not stmt.strip():
                continue
            m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=(?!=)(.*)$", stmt)
            if m:
                self.env[_canon(m.group(1))] = self._eval(m.group(2))
                continue
            st = stmt.strip()
            if st.lower().startswith("return "):
                st = st[7:]
            val = self._eval(st)
        return val

    def _eval(self, s):
        self.t = _tokens(s)
        self.i = 0
        v = self._expr(0)
        return float(v) if not isinstance(v, str) else v

    def _peek(self):
        return self.t[self.i]

    def _next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def _expr(self, rbp):
        left = self._nud(self._next())
        while True:
            k, v = self._peek()
            if k != "o":
                break
            if v == "?":
                if rbp >= 2:
                    break
                self._next()
                a = self._expr(0)
                if self._peek() == ("o", ":"):
                    self._next()
                    b = self._expr(1)
                else:
                    b = 0.0
                left = a if _truth(left) else b
                continue
            bp = _BP.get(v)
            if bp is None or bp <= rbp:
                break
            self._next()
            right = self._expr(bp - (1 if v == "??" else 0))
            left = _binop(v, left, right)
        return left

    def _nud(self, tok):
        k, v = tok
        if k == "n" or k == "s":
            return v
        if k == "o" and v == "(":
            e = self._expr(0)
            self._next()
            return e
        if k == "o" and v == "-":
            return -self._expr(9)
        if k == "o" and v == "+":
            return self._expr(9)
        if k == "o" and v == "!":
            return 0.0 if _truth(self._expr(9)) else 1.0
        if k == "i":
            name = _canon(v)
            if self._peek() == ("o", "("):
                self._next()
                args = []
                if self._peek() != ("o", ")"):
                    while True:
                        args.append(self._expr(0))
                        if self._peek() == ("o", ","):
                            self._next()
                            continue
                        break
                self._next()
                fn = _FUN.get(name)
                if fn is None:
                    return float(self.env.get(name, 0.0))
                return float(fn(*args))
            if name == "math.pi":
                return math.pi
            if name in ("true",):
                return 1.0
            if name in ("false",):
                return 0.0
            return self.env.get(name, 0.0)
        raise ValueError(f"molang: unexpected {tok}")


def _truth(v):
    return bool(v) if not isinstance(v, str) else bool(v)


def _binop(op, a, b):
    if op == "??":
        return a if a is not None else b
    if op == "||":
        return 1.0 if (_truth(a) or _truth(b)) else 0.0
    if op == "&&":
        return 1.0 if (_truth(a) and _truth(b)) else 0.0
    if op == "==":
        return 1.0 if a == b else 0.0
    if op == "!=":
        return 1.0 if a != b else 0.0
    a = float(a) if not isinstance(a, str) else 0.0
    b = float(b) if not isinstance(b, str) else 0.0
    return {"<": lambda: float(a < b), ">": lambda: float(a > b), "<=": lambda: float(a <= b),
            ">=": lambda: float(a >= b), "+": lambda: a + b, "-": lambda: a - b,
            "*": lambda: a * b, "/": lambda: a / b if b else 0.0}[op]()


# ===========================================================================
#  アニメーションの評価
# ===========================================================================
def _vec(v, ev, n=3):
    if isinstance(v, (list, tuple)):
        return [ev(x) for x in v]
    x = ev(v)
    return [x] * n


def _channel(ch, t, ev, length):
    """チャンネル（定数・Molang・キーフレーム辞書）を t で評価（キーの間は線形）。"""
    if isinstance(ch, dict):
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
                u = (t - ts[i]) / ((ts[i + 1] - ts[i]) or 1)
                return [a[j] + (b[j] - a[j]) * u for j in range(3)]
    return _vec(ch, ev)


def eval_animation(anim: dict, t: float, env=None) -> dict:
    """1 本のアニメを t 秒で評価 → {bone: {"rotation","position","scale"}}。"""
    length = anim.get("animation_length")
    loop = anim.get("loop", False)
    tt = t
    if length:
        if loop is True:
            tt = math.fmod(t, length)
        else:
            tt = min(t, length)
    e = dict(env or {})
    e["q.anim_time"] = tt
    e.setdefault("q.life_time", t)
    ev = Molang(e)
    out = {}
    for bone, tr in anim.get("bones", {}).items():
        d = {}
        for key in ("rotation", "position", "scale"):
            if key in tr:
                d[key] = _channel(tr[key], tt, ev, length)
        out[bone] = d
    return out


def combine(*anims) -> dict:
    """複数のアニメの結果を足し合わせる（回転・位置は和、スケールは積）。"""
    out: Dict[str, dict] = {}
    for a in anims:
        for bone, d in a.items():
            o = out.setdefault(bone, {"rotation": [0, 0, 0], "position": [0, 0, 0],
                                      "scale": [1, 1, 1]})
            for k in ("rotation", "position"):
                if k in d:
                    o[k] = [o[k][i] + d[k][i] for i in range(3)]
            if "scale" in d:
                o["scale"] = [o["scale"][i] * d["scale"][i] for i in range(3)]
    return out


# ===========================================================================
#  資産
# ===========================================================================
class SuitAsset:
    def __init__(self, key, geo, tex, anims):
        self.key = key
        self.geo = geo
        self.tex = tex
        self.anims = anims          # 短い名前（assemble, idle, …）→ アニメ本体

    def anim(self, name):
        return self.anims.get(name, {"bones": {}})


def load_suit(key, geo=None, tex=None) -> SuitAsset:
    gp = geo or os.path.join(AC.GEO_DIR, f"astro_suit_{key}.geo.json")
    tp = tex or os.path.join(AC.TEX_DIR, f"suit_{key}.png")
    g = json.load(open(gp, encoding="utf-8"))["minecraft:geometry"][0] if isinstance(gp, str) \
        else gp
    t = Image.open(tp).convert("RGBA") if isinstance(tp, str) else tp
    anims = {}
    ap = os.path.join(AC.ANIM_DIR, "astro_suits.animation.json")
    if os.path.exists(ap):
        doc = json.load(open(ap, encoding="utf-8"))["animations"]
        pre = f"animation.{AC.NS}.suit.{key}."
        for k, v in doc.items():
            if k.startswith(pre):
                anims[k[len(pre):]] = v
    return SuitAsset(key, g, t, anims)


# ===========================================================================
#  プレイヤーの姿勢
# ===========================================================================
def pose(name="stand", t=0.0) -> dict:
    """よく使う姿勢。stand（腕を少し開く）/ walk（t 秒目の歩き）/ hold（右手に物を持つ）/
    air（跳躍中）/ sneak / fp（一人称の腕）/ tpose。"""
    if name == "stand":
        return {"rightArm": {"rotation": (0, 0, 4)}, "leftArm": {"rotation": (0, 0, -4)}}
    if name == "tpose":
        return {"rightArm": {"rotation": (0, 0, 90)}, "leftArm": {"rotation": (0, 0, -90)}}
    if name == "walk":
        a = math.sin(t * math.pi * 2) * 32
        return {"rightArm": {"rotation": (-a, 0, 3)}, "leftArm": {"rotation": (a, 0, -3)},
                "rightLeg": {"rotation": (a, 0, 0)}, "leftLeg": {"rotation": (-a, 0, 0)}}
    if name == "hold":
        return {"rightArm": {"rotation": (-18, 0, 4)}, "leftArm": {"rotation": (0, 0, -4)}}
    if name == "air":
        return {"rightArm": {"rotation": (-14, 0, 18)}, "leftArm": {"rotation": (-14, 0, -18)},
                "rightLeg": {"rotation": (-18, 0, 4)}, "leftLeg": {"rotation": (12, 0, -4)}}
    if name == "sneak":
        return {"body": {"rotation": (28.6, 0, 0), "position": (0, -0.2, 0)},
                "rightLeg": {"position": (0, 0.2, 4)}, "leftLeg": {"position": (0, 0.2, 4)}}
    if name == "fp":
        return {"rightArm": {"rotation": FP_ARM_ROT, "position": FP_ARM_POS}}
    return {}


# ===========================================================================
#  四角形の列（描く物）
# ===========================================================================
FACE_AXIS = {"up": (1, 1), "down": (1, -1), "east": (0, 1), "west": (0, -1),
             "south": (2, 1), "north": (2, -1)}


def geo_quads(geo, W, tex_id, hide=(), tag=False):
    """ジオメトリ（ボーンのワールド行列 W 付き）を四角形の列に。スケール 0 の物は描かない。"""
    out = []
    hidden = set(hide)
    for b in geo["bones"]:
        if b.get("parent") in hidden:
            hidden.add(b["name"])
    for b in geo["bones"]:
        name = b["name"]
        if name in hidden or name not in W:
            continue
        M = W[name]
        if abs(np.linalg.det(M[:3, :3])) < 1e-9:
            continue
        for ci, c in enumerate(b.get("cubes", [])):
            o = np.array(c["origin"], float)
            s = np.array(c["size"], float)
            inf = c.get("inflate", 0.0)
            a, b2 = o - inf, o + s + inf
            CM = M
            if c.get("rotation"):
                cp = np.array(c.get("pivot", o + s / 2), float)
                CM = M @ mat4(t=cp) @ mat4(rot(*c["rotation"])) @ mat4(t=-cp)
            for face, fn in FACES.items():
                uvd = c.get("uv", {})
                f = uvd.get(face) if isinstance(uvd, dict) else None
                pts = [(CM @ np.array([*q, 1.0]))[:3] for q in fn(a, b2)]
                ax, sg = FACE_AXIS[face]
                nl = np.zeros(3)
                nl[ax] = sg
                n = CM[:3, :3] @ nl
                nn = np.linalg.norm(n) or 1.0
                if f:
                    u0, v0 = f["uv"]
                    du, dv = f["uv_size"]
                    uvs = [(u0, v0), (u0 + du, v0), (u0 + du, v0 + dv), (u0, v0 + dv)]
                else:
                    uvs = None
                out.append({"pts": pts, "uvs": uvs, "tex": tex_id, "n": n / nn,
                            "col": (200, 200, 200), "tag": f"{name}#{ci}" if tag else None})
    return out


SKIN_COL = {"head": (214, 168, 132), "body": (60, 150, 160), "rightArm": (196, 150, 118),
            "leftArm": (196, 150, 118), "rightLeg": (52, 60, 120), "leftLeg": (52, 60, 120)}


def player_quads(W, hide=(), layer=True):
    """プレイヤー（肌の箱 + 外側レイヤーの厚み）を色の四角形で。"""
    out = []
    for name, _p, _pv, cube in SKELETON:
        if not cube or name in hide:
            continue
        o, s, col = cube
        inf = (0.5 if name == "head" else 0.25) if layer else 0.0
        a = np.array(o, float) - inf
        b = a + np.array(s, float) + 2 * inf
        M = W[name]
        for face, fn in FACES.items():
            pts = [(M @ np.array([*q, 1.0]))[:3] for q in fn(a, b)]
            ax, sg = FACE_AXIS[face]
            nl = np.zeros(3)
            nl[ax] = sg
            out.append({"pts": pts, "uvs": None, "tex": None, "n": M[:3, :3] @ nl,
                        "col": SKIN_COL.get(name, col), "tag": None})
    return out


def attach_quads(item, W, tex_id):
    """武器などのアタッチャブルを描き足す。item: {"geo","tex","anim","bind"}。"""
    from hd_scene import weapon_quads
    geo = item["geo"]
    if isinstance(geo, str):
        geo = json.load(open(geo, encoding="utf-8"))["minecraft:geometry"][0]
    tex = item["tex"]
    if isinstance(tex, str):
        tex = Image.open(tex).convert("RGBA")
    qs = weapon_quads(geo, tex, W if item.get("bind", "hand") == "hand" else None,
                      item.get("anim", {}), hide=item.get("hide", ()))
    out = []
    for pts, uvs, _c in qs:
        e1, e2 = np.subtract(pts[1], pts[0]), np.subtract(pts[3], pts[0])
        n = np.cross(e1, e2)
        out.append({"pts": pts, "uvs": uvs, "tex": tex_id, "n": n / (np.linalg.norm(n) or 1),
                    "col": (200, 200, 200), "tag": None, "two_sided": True})
    return out, tex


# ===========================================================================
#  ラスタライズ
# ===========================================================================
LIGHT = np.array([-0.35, 0.85, -0.55])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def raster(quads, textures, size, project, bg=None, ss=2, bloom=True, ink=True,
           shadow_y=None, view=None):
    """quads を描く。textures: tex_id -> PIL.Image。発光（アルファが低い texel）は陰影なしで明るく、
    周りに淡いにじみ（bloom）。ink=True で輪郭（深度の段差）に墨線。"""
    W_, H_ = size[0] * ss, size[1] * ss
    img = np.zeros((H_, W_, 3), np.float32)
    if bg is None:
        top, bot = np.array((34, 38, 52), np.float32), np.array((14, 15, 22), np.float32)
        g = np.linspace(0, 1, H_)[:, None, None]
        img[:] = top * (1 - g) + bot * g
    else:
        img[:] = bg
    emis = np.zeros((H_, W_), np.float32)
    z = np.full((H_, W_), 1e9, np.float32)
    tpx = {k: np.asarray(v.convert("RGBA"), np.float32) for k, v in textures.items()}

    def proj(p):
        r = project(p)
        if r is None:
            return None
        return (r[0] * ss, r[1] * ss, r[2])

    # 足元の影（地面 y=shadow_y の楕円）
    if shadow_y is not None:
        c = proj((0, shadow_y, 0))
        ex = proj((7, shadow_y, 0))
        ez = proj((0, shadow_y, 5))
        if c and ex and ez:
            rx = max(abs(ex[0] - c[0]), abs(ez[0] - c[0]), 4)
            ry = max(abs(ez[1] - c[1]), abs(ex[1] - c[1]), 3)
            yy, xx = np.mgrid[0:H_, 0:W_]
            d = ((xx - c[0]) / rx) ** 2 + ((yy - c[1]) / ry) ** 2
            k = np.clip(1 - d, 0, 1)[..., None] * 0.55
            img *= (1 - k)

    for q in quads:
        pts = q["pts"]
        scr = [proj(p) for p in pts]
        if any(s is None for s in scr):
            continue
        n = q["n"]
        lit = 0.62 + 0.38 * max(0.0, float(np.dot(n, LIGHT)))
        if q.get("two_sided"):
            lit = 0.62 + 0.38 * abs(float(np.dot(n, LIGHT)))
        uvs = q["uvs"]
        tx = tpx.get(q["tex"]) if q["tex"] is not None else None
        for tri in ((0, 1, 2), (0, 2, 3)):
            p0, p1, p2 = (scr[i] for i in tri)
            minx = max(0, int(min(p0[0], p1[0], p2[0])))
            maxx = min(W_ - 1, int(max(p0[0], p1[0], p2[0])) + 1)
            miny = max(0, int(min(p0[1], p1[1], p2[1])))
            maxy = min(H_ - 1, int(max(p0[1], p1[1], p2[1])) + 1)
            if minx > maxx or miny > maxy:
                continue
            d = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
            if abs(d) < 1e-9:
                continue
            ys, xs = np.mgrid[miny:maxy + 1, minx:maxx + 1].astype(np.float32)
            xs += 0.5
            ys += 0.5
            w0 = ((p1[1] - p2[1]) * (xs - p2[0]) + (p2[0] - p1[0]) * (ys - p2[1])) / d
            w1 = ((p2[1] - p0[1]) * (xs - p2[0]) + (p0[0] - p2[0]) * (ys - p2[1])) / d
            w2 = 1 - w0 - w1
            m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
            if not m.any():
                continue
            zz = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
            sub = z[miny:maxy + 1, minx:maxx + 1]
            m &= zz < sub
            if not m.any():
                continue
            reg = img[miny:maxy + 1, minx:maxx + 1]
            ereg = emis[miny:maxy + 1, minx:maxx + 1]
            if uvs is not None and tx is not None:
                t0, t1, t2 = (uvs[i] for i in tri)
                u = w0 * t0[0] + w1 * t1[0] + w2 * t2[0]
                v = w0 * t0[1] + w1 * t1[1] + w2 * t2[1]
                ui = np.clip(np.floor(u).astype(int), 0, tx.shape[1] - 1)
                vi = np.clip(np.floor(v).astype(int), 0, tx.shape[0] - 1)
                tt = tx[vi, ui]
                e = 1 - tt[..., 3] / 255
                c = tt[..., :3] * (lit * (1 - e) + 1.12 * e)[..., None]
                reg[m] = np.clip(c[m], 0, 255)
                ereg[m] = e[m]
            else:
                reg[m] = np.clip(np.array(q["col"], np.float32) * lit, 0, 255)
                ereg[m] = 0
            sub[m] = zz[m]

    if ink:
        fg = z < 1e8
        zf = np.where(fg, z, 1e4)
        dz = np.zeros_like(z)
        dz[:, 1:] = np.maximum(dz[:, 1:], np.abs(zf[:, 1:] - zf[:, :-1]))
        dz[1:, :] = np.maximum(dz[1:, :], np.abs(zf[1:, :] - zf[:-1, :]))
        thr = 1.6
        edge = (dz > thr) & (emis < 0.5)
        img[edge] *= 0.35
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if bloom:
        glow = (np.clip(img, 0, 255) * emis[..., None]).astype(np.uint8)
        gl = Image.fromarray(glow).filter(ImageFilter.GaussianBlur(3 * ss))
        out = Image.fromarray(np.clip(np.asarray(out, np.float32)
                                      + np.asarray(gl, np.float32) * 0.9, 0, 255).astype(np.uint8))
    if ss > 1:
        out = out.resize(size, Image.LANCZOS)
    return out


def ortho(yaw, pitch, centre, scale, size):
    """正射影。yaw=0 で正面（-Z 側）から、180 で背後、90 で左側面。X は鏡映（hd_scene と同じ）。"""
    V = Rx(pitch) @ Ry(yaw)
    W_, H_ = size
    c = np.asarray(centre, float)

    def project(p):
        q = V @ (np.asarray(p, float) - c)
        return (W_ / 2 + q[0] * scale, H_ / 2 - q[1] * scale, q[2])
    return project


# ===========================================================================
#  描く
# ===========================================================================
def scene_quads(asset, pose_, anim, weapon=None, extra=None, show_player=True,
                hide=(), player_hide=()):
    W = skeleton_world(pose_ or {})
    SW = suit_world(asset.geo, W, anim)
    quads = geo_quads(asset.geo, SW, "suit", hide=hide)
    textures = {"suit": asset.tex}
    if show_player:
        quads = player_quads(W, hide=player_hide) + quads
    for i, it in enumerate([x for x in (weapon, extra) if x]):
        q, t = attach_quads(it, W, f"att{i}")
        quads += q
        textures[f"att{i}"] = t
    return quads, textures


def render(asset, pose_=None, anim=None, view="front", size=(300, 400), scale=None,
           centre=(0, 16.5, 0), weapon=None, extra=None, show_player=True, hide=(),
           ss=2, bloom=True, shadow=True):
    """三人称（正射影）。view は VIEWS の名前か (yaw, pitch)。"""
    yaw, pitch = VIEWS[view] if isinstance(view, str) else view
    scale = scale or size[1] / 40.0
    quads, textures = scene_quads(asset, pose_ if pose_ is not None else pose("stand"),
                                  anim or {}, weapon, extra, show_player, hide)
    proj = ortho(yaw, pitch, centre, scale, size)
    return raster(quads, textures, size, proj, ss=ss, bloom=bloom,
                  shadow_y=-0.6 if shadow else None)


def render_fp(asset, anim=None, size=(400, 225), fov=70.0, weapon=None, show_player=True):
    """一人称。腕は (95,-45,115)/(13.5,-10,12)、目 (0,26,0) から +Z を見る（hd_scene.fp と同じ）。
    anim に fp_hide を入れておくと、一人称で実際に残る物だけが描かれる。"""
    W = skeleton_world(pose("fp"))
    SW = suit_world(asset.geo, W, anim or {})
    quads = geo_quads(asset.geo, SW, "suit")
    textures = {"suit": asset.tex}
    if show_player:
        quads = player_quads(W, hide=("head", "body", "leftArm", "rightLeg", "leftLeg"),
                             layer=False) + quads
    if weapon:
        q, t = attach_quads(weapon, W, "att0")
        quads += q
        textures["att0"] = t
    W_, H_ = size
    f = (H_ / 2) / math.tan(math.radians(fov / 2))

    def project(p):
        q = np.asarray(p, float) - FP_EYE
        if q[2] < 0.5:
            return None
        return (W_ / 2 + q[0] / q[2] * f, H_ / 2 - q[1] / q[2] * f, q[2])
    bg = None
    return raster(quads, textures, size, project, bg=bg, ss=2, ink=False)


# ---- アニメの組み合わせ ------------------------------------------------------
def suit_anim(asset, names, t=0.0, env=None) -> dict:
    """スーツのアニメ（短い名前のリスト、例 ["idle","thrust"]）を t 秒で評価して合成。"""
    e = {"v.astro_air": 0.0, "v.astro_run": 0.0, "v.astro_fp": 0.0, "q.is_on_ground": 1.0}
    e.update(env or {})
    return combine(*[eval_animation(asset.anim(n), t, e) for n in names])


def assembly_anim(asset, t) -> dict:
    return suit_anim(asset, ["assemble", "idle", "thrust"], t)


def release_anim(asset, t) -> dict:
    return suit_anim(asset, ["release", "idle", "thrust"], t)


# ===========================================================================
#  並べ図
# ===========================================================================
def font(size):
    for path in ("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
                 "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def label(img, text, sub=None, col=(236, 240, 248)):
    d = ImageDraw.Draw(img)
    d.text((10, 8), text, font=font(17), fill=col)
    if sub:
        d.text((10, 30), sub, font=font(12), fill=(150, 158, 176))
    return img


def sheet(tiles, path, cols=5, title=None, bg=(12, 13, 18)):
    w = max(t.size[0] for t in tiles)
    h = max(t.size[1] for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    th = 44 if title else 0
    out = Image.new("RGB", (w * cols, h * rows + th), bg)
    if title:
        ImageDraw.Draw(out).text((12, 10), title, font=font(22), fill=(240, 244, 255))
    for k, t in enumerate(tiles):
        out.paste(t, ((k % cols) * w, th + (k // cols) * h))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    return path
