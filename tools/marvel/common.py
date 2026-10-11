# -*- coding: utf-8 -*-
"""生成モジュールが共有する小道具。"""
from __future__ import annotations

import json
import os

import _path  # noqa: F401  (sys.path を整える。必ず最初に import する)

import contract as K  # noqa: E402
import colours  # noqa: E402
from mcmodel import Model  # noqa: E402
from paint import MarvelPainter  # noqa: E402


def write_json(path: str, doc) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def emit(model: Model, palette: dict, key: str, seed: int = 7,
         tex_key: str | None = None) -> Model:
    """ジオメトリを書き出し、同じ UV 割り当てにテクスチャを描き込む。"""
    K.ensure_dirs()
    model.write(K.geo_path(key))
    p = MarvelPainter(model.tex_w, model.tex_h, seed)
    p.paint_model(model, palette)
    p.save(K.tex_path(tex_key or key))
    print(f"  {key:24s} {model.stats()}")
    return model


def palette_for(key: str) -> dict:
    return colours.ALL[K.CHARACTERS[key]["pal"]]


def seed_for(key: str) -> int:
    return abs(hash(key)) % 9973 + 3


def animations_doc(clips: dict) -> dict:
    return {"format_version": "1.10.0", "animations": clips}


def controllers_doc(ctrls: dict) -> dict:
    return {"format_version": "1.10.0", "animation_controllers": ctrls}
