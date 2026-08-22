#!/usr/bin/env bash
# 怪獣8号アドオンをビルドして dist/ に .mcaddon / .mcpack を書き出す
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/build.py
