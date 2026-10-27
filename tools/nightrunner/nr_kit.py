# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — ゾンビの組み立て（spec の 1 体 → モデル・stylebook・情報）。DESIGN.md §3 / §11 / §13。

使い方（gen_nr_zombies から）::

    import nr_kit
    model, book, info = nr_kit.build_zombie(nr_spec.ZOMBIE_BY_KEY["office_worker"])
    tex = nr_paint.paint_model(model, book, seed=...)          # アトラスは build_zombie が詰め済み
    nr_common.write_geometry(path, model)                      # geometry.nr.z.<key>（1.16.0）
    gib = nr_rig.extract_gibs(model, key)                      # geometry.nr.gib.<key>
    rules = nr_kit.visibility_rules(model, z)                  # part_visibility（全種類を merge_visibility）
    hit = nr_kit.hitboxes(model)                               # 当たり箱（長い突起は数えない）

build_zombie(z) の手順:
  1. ``nr_rig.new_model(key)``（geometry.nr.z.<key>）と ``ZombieRig``（spec の骨格欄 height_cm / heads / bulk /
     limb / hunch / arm_len / female。gen_nr_zombie_anim.rig_build と同じ寸法なので、アニメのボーンの pivot・
     休みの回転と一致する）＋顔デカール（eyes / decay / 口の形 / 鼻。変異の eyeless / missing_nose /
     split_face / elongated_jaw を見て決める）。
  2. 服（nr_kit_outfit.dress。内側から）→ 変異（nr_kit_mut.mutate。DEPTH の順）→ 種類ごとの特注
     （BESPOKE[key]）→ 獣の脚（z["digitigrade"]: 浮いた踵の瘤・長い足の甲・鉤爪。骨格は変えない）。
  3. キューブの予算（DESIGN §11: 一般・ヴァイラル ≤ 450、特殊・夜 ≤ 650、ボス ≤ 1100）。超えたら
     detail 1（指を板に）→ 変異の数の倍率 scale を下げて作り直す。
  4. アトラス: 512×512（ボスは 1024×1024）。uv の密度の倍率 texel を大きい方から段階的に試し、
     最初に詰められた物を使う（アトラスの大きさは固定なので、空きを残さず細かく塗る）。
  info = {key, cls, cubes, cap, bones, atlas, texel, detail, scale, styles, warnings, mut_cubes, outfit_cubes,
          visibility, glow, particles, breakables, bespoke, emissive}
  （gen_nr_zombies.zombie_assets(key) は visibility をそのまま渡すこと。渡さないと gen_nr_entities は
  nr_rig.visibility_rules に戻り、breakables・明滅・段階の条件が落ちる。emissive が True なら
  マテリアルは entity_emissive_alpha（光る texel を alphatest で描くと穴になる）。）

visibility_rules(model, z) … nr_rig.visibility_rules の規則（§3 のプロパティ・armor_*）に、gore.breakables
  （そのボーンは nr:armor >= 段階の間だけ表示）と、変異・特注の明滅・能力の段階の項（model.nr_vis_terms。
  glow_* / held_debris / spawn_sac / shriek）を祖先ごと AND した (ボーン, Molang) の並び。
hitboxes(model) … nr_rig.hitboxes から cube.nr_nohit のキューブ（触手・刺さった棒・余分な腕・瓦礫）を除いた物。

自己テスト: ``python3 tools/nightrunner/nr_kit.py`` … spec の 50 体を全部組み立てて予算・アトラス・ボーンの親・
part_visibility の一貫性・gib の抽出・決定性を確かめ、特注の 5 体とボスの確認画像
（build_preview/nightrunner/kit_build.png）を作る。--all-sheets で 50 体全部の確認画像（kit_build_<n>.png）。
"""
from __future__ import annotations

import copy
import os
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nr_common as C  # noqa: E402
import nr_kit_mut as KM  # noqa: E402
import nr_kit_outfit as KO  # noqa: E402
import nr_paint as P  # noqa: E402
import nr_rig as R  # noqa: E402
import nr_spec as S  # noqa: E402

# DESIGN §11 のキューブの上限（区分ごと）
CAPS = {"common": 450, "viral": 450, "special": 650, "night": 650, "boss": 1100}
# 予算に収める段: (detail, 変異の数の倍率)
_TRIES = ((2, 1.0), (1, 1.0), (1, 0.75), (1, 0.55), (1, 0.4))
# アトラスに詰める uv の密度の倍率（大きい方から）
_TEXELS = (1.25, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5)
_TEXELS_BOSS = (2.0, 1.75, 1.5, 1.3, 1.15, 1.0, 0.85, 0.7, 0.6)


def spec_build(z: dict) -> dict:
    """spec の骨格欄 → ZombieRig の build（gen_nr_zombie_anim.rig_build と同じ寸法）。"""
    return KO.spec_build(z)


def _mut_keys(z: dict) -> set:
    return {m[0] for m in z.get("mutations", ())}


def face_build(z: dict) -> dict:
    """顔デカールの欄（eyes / decay / mouth / gore_face / nose）。変異に合わせる。"""
    mk = _mut_keys(z)
    decay = int(z.get("decay", 2))
    eyes = "none" if "eyeless" in mk else z.get("eyes", "clouded")
    split = any(m[0] == "elongated_jaw" and m[1].get("split") for m in z.get("mutations", ()))
    if split or "missing_cheek_teeth" in mk or "torn_throat" in mk:
        mouth = "torn"
    elif decay >= 3:
        mouth = "gaping"
    else:
        mouth = "snarl"
    fresh = any(m[0] == "bite_wound" and m[1].get("fresh") for m in z.get("mutations", ()))
    gore = min(0.9, 0.25 + 0.1 * decay + (0.2 if fresh else 0.0))
    nose = not ({"missing_nose", "split_face"} & mk) and decay < 4
    return dict(eyes=eyes, decay=decay, mouth=mouth, gore_face=round(gore, 2), nose=nose)


def _hair_colour(z: dict):
    for k, over in z.get("outfit", ()):
        if k == "hair" and over.get("color") is not None:
            return KO._c3(over["color"])
    return None


def zombie_book(z: dict) -> dict:
    """体の stylebook（nr_paint.zombie_styles。肌・腐敗・目・血の種類・生前の肌色）。体の血は控えめ
    （血は傷・断面・口元が受け持つ。全身が血で黒ずむと形が読めない）。"""
    fb = face_build(z)
    return P.zombie_styles(z["skin"], fb["decay"], fb["eyes"], hair_colour=_hair_colour(z),
                           blood=min(0.3, 0.15 + 0.04 * fb["decay"]), life_tone=z.get("tone"),
                           blood_kind=(z.get("gore") or {}).get("blood", "red"))
def visibility_rules(model, z: Optional[dict] = None, breakables: Optional[dict] = None) -> List[Tuple[str, str]]:
    """part_visibility の (ボーン, Molang)。nr_rig の規則＋gore.breakables（nr:armor >= 段階）＋
    model.nr_vis_terms（明滅・能力の段階）を、ボーンと全祖先について AND する。"""
    bones = {b.name: b for b in model.bones}
    brk = dict(breakables if breakables is not None else ((z or {}).get("gore") or {}).get("breakables") or {})
    terms = getattr(model, "nr_vis_terms", None) or {}
    out = []
    for b in model.bones:
        enum_c, int_c = R._bone_constraints(bones, b.name)
        extra: List[str] = []
        cur, seen = b.name, set()
        while cur and cur not in seen:
            seen.add(cur)
            if cur in brk:
                int_c["nr:armor"] = max(int_c.get("nr:armor", 0), int(brk[cur]))
            for t in terms.get(cur, ()):
                if t not in extra:
                    extra.append(t)
            cur = bones[cur].parent if cur in bones else None
        e = R._expr(enum_c, int_c)
        if e == "false":
            out.append((b.name, e))
            continue
        parts = ([e] if e else []) + [f"({t})" for t in extra]
        if parts:
            out.append((b.name, " && ".join(parts)))
    return out


def hitboxes(model) -> dict:
    """nr_rig.hitboxes（nr_nohit のキューブを除く）。"""
    saved = []
    for b in model.bones:
        keep = [c for c in b.cubes if not getattr(c, "nr_nohit", False)]
        if len(keep) != len(b.cubes):
            saved.append((b, b.cubes))
            b.cubes = keep
    try:
        return R.hitboxes(model)
    finally:
        for b, cubes in saved:
            b.cubes = cubes


# ---------------------------------------------------------------------------
#  獣の脚（踵の浮いた脚。骨格はそのまま、足と脛の形だけ）
# ---------------------------------------------------------------------------
def _digitigrade(rig, z: dict, book: dict, scale: float = 1.0) -> Dict[str, dict]:
    ctx = KM.MutCtx(z, "digitigrade", book, scale=scale)
    M = KM._M(rig, {}, ctx, "digitigrade")
    L = M.L
    claw = M.ms("toe_claw", "nail", base=(36, 30, 28), blood=0.3)
    for s in ("r", "l"):
        foot, shin = f"foot_{s}", f"shin_{s}"
        if foot not in rig.bones or shin not in rig.bones:
            continue
        fs = M.seg(foot)
        fx = (fs["lo"][0] + fs["hi"][0]) / 2
        fz0, fz1 = fs["lo"][2], fs["hi"][2]
        covered = M.outer(foot) > 0
        if not covered:
            fb = rig.bones[foot]
            fb.cubes = [c for c in fb.cubes if getattr(c, "nr_kit", None) or c.origin[2] < 0.02 * L.foot_l]
        # 踵の瘤（後ろ上へ突き出た距骨）と、張った腱
        a = np.array([fx, L.ankle_y + 0.2 * M.T, 0.15 * fz1])
        hock = a + np.array([0.0, 1.5 * M.T, 0.9 * M.T + 0.4 * fz1])
        M.beam(shin, a, hock, 0.55 * M.T, 0.62 * M.T, M.skin_st(shin, "skin_dark"))
        M.beam(shin, hock + np.array([0.0, -0.1, -0.15]), hock + np.array([0.0, 1.4 * M.T, -0.5 * M.T]), 0.32 * M.T,
               0.3 * M.T, M.skin_st(shin))
        # 前へ長く伸びた足の甲と指、鉤爪
        ext = 0.9 * M.T
        M.box(foot, fx - 0.42 * L.foot_w, 0.0, fz0 - ext, fx + 0.42 * L.foot_w, 0.035 * L.t, fz0 + 0.6,
              M.skin_st(foot))
        for k in (-1, 0, 1):
            base = np.array([fx + k * 0.27 * L.foot_w, 0.12 * M.T, fz0 - ext + 0.05])
            M.spike(foot, base, (k * 0.12, -0.22, -1.0), 0.65 * M.T, 0.22 * M.T, claw, segs=2, bend=(0.0, -0.25, 0.0),
                    uv=M.U["fine"])
    return M.done()


# ---------------------------------------------------------------------------
#  特注（語彙だけでは形にならない種類）
# ---------------------------------------------------------------------------
def _ctxM(rig, z, book, key, scale):
    ctx = KM.MutCtx(z, "bespoke_" + key, book, scale=scale)
    return KM._M(rig, {}, ctx, "bespoke_" + key)


def _phase(z: dict, name: str) -> Optional[int]:
    try:
        return S.ability_states(z).get(name)
    except Exception:  # noqa: BLE001
        return None


def b_flesh_colossus(rig, z, book, scale=1.0):
    """肉の山: 肩の後ろに盛り上がる瘤（犠牲者の肌・腫瘍・肉。頭は埋めない）と瘤から突き出た犠牲者の手、
    腹と脇に癒着した犠牲者の胴（白い肌とシャツの切れ端）、腹から垂れる黄色い脂肪の襞、
    腹の下に吊るされた卵嚢（tumor_spawn の drop の間は消える = 落とした）。"""
    M = _ctxM(rig, z, book, "flesh_colossus", scale)
    L = M.L
    ct, cb, ab = L.chest_top, L.chest_bot, L.abdomen_bot
    ch = ct - cb
    T = M.T
    H = L.H
    rng = M.rng
    mass = M.ms("colossus_mass", "tumor", base=(196, 140, 120))
    fat = M.ms("colossus_fat", "tumor", base=(222, 196, 136))
    raw = M.bs("flesh")
    shirt = M.ms("victim_shirt", "cloth", base=(196, 196, 186), pattern="plain", torn=0.5, blood=0.6, dirt=0.5,
                 under=(120, 60, 50))
    v = [KM._victim_skin(M, i) for i in range(4)]
    x0, z0, x1, z1 = M.sring("chest", cb + 0.7 * ch)
    cw = x1 - x0
    # 肩の後ろの瘤（頭の大きさに合わせ、頭のてっぺんより上へは出さない）
    humps = [(0.0, 0.62, 0.72, mass), (-0.3, 0.75, 0.6, v[0]), (0.32, 0.7, 0.62, v[1]),
             (-0.12, 0.4, 0.66, fat), (0.18, 0.92, 0.5, mass), (-0.36, 0.45, 0.5, v[3])]
    for fx, fy, fr, st in humps:
        r = fr * H
        y = min(cb + fy * ch, L.chin - 0.1 * H)
        q = np.array([fx * cw, y, z1 - 0.15 * r])
        M.blob("chest", q, "s", r, 0.85 * r, st, cap_style=mass if st is not mass else v[2], spin=rng.uniform(-15, 15))
    # 瘤から突き出た犠牲者の手（指を開いて）
    for i in range(M.n(4)):
        fx, fy = rng.uniform(-0.38, 0.38), rng.uniform(0.45, 0.95)
        root = np.array([fx * cw, cb + fy * ch, z1 + 0.6 * H])
        d = KM._unit((fx * 0.8, rng.uniform(0.2, 0.9), 1.0))
        tip = root + d * 1.6 * T
        vs = v[i % 4]
        cubes = [M.beam("chest", root, tip, 0.6 * T, 0.6 * T, vs)]
        palm = tip + d * 0.45 * T
        cubes.append(M.cbox("chest", tuple(palm), (0.75 * T, 0.75 * T, 0.75 * T), vs))
        for k in (-1, 0, 1):
            a = palm + np.array([k * 0.24 * T, 0.0, 0.0])
            cubes.append(M.beam("chest", a, a + KM._unit(d + np.array([k * 0.3, 0.2, 0.0])) * 0.85 * T, 0.16 * T,
                                0.16 * T, vs))
        for cb_ in cubes:
            cb_.nr_nohit = True
    # 腹と脇に癒着した犠牲者の胴（白い肌・シャツの切れ端・肋骨）
    hh = cb - ab
    x0b, z0b, x1b, z1b = M.sring("abdomen", ab + 0.5 * hh)
    for k, (sx, fy, tilt) in enumerate(((-1, 0.55, 14.0), (1, 0.35, -18.0))):
        cx = sx * 0.3 * (x1b - x0b)
        P0 = np.array([cx, ab + fy * hh, z0b])
        tw, th_ = 0.3 * (x1b - x0b), 0.8 * hh
        rot = (rng.uniform(-6, 6), sx * 10.0, tilt)
        piv = tuple(P0)
        M.box("torso", cx - tw / 2, P0[1] - th_ / 2, z0b - 1.2 * T, cx + tw / 2, P0[1] + th_ / 2, z0b + 0.5,
              v[(k + 1) % 4], rot=rot, pivot=piv)
        M.box("torso", cx - tw / 2 - 0.08, P0[1] - th_ * 0.1, z0b - 1.32 * T, cx + tw / 2 + 0.08, P0[1] + th_ / 2 + 0.08,
              z0b + 0.3, shirt, rot=rot, pivot=piv)
        for j in (-1, 1):
            yy = P0[1] - th_ * 0.25 + j * 0.45 * T
            M.box("torso", cx - tw * 0.36, yy - 0.15 * T, z0b - 1.45 * T, cx + tw * 0.36, yy + 0.15 * T, z0b - 1.15 * T,
                  M.bs("bone"), rot=rot, pivot=piv)
    # 腹から垂れる黄色い脂肪の襞（2 段）
    fold = [dict(name="stripe", orient="h", count=3, width=0.05, gap=0.18, colour=(150, 110, 70), wear=0.3)]
    M.box("torso", x0b * 0.92, ab - 0.4 * hh, z0b - 1.6 * T, x1b * 0.92, ab + 0.25 * hh, z0b + 0.6, fat,
          decals={"north": fold})
    M.box("torso", x0b * 0.7, ab - 0.68 * hh, z0b - 1.3 * T, x1b * 0.7, ab - 0.3 * hh, z0b + 0.4, fat)
    # 卵嚢（腹の下に吊るされ、drop の段階で消える）
    v_drop = _phase(z, "tumor_spawn.drop")
    sac_piv = (0.0, ab - 0.6 * hh, z0b - 1.0 * T)
    sb = M.child_bone("spawn_sac", pivot=sac_piv, parent="torso")
    if v_drop:
        rig.model.nr_vis_terms[sb] = [f"q.property('nr:ability') != {v_drop}"]
    memb = M.ms("spawn_sac", "tumor", base=(214, 196, 160))
    for k, (dx, dy) in enumerate(((-0.6, -0.9), (0.55, -1.1), (0.0, -1.5))):
        c = np.array([sac_piv[0] + dx * T * 1.3, sac_piv[1] + dy * T * 1.4, sac_piv[2] - 0.6 * T])
        r = (1.0 - 0.12 * k) * T
        M.box(sb, c[0] - r, c[1] - r * 1.1, c[2] - r, c[0] + r, c[1] + r * 1.1, c[2] + r, memb,
              decals={"north": dict(name="veins", colour=(120, 50, 60), amount=0.7)})
        M.box(sb, c[0] - r * 0.6, c[1] - r * 1.25, c[2] - r * 0.6, c[0] + r * 0.6, c[1] + r * 1.25, c[2] + r * 0.6,
              memb)
        M.beam(sb, c + np.array([0.0, r * 1.05, 0.0]), np.array(sac_piv), 0.22 * T, 0.22 * T, raw)
    for cb_ in rig.bones[sb].cubes:
        cb_.nr_nohit = True
    return M.done()


def b_subject_zero(rig, z, book, scale=1.0):
    """研究所の最初の変異体: 頭蓋に 4 本のねじで留めた固定輪（ハロー）、背骨に沿った金属の装具と
    再生の血清の光る小瓶（明滅）・首のポートへの管、千切れた首輪、首の識別番号。"""
    M = _ctxM(rig, z, book, "subject_zero", scale)
    L = M.L
    T = M.T
    steel = M.ms("sz_steel", "metal", base=(150, 156, 164), scratches=0.5, blood=0.3)
    dark = M.ms("sz_dark", "metal", base=(60, 64, 70), scratches=0.4)
    serum = M.ms("sz_serum", "glow", base=(120, 220, 255))
    glass = M.ms("sz_glass", "glass", crack=0.2)
    tube = M.ms("sz_tube", "plastic", base=(190, 200, 210), blood=0.4)
    # ハロー（頭を囲む輪と頭蓋へのねじ）
    Hd = M.head()
    o = 0.55 * T
    y = Hd.brow + 0.2
    hx0, hx1, hz0, hz1 = Hd.ex0 - o, Hd.ex1 + o, Hd.z0 - o, Hd.z1 + o
    th = 0.16 * T
    M.box("head", hx0, y - th, hz0, hx1, y + th, hz0 + th * 1.6, steel)
    M.box("head", hx0, y - th, hz1 - th * 1.6, hx1, y + th, hz1, steel)
    M.box("head", hx0, y - th, hz0, hx0 + th * 1.6, y + th, hz1, steel)
    M.box("head", hx1 - th * 1.6, y - th, hz0, hx1, y + th, hz1, steel)
    for sx in (-1, 1):
        for zz in (Hd.z0 + 0.2 * Hd.d, Hd.z1 - 0.25 * Hd.d):
            xs = Hd.x1 if sx > 0 else Hd.x0
            M.beam("head", (xs - sx * 0.1, y, zz), (sx * (abs(hx1) + 0.1), y, zz), 0.12, 0.12, dark)
    # 背中の装具（背骨の両脇の金属の柱と横木）・血清の小瓶
    ct, cb = L.chest_top, L.chest_bot
    ch = ct - cb
    zb = M.sring("chest", cb + 0.6 * ch)[3]
    for sx in (-1, 1):
        M.box("chest", sx * 0.75 * T - 0.18 * T, cb + 0.1 * ch, zb + 0.35 * T, sx * 0.75 * T + 0.18 * T,
              ct - 0.05 * ch, zb + 0.75 * T, steel)
    for k in range(3):
        yy = cb + (0.25 + 0.3 * k) * ch
        M.box("chest", -1.1 * T, yy - 0.12 * T, zb + 0.4 * T, 1.1 * T, yy + 0.12 * T, zb + 0.7 * T, dark)
    gb = M.glow_bone("chest", 1.0)
    for k, sx in enumerate((-1, 1)):
        c = np.array([sx * 1.45 * T, cb + 0.62 * ch, zb + 0.75 * T])
        M.box("chest", c[0] - 0.36 * T, c[1] - 0.95 * T, c[2] - 0.36 * T, c[0] + 0.36 * T, c[1] + 0.95 * T,
              c[2] + 0.36 * T, glass)
        M.box("chest", c[0] - 0.4 * T, c[1] + 0.95 * T, c[2] - 0.4 * T, c[0] + 0.4 * T, c[1] + 1.2 * T,
              c[2] + 0.4 * T, steel)
        M.box(gb, c[0] - 0.4 * T, c[1] - 0.85 * T, c[2] - 0.4 * T, c[0] + 0.4 * T, c[1] + 0.75 * T, c[2] + 0.4 * T,
              serum)
        # 小瓶から首の後ろへの管
        a = c + np.array([0.0, 1.2 * T, 0.0])
        nz = M.sring("neck", L.shoulder_y + 0.3)[3]
        b_ = np.array([sx * 0.3 * T, L.shoulder_y + 0.4, nz])
        mid = (a + b_) / 2 + np.array([0.0, 0.6 * T, 0.5 * T])
        for p0, p1 in ((a, mid), (mid, b_)):
            M.beam("chest", p0, p1, 0.16 * T, 0.16 * T, tube).nr_nohit = True
    # 千切れた首輪
    y0 = L.shoulder_y + 0.25 * (L.chin - L.shoulder_y)
    x0, z0, x1, z1 = M.sring("neck", y0)
    M.box("neck", x0 - 0.12, y0 - 0.22 * T, z0 - 0.12, x1 + 0.12, y0 + 0.22 * T, z1 + 0.12, dark,
          decals={"north": dict(name="text", text="S-0", colour=(220, 220, 220), wear=0.4)})
    KO._chain(M, "neck", ((x0 + x1) / 2, y0 - 0.25 * T, z0 - 0.15), 3, steel, drift=(0.1, -1.0, -0.3), link=0.5)
    return M.done()


def b_night_apex(rig, z, book, scale=1.0):
    """夜の頂点: 後ろへ反る骨の冠（頭）、肩から背へ扇のように立つ骨の鬣、肘の後ろの骨の鉤、
    叫び（uv_shatter.shriek）の間だけ光る首の共鳴の裂け目（ふだんは暗い）。"""
    M = _ctxM(rig, z, book, "night_apex", scale)
    L = M.L
    T = M.T
    col = (206, 200, 184)
    bone = M.ms("apex_bone", "bone", base=col, age=0.4, blood=0.35)
    bone_dk = M.ms("apex_bone_dark", "bone", base=(150, 142, 130), age=0.7, blood=0.3)
    Hd = M.head()
    o = min(M.outer("head"), 0.6) + 0.3 * T
    rng = M.rng
    # 骨の冠: 額の上から後ろへ反る角（左右に 3 本ずつ、外ほど短い）
    for sx in (-1, 1):
        for k in range(3):
            base = np.array([Hd.cx + sx * Hd.w * (0.12 + 0.17 * k), Hd.top + o * 0.6 - 0.15 * k,
                             Hd.z0 + Hd.d * (0.15 + 0.12 * k)])
            d = (sx * (0.25 + 0.2 * k), 0.75, 0.9)
            M.spike("head", base, d, (3.6 - 0.7 * k) * T, (0.55 - 0.08 * k) * T, bone if k % 2 == 0 else bone_dk,
                    segs=3, bend=(sx * 0.03, -0.12, 0.1))
    # 肩から背への鬣（扇形に立つ長い骨の棘）
    ct, cb = L.chest_top, L.chest_bot
    ch = ct - cb
    zb = M.sring("chest", ct - 0.25 * ch)[3]
    n = M.n(9)
    for i in range(n):
        t = i / max(1, n - 1)
        sx = -1 + 2 * t
        base = np.array([sx * 0.42 * L.chest_w, ct - 0.08 * ch - 0.25 * abs(sx) * ch, zb - 0.4 * T])
        d = (sx * 0.9, 1.0 - 0.3 * abs(sx), 0.75)
        ln = (4.2 - 1.6 * abs(sx)) * T * rng.uniform(0.9, 1.1)
        M.spike("chest", base, d, ln, 0.5 * T, bone if i % 2 == 0 else bone_dk, segs=3, bend=(0.0, -0.08, 0.1),
                aspect=(0.6, 1.0))
    # 肘の後ろの骨の鉤
    for s in ("r", "l"):
        arm = f"arm_{s}"
        if arm not in rig.bones:
            continue
        sx = -1.0 if s == "r" else 1.0
        base = np.array([sx * L.arm_x, L.elbow_y + 0.1, 0.45 * L.arm_t])
        M.spike(arm, base, (sx * 0.2, -0.4, 1.0), 2.0 * T, 0.45 * T, bone, segs=3, bend=(0.0, -0.15, -0.05))
    # 首の共鳴の裂け目（ふだんは暗く、叫びの間だけ光る）
    v = _phase(z, "uv_shatter.shriek")
    slit_dk = M.ms("apex_slit", "gore_wet")
    glow = M.ms("apex_slit_glow", "glow", base=(255, 210, 90))
    gb = M.glow_bone("neck", 6.0, phase=v) if v else None
    ym = (L.shoulder_y + L.chin) / 2
    for sx in (-1, 1):
        side = "w" if sx > 0 else "e"
        for k in range(3):
            q = M.pt("neck", side, 0.3 + 0.18 * k, ym + (k - 1) * 0.35 * T)
            M.fbox("neck", q, side, 0.1 * T, 0.5 * T, -0.04, 0.06, slit_dk, spin=sx * 12)
            if gb:
                M.fbox(gb, q, side, 0.12 * T, 0.52 * T, -0.02, 0.09, glow, spin=sx * 12)
    return M.done()


def b_wrecker(rig, z, book, scale=1.0):
    """瓦礫投げ: 右手の子ボーン held_debris に、鉄筋の突き出たコンクリートの塊（debris_throw の
    lift の段階だけ表示。当たり箱に数えない）。"""
    M = _ctxM(rig, z, book, "wrecker", scale)
    L = M.L
    T = M.T
    hs = M.seg("hand_r")
    cx = (hs["lo"][0] + hs["hi"][0]) / 2
    y = hs["lo"][1]
    hb = M.child_bone("held_debris", pivot=(cx, L.wrist_y, 0.0))
    v = _phase(z, "debris_throw.lift")
    rig.model.nr_vis_terms[hb] = [f"q.property('nr:ability') == {v or 1}"]
    conc = M.ms("debris_concrete", "concrete", cracks=0.7, base=(150, 148, 142))
    conc2 = M.ms("debris_concrete2", "concrete", cracks=0.9, base=(122, 120, 116))
    rebar = M.ms("debris_rebar", "rust", amount=0.95)
    s = 6.5 * T
    c = np.array([cx - 0.3 * T, y - 1.6 * T, 0.0])
    cubes = [M.box(hb, c[0] - s * 0.55, c[1] - s * 0.45, c[2] - s * 0.6, c[0] + s * 0.5, c[1] + s * 0.4, c[2] + s * 0.55,
                   conc, rot=(8, 14, -6), pivot=tuple(c)),
             M.box(hb, c[0] - s * 0.35, c[1] - s * 0.62, c[2] - s * 0.4, c[0] + s * 0.42, c[1] - s * 0.3, c[2] + s * 0.42,
                   conc2, rot=(-6, 30, 10), pivot=tuple(c)),
             M.box(hb, c[0] - s * 0.6, c[1] + s * 0.2, c[2] - s * 0.3, c[0] - s * 0.1, c[1] + s * 0.55, c[2] + s * 0.4,
                   conc2, rot=(0, -12, 14), pivot=tuple(c))]
    for d in ((1.0, 0.6, -0.3), (-0.6, 0.9, 0.5), (0.3, -0.2, 1.0)):
        a = c + KM._unit(d) * s * 0.3
        cubes.append(M.beam(hb, a, a + KM._unit(d) * s * 0.7, 0.24 * T, 0.24 * T, rebar))
    for cb_ in cubes:
        cb_.nr_nohit = True
    return M.done()


def b_hive_warden(rig, z, book, scale=1.0):
    """巣の番人: 背中の巣（菌の巣板の層）と、透けた卵嚢（中の光る芯は hive_summon の birth で脈打つ）。"""
    M = _ctxM(rig, z, book, "hive_warden", scale)
    L = M.L
    T = M.T
    ct, cb = L.chest_top, L.chest_bot
    ch = ct - cb
    comb = M.ms("hive_comb", "fungus", base=(170, 150, 110), alt=(214, 196, 150))
    comb2 = M.ms("hive_comb_dark", "fungus", base=(120, 100, 76), alt=(170, 150, 110))
    memb = M.ms("brood_membrane", "tumor", base=(196, 206, 160))
    dim = M.ms("brood_core", "tumor", base=(110, 150, 120))
    glow = M.ms("brood_glow", "glow", base=(140, 255, 190))
    x0, z0, x1, z1 = M.sring("chest", cb + 0.55 * ch)
    zb = z1
    cw = x1 - x0
    for k, (fy, fr) in enumerate(((0.45, 0.36), (0.75, 0.3), (0.2, 0.28))):
        q = np.array([(k - 1) * 0.12 * cw, cb + fy * ch, zb - 0.1])
        M.fbox("chest", q, "s", fr * cw, fr * ch * 1.3, -0.1, (1.1 - 0.2 * k) * T, comb if k % 2 == 0 else comb2,
               spin=(k - 1) * 9, decals={"south": dict(name="cracks", amount=0.9)})
    v = _phase(z, "hive_summon.birth")
    gb = M.glow_bone("chest", 0.6, phase=v) if v else M.glow_bone("chest", 0.6)
    rng = M.rng
    for i in range(M.n(5)):
        fx = rng.uniform(-0.38, 0.38)
        fy = rng.uniform(0.25, 0.95)
        q = np.array([fx * cw, cb + fy * ch, zb + 0.9 * T])
        r = rng.uniform(0.6, 0.95) * T
        M.lump("chest", q, "s", r, r * 1.2, memb, cap_style=memb)
        M.fbox("chest", q, "s", r * 0.45, r * 0.45, 0.0, r * 1.05, dim)
        M.fbox(gb, q, "s", r * 0.5, r * 0.5, 0.0, r * 1.1, glow, uv=M.U["fine"])
    return M.done()


def uses_emissive(model, book: dict) -> bool:
    """組み立てたモデルが光る texel（entity_emissive_alpha の小さな α）を出すか。マテリアル選びに使う
    （光る画素を alphatest で描くと穴になる）。glow 素材・光る目・光る血・燠火・発光する血管・
    菌の光る斑点・発光のデカール（veins emissive / glow_spot / burn embers / text emissive）を見る。"""
    used = {c.style for c in model.all_cubes()}
    for name in used:
        sd = book.get(name) or {}
        mat = sd.get("mat")
        if mat == "glow":
            return True
        if mat == "eye" and str(sd.get("kind", "")).startswith("glowing"):
            return True
        if sd.get("blood_kind") in ("acid", "ember") and (mat in ("blood", "blood_dry") or sd.get("blood", 0)):
            return True
        if mat == "skin" and sd.get("emissive_vein") and float(sd.get("cracks", 0) or 0) > 0:
            return True
        if mat == "fungus" and (sd.get("glow_spots") or sd.get("emissive")):
            return True
        if mat == "char" and (sd.get("embers") or sd.get("emissive")):
            return True
    for c in model.all_cubes():
        for v in (c.decals or {}).values():
            for d in (v if isinstance(v, list) else [v]):
                if not isinstance(d, dict):
                    continue
                if d.get("emissive") or d.get("name") == "glow_spot" or (d.get("name") == "burn" and d.get("embers")):
                    return True
                if d.get("name") == "face" and str(d.get("eyes", "")).startswith("glowing"):
                    return True
    return False


BESPOKE = {k[2:]: v for k, v in list(globals().items())
           if k.startswith("b_") and callable(v) and k[2:] in S.ZOMBIE_BY_KEY}

# 顔の肌の血の上限。体の skin の血の染み（3D のノイズ）がたまたま顔に掛かると、目・鼻・口が赤黒い面に
# 埋もれて読めない（QA: wrecker・crawler・ticker・bride の顔の上半分の 35〜70% が血）。口元・顎の血は
# 顔デカールの gore が受け持つので、頭（head / jaw）の肌のキューブだけ血を減らした写しのスタイルにする。
FACE_BLOOD = 0.06
_FACE_BONES = ("head", "jaw")


def _clean_face(model, book: dict) -> Dict[str, dict]:
    """head / jaw の肌（mat == skin、変異の派生も）のキューブを、血を FACE_BLOOD 以下にした「<style>_face」へ。"""
    added: Dict[str, dict] = {}
    for b in model.bones:
        if b.name not in _FACE_BONES:
            continue
        for c in b.cubes:
            sd = book.get(c.style) or {}
            if sd.get("mat") != "skin" or float(sd.get("blood", 0.0) or 0.0) <= FACE_BLOOD:
                continue
            name = c.style + "_face"
            if name not in book:
                book[name] = dict(sd, blood=round(min(FACE_BLOOD, float(sd["blood"]) * 0.25), 3))
                added[name] = book[name]
            c.style = name
    return added


# ---------------------------------------------------------------------------
#  組み立て
# ---------------------------------------------------------------------------
def _assemble(z: dict, detail: int, texel: float, scale: float):
    key = z["key"]
    boss = z["cls"] == "boss"
    m = R.new_model(key, max_atlas=(1024, 1024) if boss else (512, 512),
                    visible_bounds=(3.5, 3.5) if not boss else (6.0, 6.5),
                    vb_offset=(0, 1.25, 0) if not boss else (0, 2.5, 0))
    build = spec_build(z)
    build.update(face_build(z))
    build["texel"] = texel
    rig = R.ZombieRig(m, build, detail=detail, seed=C.stable_hash(key))
    book = zombie_book(z)
    added = KO.dress(rig, z, book)
    added.update(KM.mutate(rig, z, book, scale=scale))
    if key in BESPOKE:
        added.update(BESPOKE[key](rig, z, book, scale))
    if z.get("digitigrade"):
        added.update(_digitigrade(rig, z, book, scale))
    added.update(_clean_face(m, book))
    for attr, empty in (("nr_vis_terms", {}), ("nr_particles", []), ("nr_glow", {})):
        if not hasattr(m, attr):
            setattr(m, attr, copy.deepcopy(empty))
    return m, rig, book, added


def build_zombie(z: dict, detail: Optional[int] = None, texel: Optional[float] = None):
    """spec の 1 体 → (model, stylebook, info)。model はアトラスに詰め済み（model.tex_w / tex_h）。"""
    cls = z.get("cls", "common")
    cap = CAPS.get(cls, 450)
    boss = cls == "boss"
    warnings: List[str] = []
    tries = [(detail, 1.0)] if detail is not None else list(_TRIES)
    chosen = None
    for det, sc in tries:
        m, rig, book, added = _assemble(z, det, 1.0, sc)
        n = len(m.all_cubes())
        chosen = (det, sc)
        if n <= cap:
            break
        warnings.append(f"cubes {n} > {cap} (detail={det}, scale={sc})")
    det, sc = chosen
    size = (1024, 1024) if boss else (512, 512)
    texels = [texel] if texel is not None else list(_TEXELS_BOSS if boss else _TEXELS)
    fitted = None
    for tx in texels:
        m, rig, book, added = _assemble(z, det, tx, sc)
        try:
            m.pack(size=size)
            fitted = tx
            break
        except ValueError:
            continue
    if fitted is None:
        warnings.append(f"atlas {size} に収まらない（texel {texels[-1]} でも）")
        m.pack()
    n = len(m.all_cubes())
    if n > cap:
        warnings.append(f"cubes {n} > cap {cap}")
    info = dict(
        key=z["key"], cls=cls, cubes=n, cap=cap, bones=len(m.bones), atlas=[m.tex_w, m.tex_h], texel=fitted,
        detail=det, scale=sc, styles=len(book), warnings=warnings, mut_cubes=KM.mut_cubes(m),
        outfit_cubes=sum(1 for c in m.all_cubes() if getattr(c, "nr_kit", None) and not getattr(c, "nr_mut", None)),
        visibility=visibility_rules(m, z), glow=dict(m.nr_glow), particles=list(m.nr_particles),
        breakables=dict((z.get("gore") or {}).get("breakables") or {}), bespoke=z["key"] in BESPOKE,
        emissive=uses_emissive(m, book),
    )
    return m, book, info


# ---------------------------------------------------------------------------
#  自己テスト
# ---------------------------------------------------------------------------
def _selftest(render: bool = True, all_sheets: bool = False, only: Optional[Sequence[str]] = None) -> int:
    import json
    errs: List[str] = []
    rules_all = []
    rows = []
    tiles = []
    t0 = time.time()
    show = set(BESPOKE) | {"night_apex", "subject_zero", "flesh_colossus", "keener", "longarm", "gasbag"}
    zs = [z for z in S.ZOMBIES if not only or z["key"] in only]
    for z in zs:
        try:
            m, book, info = build_zombie(z)
            rules_all.append(info["visibility"])
            R.extract_gibs(m, z["key"])
            hitboxes(m)
            for b in m.bones:
                want = KM.mut_bone_parent(b.name) or KO.bone_parent(b.name)
                if want and b.parent != want:
                    errs.append(f"{z['key']}: ボーン {b.name} の親 {b.parent} != {want}")
            for need in S.part_bones(z):
                if need not in {b.name for b in m.bones}:
                    errs.append(f"{z['key']}: spec の部品ボーン {need} が無い")
            names = {b.name for b in m.bones}
            for core in R.BONE_NAMES:
                if core not in names:
                    errs.append(f"{z['key']}: §3 のボーン {core} が無い")
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            errs.append(f"{z['key']}: {type(e).__name__}: {e}")
            continue
        rows.append(info)
        if info["cubes"] > info["cap"]:
            errs.append(f"{z['key']}: キューブ {info['cubes']} > {info['cap']}")
        if render and (all_sheets or z["key"] in show):
            tex = P.paint_model(m, book, seed=5)
            tiles.append((f"{z['key']} [{info['cubes']}/{info['cap']}] {info['atlas'][0]}px t{info['texel']}",
                          KM._render3(m, tex, "body")))
    try:
        R.merge_visibility(*rules_all)
    except ValueError as e:
        errs.append(f"merge_visibility: {e}")
    if not only or "flesh_colossus" in only:
        outs = []
        for _ in range(2):
            m, book, info = build_zombie(S.ZOMBIE_BY_KEY["flesh_colossus"])
            outs.append(json.dumps([m.to_json(), sorted(book)], sort_keys=True, default=str))
        if outs[0] != outs[1]:
            errs.append("同じ入力で結果が変わる（決定的でない）")
    print(f"組み立て {len(rows)} 体 ({time.time() - t0:.1f}s)")
    for i in rows:
        w = f"  warn: {'; '.join(i['warnings'])}" if i["warnings"] else ""
        print(f"  {i['key']:18s} {i['cls']:8s} cubes={i['cubes']:4d}/{i['cap']:4d} mut={i['mut_cubes']:3d} "
              f"outfit={i['outfit_cubes']:3d} atlas={i['atlas'][0]} texel={i['texel']} det={i['detail']} "
              f"scale={i['scale']} styles={i['styles']} bones={i['bones']}{w}")
    if render and tiles:
        import nr_preview as NP
        os.makedirs(C.SCRATCH, exist_ok=True)
        per = 12
        for i in range(0, len(tiles), per):
            name = "kit_build.png" if not all_sheets else f"kit_build_{i // per + 1}.png"
            path = os.path.join(C.SCRATCH, name)
            NP.contact_sheet(tiles[i:i + per], cols=3, title="nr_kit.build_zombie").save(path)
            print("wrote", path)
            if not all_sheets:
                break
    for e in errs:
        print("ERROR", e)
    return 1 if errs else 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--all-sheets", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    sys.exit(_selftest(render=not a.no_render, all_sheets=a.all_sheets,
                       only=[k for k in a.only.split(",") if k] or None))
