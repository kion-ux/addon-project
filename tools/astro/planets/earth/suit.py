# -*- coding: utf-8 -*-
"""地球 — 蒼星機装 ガイア（作り直し中: frame7 の確認）。"""
from __future__ import annotations

from astro_suit import Suit

SUIT_STYLES = {}
SUIT_ANIMS = {"idle": {}, "thrust": {}, "sprint": {}}


def build_suit(s: Suit):
    s.frame7()
