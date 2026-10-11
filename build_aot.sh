#!/usr/bin/env bash
# 進撃の巨人アドオンをビルドして dist/ に .mcaddon / .mcpack を書き出す
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/aot/build_aot.py
