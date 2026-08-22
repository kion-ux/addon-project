# -*- coding: utf-8 -*-
"""Proportional humanoid rig.

Characters are described by real height and 等身 (head-to-body ratio) and the
skeleton is derived from human landmark proportions, so 187cm カフカ and 156cm
キコル come out with genuinely different silhouettes rather than a recoloured
Steve.

Bone topology mirrors the vanilla player (`head`, `body`, `rightArm`, `leftArm`,
`rightLeg`, `leftLeg` are all root-level joints) so the same geometry can be worn
as an attachable and driven by the player's own animations.  Everything finer -
`chest`, `rightForearm`, `rightHand`, `rightShin`, `rightFoot` … - hangs off those
joints and is driven by our own animation set on NPCs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from mcmodel import Bone, Cube, Model

# Steve reads as roughly 180cm at 32 model units tall.
PX_PER_CM = 32.0 / 180.0


@dataclass
class Build:
    height_cm: float
    heads: float = 6.4            # 等身
    shoulder: float = 0.245       # shoulder span / height
    limb: float = 1.0             # limb thickness multiplier
    female: bool = False
    bulk: float = 1.0             # torso depth multiplier
    leg_ratio: float = 0.515      # hip height / total height
    digitigrade: bool = False     # raised heel, beast stance
    hunch: float = 0.0            # forward lean of the whole torso, degrees
    arm_len: float = 1.0          # 怪獣は腕が長い
    # プレイヤーのアタッチャブルとして着るモデルは、関節の枢軸をバニラの
    # プレイヤー骨格 (頭24 / 肩22 / 腰12 / 腕±5 / 脚±1.9) に合わせないと
    # 各ボーンがプレイヤー側のボーン位置へ引き寄せられて崩壊する。
    player_anchor: bool = False

    @property
    def px(self) -> float:
        return self.height_cm * PX_PER_CM


@dataclass
class Landmarks:
    total: float
    head_h: float
    head_w: float
    head_d: float
    chin: float
    neck_h: float
    shoulder_y: float
    chest_top: float
    chest_bot: float
    abdomen_bot: float
    pelvis_bot: float
    hip_y: float
    knee_y: float
    ankle_y: float
    elbow_y: float
    wrist_y: float
    shoulder_w: float
    chest_w: float
    waist_w: float
    hip_w: float
    chest_d: float
    waist_d: float
    arm_t: float
    forearm_t: float
    hand_l: float
    thigh_t: float
    shin_t: float
    foot_l: float
    foot_h: float
    stance: float                 # half distance between the leg centres


# バニラのプレイヤー骨格の枢軸
PLAYER_PIVOTS = {
    "body": (0, 24, 0),
    "head": (0, 24, 0),
    "rightArm": (-5, 22, 0),
    "leftArm": (5, 22, 0),
    "rightLeg": (-1.9, 12, 0),
    "leftLeg": (1.9, 12, 0),
}


def player_landmarks(build: Build) -> Landmarks:
    """プレイヤー骨格に固定した寸法。

    関節の高さ (顎24 / 肩22 / 腰12 / 足0) は動かせないので、等身は頭の大きさで
    決まる: total = 24 + head_h、head_h = 24 / (等身 - 1)。
    バニラの8px頭は4等身に相当するので、頭を小さくするほど痩身に見える。
    足りない背丈は鶏冠・角・マントルで稼ぐ。"""
    limb = build.limb
    bulk = build.bulk
    arm_t = 4.0 * limb
    head_h = 24.0 / max(2.0, build.heads - 1.0)
    return Landmarks(
        total=24.0 + head_h,
        head_h=head_h, head_w=head_h * 1.06, head_d=head_h * 1.20,
        chin=24.0, neck_h=2.0,
        shoulder_y=22.0,
        chest_top=22.0, chest_bot=17.0, abdomen_bot=14.0, pelvis_bot=10.4,
        hip_y=12.0,
        knee_y=6.0, ankle_y=0.0,
        elbow_y=22.0 - 6.4 * build.arm_len,
        wrist_y=22.0 - 11.0 * build.arm_len,
        shoulder_w=10.0 + arm_t,
        chest_w=9.0 * bulk,
        waist_w=7.6 * bulk,
        hip_w=8.4 * bulk,
        chest_d=6.0 * bulk,
        waist_d=5.0 * bulk,
        arm_t=arm_t,
        forearm_t=3.6 * limb,
        hand_l=3.0,
        thigh_t=4.6 * limb,
        shin_t=4.0 * limb,
        foot_l=6.0,
        foot_h=2.0,
        stance=1.9,
    )


def landmarks(build: Build) -> Landmarks:
    if build.player_anchor:
        return player_landmarks(build)
    t = build.px
    h = t / build.heads
    neck_h = 0.036 * t
    chin = t - h
    shoulder_y = chin - neck_h
    hip_y = build.leg_ratio * t
    torso = shoulder_y - hip_y
    shoulder_w = build.shoulder * t
    arm_t = 0.053 * t * build.limb
    # `shoulder` is the full deltoid-to-deltoid span, so the ribcage has to be
    # narrower than it by (almost) two arm widths or the arms end up buried.
    chest_w = max(shoulder_w * 0.46, shoulder_w - 1.85 * arm_t)
    return Landmarks(
        total=t,
        head_h=h,
        head_w=h * 0.82,
        head_d=h * 0.88,
        chin=chin,
        neck_h=neck_h,
        shoulder_y=shoulder_y,
        chest_top=shoulder_y,
        chest_bot=hip_y + torso * 0.46,
        abdomen_bot=hip_y + torso * 0.16,
        pelvis_bot=hip_y - 0.055 * t,
        hip_y=hip_y,
        knee_y=(0.330 if build.digitigrade else 0.285) * t,
        ankle_y=(0.150 if build.digitigrade else 0.058) * t,
        elbow_y=shoulder_y - 0.190 * t * build.arm_len,
        wrist_y=shoulder_y - 0.345 * t * build.arm_len,
        shoulder_w=shoulder_w,
        chest_w=chest_w,
        waist_w=chest_w * (0.84 if not build.female else 0.78),
        hip_w=chest_w * (0.96 if not build.female else 1.08),
        chest_d=0.118 * t * build.bulk,
        waist_d=0.100 * t * build.bulk,
        arm_t=arm_t,
        forearm_t=0.046 * t * build.limb,
        hand_l=0.058 * t,
        thigh_t=0.079 * t * build.limb,
        shin_t=0.063 * t * build.limb,
        foot_l=(0.215 if build.digitigrade else 0.150) * t,
        foot_h=(0.085 if build.digitigrade else 0.058) * t,
        stance=shoulder_w * 0.21,
    )


class HumanRig:
    """Builds the shared skeleton; callers bolt clothing and gear onto it."""

    def __init__(self, model: Model, build: Build,
                 styles: Optional[Dict[str, str]] = None,
                 player_rig: bool = False):
        self.model = model
        self.build = build
        # player_rig keeps the vanilla topology (head/arms/legs at the root) so the
        # geometry can be worn as an attachable and driven by player animations
        self.player_rig = player_rig
        self.L = landmarks(build)
        self.s = {
            "skin": "skin", "suit": "suit", "armor": "armor", "accent": "accent",
            "hair": "hair", "steel": "steel", "cloth": "cloth",
            "underlay": "underlay",
        }
        self.s.update(styles or {})
        self.bones: Dict[str, Bone] = {}
        self._skeleton()

    # ------------------------------------------------------------------
    def b(self, name: str) -> Bone:
        return self.bones[name]

    def _bone(self, name, pivot, parent=None, rotation=None) -> Bone:
        bone = self.model.bone(name, pivot, parent, rotation)
        self.bones[name] = bone
        return bone

    def _pivot(self, name, fallback):
        if self.build.player_anchor and name in PLAYER_PIVOTS:
            return PLAYER_PIVOTS[name]
        return fallback

    def _skeleton(self) -> None:
        L = self.L
        self._bone("body", self._pivot("body", (0, L.hip_y, 0)),
                   rotation=(self.build.hunch, 0, 0) if self.build.hunch else None)
        self._bone("chest", (0, L.chest_bot, 0), "body")
        self._bone("neck", (0, L.shoulder_y, 0), "chest")
        self._bone("head", self._pivot("head", (0, L.chin, 0)),
                   None if self.player_rig else "neck")
        self._bone("hair", (0, L.chin, 0), "head")
        self._bone("face", (0, L.chin, 0), "head")
        for side, sgn in (("right", -1), ("left", 1)):
            sx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
            self._bone(f"{side}Arm",
                       self._pivot(f"{side}Arm", (sx, L.shoulder_y - L.arm_t * 0.35, 0)),
                       None if self.player_rig else "chest")
            self._bone(f"{side}Forearm", (sx, L.elbow_y, 0), f"{side}Arm")
            self._bone(f"{side}Hand", (sx, L.wrist_y, 0), f"{side}Forearm")
            self._bone(f"{side}Shoulder", (sx, L.shoulder_y, 0), f"{side}Arm")
            lx = sgn * L.stance
            self._bone(f"{side}Leg",
                       self._pivot(f"{side}Leg", (lx, L.hip_y, 0)),
                       None if self.player_rig else "body")
            self._bone(f"{side}Shin", (lx, L.knee_y, 0), f"{side}Leg")
            self._bone(f"{side}Foot", (lx, L.ankle_y, 0), f"{side}Shin")
            self._bone(f"{side}Toe", (lx, L.ankle_y, -L.foot_l * 0.55), f"{side}Foot")

    # ------------------------------------------------------------------
    def flesh(self, skin: Optional[str] = None, suit: Optional[str] = None,
              hands_bare: bool = True, face: Optional[dict] = None) -> None:
        """Body volumes: torso in three sections, segmented limbs, neck, head."""
        L = self.L
        skin = skin or self.s["skin"]
        suit = suit or self.s["suit"]

        # --- torso ------------------------------------------------------
        body = self.b("body")
        body.add(Cube((-L.hip_w / 2, L.pelvis_bot, -L.waist_d / 2),
                      (L.hip_w, L.abdomen_bot - L.pelvis_bot, L.waist_d), suit))
        body.add(Cube((-L.waist_w / 2, L.abdomen_bot, -L.waist_d / 2),
                      (L.waist_w, L.chest_bot - L.abdomen_bot, L.waist_d), suit))
        chest = self.b("chest")
        chest.add(Cube((-L.chest_w / 2, L.chest_bot, -L.chest_d / 2),
                       (L.chest_w, L.chest_top - L.chest_bot, L.chest_d), suit))
        # trapezius wedge so the shoulders do not read as a flat slab
        chest.add(Cube((-L.chest_w * 0.60, L.chest_top - L.arm_t * 0.85,
                        -L.chest_d * 0.42),
                       (L.chest_w * 1.20, L.arm_t * 0.85, L.chest_d * 0.84), suit))
        if self.build.female:
            # くびれてから腰へ広がるライン（胸は装甲側で出す）
            body.add(Cube((-L.hip_w * 0.54, L.pelvis_bot, -L.waist_d * 0.58),
                          (L.hip_w * 1.08, (L.abdomen_bot - L.pelvis_bot) * 0.76,
                           L.waist_d * 1.16), suit, uv_scale=4))
        neck = self.b("neck")
        neck.add(Cube((-L.head_w * (0.30 if not self.build.female else 0.26),
                       L.shoulder_y - L.neck_h * 0.3, -L.head_d * 0.24),
                      (L.head_w * (0.60 if not self.build.female else 0.52),
                       L.neck_h * 1.35, L.head_d * 0.48), skin))
        # dark under-suit at the shoulders and waist
        chest.add(Cube((-L.chest_w * 0.50, L.chest_bot - 0.01, -L.chest_d * 0.52),
                       (L.chest_w * 1.00, (L.chest_top - L.chest_bot) * 0.30,
                        L.chest_d * 1.04), self.s["underlay"], uv_scale=3))

        # --- head -------------------------------------------------------
        head = self.b("head")
        face_decal = dict(face or {})
        face_decal["name"] = "face"
        head.add(Cube((-L.head_w / 2, L.chin, -L.head_d * 0.52),
                      (L.head_w, L.head_h, L.head_d), skin, uv_scale=6,
                      decals={"north": face_decal}))
        # ears
        for sgn in (-1, 1):
            head.add(Cube((sgn * L.head_w * 0.5 - (L.head_w * 0.06 if sgn > 0 else 0),
                           L.chin + L.head_h * 0.30, -L.head_d * 0.06),
                          (L.head_w * 0.06, L.head_h * 0.26, L.head_d * 0.20), skin,
                          uv_scale=4))

        # --- arms -------------------------------------------------------
        for side, sgn in (("right", -1), ("left", 1)):
            cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
            arm = self.b(f"{side}Arm")
            arm.add(Cube((cx - L.arm_t / 2, L.elbow_y, -L.arm_t / 2),
                         (L.arm_t, L.shoulder_y - L.elbow_y, L.arm_t), suit))
            sh = self.b(f"{side}Shoulder")
            sh.add(Cube((cx - L.arm_t * 0.58, L.shoulder_y - L.arm_t * 1.05, -L.arm_t * 0.58),
                        (L.arm_t * 1.16, L.arm_t * 1.15, L.arm_t * 1.16), suit))
            fore = self.b(f"{side}Forearm")
            fore.add(Cube((cx - L.forearm_t / 2, L.wrist_y, -L.forearm_t / 2),
                          (L.forearm_t, L.elbow_y - L.wrist_y, L.forearm_t),
                          self.s["underlay"] if suit == self.s["suit"] else suit))
            hand = self.b(f"{side}Hand")
            hand.add(Cube((cx - L.forearm_t * 0.52, L.wrist_y - L.hand_l, -L.forearm_t * 0.42),
                          (L.forearm_t * 1.04, L.hand_l, L.forearm_t * 0.84),
                          skin if hands_bare else suit, uv_scale=3))
            # thumb
            hand.add(Cube((cx + sgn * L.forearm_t * 0.42, L.wrist_y - L.hand_l * 0.72,
                           -L.forearm_t * 0.30),
                          (L.forearm_t * 0.30, L.hand_l * 0.5, L.forearm_t * 0.34),
                          skin if hands_bare else suit, uv_scale=3))

        # --- legs -------------------------------------------------------
        for side, sgn in (("right", -1), ("left", 1)):
            cx = sgn * L.stance
            leg = self.b(f"{side}Leg")
            leg.add(Cube((cx - L.thigh_t / 2, L.knee_y, -L.thigh_t / 2),
                         (L.thigh_t, L.hip_y - L.knee_y, L.thigh_t), suit))
            shin = self.b(f"{side}Shin")
            shin.add(Cube((cx - L.shin_t / 2, L.ankle_y, -L.shin_t / 2),
                          (L.shin_t, L.knee_y - L.ankle_y, L.shin_t),
                          self.s["underlay"] if suit == self.s["suit"] else suit))
            # calf swell
            shin.add(Cube((cx - L.shin_t * 0.52, L.ankle_y + (L.knee_y - L.ankle_y) * 0.42,
                           -L.shin_t * 0.10),
                          (L.shin_t * 1.04, (L.knee_y - L.ankle_y) * 0.42, L.shin_t * 0.55), suit))
            foot = self.b(f"{side}Foot")
            foot.add(Cube((cx - L.shin_t * 0.60, 0, -L.foot_l * 0.62),
                          (L.shin_t * 1.20, L.foot_h, L.foot_l * 0.95), suit))
            toe = self.b(f"{side}Toe")
            toe.add(Cube((cx - L.shin_t * 0.56, 0, -L.foot_l * 0.95),
                         (L.shin_t * 1.12, L.foot_h * 0.72, L.foot_l * 0.36), suit))

    # ------------------------------------------------------------------
    def combat_suit(self, armor: Optional[str] = None, accent: Optional[str] = None,
                    green: str = "green", spine: int = 7, holster: bool = True,
                    emblem: str = "emblem") -> None:
        """戦闘服 G-X4552.

        Black under-suit, silver hard plates, olive-green rig panels, and a
        seven-segment spine strip.  Deliberately **no helmet, no visor and no
        backpack** — the series treats the exposed head as the suit's weak point.
        """
        L = self.L
        armor = armor or self.s["armor"]
        accent = accent or self.s["accent"]
        chest = self.b("chest")
        body = self.b("body")
        ch = L.chest_top - L.chest_bot

        # --- 女性キャラは胸のラインを装甲の上に出す
        if self.build.female:
            chest.add(Cube((-L.chest_w * 0.44, L.chest_bot + ch * 0.34,
                            -L.chest_d * 0.74),
                           (L.chest_w * 0.88, ch * 0.30, L.chest_d * 0.18), green,
                           uv_scale=4))
            chest.add(Cube((-L.chest_w * 0.30, L.chest_bot + ch * 0.40,
                            -L.chest_d * 0.82),
                           (L.chest_w * 0.60, ch * 0.20, L.chest_d * 0.10), green,
                           uv_scale=5))
        # --- 胸のリグ (olive) — wraps the front only
        chest.add(Cube((-L.chest_w * 0.50, L.chest_bot + ch * 0.08, -L.chest_d * 0.62),
                       (L.chest_w * 1.00, ch * 0.74, L.chest_d * 0.42), green,
                       uv_scale=4, decals={"north": emblem, "east": "panel_line",
                                           "west": "panel_line"}))
        chest.add(Cube((-L.chest_w * 0.30, L.chest_bot + ch * 0.30, -L.chest_d * 0.66),
                       (L.chest_w * 0.60, ch * 0.16, L.chest_d * 0.10), "decal",
                       uv_scale=5, decals={"north": "logo"}))
        # 胸中央のセンサー
        chest.add(Cube((-L.chest_w * 0.06, L.chest_bot + ch * 0.52, -L.chest_d * 0.68),
                       (L.chest_w * 0.12, ch * 0.10, L.chest_d * 0.06), accent,
                       uv_scale=6, decals={"north": "core"}))

        # --- 背骨アーマー: 7 vertebrae, floating off the back
        spine_bone = self.model.bone("spine", (0, L.chest_bot, L.chest_d * 0.5), "chest")
        self.bones["spine"] = spine_bone
        for i in range(spine):
            t = i / max(1, spine - 1)
            w = L.chest_w * (0.42 - 0.16 * t)
            y = L.chest_top - ch * 0.05 - (ch * 0.92 + (L.chest_bot - L.abdomen_bot)) * t
            spine_bone.add(Cube((-w / 2, y, L.chest_d * 0.46),
                                (w, ch * 0.13, L.chest_d * 0.16), armor, uv_scale=4))

        # --- ベルト / 腰アーマー
        body.add(Cube((-L.hip_w * 0.58, L.abdomen_bot - L.total * 0.016,
                       -L.waist_d * 0.62),
                      (L.hip_w * 1.16, L.total * 0.038, L.waist_d * 1.24), armor,
                      uv_scale=3, decals={"north": "buckle"}))
        for i, sgn in enumerate((-1, 1)):                 # 緑のボックスポーチ×4
            for j, dz in enumerate((-0.5, 0.42)):
                body.add(Cube((sgn * L.hip_w * 0.34 - L.hip_w * 0.13,
                               L.abdomen_bot - L.total * 0.052,
                               dz * L.waist_d * 1.25),
                              (L.hip_w * 0.26, L.total * 0.036, L.waist_d * 0.22),
                              green, uv_scale=4))
        body.add(Cube((-L.hip_w * 0.54, L.pelvis_bot + L.total * 0.004,
                       -L.waist_d * 0.58),
                      (L.hip_w * 1.08, (L.abdomen_bot - L.pelvis_bot) * 0.80,
                       L.waist_d * 1.16), armor, uv_scale=3))

        for side, sgn in (("right", -1), ("left", 1)):
            cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
            # --- パウルドロン: dome plate with the two service decals
            sh = self.b(f"{side}Shoulder")
            sh.add(Cube((cx - L.arm_t * 0.80, L.shoulder_y - L.arm_t * 1.10,
                         -L.arm_t * 0.80),
                        (L.arm_t * 1.60, L.arm_t * 1.26, L.arm_t * 1.60), armor,
                        uv_scale=5,
                        decals={"east" if sgn < 0 else "west": "emblem",
                                "up": "logo", "north": "rivets"}))
            sh.add(Cube((cx - L.arm_t * 0.66, L.shoulder_y - L.arm_t * 1.52,
                         -L.arm_t * 0.66),
                        (L.arm_t * 1.32, L.arm_t * 0.44, L.arm_t * 1.32), armor,
                        uv_scale=4))
            # --- ガントレット (silver half-cylinder over the forearm)
            fore = self.b(f"{side}Forearm")
            fore.add(Cube((cx - L.forearm_t * 0.70,
                           L.wrist_y + (L.elbow_y - L.wrist_y) * 0.06,
                           -L.forearm_t * 0.70),
                          (L.forearm_t * 1.40, (L.elbow_y - L.wrist_y) * 0.74,
                           L.forearm_t * 1.40), armor, uv_scale=4,
                          decals={"north": "panel_line", "east": "rivets"}))
            # --- 黒い手袋
            hand = self.b(f"{side}Hand")
            hand.add(Cube((cx - L.forearm_t * 0.58, L.wrist_y - L.hand_l * 1.04,
                           -L.forearm_t * 0.48),
                          (L.forearm_t * 1.16, L.hand_l * 1.06, L.forearm_t * 0.96),
                          self.s["cloth"], uv_scale=3))
            # --- 膝: olive dome cap / 脛とつま先: silver
            leg = self.b(f"{side}Leg")
            lx = sgn * L.stance
            shin = self.b(f"{side}Shin")
            shin.add(Cube((lx - L.shin_t * 0.74, L.knee_y - (L.knee_y - L.ankle_y) * 0.20,
                           -L.shin_t * 0.86),
                          (L.shin_t * 1.48, (L.knee_y - L.ankle_y) * 0.28,
                           L.shin_t * 1.30), green, uv_scale=4))
            shin.add(Cube((lx - L.shin_t * 0.66, L.ankle_y + (L.knee_y - L.ankle_y) * 0.06,
                           -L.shin_t * 0.74),
                          (L.shin_t * 1.32, (L.knee_y - L.ankle_y) * 0.46,
                           L.shin_t * 1.20), armor, uv_scale=4,
                          decals={"north": "panel_line", "east": "rivets"}))
            foot = self.b(f"{side}Foot")
            foot.add(Cube((lx - L.shin_t * 0.66, 0, -L.foot_l * 0.66),
                          (L.shin_t * 1.32, L.foot_h * 1.12, L.foot_l * 0.62), armor,
                          uv_scale=3))
            if holster:
                if sgn < 0:                     # 右腿のホルスター
                    leg.add(Cube((lx - L.thigh_t * 0.92,
                                  L.knee_y + (L.hip_y - L.knee_y) * 0.30,
                                  -L.thigh_t * 0.20),
                                 (L.thigh_t * 0.40, (L.hip_y - L.knee_y) * 0.44,
                                  L.thigh_t * 0.56), green, uv_scale=4))
                else:                            # 左脚のレッグバッグ
                    leg.add(Cube((lx + L.thigh_t * 0.50,
                                  L.knee_y + (L.hip_y - L.knee_y) * 0.24,
                                  -L.thigh_t * 0.30),
                                 (L.thigh_t * 0.46, (L.hip_y - L.knee_y) * 0.50,
                                  L.thigh_t * 0.72), green, uv_scale=4))
                    leg.add(Cube((lx - L.thigh_t * 0.56,
                                  L.knee_y + (L.hip_y - L.knee_y) * 0.58,
                                  -L.thigh_t * 0.56),
                                 (L.thigh_t * 1.12, (L.hip_y - L.knee_y) * 0.10,
                                  L.thigh_t * 1.12), armor, uv_scale=4))

    def visor_bar(self, style: str = "visor") -> None:
        """亜白ミナ専用の白いバイザー — 目元だけを覆う横長バー。"""
        L = self.L
        head = self.b("head")
        head.add(Cube((-L.head_w * 0.54, L.chin + L.head_h * 0.60, -L.head_d * 0.60),
                      (L.head_w * 1.08, L.head_h * 0.13, L.head_d * 0.10), style,
                      uv_scale=8, decals={"north": "hud_bar"}))

    def face_mask(self, style: Optional[str] = None) -> None:
        """保科・鳴海の面体マスク（鼻〜顎の浅いシェル）。"""
        L = self.L
        style = style or self.s["cloth"]
        head = self.b("head")
        head.add(Cube((-L.head_w * 0.44, L.chin + L.head_h * 0.04, -L.head_d * 0.58),
                      (L.head_w * 0.88, L.head_h * 0.34, L.head_d * 0.30), style,
                      uv_scale=5))

    def helmet(self, armor: Optional[str] = None) -> None:
        L = self.L
        armor = armor or self.s["armor"]
        head = self.b("head")
        head.add(Cube((-L.head_w * 0.56, L.chin + L.head_h * 0.30, -L.head_d * 0.58),
                      (L.head_w * 1.12, L.head_h * 0.78, L.head_d * 1.12), armor,
                      uv_scale=4))
        head.add(Cube((-L.head_w * 0.54, L.chin + L.head_h * 0.34, -L.head_d * 0.66),
                      (L.head_w * 1.08, L.head_h * 0.30, L.head_d * 0.16), "visor",
                      uv_scale=4, decals={"north": "visor"}))

    # ------------------------------------------------------------------
    def hair(self, spec, style: Optional[str] = None) -> None:
        """髪をレイヤーで組む。

        キャップ（頭を覆う土台）／前髪（列ごとに長さを変えてギザつかせる）／
        サイドの毛束／後ろ髪／逆立った毛先、という順で重ねる。アニメの髪が
        ボクセルで「髪に見える」かどうかは、前髪の段差と顔を挟むサイドの毛束で
        ほぼ決まるので、そこを列単位で指定できるようにしてある。

        座標は頭ローカル（xは頭幅、yは顎からの頭高、zは頭奥行き）。
        """
        if isinstance(spec, (list, tuple)):       # 旧形式（キューブの直書き）
            return self._hair_cubes(spec, style)
        L = self.L
        style = style or self.s["hair"]
        bone = self.b("hair")
        HW, HH, HD = L.head_w, L.head_h, L.head_d

        def cube(x, y, z, w, h, d, st=None, uv=4, **kw):
            bone.add(Cube((x * HW, L.chin + y * HH, z * HD),
                          (w * HW, h * HH, d * HD), st or style, uv_scale=uv, **kw))

        # --- キャップ: 頭より僅かに大きく被せる
        cap = spec.get("cap", {})
        cy = cap.get("y", 0.58)
        ch = cap.get("h", 0.50)
        out = cap.get("out", 0.04)
        cube(-0.5 - out, cy, -0.52 - out, 1.0 + out * 2, ch, 1.04 + out * 2)
        if cap.get("crown"):                      # 頭頂の膨らみ
            cube(-0.40, cy + ch - 0.02, -0.40, 0.80, 0.14, 0.84)

        # --- 後頭部
        back = spec.get("back")
        if back:
            cube(-0.48, back.get("y", 0.16), 0.42,
                 0.96, back.get("h", 0.46), back.get("t", 0.16))
        # --- 背中まで届く長い髪
        long = spec.get("long")
        if long:
            cube(-long.get("w", 0.92) / 2, long.get("y", -1.2), 0.40,
                 long.get("w", 0.92), long.get("h", 1.8), long.get("t", 0.16), uv=3)
            cube(-long.get("w", 0.92) / 2 * 0.7, long.get("y", -1.2) - 0.28, 0.44,
                 long.get("w", 0.92) * 0.7, 0.34, long.get("t", 0.16) * 0.8, uv=3)

        # --- 前髪: 列ごとに落ちる長さを変えて段差を作る
        bangs = spec.get("bangs")
        if bangs:
            # low[i] は「その列の前髪がどこまで垂れるか」を顎からの頭高で指定する。
            # 目は 0.50、眉は 0.60 付近にあるので、覆いたくなければ 0.56 以上に置く。
            top = bangs.get("y", cy + 0.02)
            if "low" in bangs:
                drops = [max(0.02, top - v) for v in bangs["low"]]
            else:
                drops = bangs.get("drops", [0.14] * 6)
            n = len(drops)
            t = bangs.get("t", 0.14)
            for i, drop in enumerate(drops):
                u0 = -0.5 + i / n
                cube(u0, top - drop, -0.52 - t, 1.0 / n + 0.005, drop, t)
            l2 = bangs.get("layer2")
            if l2:
                for i, drop in enumerate(drops):
                    d2 = drop * l2
                    u0 = -0.46 + i / n * 0.92
                    cube(u0, top - d2 - 0.02, -0.52 - t * 1.9,
                         0.92 / n + 0.005, d2, t * 0.9, uv=5)
            if bangs.get("parting") is not None:  # 分け目の一房を持ち上げる
                pu = bangs["parting"]
                cube(pu - 0.09, top - 0.06, -0.56 - t, 0.18, 0.20, t * 1.4, uv=5)

        # --- サイドの毛束（顔を挟む）
        sides = spec.get("sides")
        if sides:
            t = sides.get("t", 0.14)
            h = sides.get("h", 0.46)
            y = sides.get("y", 0.16)
            z0 = sides.get("z0", -0.54)
            d = sides.get("d", 0.60)
            for sgn in (-1, 1):
                x = sgn * 0.5 - (t if sgn > 0 else 0)
                cube(x, y, z0, t, h, d)
                if sides.get("tip"):
                    cube(x + (0.02 if sgn > 0 else 0), y - sides["tip"], z0 + 0.08,
                         t * 0.8, sides["tip"], d * 0.7, uv=5)

        # --- 刈り上げ / もみあげ
        if spec.get("shaved"):
            for sgn in (-1, 1):
                cube(sgn * 0.5 - (0.07 if sgn > 0 else 0), 0.30, -0.40,
                     0.07, 0.30, 0.80, uv=5)

        # --- 逆立った毛先
        for sp in spec.get("spikes", []):
            u, y, ln, tilt = sp
            cube(u - 0.07, y, -0.20, 0.14, ln, 0.20, uv=5, rotation=(tilt, 0, 0))

        # --- 後頭部のお団子
        bun = spec.get("bun")
        if bun:
            r = bun.get("r", 0.28)
            cube(bun.get("u", 0.0) - r / 2, bun.get("y", 0.52), 0.46 + 0.02,
                 r, r * (HW / HH), r, uv=5)

        # --- リーゼント（前髪だけ立ち上げる）
        pomp = spec.get("pompadour")
        if pomp:
            cube(-0.36, cy + 0.02, -0.56, 0.72, pomp.get("h", 0.34), 0.26, uv=4,
                 rotation=(-16, 0, 0))
            cube(-0.30, cy + pomp.get("h", 0.34) - 0.04, -0.50, 0.60, 0.18, 0.30,
                 uv=4, rotation=(-28, 0, 0))

        # --- 髭（もみあげと繋がる）
        beard = spec.get("beard")
        if beard:
            cube(-0.42, 0.02, -0.56, 0.84, beard.get("h", 0.22), 0.14, uv=6)
            for sgn in (-1, 1):
                cube(sgn * 0.46 - (0.10 if sgn > 0 else 0), 0.06, -0.50,
                     0.10, beard.get("h", 0.22) + 0.18, 0.56, uv=6)

    def _hair_cubes(self, spec, style=None) -> None:
        L = self.L
        style = style or self.s["hair"]
        bone = self.b("hair")
        for origin, size in spec:
            bone.add(Cube(
                (origin[0] * L.head_w, L.chin + origin[1] * L.head_h,
                 origin[2] * L.head_d),
                (size[0] * L.head_w, size[1] * L.head_h, size[2] * L.head_d),
                style, uv_scale=3))

    def ponytail(self, name: str, anchor: Sequence[float], segments: int,
                 length: float, thickness: float, style: Optional[str] = None,
                 tilt: float = 8.0) -> None:
        """A jointed hair tail so it can swing in the idle animation."""
        L = self.L
        style = style or self.s["hair"]
        parent = "hair"
        y = L.chin + anchor[1] * L.head_h
        z = anchor[2] * L.head_d
        seg_len = length * L.head_h / segments
        for i in range(segments):
            bone_name = f"{name}{i}"
            bone = self.model.bone(bone_name, (anchor[0] * L.head_w, y, z), parent,
                                   rotation=(tilt if i else tilt * 0.5, 0, 0))
            self.bones[bone_name] = bone
            t = thickness * (1.0 - 0.5 * i / max(1, segments - 1))
            bone.add(Cube((anchor[0] * L.head_w - t * L.head_w / 2, y - seg_len,
                           z - t * L.head_d / 2),
                          (t * L.head_w, seg_len, t * L.head_d), style, uv_scale=3))
            parent = bone_name
            y -= seg_len

    def mount(self, name: str, side: str = "right", rotation=(0, 0, 0),
              drop: float = 0.5) -> Tuple[Bone, Tuple[float, float, float], float]:
        """A bone in the hand for a weapon, plus the offset+scale to build it at."""
        L = self.L
        sgn = -1 if side == "right" else 1
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        y = L.wrist_y - L.hand_l * drop
        bone = self.model.bone(name, (cx, y, 0), f"{side}Hand", rotation=list(rotation))
        self.bones[name] = bone
        return bone, (cx, y, 0.0), L.total / 32.0

    def cape(self, style: str, length: float = 0.55, width: float = 1.0) -> None:
        L = self.L
        bone = self.model.bone("cape", (0, L.chest_top, L.chest_d * 0.5), "chest",
                               rotation=(4, 0, 0))
        self.bones["cape"] = bone
        bone.add(Cube((-L.shoulder_w * 0.5 * width, L.chest_top - L.total * length,
                       L.chest_d * 0.5),
                      (L.shoulder_w * width, L.total * length, L.total * 0.012),
                      style, uv_scale=2))


# ---------------------------------------------------------------------------
#  hair silhouettes, expressed in head-local units
#  each entry is (origin_xyz, size_xyz) with x,z in head widths/depths and
#  y measured up from the chin in head heights
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
#  髪型。アニメの各キャラのシルエットに合わせたレイヤー指定。
#  座標は頭ローカル: x=頭幅 / y=顎からの頭高 / z=頭奥行き
# ---------------------------------------------------------------------------
HAIR: Dict[str, dict] = {
    # 日比野カフカ: 分け目なしの不揃いなツンツン短髪
    "kafka": {
        "cap": {"y": 0.78, "h": 0.34, "out": 0.05, "crown": True},
        "back": {"y": 0.24, "h": 0.56, "t": 0.16},
        "bangs": {"y": 0.80, "low": [0.66, 0.74, 0.63, 0.72, 0.65, 0.73],
                  "t": 0.15, "layer2": 0.55},
        "sides": {"y": 0.34, "h": 0.34, "t": 0.13, "d": 0.44},
        "spikes": [(-0.26, 1.10, 0.20, -24), (0.04, 1.14, 0.18, -14),
                   (0.30, 1.08, 0.16, -30), (-0.06, 1.12, 0.14, -34)],
    },
    # 市川レノ: 眉上で切り揃えた厚い前髪、低ボリューム
    "reno": {
        "cap": {"y": 0.80, "h": 0.32, "out": 0.035},
        "back": {"y": 0.32, "h": 0.50, "t": 0.14},
        "bangs": {"y": 0.82, "low": [0.68, 0.67, 0.675, 0.675, 0.67, 0.68],
                  "t": 0.16, "layer2": 0.45},
        "sides": {"y": 0.30, "h": 0.40, "t": 0.12, "d": 0.50, "tip": 0.10},
    },
    # 亜白ミナ: 腰まで届くストレートのポニーテール、顔を挟む長いサイド
    "mina": {
        "cap": {"y": 0.80, "h": 0.32, "out": 0.04},
        "back": {"y": 0.22, "h": 0.60, "t": 0.16},
        "bangs": {"y": 0.82, "low": [0.64, 0.70, 0.78, 0.78, 0.70, 0.64],
                  "t": 0.14, "layer2": 0.50, "parting": 0.0},
        "sides": {"y": 0.02, "h": 0.66, "t": 0.13, "d": 0.62, "tip": 0.12},
    },
    # 保科宗四郎: 顎ラインで切り揃えた丸いマッシュ
    "hoshina": {
        "cap": {"y": 0.76, "h": 0.36, "out": 0.06, "crown": True},
        "back": {"y": 0.04, "h": 0.74, "t": 0.18},
        "bangs": {"y": 0.78, "low": [0.63, 0.61, 0.62, 0.62, 0.61, 0.63],
                  "t": 0.16, "layer2": 0.55},
        "sides": {"y": 0.00, "h": 0.68, "t": 0.15, "d": 0.66},
    },
    # 四ノ宮キコル: 低めに結んだ長いツインテール
    "kikoru": {
        "cap": {"y": 0.80, "h": 0.32, "out": 0.045},
        "back": {"y": 0.24, "h": 0.58, "t": 0.16},
        "bangs": {"y": 0.82, "low": [0.66, 0.72, 0.79, 0.79, 0.72, 0.66],
                  "t": 0.14, "layer2": 0.50, "parting": 0.0},
        "sides": {"y": 0.06, "h": 0.62, "t": 0.13, "d": 0.58, "tip": 0.12},
    },
    # 鳴海弦: 目を覆うもっさりマッシュ（前髪だけ色が違う）
    "narumi": {
        "cap": {"y": 0.76, "h": 0.36, "out": 0.055, "crown": True},
        "back": {"y": 0.10, "h": 0.68, "t": 0.17},
        "sides": {"y": 0.02, "h": 0.66, "t": 0.14, "d": 0.62},
    },
    # 四ノ宮功: 前髪なしのオールバック＋もみあげと繋がる髭
    "isao": {
        "cap": {"y": 0.82, "h": 0.30, "out": 0.04},
        "back": {"y": 0.26, "h": 0.58, "t": 0.16},
        "beard": {"h": 0.24},
    },
    # 古橋伊春: 前髪だけ立ち上げたリーゼント＋サイド刈り上げ
    "furuhashi": {
        "cap": {"y": 0.82, "h": 0.28, "out": 0.03},
        "back": {"y": 0.38, "h": 0.46, "t": 0.12},
        "pompadour": {"h": 0.36},
        "shaved": True,
    },
    # 出雲ハルイチ: 額を出したオールバック＋後頭部のハーフアップお団子
    "izumo": {
        "cap": {"y": 0.82, "h": 0.30, "out": 0.04},
        "back": {"y": 0.16, "h": 0.68, "t": 0.16},
        "bun": {"u": 0.0, "y": 0.52, "r": 0.30},
    },
    # 神楽木葵: 刈り込んだ短いツンツンの軍人カット
    "kaguragi": {
        "cap": {"y": 0.84, "h": 0.26, "out": 0.025},
        "back": {"y": 0.44, "h": 0.40, "t": 0.10},
        "spikes": [(-0.22, 1.08, 0.12, -18), (0.06, 1.09, 0.10, -12),
                   (0.26, 1.08, 0.11, -22)],
    },
    # 一般隊員
    "crew": {
        "cap": {"y": 0.80, "h": 0.32, "out": 0.035},
        "back": {"y": 0.34, "h": 0.48, "t": 0.14},
        "bangs": {"y": 0.82, "low": [0.71, 0.73, 0.69, 0.72, 0.69, 0.72],
                  "t": 0.13, "layer2": 0.50},
        "sides": {"y": 0.36, "h": 0.32, "t": 0.11, "d": 0.42},
    },
}

# 鳴海の前髪だけ地毛と色が違うので、別スタイルで重ねる
HAIR_FRONT = {
    "narumi": {
        "bangs": {"y": 0.78, "low": [0.52, 0.48, 0.50, 0.50, 0.48, 0.52],
                  "t": 0.17, "layer2": 0.55},
    },
}


# ===========================================================================
#  Kaiju parts bolted onto the human topology.  怪獣8号 keeps the vanilla bone
#  names so the same geometry can be worn as a player attachable.
# ===========================================================================
class KaijuParts:
    def __init__(self, rig: HumanRig):
        self.r = rig
        self.m = rig.model
        self.L = rig.L

    def _bone(self, name, pivot, parent=None, rotation=None) -> Bone:
        b = self.m.bone(name, pivot, parent, rotation)
        self.r.bones[name] = b
        return b

    # ------------------------------------------------------------------
    def mask(self, style="mask", horn_style="horn", jaw_style="sinew",
             horns=2, crest=True, glow_decal="mask_no8", damage=False,
             throat_teeth=False, skull=True) -> None:
        """骨のフェイスプレート、鶏冠、可動顎、角。

        `damage=True` は左目の左下の骨を数片欠けさせ、内部組織とシアン光を
        覗かせる — 怪獣8号の非対称ダメージ。"""
        L = self.L
        head = self.r.b("head")
        head.add(Cube((-L.head_w * 0.54, L.chin + L.head_h * 0.06, -L.head_d * 0.62),
                      (L.head_w * 1.08, L.head_h * 0.84, L.head_d * 0.28), style,
                      uv_scale=6, decals={"north": glow_decal}))
        head.add(Cube((-L.head_w * 0.52, L.chin + L.head_h * 0.26, -L.head_d * 0.36),
                      (L.head_w * 1.04, L.head_h * 0.68, L.head_d * 0.94), style,
                      uv_scale=4))
        if skull:
            # 前傾した細長い頭蓋
            head.add(Cube((-L.head_w * 0.40, L.chin + L.head_h * 0.16,
                           -L.head_d * 0.86),
                          (L.head_w * 0.80, L.head_h * 0.44, L.head_d * 0.30),
                          style, uv_scale=5, rotation=(10, 0, 0)))
        if crest:
            head.add(Cube((-L.head_w * 0.46, L.chin + L.head_h * 0.90,
                           -L.head_d * 0.34),
                          (L.head_w * 0.92, L.head_h * 0.24, L.head_d * 0.92),
                          horn_style, uv_scale=4))
        if damage:
            head.add(Cube((L.head_w * 0.12, L.chin + L.head_h * 0.28,
                           -L.head_d * 0.66),
                          (L.head_w * 0.32, L.head_h * 0.28, L.head_d * 0.10),
                          jaw_style, uv_scale=6, decals={"north": "veins"}))
            head.add(Cube((L.head_w * 0.08, L.chin + L.head_h * 0.22,
                           -L.head_d * 0.64),
                          (L.head_w * 0.18, L.head_h * 0.16, L.head_d * 0.08),
                          "crack", uv_scale=6))
        jaw = self._bone("jaw", (0, L.chin + L.head_h * 0.24, -L.head_d * 0.24), "head")
        jaw.add(Cube((-L.head_w * 0.40, L.chin - L.head_h * 0.04, -L.head_d * 0.58),
                     (L.head_w * 0.80, L.head_h * 0.26, L.head_d * 0.78), jaw_style,
                     uv_scale=5, decals={"north": "fangs", "up": "maw"}))
        if throat_teeth:
            jaw.add(Cube((-L.head_w * 0.30, L.chin - L.head_h * 0.32,
                          -L.head_d * 0.42),
                         (L.head_w * 0.60, L.head_h * 0.30, L.head_d * 0.58),
                         jaw_style, uv_scale=5, decals={"north": "fangs"}))
            self.r.b("neck").add(Cube(
                (-L.head_w * 0.26, L.shoulder_y - L.neck_h * 0.1, -L.head_d * 0.36),
                (L.head_w * 0.52, L.neck_h * 1.0, L.head_d * 0.14), style,
                uv_scale=6, decals={"north": "fangs"}))
        for i in range(horns):
            for sgn in (-1, 1):
                side = "r" if sgn < 0 else "l"
                spread = 0.28 + i * 0.16
                base_y = L.chin + L.head_h * (0.82 - i * 0.28)
                name = f"horn_{side}{i}"
                b = self._bone(name, (sgn * L.head_w * spread, base_y, 0), "head",
                               rotation=(-30 - i * 10, 0, (22 + i * 14) * sgn))
                t = L.head_w * (0.20 - i * 0.04)
                b.add(Cube((sgn * L.head_w * spread - t / 2, base_y, -L.head_d * 0.06),
                           (t, L.head_h * (0.60 - i * 0.14), t), horn_style,
                           uv_scale=4))
                tip = self._bone(f"{name}_tip",
                                 (sgn * L.head_w * spread,
                                  base_y + L.head_h * (0.60 - i * 0.14), 0),
                                 name, rotation=(-18, 0, 0))
                tip.add(Cube((sgn * L.head_w * spread - t * 0.36,
                              base_y + L.head_h * (0.58 - i * 0.14), -L.head_d * 0.05),
                             (t * 0.72, L.head_h * (0.34 - i * 0.08), t * 0.72),
                             horn_style, uv_scale=4))

    def cross_face(self, plate="mask", eye="eye") -> None:
        """怪獣10号: 目鼻のない装甲面に十字の切れ込み、その奥に青い単眼。"""
        L = self.L
        head = self.r.b("head")
        head.add(Cube((-L.head_w * 0.56, L.chin + L.head_h * 0.04, -L.head_d * 0.64),
                      (L.head_w * 1.12, L.head_h * 0.92, L.head_d * 0.26), plate,
                      uv_scale=6, decals={"north": "cross_slit"}))
        head.add(Cube((-L.head_w * 0.16, L.chin + L.head_h * 0.34, -L.head_d * 0.56),
                      (L.head_w * 0.32, L.head_h * 0.30, L.head_d * 0.10), eye,
                      uv_scale=6, decals={"north": "single_eye"}))
        horn = self._bone("horn_c", (0, L.chin + L.head_h * 0.86, -L.head_d * 0.4),
                          "head", rotation=(-64, 0, 0))
        horn.add(Cube((-L.head_w * 0.10, L.chin + L.head_h * 0.84, -L.head_d * 0.62),
                      (L.head_w * 0.20, L.head_h * 0.90, L.head_d * 0.22),
                      "horn", uv_scale=5))

    def mantle(self, plate="plate", top="bone", spines: int = 5) -> None:
        """後頭部〜肩上を覆う大型プレート。遠景のシルエットの主役。"""
        L = self.L
        chest = self.r.b("chest")
        ch = L.chest_top - L.chest_bot
        chest.add(Cube((-L.chest_w * 0.62, L.chest_top - ch * 0.40, L.chest_d * 0.26),
                       (L.chest_w * 1.24, ch * 0.46, L.chest_d * 0.42), plate,
                       uv_scale=3))
        # the bone-white top segment rises *behind* the skull, framing it
        chest.add(Cube((-L.chest_w * 0.32, L.chest_top - ch * 0.06, L.chest_d * 0.48),
                       (L.chest_w * 0.64, L.head_h * 0.70, L.chest_d * 0.24), top,
                       uv_scale=4, rotation=(-16, 0, 0)))
        for i in range(spines):
            u = (i - (spines - 1) / 2) / max(1, spines - 1)
            chest.add(Cube((u * L.chest_w * 0.46 - L.total * 0.014,
                            L.chest_top - ch * 0.10, L.chest_d * 0.50),
                           (L.total * 0.028, L.total * 0.060 * (1 - abs(u) * 0.40),
                            L.total * 0.030), top, uv_scale=4,
                           rotation=(-42, 0, u * 26)))

    def plates(self, style="plate", crack_style="crack", seams=True,
               limb_style=None) -> None:
        """外骨格プレート。発光ラインはプレートの隙間に、面より低い位置で走らせる。"""
        L = self.L
        chest = self.r.b("chest")
        body = self.r.b("body")
        ch = L.chest_top - L.chest_bot
        chest.add(Cube((-L.chest_w * 0.54, L.chest_bot + ch * 0.14, -L.chest_d * 0.66),
                       (L.chest_w * 1.08, ch * 0.72, L.chest_d * 0.30), style,
                       uv_scale=4, decals={"north": "scale_row"}))
        chest.add(Cube((-L.chest_w * 0.56, L.chest_top - ch * 0.26, -L.chest_d * 0.60),
                       (L.chest_w * 1.12, ch * 0.28, L.chest_d * 1.18), style,
                       uv_scale=3))
        if seams:
            body.add(Cube((-L.waist_w * 0.50, L.abdomen_bot, -L.waist_d * 0.64),
                          (L.waist_w * 1.00, (L.chest_bot - L.abdomen_bot) * 0.94,
                           L.waist_d * 0.16), crack_style, uv_scale=4,
                          decals={"north": "veins"}))
        body.add(Cube((-L.hip_w * 0.56, L.pelvis_bot + (L.abdomen_bot - L.pelvis_bot) * 0.08,
                       -L.waist_d * 0.60),
                      (L.hip_w * 1.12, (L.abdomen_bot - L.pelvis_bot) * 0.82,
                       L.waist_d * 1.20), style, uv_scale=3))
        limb = limb_style or style
        for side, sgn in (("right", -1), ("left", 1)):
            cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
            sh = self.r.b(f"{side}Shoulder")
            sh.add(Cube((cx - L.arm_t * 0.68, L.shoulder_y - L.arm_t * 1.05,
                         -L.arm_t * 0.68),
                        (L.arm_t * 1.36, L.arm_t * 1.15, L.arm_t * 1.36), limb,
                        uv_scale=4))
            for i in range(3):
                sh.add(Cube((cx - L.arm_t * (0.44 - i * 0.05),
                             L.shoulder_y + L.arm_t * (0.02 + i * 0.16),
                             -L.arm_t * (0.34 - i * 0.16)),
                            (L.arm_t * (0.88 - i * 0.10), L.arm_t * 0.26,
                             L.arm_t * 0.22), "horn", uv_scale=5,
                            rotation=(-24 - i * 10, 0, 0)))
            fore = self.r.b(f"{side}Forearm")
            fore.add(Cube((cx - L.forearm_t * 0.68, L.wrist_y,
                           -L.forearm_t * 0.68),
                          (L.forearm_t * 1.36, (L.elbow_y - L.wrist_y) * 0.76,
                           L.forearm_t * 1.36), limb, uv_scale=4))
            if seams:
                fore.add(Cube((cx - L.forearm_t * 0.30,
                               L.wrist_y + (L.elbow_y - L.wrist_y) * 0.12,
                               -L.forearm_t * 0.86),
                              (L.forearm_t * 0.60, (L.elbow_y - L.wrist_y) * 0.5,
                               L.forearm_t * 0.10), crack_style, uv_scale=5))
            shin = self.r.b(f"{side}Shin")
            lx = sgn * L.stance
            shin.add(Cube((lx - L.shin_t * 0.70, L.knee_y - (L.knee_y - L.ankle_y) * 0.26,
                           -L.shin_t * 0.74),
                          (L.shin_t * 1.40, (L.knee_y - L.ankle_y) * 0.38,
                           L.shin_t * 1.40), limb, uv_scale=4))
            if seams:
                shin.add(Cube((lx - L.shin_t * 0.30, L.ankle_y + (L.knee_y - L.ankle_y) * 0.06,
                               -L.shin_t * 0.88),
                              (L.shin_t * 0.60, (L.knee_y - L.ankle_y) * 0.24,
                               L.shin_t * 0.10), crack_style, uv_scale=5))

    def claws(self, style="claw", fingers: int = 3, feet: bool = True) -> None:
        L = self.L
        for side, sgn in (("right", -1), ("left", 1)):
            cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
            hand = self.r.b(f"{side}Hand")
            span = L.forearm_t * 1.00
            for i in range(fingers):
                u = (i - (fingers - 1) / 2) / max(1, fingers - 1) if fingers > 1 else 0
                fx = cx + u * span * 0.5
                t = L.forearm_t * 0.26
                name = f"{side}Finger{i}"
                b = self._bone(name, (fx, L.wrist_y - L.hand_l, 0), f"{side}Hand",
                               rotation=(12, 0, 0))
                b.add(Cube((fx - t / 2, L.wrist_y - L.hand_l - L.hand_l * 0.75,
                            -L.forearm_t * 0.30),
                           (t, L.hand_l * 0.75, t * 1.10), style, uv_scale=4))
                tip = self._bone(f"{name}_tip",
                                 (fx, L.wrist_y - L.hand_l - L.hand_l * 0.75, 0),
                                 name, rotation=(26, 0, 0))
                tip.add(Cube((fx - t * 0.38, L.wrist_y - L.hand_l - L.hand_l * 1.35,
                              -L.forearm_t * 0.28),
                             (t * 0.76, L.hand_l * 0.60, t * 0.90), style, uv_scale=4))
            if feet:
                foot = self.r.b(f"{side}Foot")
                lx = sgn * L.stance
                for i in range(3):
                    t = L.shin_t * 0.30
                    foot.add(Cube((lx - L.shin_t * 0.55 + i * t * 1.25, 0,
                                   -L.foot_l * 0.95),
                                  (t, L.foot_h * 0.75, L.foot_l * 0.30), style,
                                  uv_scale=4))

    def tail(self, segments: int = 5, length: float = 1.1, thickness: float = 0.32,
             style: str = "hide", tip_style: str = "horn", droop: float = -8.0,
             parent: str = "body", spikes: bool = False) -> None:
        L = self.L
        seg_len = L.total * length / segments
        y = L.hip_y + L.total * 0.02
        z = L.waist_d * 0.5
        prev = parent
        for i in range(segments):
            name = f"tail{i}"
            b = self._bone(name, (0, y, z), prev, rotation=(droop, 0, 0))
            t = L.total * thickness * 0.35 * (1 - 0.62 * i / max(1, segments - 1))
            b.add(Cube((-t / 2, y - t * 0.5, z), (t, t, seg_len), style, uv_scale=3))
            if spikes:
                b.add(Cube((-t * 0.16, y + t * 0.42, z + seg_len * 0.3),
                           (t * 0.32, t * 0.60, t * 0.30), tip_style, uv_scale=4,
                           rotation=(-32, 0, 0)))
            if i >= segments - 2:
                b.add(Cube((-t * 0.22, y + t * 0.3, z + seg_len * 0.2),
                           (t * 0.44, t * 0.55, seg_len * 0.55), tip_style,
                           uv_scale=4, rotation=(-18, 0, 0)))
            prev = name
            z += seg_len
            y -= seg_len * 0.10

    def spine(self, count: int = 6, style: str = "horn", scale: float = 1.0) -> None:
        L = self.L
        chest = self.r.b("chest")
        for i in range(count):
            t = i / max(1, count - 1)
            h = L.total * 0.055 * scale * (1.0 - 0.45 * abs(t - 0.35) * 2)
            y = L.chest_bot + (L.chest_top - L.chest_bot) * (0.15 + 0.75 * t)
            chest.add(Cube((-L.total * 0.014 * scale, y, L.chest_d * 0.42),
                           (L.total * 0.028 * scale, h, L.total * 0.024 * scale),
                           style, uv_scale=4, rotation=(-24, 0, 0)))

    def spurs(self, style: str = "horn", count: int = 2) -> None:
        """怪獣9号γ: 肘・肩・指・膝・足に生えるクリムゾンの突起。"""
        L = self.L
        for side, sgn in (("right", -1), ("left", 1)):
            cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
            lx = sgn * L.stance
            for i in range(count):
                self.r.b(f"{side}Forearm").add(Cube(
                    (cx - L.forearm_t * 0.28,
                     L.elbow_y - (L.elbow_y - L.wrist_y) * (0.05 + i * 0.16),
                     L.forearm_t * 0.35),
                    (L.forearm_t * 0.56, L.forearm_t * 0.5, L.forearm_t * 0.9),
                    style, uv_scale=4, rotation=(34 + i * 12, 0, 0)))
                self.r.b(f"{side}Shoulder").add(Cube(
                    (cx - L.arm_t * (0.30 - i * 0.05),
                     L.shoulder_y + L.arm_t * (0.10 + i * 0.30), -L.arm_t * 0.20),
                    (L.arm_t * 0.60, L.arm_t * 0.7, L.arm_t * 0.34), style,
                    uv_scale=4, rotation=(-20 - i * 14, 0, 20 * sgn)))
                self.r.b(f"{side}Shin").add(Cube(
                    (lx - L.shin_t * 0.28,
                     L.knee_y - (L.knee_y - L.ankle_y) * (0.05 + i * 0.2),
                     -L.shin_t * 0.95),
                    (L.shin_t * 0.56, L.shin_t * 0.5, L.shin_t * 0.7), style,
                    uv_scale=4, rotation=(-28 - i * 10, 0, 0)))


# ---------------------------------------------------------------------------
#  余獣: stocky armoured quadruped
# ---------------------------------------------------------------------------
class BeastRig:
    def __init__(self, model: Model, length_px: float, height_px: float,
                 legs: int = 4, styles: Optional[Dict[str, str]] = None):
        self.m = model
        self.len = length_px
        self.h = height_px
        self.legs = legs
        self.s = {"shell": "shell", "flesh": "flesh", "claw": "claw",
                  "plate": "plate", "horn": "horn"}
        self.s.update(styles or {})
        self.bones: Dict[str, Bone] = {}

    def _bone(self, name, pivot, parent=None, rotation=None) -> Bone:
        b = self.m.bone(name, pivot, parent, rotation)
        self.bones[name] = b
        return b

    def build(self, segments: int = 3, tail_segments: int = 3, back_plates: int = 4,
              horns: int = 2, eye_rows: int = 3, head_scale: float = 1.0) -> None:
        L, H = self.len, self.h
        body_w = H * 0.46
        body_h = H * 0.36
        top = H * 0.88
        body = self._bone("body", (0, top - body_h / 2, 0))
        seg_len = L * 0.60 / segments
        z = -L * 0.14
        for i in range(segments):
            taper = 1.0 - 0.14 * abs(i - (segments - 1) / 2)
            w, hh = body_w * taper, body_h * taper
            body.add(Cube((-w / 2, top - hh, z), (w, hh, seg_len), self.s["shell"],
                          uv_scale=3))
            body.add(Cube((-w * 0.44, top - hh - H * 0.02, z + seg_len * 0.08),
                          (w * 0.88, H * 0.07, seg_len * 0.84), self.s["flesh"],
                          uv_scale=3))
            z += seg_len
        for i in range(back_plates):
            t = i / max(1, back_plates - 1)
            w = body_w * (0.86 - 0.18 * t)
            body.add(Cube((-w / 2, top - H * 0.02, -L * 0.13 + t * L * 0.52),
                          (w, H * 0.10, L * 0.13), self.s["plate"], uv_scale=3,
                          rotation=(-14, 0, 0)))

        neck = self._bone("neck", (0, top - body_h * 0.34, -L * 0.14), "body",
                          rotation=(8, 0, 0))
        neck.add(Cube((-body_w * 0.34, top - body_h * 0.66, -L * 0.26),
                      (body_w * 0.68, body_h * 0.58, L * 0.14), self.s["flesh"],
                      uv_scale=3))
        head = self._bone("head", (0, top - body_h * 0.30, -L * 0.26), "neck")
        hw = body_w * 0.72 * head_scale
        hh = body_h * 0.66 * head_scale
        head.add(Cube((-hw / 2, top - body_h * 0.26 - hh, -L * 0.44),
                      (hw, hh, L * 0.19), self.s["shell"], uv_scale=4,
                      decals={"north": "eye_rows"}))
        head.add(Cube((-hw * 0.42, top - body_h * 0.30 - hh * 0.70, -L * 0.54),
                      (hw * 0.84, hh * 0.46, L * 0.12), self.s["flesh"], uv_scale=5,
                      decals={"north": "fangs"}))
        for i in range(horns):
            for sgn in (-1, 1):
                head.add(Cube((sgn * hw * (0.16 + i * 0.16) - hw * 0.06,
                               top - body_h * 0.24 - hh * 0.06, -L * 0.36),
                              (hw * 0.12, hh * 0.34, L * 0.05), self.s["horn"],
                              uv_scale=4, rotation=(-30, 0, 24 * sgn)))
        for sgn in (-1, 1):
            m = self._bone(f"mandible_{'r' if sgn < 0 else 'l'}",
                           (sgn * hw * 0.34, top - body_h * 0.52, -L * 0.46), "head",
                           rotation=(0, 14 * sgn, 0))
            m.add(Cube((sgn * hw * 0.40 - hw * 0.06, top - body_h * 0.26 - hh * 0.80,
                        -L * 0.60), (hw * 0.12, hh * 0.16, L * 0.16),
                       self.s["claw"], uv_scale=4))
        jaw = self._bone("jaw", (0, top - body_h * 0.26 - hh * 0.84, -L * 0.42), "head")
        jaw.add(Cube((-hw * 0.38, top - body_h * 0.26 - hh * 1.02, -L * 0.54),
                     (hw * 0.76, hh * 0.20, L * 0.14), self.s["flesh"],
                     uv_scale=4, decals={"up": "maw"}))

        rows = max(1, self.legs // 2)
        for r in range(rows):
            zc = -L * 0.08 + (r / max(1, rows - 1) if rows > 1 else 0.5) * L * 0.46
            for sgn in (-1, 1):
                side = "r" if sgn < 0 else "l"
                name = f"leg_{side}{r}"
                b = self._bone(name, (sgn * body_w * 0.46, top - body_h * 0.52, zc),
                               "body", rotation=(0, 0, -14 * sgn))
                t = H * 0.13
                b.add(Cube((sgn * body_w * 0.46 - t / 2, top - body_h * 0.52 - H * 0.27,
                            zc - t / 2), (t, H * 0.29, t), self.s["shell"], uv_scale=4))
                knee = self._bone(f"{name}_lower",
                                  (sgn * body_w * 0.46, top - body_h * 0.52 - H * 0.27, zc),
                                  name, rotation=(0, 0, 24 * sgn))
                t2 = t * 0.8
                knee.add(Cube((sgn * body_w * 0.46 - t2 / 2, H * 0.06, zc - t2 / 2),
                              (t2, top - body_h * 0.52 - H * 0.33, t2),
                              self.s["shell"], uv_scale=4))
                foot = self._bone(f"{name}_foot",
                                  (sgn * body_w * 0.46, H * 0.06, zc), f"{name}_lower")
                foot.add(Cube((sgn * body_w * 0.46 - t2 * 0.62, 0, zc - H * 0.12),
                              (t2 * 1.24, H * 0.07, H * 0.24), self.s["claw"],
                              uv_scale=4))

        prev = "body"
        z = L * 0.44
        y = top - body_h * 0.42
        seg = L * 0.30 / max(1, tail_segments)
        for i in range(tail_segments):
            name = f"tail{i}"
            b = self._bone(name, (0, y, z), prev, rotation=(-8, 0, 0))
            t = H * 0.28 * (1 - 0.55 * i / max(1, tail_segments - 1))
            b.add(Cube((-t / 2, y - t / 2, z), (t, t, seg), self.s["shell"], uv_scale=3))
            if i == tail_segments - 1:
                b.add(Cube((-t * 0.3, y - t * 0.3, z + seg * 0.7),
                           (t * 0.6, t * 0.6, seg * 0.9), self.s["claw"], uv_scale=4))
            prev = name
            z += seg
