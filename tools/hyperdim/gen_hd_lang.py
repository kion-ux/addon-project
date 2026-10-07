# -*- coding: utf-8 -*-
"""言語ファイル（ja_JP / en_US）。"""
from hd_common import NS, WEAPONS

JA = [
    "pack.name=超次元バトルアーツ",
    "pack.description=超次元武器 8 種・必殺技・アクション機動の PvP アドオン",
]
EN = [
    "pack.name=Hyper Dimension Arts",
    "pack.description=8 hyper-dimensional weapons, ultimates and action mobility for PvP",
]
for key, (ja, en, _el) in WEAPONS.items():
    JA.append(f"item.{NS}.{key}.name={ja}")
    EN.append(f"item.{NS}.{key}.name={en}")
JA += [
    f"item.{NS}.dimension_crystal.name=次元結晶",
    f"item.{NS}.guide.name=超次元指南書",
    f"entity.{NS}:training_dummy.name=訓練用カカシ",
    f"item.spawn_egg.entity.{NS}:training_dummy.name=訓練用カカシ",
    f"entity.{NS}:dmg_text.name=ダメージ表示",
]
EN += [
    f"item.{NS}.dimension_crystal.name=Dimension Crystal",
    f"item.{NS}.guide.name=Hyper Dimension Codex",
    f"entity.{NS}:training_dummy.name=Training Dummy",
    f"item.spawn_egg.entity.{NS}:training_dummy.name=Spawn Training Dummy",
    f"entity.{NS}:dmg_text.name=Damage Text",
]

LANGS = {"ja_JP": JA, "en_US": EN}
