#!/usr/bin/env bash
# 超次元バトルアーツをビルドして dist/ に .mcaddon / .mcpack を書き出す
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/hyperdim/build_hd.py
