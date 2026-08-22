# -*- coding: utf-8 -*-
"""sys.path を整える。すべての marvel モジュールが最初にこれを import する。

``tools/`` には kaiju8 用の ``palettes.py`` / ``build.py`` / ``validate.py`` が
あるので、探索順を間違えると別アドオンのモジュールを掴んでしまう。
ここで **marvel ディレクトリを必ず先頭** に置き、共有エンジン
(``mcmodel`` / ``mctexture`` / ``rig``) はその後ろから拾わせる。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)

for _p in (TOOLS, HERE):          # 後に insert した HERE が index 0 になる
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)
