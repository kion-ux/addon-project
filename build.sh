#!/usr/bin/env bash
# このリポジトリの2つのアドオン（怪獣8号 / GRAND LINE AWAKENING）を
# ビルドして dist/ に .mcaddon / .mcpack を書き出す
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/build.py
