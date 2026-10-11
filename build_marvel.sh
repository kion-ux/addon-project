#!/usr/bin/env bash
# マーベル・ミュータント アドオンをビルドして dist/ に書き出す
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/marvel/build.py
