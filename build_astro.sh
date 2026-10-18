#!/usr/bin/env bash
# アストロ・ナノギアをビルドして dist/ に .mcaddon / .mcpack を書き出す
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/astro/build_astro.py "$@"
