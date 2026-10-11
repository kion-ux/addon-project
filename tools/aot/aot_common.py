# -*- coding: utf-8 -*-
"""進撃の巨人アドオン — 生成スクリプト共通の定数と補助。

座標はすべて統合版のモデル空間（16 単位 = 1 ブロック、モデルの正面は -Z）。
共有モジュール（mcmodel / mctexture / rig、超次元の hd_space / hd_holds）を
そのまま使うので、ここで sys.path を通す。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
HD = os.path.join(TOOLS, "hyperdim")
for p in (TOOLS, HD, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

NS = "aot"
BP = os.path.join(ROOT, "packs", "aot_BP")
RP = os.path.join(ROOT, "packs", "aot_RP")
SCRATCH = os.environ.get("AOT_SCRATCH", os.path.join(ROOT, "build_preview", "aot"))

GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "aot")
ATT_DIR = os.path.join(RP, "attachables")
ICON_DIR = os.path.join(RP, "textures", "items", "aot")

VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 30]


def write_json(path: str, doc) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def write_json_compact(path: str, doc) -> None:
    """大きいアニメーションは改行だけ入れて詰める（差分が読める程度に）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------------------
#  巨人の級。ジオメトリは全高 BASE_M で作り、クライアントの scripts.scale で拡大する。
#  当たり判定は BP 側で級ごとに直接書く（minecraft:scale は使わない）。
# ---------------------------------------------------------------------------
BASE_M = 3.0

TITANS = {
    # key: (全高 m, 体力, 攻撃, 速さ, 衝突 (幅, 高さ), 被弾 (幅, 高さ), 掴むか, 経験値)
    "titan_small":    (4.0, 50, 6, 0.25, (1.0, 3.2), (1.4, 4.0), False, 20),
    "titan_medium":   (7.0, 110, 10, 0.26, (1.6, 3.8), (2.2, 7.0), True, 45),
    "titan_large":    (13.0, 220, 16, 0.24, (2.4, 4.8), (3.4, 13.0), True, 90),
    "titan_abnormal": (10.0, 160, 12, 0.34, (2.0, 4.2), (2.8, 10.0), True, 80),
}

# 体型 4 種 × 顔と肌 3 種。テクスチャはジオメトリごとの UV に合わせて描くので 12 枚
BODIES = ["lanky", "chubby", "muscular", "bighead"]
SKINS = 3

# 調査兵団。key -> 表示名は lang、ここは体格と見た目
SOLDIERS = [
    "eren_yeager", "mikasa_ackerman", "armin_arlert", "levi_ackerman", "hange_zoe",
    "erwin_smith", "jean_kirstein", "sasha_blouse", "connie_springer", "survey_soldier",
]
