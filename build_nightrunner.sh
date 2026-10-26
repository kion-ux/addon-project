#!/usr/bin/env bash
# NIGHT RUNNER: 感染都市をビルドして dist/ に .mcaddon / .mcpack を書き出す
# 引数はそのまま build_nr.py へ（例: ./build_nightrunner.sh -j --strict）
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/nightrunner/build_nr.py "$@"
