# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 全生成 → 挙動テスト → 型検査 → 参照検証 → dist/ に書き出し。

    ./build_nightrunner.sh                     # 普通のビルド（まだ無い生成器は WARNING を出して飛ばす）
    python3 tools/nightrunner/build_nr.py -j    # 独立した生成器を並列に（CPU 数まで。-j 4 で 4 並列）
    python3 tools/nightrunner/build_nr.py --strict      # 最終・CI 用: 生成器や main.js が欠けていたら失敗
    python3 tools/nightrunner/build_nr.py --only weapons,packs   # 一部の生成器だけ（検証・dist はしない）
    python3 tools/nightrunner/build_nr.py --only weapons --verify  # 一部だけ生成して検証まで
    python3 tools/nightrunner/build_nr.py --no-dist     # 検証まで（dist/ を書かない）
    python3 tools/nightrunner/build_nr.py --no-verify   # 生成と dist だけ（急ぎの見た目確認用。strict とは併用不可）
    python3 tools/nightrunner/build_nr.py -k            # 生成器が失敗しても残りを走らせる（最後に失敗で終わる）

流れ:
1. `tools/nightrunner/.frag/` を空にする（`--only` のときは、その生成器が書いた断片だけ消す）
2. 生成器（下の STEPS の順。DESIGN.md §1）。`gen_nr_packs.py` が**最後**に断片をまとめる
3. `test_nr.py`（Node の偽 @minecraft/server で挙動テスト）→ `check_nr_types.py`（公式 d.ts で型検査）
   → `validate_nr.py`（参照切れ・UV・Molang・ボーン・上限）。三つとも走らせてから、どれかが落ちていれば失敗
4. `dist/NightRunner_v1.0.0.mcaddon`（中は `nightrunner_BP/` と `nightrunner_RP/`）と
   `dist/NightRunner_BP_v1.0.0.mcpack` / `dist/NightRunner_RP_v1.0.0.mcpack`（.pyc・.DS_Store などは入れない。
   zip の中の並びと時刻を固定して、同じ入力から同じバイト列）

生成器どうしの依存（`-j` の並べ方。DEPENDS に書く）:
* 独立（並列で走ってよい）: zombies / zombie_anim / player_anim / weapons / weapons_ranged / props / blocks /
  structures / particles / sounds / ui / items — 互いのファイルを読まない（ID は DESIGN.md・nr_registry・nr_spec で決まっている）
* `gen_nr_entities`: ゾンビ・gib・小道具のジオメトリとアニメ ID（zombies / zombie_anim / props）と、
  飛び道具・パーティクル（weapons / weapons_ranged / items / particles）を参照するので、それらの後
* `gen_nr_data_js`: `gen_nr_zombies` の当たり箱（zombie_shapes.js）と同じリグ寸法を使うので zombies の後、
  エンティティの ID 表を作るので entities の後。BP のブロック・アイテムの JSON を走査して `components.js`
  （カスタムコンポーネントの名前）を、RP の演出を走査して `fx.js` を書くので blocks / weapons / weapons_ranged / items /
  sounds / player_anim / zombie_anim / particles の後
* `gen_nr_packs`: 全部の断片をまとめるので**全部の後**
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nr_common import BP, DIST, FRAG, FRAG_KINDS, NAME, ROOT, RP, VERSION  # noqa: E402

STEPS = [
    "gen_nr_zombies.py",
    "gen_nr_zombie_anim.py",
    "gen_nr_player_anim.py",
    "gen_nr_weapons.py",
    "gen_nr_weapons_ranged.py",   # 飛び道具（銃・弓・クロスボウ・投げ物）。置き場所は近接と同じ
    "gen_nr_props.py",
    "gen_nr_blocks.py",
    "gen_nr_structures.py",
    "gen_nr_particles.py",
    "gen_nr_sounds.py",
    "gen_nr_ui.py",
    "gen_nr_entities.py",
    "gen_nr_items.py",
    "gen_nr_data_js.py",
    "gen_nr_packs.py",       # 必ず最後（断片のまとめ）
]
# 生成器 -> 先に終わっていなければならない生成器（-j のときだけ意味がある。順番に走らせるときは STEPS の順）
DEPENDS = {
    "gen_nr_entities.py": ["gen_nr_zombies.py", "gen_nr_zombie_anim.py", "gen_nr_props.py",
                           "gen_nr_weapons.py", "gen_nr_weapons_ranged.py", "gen_nr_items.py",
                           "gen_nr_particles.py"],
    # data_js は BP のブロック・アイテム（components.js のカスタムコンポーネント）と RP の演出（fx.js）も走査する
    "gen_nr_data_js.py": ["gen_nr_zombies.py", "gen_nr_entities.py", "gen_nr_blocks.py", "gen_nr_weapons.py",
                          "gen_nr_weapons_ranged.py", "gen_nr_items.py", "gen_nr_sounds.py", "gen_nr_player_anim.py",
                          "gen_nr_zombie_anim.py", "gen_nr_particles.py"],
    "gen_nr_packs.py": [s for s in STEPS if s != "gen_nr_packs.py"],
}
VERIFY = ["test_nr.py", "check_nr_types.py", "validate_nr.py"]
STRICT_ARGS = {"test_nr.py": ["--strict"], "validate_nr.py": ["--strict"]}

# zip に入れないもの
SKIP_SUFFIX = (".pyc", ".pyo", ".DS_Store", ".tmp", ".bak", ".swp", "~")
SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"}
SKIP_DIRS = {"__pycache__", ".git", ".frag", "node_modules"}
ZIP_TIME = (2026, 1, 1, 0, 0, 0)     # zip の中の時刻を固定（同じ入力 → 同じバイト列）


def banner(text: str) -> None:
    print(f"\n=== {text} ===", flush=True)


def loud_warning(lines) -> None:
    bar = "!" * 78
    print("\n" + bar)
    for ln in lines:
        print("!!! WARNING: " + ln)
    print(bar, flush=True)


def norm_step(name: str) -> str:
    """'weapons' / 'gen_nr_weapons' / 'gen_nr_weapons.py' を 'gen_nr_weapons.py' に。"""
    n = name.strip()
    if not n.endswith(".py"):
        n += ".py"
    if not n.startswith("gen_nr_"):
        n = "gen_nr_" + n
    return n


# ---------------------------------------------------------------------------
#  断片
# ---------------------------------------------------------------------------
def clear_frags(producers=None) -> int:
    """断片を消す。producers を渡すとその生成器の断片だけ。消した数を返す。"""
    n = 0
    if not os.path.isdir(FRAG):
        return 0
    for kind in os.listdir(FRAG):
        d = os.path.join(FRAG, kind)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if producers is None or f[:-5] in producers:
                os.remove(os.path.join(d, f))
                n += 1
        if not os.listdir(d):
            os.rmdir(d)
    return n


# ---------------------------------------------------------------------------
#  実行
# ---------------------------------------------------------------------------
def run_script(script: str, args=(), capture: bool = False):
    """スクリプトを走らせて (returncode, 出力, 秒) を返す。capture=False なら出力はそのまま流す。"""
    t0 = time.time()
    cmd = [sys.executable, os.path.join(HERE, script), *args]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    if capture:
        res = subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        return res.returncode, res.stdout, time.time() - t0
    res = subprocess.run(cmd, cwd=ROOT, env=env)
    return res.returncode, "", time.time() - t0


def run_generators(steps, jobs: int, keep_going: bool, timings: dict) -> list:
    """生成器を走らせる。失敗した生成器の名前のリストを返す。"""
    failed: list = []
    if jobs <= 1:
        for s in steps:
            banner(s)
            rc, _out, dt = run_script(s)
            timings[s] = dt
            if rc:
                print(f"  FAIL {s} (exit {rc})")
                failed.append(s)
                if not keep_going:
                    break
        return failed

    # 並列: 依存が全部終わった生成器から順に。出力は終わった順にまとめて出す
    pending = list(steps)
    done: set = set()
    running: dict = {}
    stop = False
    with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
        while pending or running:
            if not stop:
                for s in list(pending):
                    if len(running) >= jobs:
                        break
                    deps = [d for d in DEPENDS.get(s, []) if d in steps]
                    if all(d in done for d in deps):
                        pending.remove(s)
                        running[pool.submit(run_script, s, (), True)] = s
                        print(f"  [-j] start {s}", flush=True)
            if not running:
                if pending and not stop:
                    # 依存が満たせない（循環）— 起きないはずだが、念のため順に走らせる
                    s = pending.pop(0)
                    running[pool.submit(run_script, s, (), True)] = s
                else:
                    break
            fin, _ = cf.wait(list(running), return_when=cf.FIRST_COMPLETED)
            for fut in fin:
                s = running.pop(fut)
                rc, out, dt = fut.result()
                timings[s] = dt
                banner(f"{s}  ({dt:.1f}s)")
                if out:
                    print(out.rstrip(), flush=True)
                done.add(s)
                if rc:
                    print(f"  FAIL {s} (exit {rc})")
                    failed.append(s)
                    if not keep_going:
                        stop = True
                        pending.clear()
    return failed


def verify(strict: bool, timings: dict) -> list:
    """test_nr → check_nr_types → validate_nr を全部走らせ、落ちたものの名前を返す。"""
    failed = []
    for v in VERIFY:
        if not os.path.exists(os.path.join(HERE, v)):
            if strict or v != "check_nr_types.py":
                loud_warning([f"{v} が無い（検証を飛ばした）"])
                if strict:
                    failed.append(v)
            continue
        banner(v)
        args = STRICT_ARGS.get(v, []) if strict else []
        rc, _out, dt = run_script(v, args)
        timings[v] = dt
        if v == "check_nr_types.py" and rc == 2 and not strict:
            loud_warning(["check_nr_types.py: 型検査の道具（node / npm / typescript）が使えなかった。",
                          "型検査を飛ばして続ける（--strict では失敗にする）"])
            continue
        if rc:
            print(f"  FAIL {v} (exit {rc})")
            failed.append(v)
    return failed


# ---------------------------------------------------------------------------
#  dist
# ---------------------------------------------------------------------------
def _skip(name: str) -> bool:
    return name in SKIP_NAMES or name.endswith(SKIP_SUFFIX)


def zip_dir(zf: zipfile.ZipFile, folder: str, arc_root: str) -> int:
    """folder を arc_root/ の下に入れる（並び・時刻を固定）。入れたファイル数を返す。"""
    n = 0
    for base, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if _skip(f):
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            arc = f"{arc_root}/{rel}" if arc_root else rel
            info = zipfile.ZipInfo(arc, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                zf.writestr(info, fh.read(), compresslevel=9)
            n += 1
    return n


def write_dist() -> list:
    os.makedirs(DIST, exist_ok=True)
    for f in os.listdir(DIST):
        if f.startswith(NAME + "_"):
            os.remove(os.path.join(DIST, f))
    out = []
    addon = os.path.join(DIST, f"{NAME}_v{VERSION}.mcaddon")
    with zipfile.ZipFile(addon, "w") as zf:
        zip_dir(zf, BP, "nightrunner_BP")
        zip_dir(zf, RP, "nightrunner_RP")
    out.append(addon)
    for folder, suffix in ((BP, "BP"), (RP, "RP")):
        path = os.path.join(DIST, f"{NAME}_{suffix}_v{VERSION}.mcpack")
        with zipfile.ZipFile(path, "w") as zf:
            zip_dir(zf, folder, "")
        out.append(path)
    return out


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NIGHT RUNNER のビルド（生成 → 検証 → dist）")
    ap.add_argument("--only", action="append", default=[],
                    help="この生成器だけ走らせる（'weapons' / 'gen_nr_weapons.py'。カンマ区切り・複数回可）。"
                         "検証と dist は --verify を付けたときだけ")
    ap.add_argument("--verify", action="store_true", help="--only のときも検証（test/types/validate）まで走らせる")
    ap.add_argument("--no-dist", action="store_true", help="dist/ を書かない")
    ap.add_argument("--no-verify", action="store_true", help="検証を飛ばす（急ぎの確認用）")
    ap.add_argument("--strict", action="store_true",
                    help="最終・CI 用: まだ無い生成器・検証スクリプト・main.js を失敗として扱う")
    ap.add_argument("-j", "--jobs", nargs="?", type=int, const=os.cpu_count() or 2, default=1,
                    help="独立した生成器を並列に走らせる数（-j だけなら CPU 数）")
    ap.add_argument("-k", "--keep-going", action="store_true", help="生成器が失敗しても残りを走らせる")
    args = ap.parse_args(argv)
    if args.strict and args.no_verify:
        ap.error("--strict と --no-verify は一緒に使えない")

    t_all = time.time()
    timings: dict = {}
    only = [norm_step(x) for o in args.only for x in o.split(",") if x.strip()]
    unknown = [o for o in only if o not in STEPS]
    if unknown:
        ap.error(f"知らない生成器: {', '.join(unknown)}（{', '.join(STEPS)}）")
    steps = [s for s in STEPS if (not only or s in only)]

    # 1. 断片を消す
    if only:
        n = clear_frags({s[:-3] for s in steps})
        print(f"  frag: {', '.join(s[:-3] for s in steps)} の断片 {n} 件を消した（ほかの生成器の断片は残す）")
    else:
        n = clear_frags()
        print(f"  frag: tools/nightrunner/.frag/ を空にした（{n} 件）")

    # 2. 生成器（無いものは飛ばす。strict なら失敗）
    missing = [s for s in steps if not os.path.exists(os.path.join(HERE, s))]
    present = [s for s in steps if s not in missing]
    if missing:
        if args.strict:
            print("\nERROR: --strict: まだ無い生成器: " + ", ".join(missing))
            return 1
        loud_warning([f"まだ無い生成器を飛ばす（{len(missing)} / {len(steps)}）: " + ", ".join(missing),
                      "出来上がるパックはその分欠けている（--strict ではこれを失敗にする）"])
    failed = run_generators(present, args.jobs, args.keep_going, timings)
    if failed:
        print(f"\nERROR: 生成器が失敗: {', '.join(failed)}")
        return 1

    # 3. 検証
    verify_failed = []
    do_verify = (not args.no_verify) and (not only or args.verify)
    if do_verify:
        verify_failed = verify(args.strict, timings)
        if verify_failed:
            print(f"\nERROR: 検証が失敗: {', '.join(verify_failed)}（dist は書かない）")
            return 1
    elif not args.no_verify:
        print("\n  （--only なので検証と dist は飛ばした。--verify で検証まで走る）")

    # 4. dist
    if not args.no_dist and not only:
        banner("dist")
        for path in write_dist():
            print(f"  {os.path.relpath(path, ROOT):48s} {os.path.getsize(path) / 1024:10.1f} KB")

    # まとめ
    banner("summary")
    for name, dt in sorted(timings.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {name:28s} {dt:7.1f}s")
    print(f"  total {time.time() - t_all:.1f}s — ran {len(present)} generator(s)"
          + (f", SKIPPED {len(missing)}: {', '.join(m[:-3] for m in missing)}" if missing else ""))
    if missing and not args.strict:
        print("  !!! 欠けた生成器がある（上の WARNING）。最終ビルドは --strict で。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
