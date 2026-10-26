# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 手書き JS を公式の型定義（d.ts）で型検査する（tsc --checkJs --noEmit）。

* 型定義は tools/nightrunner/typings/ に固定して同梱（@minecraft/server 2.3.0、
  @minecraft/server-ui 2.0.0、@minecraft/common 1.2.0。npm の公式 tarball を無改変）。
* TypeScript 5.6.3 を tools/nightrunner/.node/ に入れる（無ければ npm で入れる。gitignore 済み）。
* 設定は tools/nightrunner/tsconfig.nr.json（lib は ES2022 だけ。DOM・Node のグローバルは無い）。

使い方:
    python3 tools/nightrunner/check_nr_types.py              # packs/nightrunner_BP/scripts/**/*.js
    python3 tools/nightrunner/check_nr_types.py PATH [...]   # 別のフォルダ／ファイルを検査（試験用）
    python3 tools/nightrunner/check_nr_types.py --raw        # tsc の出力をそのまま全部出す

終了コード: 0 = 誤りなし（またはスクリプトがまだ無い）、1 = 型の誤りあり、2 = 道具が動かない。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nr_common import HERE, ROOT, SCRIPTS  # noqa: E402

TS_VERSION = "5.6.3"
NODE_DIR = os.path.join(HERE, ".node")
TSC_JS = os.path.join(NODE_DIR, "node_modules", "typescript", "lib", "tsc.js")
TSCONFIG = os.path.join(HERE, "tsconfig.nr.json")
OVERRIDE = os.path.join(NODE_DIR, "tsconfig.override.json")

# path(line,col): error TS1234: message
LINE_RE = re.compile(r"^(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\): (?P<sev>error|warning) "
                     r"(?P<code>TS\d+): (?P<msg>.*)$")
GLOBAL_RE = re.compile(r"^(?P<sev>error|warning) (?P<code>TS\d+): (?P<msg>.*)$")

# よく出る誤りと、直し方の手がかり（要約の最後に出す）
HINTS = {
    "TS2304": "名前が無い。setTimeout/setInterval/require などはゲームに無い → system.runTimeout 等へ",
    "TS2305": "その名前は import できない（2.3.0 安定版に無い＝ベータ専用か綴り違い）",
    "TS2339": "そのプロパティ／メソッドは型に無い（ベータ専用・古い 1.x の名前・綴り違い）",
    "TS2349": "呼べない値を呼んでいる（例: isValid はプロパティ。isValid() ではない）",
    "TS2353": "オプションの辞書に無いキー（オプション名の綴り・2.x で変わった名前）",
    "TS2345": "引数の型が違う（例: applyKnockback は ({x, z}, vertical)）",
    "TS2554": "引数の数が違う（例: applyKnockback(dirX, dirZ, h, v) は 1.x の形。2.x は 2 引数）",
    "TS2551": "似た名前はある（綴り違い）",
    "TS2322": "代入する型が違う",
    "TS2307": "モジュールが見つからない（相対 import の綴り・拡張子 .js を確認）",
    "TS2306": "ファイルがモジュールでない（export が無い）",
    "TS2614": "その名前は export されていない（default と名前付きの取り違えも）",
    "TS2724": "その名前は import できない（ベータ専用か綴り違い。候補が出ていれば綴り違い）",
    "TS2559": "オプションの辞書を渡すところに値を渡している（server-ui 2.0 は toggle(label, {defaultValue}) の形）",
    "TS2571": "unknown の値を使っている（CustomComponentParameters.params は JSDoc の @type で型を付ける）",
    "TS18046": "unknown の値を使っている（CustomComponentParameters.params は JSDoc の @type で型を付ける）",
}


def _rel(path: str) -> str:
    """表示用に ROOT からの相対パスへ（外なら絶対パスのまま）。"""
    try:
        ap = os.path.abspath(os.path.join(HERE, path)) if not os.path.isabs(path) else path
        rp = os.path.relpath(ap, ROOT)
        return ap if rp.startswith("..") else rp.replace(os.sep, "/")
    except ValueError:
        return path


def _installed_version():
    pj = os.path.join(NODE_DIR, "node_modules", "typescript", "package.json")
    try:
        with open(pj, encoding="utf-8") as fh:
            return json.load(fh).get("version")
    except (OSError, ValueError):
        return None


def ensure_tsc(node: str) -> bool:
    """TypeScript TS_VERSION を .node/ に用意する。用意できたら True。"""
    if _installed_version() == TS_VERSION and os.path.isfile(TSC_JS):
        return True
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        print("  [types] npm が見つからない（Node.js を入れること）", file=sys.stderr)
        return False
    os.makedirs(NODE_DIR, exist_ok=True)
    pkg = os.path.join(NODE_DIR, "package.json")
    if not os.path.isfile(pkg):
        with open(pkg, "w", encoding="utf-8") as fh:
            json.dump({"name": "nr-typecheck", "private": True,
                       "description": "NIGHT RUNNER の型検査用（check_nr_types.py が作る）"}, fh, indent=2)
            fh.write("\n")
    print(f"  [types] typescript@{TS_VERSION} を {_rel(NODE_DIR)} に入れる…")
    res = subprocess.run([npm, "install", f"typescript@{TS_VERSION}", "--save-exact",
                          "--no-audit", "--no-fund", "--loglevel=error"],
                         cwd=NODE_DIR, capture_output=True, text=True)
    if res.returncode or _installed_version() != TS_VERSION:
        print((res.stdout + res.stderr).strip()[-3000:], file=sys.stderr)
        print("  [types] typescript を入れられなかった", file=sys.stderr)
        return False
    return True


def _js_files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += glob.glob(os.path.join(p, "**", "*.js"), recursive=True)
        elif os.path.isfile(p) and p.endswith((".js", ".mjs", ".ts")):
            out.append(p)
    return sorted(set(out))


def write_override(paths) -> str:
    """検査対象を差し替えた tsconfig を .node/ に書く（tsconfig.nr.json を extends）。"""
    include = []
    for p in paths:
        ap = os.path.abspath(p).replace(os.sep, "/")
        include.append(ap + "/**/*.js" if os.path.isdir(p) else ap)
    doc = {"extends": TSCONFIG.replace(os.sep, "/"), "include": include}
    os.makedirs(NODE_DIR, exist_ok=True)
    with open(OVERRIDE, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    return OVERRIDE


def parse(output: str):
    """tsc --pretty false の出力を [{file, line, col, code, msg, detail}] に。"""
    items = []
    for raw in output.splitlines():
        if not raw.strip():
            continue
        m = LINE_RE.match(raw)
        g = None if m else GLOBAL_RE.match(raw)
        if m:
            items.append(dict(file=_rel(m["file"]), line=int(m["line"]), col=int(m["col"]),
                              sev=m["sev"], code=m["code"], msg=m["msg"], detail=[]))
        elif g:
            items.append(dict(file="(tsconfig)", line=0, col=0, sev=g["sev"], code=g["code"],
                              msg=g["msg"], detail=[]))
        elif items and raw[:1].isspace():
            items[-1]["detail"].append(raw.strip())
        else:
            items.append(dict(file="(tsc)", line=0, col=0, sev="error", code="TS????",
                              msg=raw.strip(), detail=[]))
    return items


def summarize(items, nfiles: int, limit: int) -> None:
    errs = [i for i in items if i["sev"] == "error"]
    if not errs:
        print(f"  [types] OK: {nfiles} ファイル、型の誤りなし（@minecraft/server 2.3.0 / server-ui 2.0.0）")
        return
    by_file = Counter(i["file"] for i in errs)
    by_code = Counter(i["code"] for i in errs)
    print(f"  [types] 型の誤り {len(errs)} 件（{len(by_file)} / {nfiles} ファイル）")
    for i in errs[:limit]:
        msg = i["msg"] if len(i["msg"]) <= 220 else i["msg"][:217] + "..."
        print(f"    {i['file']}:{i['line']}:{i['col']} {i['code']} {msg}")
        for d in i["detail"][:2]:
            print(f"        {d[:200]}")
    if len(errs) > limit:
        print(f"    …ほか {len(errs) - limit} 件（--max で増やす、--raw で全部）")
    print("  [types] ファイル別: " + ", ".join(f"{f} {n}" for f, n in by_file.most_common(12)))
    print("  [types] 種類別: " + ", ".join(f"{c} {n}" for c, n in by_code.most_common()))
    for c, _n in by_code.most_common():
        if c in HINTS:
            print(f"    {c}: {HINTS[c]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NIGHT RUNNER の手書き JS を公式 d.ts で型検査する")
    ap.add_argument("paths", nargs="*", help="検査するフォルダ／ファイル（省略時は BP の scripts/）")
    ap.add_argument("--max", type=int, default=60, help="一覧に出す誤りの数（既定 60）")
    ap.add_argument("--raw", action="store_true", help="tsc の出力をそのまま出す")
    args = ap.parse_args(argv)

    if os.environ.get("NR_SKIP_TYPES") == "1":
        print("  [types] NR_SKIP_TYPES=1 なので型検査は飛ばす（Node / npm が使えない時だけ）")
        return 0
    if args.paths:
        targets = [os.path.abspath(p) for p in args.paths]
        missing = [p for p in targets if not os.path.exists(p)]
        if missing:
            print("  [types] 見つからない: " + ", ".join(missing), file=sys.stderr)
            return 2
    else:
        targets = [SCRIPTS]
        if not os.path.isdir(SCRIPTS):
            print(f"  [types] {_rel(SCRIPTS)} がまだ無いので型検査は飛ばす（OK）")
            return 0
    files = _js_files(targets)
    if not files:
        print(f"  [types] 検査する .js が無い（{', '.join(_rel(t) for t in targets)}）ので飛ばす（OK）")
        return 0

    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        print("  [types] node が見つからない（Node.js 18 以上を入れること）", file=sys.stderr)
        return 2
    if not ensure_tsc(node):
        return 2

    config = write_override(targets) if args.paths else TSCONFIG
    res = subprocess.run([node, TSC_JS, "-p", config, "--pretty", "false"],
                         cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    out = (res.stdout or "") + (res.stderr or "")
    if args.raw and out.strip():
        print(out.rstrip())
    items = parse(out)
    summarize(items, len(files), args.max)
    if res.returncode and not any(i["sev"] == "error" for i in items):
        # 解析できない失敗（tsc 自体の異常）
        print(out.strip()[-3000:], file=sys.stderr)
        print(f"  [types] tsc が異常終了（{res.returncode}）", file=sys.stderr)
        return 2
    return 1 if any(i["sev"] == "error" for i in items) or res.returncode else 0


if __name__ == "__main__":
    sys.exit(main())
