# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — スクリプトの挙動テスト（Minecraft 無しで手書き JS を実際に走らせる）。

`@minecraft/server` 2.3.0 / `@minecraft/server-ui` 2.0.0 を「動く偽物」に差し替え、偽のワールド
（地面・ブロック・時間・光）・偽のプレイヤー・偽のゾンビ・tick の進行を用意して、アドオンの
`packs/nightrunner_BP/scripts/main.js` を読み込み、テストを走らせる。

偽物は **公式の d.ts（tools/nightrunner/typings/）から作る部分**と手書きの部分（tools/nightrunner/test_fakes/）からなる:

* d.ts の全 enum・全クラス名・定数を export する（実機に無い名前を import したら Node が失敗する）。
  手書きしていないクラスは「身代わり」（new すると例外、static は d.ts の値か「偽物の限界」）
* d.ts で「read-only mode では呼べない」とされた関数・プロパティを before イベントの中で呼ぶと例外
  （実機の "does not have required privileges"）。「early-execution で呼べる」と書かれていない
  World / Dimension などの関数と `new ItemStack`・`BlockPermutation.resolve` を worldLoad 前に呼ぶと例外
* 偽物がまだ持っていない実機の関数を呼ぶと「偽物の限界」と分かる例外（アドオンの不具合と区別する）
* 実機に無いメソッド（例 MolangVariableMap.setVector3 は 2.3.0 に無い）は偽物にも無い（自己テストで確かめる）

**契約違反（violation）**は、スクリプトが try/catch で握りつぶしてもテストを失敗にする:
存在しないエンティティ・パーティクル・効果音・アニメ・アイテム・ブロック・構造物（のパレットのブロック）・
BP イベント・プロパティの ID、enum に無い値・範囲外の int、有限でない座標や Molang 値、`variable.` の無い
Molang 変数名、プレイヤーへの `applyImpulse`・`remove`、1.x の形の `applyKnockback(x, z, h, v)`、
before イベント内の書き換え・subscribe・フォームの show、worldLoad 前の world、重ねられるアイテムへの動的プロパティ、
server-ui 1.x の形の `toggle(label, true)` / `slider(..., step, default)`、入力の間に挟んだ label / header /
divider、`animation.nr.*` の playAnimation に controller（`nr.` で始まる）・stopExpression・nextState が無い
（rendering.md P1 / P2）、location の無い `getEntities({maxDistance})`、ゲームに無い `setTimeout` などのグローバル、
1 tick のパーティクル 300 個超（DESIGN.md §11）、startup の外・無いフック名のカスタムコンポーネント登録、
BP が使うのにスクリプトが登録していないカスタムコンポーネント。

使い方:

    python3 tools/nightrunner/test_nr.py                 # 自己テスト + 組み込み smoke + tools/nightrunner/tests/*.mjs
    python3 tools/nightrunner/test_nr.py -k gore          # 名前（かファイル名）に gore を含むテストだけ（自己テストは飛ばす）
    python3 tools/nightrunner/test_nr.py --file tests/gore.mjs   # このファイルだけ（組み込みは走らせない）
    python3 tools/nightrunner/test_nr.py --keep -v        # 作業フォルダを残す・テストごとの結果とアドオンの console.* も出す
    python3 tools/nightrunner/test_nr.py --strict         # main.js が無ければ失敗（最終・CI 用）
    python3 tools/nightrunner/test_nr.py --json build_preview/nightrunner/test_nr.json
    python3 tools/nightrunner/test_nr.py --selftest       # 偽物の自己テストだけ

`main.js` がまだ無ければ、偽物そのものの自己テスト（小さな偽アドオンを作って走らせる）だけをして 0 で終わる。
自己テストは「正しい偽アドオンが全部通る」ことと「わざと壊した偽アドオン（test_fakes/selftest/addon_bad・
boot_*.js）が期待どおりの違反で落ちる」ことの両方を確かめる。
終了コード: 0 = 全部通った、1 = 失敗あり、2 = 道具が動かない（node が無いなど）。

ファイルの置き場所:

| ファイル | 中身 |
|---|---|
| `test_nr.py` | d.ts の読み取り、RP/BP から契約の表（DEFS）を作る、作業フォルダ、node の起動、結果のまとめ、自己テスト |
| `test_fakes/server.js` | 偽の `@minecraft/server`（手書き。末尾に d.ts から作る部分を足して置く） |
| `test_fakes/server_ui.js` / `common.js` | 偽の `@minecraft/server-ui` 2.0.0 / `@minecraft/common` |
| `test_fakes/harness.js` | テストの道具 `nr-test`（下の表。詳しくは中のコメント） |
| `test_fakes/runner.mjs` | 1 ファイル分を走らせる（起動の順・console の捕捉・結果の JSON） |
| `test_fakes/builtin_smoke.mjs` | 組み込みの通しテスト（全エンティティ・全ゾンビの全部位・全イベント・全ブロック・全構造物） |
| `test_fakes/selftest/` | 自己テストの偽アドオン（正しいもの・壊れたもの）とテスト |

----------------------------------------------------------------------------
テストの書き方（tools/nightrunner/tests/<名前>.mjs。.mjs が全部テスト、.js は補助として一緒に写す。tests/README.md も）
----------------------------------------------------------------------------

作業フォルダでは `tests/` と `scripts/`（BP の scripts の写し）が並ぶので、アドオンの関数は
`../scripts/...` で import できる。テストの道具は `nr-test` から:

    import { test, tick, spawnZombie, spawnPlayer, hit, expect, prop, used } from "nr-test";
    import { applyHit } from "../scripts/gore/gore.js";      // アドオンの中身も直接呼べる

    test("頭を重い刃で斬ると首が飛ぶ", async () => {
      const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:w_machete");   // 位置・手に持つアイテム
      const z = spawnZombie("office_worker", { x: 0, y: 64, z: 2 });   // 鍵か nr:z_* の ID。既定でプレイヤーの方を向く
      await hit(p, z, { part: "head", damage: 30 });                   // 部位を狙って殴る（視線を合わせ、entityHitEntity + entityHurt）
      await tick(5);                                                   // tick を進める（必ず await）
      expect(prop(z, "nr:head")).toBeOneOf(["severed", "crushed"]);
      expect(used().particles["nr:blood_fountain"]).toBeGreaterThan(0);
    });

ファイルごとに Node のプロセスが一つ（アドオンは一度だけ起動）。テストの間でワールド（エンティティ・
ブロック・時刻・フォームの答え）は片付けるが、アドオンの中の状態と runInterval は残る。

道具（`nr-test` の export。詳しくは test_fakes/harness.js の中のコメント）:

| 道具 | 中身 |
|---|---|
| `test(name, fn)` | テストを登録（fn は async 可）。`test.only` は無い。`-k` で絞る |
| `tick(n=1)` | n tick 進める（物理・効果・タイマー・runJob・after イベント・Promise） |
| `spawnZombie(type, pos, {yaw, face})` | ゾンビ（`dimension.spawnEntity` 経由。entitySpawn も来る）。既定でプレイヤーの方を向く |
| `spawn(id, pos, {yaw, face, event})` / `despawn(e)` | 何でも出す（gib・弾・小道具）/ イベントなしで消す |
| `spawnPlayer(pos, item, {name, mode, yaw})` | プレイヤー（playerJoin / playerSpawn が来る）。item は ID か ItemStack |
| `give(player, item, slot)` / `held(player)` | 持ち物 |
| `hit(player, target, {part, point, damage, cause})` | 近接で殴る。part は head/torso/arm_r/arm_l/leg_r/leg_l（`PARTS`） |
| `shoot(player, target, {part, point, projectile, damage})` | 飛び道具が当たる（projectileHitEntity + entityHurt） |
| `use / startUse / stopUse / releaseUse / completeUse(player, item?, ticks?)` | アイテムを使う（before/after + カスタムコンポーネントの onUse 等） |
| `press(player, "Jump"|"Sneak", down=true)` / `setInput(player, {x, y, sprint, sneak, jump})` | 入力（playerButtonInput・inputInfo・移動） |
| `interact(player, entityOrPos)` / `breakBlock(player, pos)` / `placeBlock(player, pos, id)` | 触る・壊す・置く |
| `scriptEvent(id, message, source)` / `command(name, args, source)` | `/scriptevent` / startup で登録したカスタムコマンド |
| `setBlock(pos, id)` / `fill(from, to, id)` / `blockAt(pos)` / `setGround(y)` | 偽のワールドの地形（既定は y<64 が石） |
| `setTime(t)` / `setLight(n | fn)` | 時刻（0〜23999）と光（既定は時刻と空・光るブロックから） |
| `answerForm(resp)` / `lastForm()` | フォームの答え（番号・formValues の配列・"defaults"・{canceled:true}・関数）と最後に出たフォーム |
| `partPoint(zombie, part)` / `aim(player, point)` | 部位の世界座標（scripts/data/zombie_shapes.js の当たり箱）・視線を向ける |
| `prop(e, name)` / `entities(type)` / `zombieTypes()` | 読み出し |
| `used()` / `mark()` / `since(mark)` | 使った演出の回数（particles / sounds / anims / events / props / spawned …。used() はそのテストの分） |
| `expect(v)` | toBe / toEqual / toBeTruthy / toBeGreaterThan / toBeCloseTo / toContain / toThrow / toBeOneOf / not … |
| `expectViolation(fn, kind)` | わざと契約違反を起こすテスト用（違反を確かめて記録から消す。必ず await） |
| `DATA` | scripts/data/*.js の中身（zombies / shapes / weapons / items / fx …。無ければ空） |
| `mc` / `ui` / `S` | 偽の @minecraft/server・server-ui・偽物の内部状態（S.log・S.DEFS など） |

テストが失敗になるのは: 例外・expect の失敗・契約違反・購読者や system.run の中の捕まらない例外・
捕まらない Promise の reject・console.error・tick を進めずに止まった await。
console.warn（[nr] の警告）と「偽物の限界」は数えて出すだけ。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nr_common import BP, HERE, ROOT, RP, SCRATCH, SCRIPTS  # noqa: E402

TYPINGS = os.path.join(HERE, "typings")
TESTS_DIR = os.path.join(HERE, "tests")
FAKES = os.path.join(HERE, "test_fakes")
SELF = os.path.join(FAKES, "selftest")
RESEARCH = os.path.join(ROOT, "build_preview", "nr_research")
PARTICLE_BUDGET = 300           # DESIGN.md §11
SEED = 20260101                 # 偽物の Math.random の種（同じテストは同じ結果）
FILE_TIMEOUT = 900              # 1 ファイルの上限（秒）
SELF_TIMEOUT = 180
SMOKE_NAME = "__builtin_smoke.mjs"
WORLD_EVENT_CLASSES = ("WorldAfterEvents", "WorldBeforeEvents", "SystemAfterEvents", "SystemBeforeEvents")


def rel(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return p if r.startswith("..") else r.replace(os.sep, "/")
    except ValueError:
        return p


def write_json(path: str, doc) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ===========================================================================
#  d.ts を読む（クラス・メンバーの印・enum・定数・イベント名）
# ===========================================================================
_ENUM_HEAD = re.compile(r"^export enum (\w+)\s*\{")
_ENUM_ITEM = re.compile(r"""^\s+['"]?(\w+)['"]?\s*=\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|(-?\d+(?:\.\d+)?))\s*,?\s*$""")
_CLASS_HEAD = re.compile(r"^export class (\w+)(?:<[^>]*>)?(?:\s+extends\s+([\w.]+)(?:<.*?>)?)?"
                         r"(?:\s+implements\s+[^{]+)?\s*\{\s*$")
_CONST = re.compile(r"^export const (\w+)\s*(?::\s*([^=;]+?))?\s*(?:=\s*(.+?))?\s*;\s*$")
_CTOR = re.compile(r"^    (?:(private|protected)\s+)?constructor\s*\(")
_METHOD = re.compile(r"^    (static\s+)?([A-Za-z_$][\w$]*)\s*(?:<.*>)?\s*\(")
_PROP = re.compile(r"^    (static\s+)?(readonly\s+)?['\"]?([A-Za-z_$][\w$]*)['\"]?(\?)?\s*(:|=)\s*(.*)$")


def _literal(src: str):
    s = src.strip().rstrip(";").strip()
    m = re.fullmatch(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", s)
    if m:
        return m.group(1) if m.group(1) is not None else m.group(2)
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d*", s):
        return float(s)
    if s in ("true", "false"):
        return s == "true"
    return None


def parse_dts(path: str) -> dict:
    """d.ts → {classes: {名前: {extends, ctor, error, members: {名前: {kind, static, ro, early, value?}}}},
    enums: {名前: {キー: 値}}, events: {WorldAfterEvents: [...], ...}, consts: {名前: 値 / None}}。

    ro / early は @remarks の定型文（"can't be called in read-only mode" / "can't be edited in read-only mode" /
    "can be called in early-execution mode" / "can be read in early-execution mode"）から拾う。
    """
    lines = read_text(path).splitlines()
    api = {"classes": {}, "enums": {}, "events": {}, "consts": {}}
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        m = _ENUM_HEAD.match(ln)
        if m:
            vals = {}
            i += 1
            while i < n and lines[i].rstrip() != "}":
                mm = _ENUM_ITEM.match(lines[i])
                if mm:
                    if mm.group(4) is not None:
                        v = mm.group(4)
                        vals[mm.group(1)] = float(v) if "." in v else int(v)
                    else:
                        vals[mm.group(1)] = mm.group(2) if mm.group(2) is not None else mm.group(3)
                i += 1
            api["enums"][m.group(1)] = vals
            i += 1
            continue
        m = _CLASS_HEAD.match(ln)
        if m:
            name, base = m.group(1), m.group(2)
            info = {"extends": base, "ctor": None, "error": base == "Error", "members": {}}
            doc, in_doc = [], False
            i += 1
            while i < n and lines[i].rstrip() != "}":
                s = lines[i]
                st = s.strip()
                if in_doc:
                    doc.append(st)
                    if "*/" in st:
                        in_doc = False
                elif st.startswith("/**"):
                    doc, in_doc = [st], "*/" not in st
                elif not st or st.startswith("//"):
                    pass
                else:
                    mc = _CTOR.match(s)
                    mp = None if mc else _PROP.match(s)
                    mm = None if (mc or mp) else _METHOD.match(s)
                    if mc:
                        info["ctor"] = "private" if mc.group(1) else "public"
                    elif mp or mm:
                        txt = " ".join(doc)
                        ro = "can't be called in read-only mode" in txt or "can't be edited in read-only mode" in txt
                        early = "can be called in early-execution mode" in txt or "can be read in early-execution mode" in txt
                        if mp:
                            mname = mp.group(3)
                            rec = {"kind": "property", "static": bool(mp.group(1)), "ro": ro, "early": early,
                                   "readonly": bool(mp.group(2))}
                            if mp.group(5) == "=":
                                v = _literal(mp.group(6))
                                if v is not None:
                                    rec["value"] = v
                        else:
                            mname = mm.group(2)
                            rec = {"kind": "method", "static": bool(mm.group(1)), "ro": ro, "early": early}
                        old = info["members"].get(mname)
                        if old:                       # 多重定義はまとめる
                            old["ro"] = old["ro"] or rec["ro"]
                            old["early"] = old["early"] or rec["early"]
                        else:
                            info["members"][mname] = rec
                    doc = []
                i += 1
            api["classes"][name] = info
            i += 1
            continue
        m = _CONST.match(ln)
        if m:
            api["consts"][m.group(1)] = _literal(m.group(3)) if m.group(3) else None
        i += 1
    for cls in WORLD_EVENT_CLASSES:
        info = api["classes"].get(cls)
        if info:
            api["events"][cls] = sorted(k for k, v in info["members"].items() if v["kind"] == "property")
    return api


def api_problems(api: dict, ui: dict) -> list:
    """d.ts の読み取りが壊れていないか（版の違う d.ts を置いた時など）。"""
    bad = []
    if len(api["classes"]) < 250 or len(api["enums"]) < 40:
        bad.append(f"server の d.ts からクラス {len(api['classes'])} / enum {len(api['enums'])} しか読めない")
    for cls, at_least in (("WorldAfterEvents", 40), ("WorldBeforeEvents", 8), ("SystemBeforeEvents", 1)):
        if len(api["events"].get(cls, [])) < at_least:
            bad.append(f"{cls} のイベントが {len(api['events'].get(cls, []))} 個しか読めない")
    ent = api["classes"].get("Entity", {}).get("members", {})
    if not ent.get("applyDamage", {}).get("ro") or not api["classes"].get("World", {}).get("members", {}).get(
            "afterEvents", {}).get("early"):
        bad.append("@remarks の read-only / early-execution の印が読めていない")
    if api["consts"].get("TicksPerSecond") != 20:
        bad.append("定数 TicksPerSecond が読めない")
    for c in ("ActionFormData", "ModalFormData", "MessageFormData", "UIManager", "FormRejectError"):
        if c not in ui["classes"]:
            bad.append(f"server-ui の d.ts に {c} が無い")
    return bad


def server_tail_js(api: dict, hand_src: str) -> str:
    """偽の @minecraft/server の末尾に足す部分: enum・定数・手書きしていないクラスの身代わり・ガードの取り付け。"""
    exported = set(re.findall(r"^export\s+(?:const|let|var|class|function)\s+([A-Za-z_$][\w$]*)", hand_src, re.M))
    out = ["", "// " + "=" * 75,
           "//  ここから下は test_nr.py が d.ts（typings/server/index.d.ts）から作った部分",
           "// " + "=" * 75]
    for name in sorted(api["enums"]):
        if name not in exported:
            out.append(f"export const {name} = Object.freeze({json.dumps(api['enums'][name], ensure_ascii=False)});")
    for name in sorted(api["consts"]):
        if name not in exported:
            out.append(f"export const {name} = {json.dumps(api['consts'][name])};")
    classes = api["classes"]
    stubs = {c for c in classes if c not in exported}
    order, done = [], set()

    def visit(c):
        if c in done or c not in stubs:
            return
        done.add(c)
        base = classes[c]["extends"]
        if base in stubs:
            visit(base)
        order.append(c)

    for c in sorted(stubs):
        visit(c)
    for c in order:
        info = classes[c]
        base = info["extends"]
        if info["error"]:
            out.append(f'export class {c} extends Error {{ constructor(m) {{ super(m); this.name = "{c}"; }} }}')
            continue
        ext = f" extends {base}" if base and (base in exported or base in stubs) else ""
        if info["ctor"] == "public":
            body = f'throw limitation("new {c}");'
        else:
            body = f'throw new TypeError("[fake] {c} は new できない（実機でもコンストラクタが公開されていない）");'
        out.append(f"export class {c}{ext} {{ constructor() {{ {body} }} }}")
    plain = [c for c in order if not classes[c]["error"]]
    out.append("installGuards({ ...IMPLEMENTED, " + ", ".join(plain) + " });")
    out.append("S.STUBS = " + json.dumps(plain) + ";")
    return "\n".join(out) + "\n"


# ===========================================================================
#  RP / BP → 契約の表（DEFS）
# ===========================================================================
def _walk(root: str, exts=(".json",)) -> list:
    out = []
    if not os.path.isdir(root):
        return out
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            if f.endswith(exts):
                out.append(os.path.join(base, f))
    return out


def _load(path: str, notes: list):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"{rel(path)}: 読めない JSON（{type(exc).__name__}）— validate_nr.py で直す")
        return None


def _custom_of(comps: dict) -> dict:
    """Custom Components V2: 名前空間付き（minecraft: 以外）のキーがカスタムコンポーネント。値が params。"""
    out = {k: v for k, v in comps.items() if ":" in k and not k.startswith(("minecraft:", "tag:"))}
    for name in comps.get("minecraft:custom_components") or []:     # 古い書き方（validate_nr が咎める）
        out.setdefault(name, {})
    return out


_TRAIT_STATES = {
    "minecraft:cardinal_direction": ["south", "west", "north", "east"],
    "minecraft:facing_direction": ["down", "up", "north", "south", "west", "east"],
    "minecraft:block_face": ["down", "up", "north", "south", "west", "east"],
    "minecraft:vertical_half": ["bottom", "top"],
    "minecraft:corner_and_cardinal_direction": ["south", "west", "north", "east"],
}


def load_vanilla() -> dict:
    """build_preview/nr_research にバニラの ID の一覧があれば（無ければ空 = バニラは確かめない）。"""
    out = {"items": set(), "blocks": set(), "entities": set()}
    for name, key in (("vanilla_items.txt", "items"), ("vanilla_blocks.txt", "blocks")):
        p = os.path.join(RESEARCH, "catalog", name)
        if os.path.exists(p):
            for ln in read_text(p).splitlines():
                ln = ln.strip()
                if ln:
                    out[key].add(ln if ":" in ln else "minecraft:" + ln)
    p = os.path.join(RESEARCH, "bedrock-samples", "metadata", "vanilladata_modules", "mojang-entities.json")
    if os.path.exists(p):
        try:
            for d in json.loads(read_text(p)).get("data_items", []):
                out["entities"].add(d["name"])
        except (ValueError, KeyError):
            pass
    if out["items"]:
        out["items"] |= out["blocks"]          # ブロックはアイテムとしても持てる
    return {k: sorted(v) for k, v in out.items()}


def build_defs(bp: str, rp: str, work: str, notes: list) -> dict:
    """BP / RP を読んで偽物が確かめる表を作る。構造物は work/__nr_structs/ に JSON で書き出す。"""
    defs = {"entities": {}, "items": {}, "blocks": {}, "particles": [], "sounds": [], "animations": [],
            "structures": {}, "vanilla": load_vanilla()}
    for p in _walk(os.path.join(bp, "entities")):
        doc = _load(p, notes)
        ent = (doc or {}).get("minecraft:entity") if isinstance(doc, dict) else None
        ident = ((ent or {}).get("description") or {}).get("identifier")
        if not ident:
            continue
        props = {}
        for name, pd in (ent["description"].get("properties") or {}).items():
            t = pd.get("type")
            d = {"type": t, "default": pd.get("default")}
            if t == "enum":
                d["values"] = list(pd.get("values") or [])
            if t in ("int", "float"):
                d["range"] = list(pd.get("range") or [0, 0])
            props[name] = d
        defs["entities"][ident] = {"props": props, "components": ent.get("components") or {},
                                   "groups": ent.get("component_groups") or {}, "events": ent.get("events") or {}}
    for p in _walk(os.path.join(bp, "items")):
        doc = _load(p, notes)
        it = (doc or {}).get("minecraft:item") if isinstance(doc, dict) else None
        ident = ((it or {}).get("description") or {}).get("identifier")
        if ident:
            comps = it.get("components") or {}
            defs["items"][ident] = {"components": comps, "custom": _custom_of(comps)}
    for p in _walk(os.path.join(bp, "blocks")):
        doc = _load(p, notes)
        b = (doc or {}).get("minecraft:block") if isinstance(doc, dict) else None
        desc = (b or {}).get("description") or {}
        ident = desc.get("identifier")
        if not ident:
            continue
        comps = b.get("components") or {}
        states = dict(desc.get("states") or {})
        for trait in (desc.get("traits") or {}).values():
            for st in (trait or {}).get("enabled_states") or []:
                if st in _TRAIT_STATES:
                    states[st] = list(_TRAIT_STATES[st])
                elif st.startswith("minecraft:connection_"):
                    states[st] = [False, True]
        custom = _custom_of(comps)
        for perm in b.get("permutations") or []:
            for k, v in _custom_of(perm.get("components") or {}).items():
                custom.setdefault(k, v)
        tick = comps.get("minecraft:tick")
        light = comps.get("minecraft:light_emission", 0)
        defs["blocks"][ident] = {
            "components": comps, "states": states, "custom": custom,
            "light": light if isinstance(light, int) else 0,
            "solid": comps.get("minecraft:collision_box", True) is not False,
            "tick": list(tick.get("interval_range", [20, 20])) if isinstance(tick, dict) else None,
        }
    sdir = os.path.join(bp, "structures")
    files = _walk(sdir, (".mcstructure",))
    if files:
        from validate_nr import read_mcstructure, structure_ids   # NBT の読み手は validate_nr と同じもの
        for k, p in enumerate(files):
            try:
                data = read_mcstructure(p)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"{rel(p)}: 読めない .mcstructure（{exc}）")
                continue
            out = f"__nr_structs/{k:04d}.json"
            write_json(os.path.join(work, out), {
                "indices": data["indices"],
                "palette": [{"name": nm, "states": st} for nm, st in zip(data["palette"], data["states"])]})
            for sid in structure_ids(os.path.relpath(p, sdir)):
                defs["structures"][sid] = {"size": list(data["size"]), "file": out}
    for p in _walk(os.path.join(rp, "particles")):
        doc = _load(p, notes)
        try:
            defs["particles"].append(doc["particle_effect"]["description"]["identifier"])
        except (TypeError, KeyError):
            pass
    sd = os.path.join(rp, "sounds", "sound_definitions.json")
    if os.path.exists(sd):
        doc = _load(sd, notes) or {}
        table = doc.get("sound_definitions", doc) if isinstance(doc, dict) else {}
        defs["sounds"] = sorted(k for k in table if k != "format_version")
    for p in _walk(os.path.join(rp, "animations")):
        doc = _load(p, notes)
        if isinstance(doc, dict):
            defs["animations"] += list((doc.get("animations") or {}).keys())
    for k in ("particles", "animations"):
        defs[k] = sorted(set(defs[k]))
    return defs


# ===========================================================================
#  作業フォルダ
# ===========================================================================
def fake_modules(api: dict) -> dict:
    """{パッケージ名: index.js の中身}。"""
    server = read_text(os.path.join(FAKES, "server.js"))
    return {
        "@minecraft/server": server + server_tail_js(api, server),
        "@minecraft/server-ui": read_text(os.path.join(FAKES, "server_ui.js")),
        "@minecraft/common": read_text(os.path.join(FAKES, "common.js")),
        "nr-test": read_text(os.path.join(FAKES, "harness.js")),
    }


def prepare_work(work: str, *, scripts_src, entry_file=None, tests, defs, api, ui_api, modules, seed=SEED):
    """作業フォルダを作る。tests = [(元のファイル, tests/ の中の名前)]。戻り値はテストの相対パスの一覧。"""
    os.makedirs(work, exist_ok=True)
    write_json(os.path.join(work, "package.json"), {"name": "nr-test-work", "private": True, "type": "module"})
    dst = os.path.join(work, "scripts")
    if scripts_src and os.path.isdir(scripts_src):
        shutil.copytree(scripts_src, dst, dirs_exist_ok=True)
    os.makedirs(dst, exist_ok=True)
    if entry_file:
        shutil.copyfile(entry_file, os.path.join(dst, "main.js"))
    tdir = os.path.join(work, "tests")
    os.makedirs(tdir, exist_ok=True)
    rels = []
    for src, name in tests:
        target = os.path.join(tdir, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if src is None:
            continue
        shutil.copyfile(src, target)
        if name.endswith(".mjs"):
            rels.append("tests/" + name.replace(os.sep, "/"))
    for pkg, src in modules.items():
        d = os.path.join(work, "node_modules", *pkg.split("/"))
        os.makedirs(d, exist_ok=True)
        write_json(os.path.join(d, "package.json"), {"name": pkg, "private": True, "type": "module",
                                                     "main": "index.js", "exports": "./index.js"})
        with open(os.path.join(d, "index.js"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src)
    shutil.copyfile(os.path.join(FAKES, "runner.mjs"), os.path.join(work, "__nr_runner.mjs"))
    write_json(os.path.join(work, "__nr_env.json"), {"seed": seed, "particleBudget": PARTICLE_BUDGET,
                                                     "api": api, "apiUi": ui_api, "defs": defs})
    return rels


def user_tests() -> list:
    """tools/nightrunner/tests/ の .mjs（テスト）と .js / .json（補助）。[(元, 相対名)]。"""
    out = []
    for p in _walk(TESTS_DIR, (".mjs", ".js", ".json")):
        r = os.path.relpath(p, TESTS_DIR)
        if r.startswith("node_modules"):
            continue
        out.append((p, r))
    return out


# ===========================================================================
#  走らせる
# ===========================================================================
def run_file(node: str, work: str, test_rel: str, *, entry="scripts/main.js", filt="", verbose=False,
             timeout=FILE_TIMEOUT, tag="") -> dict:
    """1 ファイルを自分の node プロセスで走らせて結果（runner.mjs の JSON）を返す。"""
    out_path = os.path.join(work, "__nr_result_" + re.sub(r"\W", "_", test_rel) + ".json")
    if os.path.exists(out_path):
        os.remove(out_path)
    env = dict(os.environ, NR_ENTRY=entry, NR_FILTER=filt or "", NR_VERBOSE="1" if verbose else "0")
    cmd = [node, "--no-warnings", "__nr_runner.mjs", test_rel, out_path]
    t0 = time.time()
    output = ""
    try:
        proc = subprocess.run(cmd, cwd=work, env=env, timeout=timeout, text=True, encoding="utf-8",
                              errors="replace", capture_output=not verbose)
        output = (proc.stdout or "") + (proc.stderr or "")
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        return {"file": test_rel, "tag": tag, "crash": f"{timeout} 秒で終わらない（アドオンかテストの無限ループ？）",
                "tests": [], "seconds": round(time.time() - t0, 2)}
    if not os.path.exists(out_path):
        tail = [ln for ln in output.strip().splitlines() if ln.strip()][-14:]
        return {"file": test_rel, "tag": tag, "crash": f"node が結果を書かずに終わった（終了コード {rc}）",
                "output": tail, "tests": [], "seconds": round(time.time() - t0, 2)}
    with open(out_path, encoding="utf-8") as fh:
        res = json.load(fh)
    res["tag"] = tag
    res["seconds"] = round(time.time() - t0, 2)
    return res


def run_all(node: str, jobs: list, workers: int) -> list:
    """jobs = [dict(work, test, entry, filt, verbose, timeout, tag)]。入力の順に結果を返す。"""
    if workers <= 1 or len(jobs) <= 1:
        return [run_file(node, j["work"], j["test"], **{k: v for k, v in j.items() if k not in ("work", "test")})
                for j in jobs]
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_file, node, j["work"], j["test"],
                          **{k: v for k, v in j.items() if k not in ("work", "test")}) for j in jobs]
        return [f.result() for f in futs]


# ===========================================================================
#  結果のまとめ
# ===========================================================================
def _at(x: dict) -> str:
    bits = [b for b in (x.get("where"), f"tick {x['tick']}" if x.get("tick") is not None else "") if b]
    return f"（{'、'.join(bits)}）" if bits else ""


def failures(res: dict) -> list:
    """失敗の一覧 [(見出し, [行...])]。"""
    out = []
    if res.get("crash"):
        out.append(("（ファイル）", [res["crash"]] + [f"  {ln}" for ln in res.get("output", [])]))
        return out
    boot = res.get("boot") or {}
    lines = []
    for e in boot.get("errors", []):
        lines.append(f"例外（{e.get('where', '?')}）: {e.get('msg')}")
        lines += [f"    at {s}" for s in (e.get("stack") or [])[:3]]
    for v in boot.get("violations", []):
        lines.append(f"違反 {v['kind']}: {v['msg']}{_at(v)}")
    for c in boot.get("consoleErrors", []):
        lines.append(f"console.error: {c['msg']}{_at(c)}")
    for d in boot.get("dataErrors", []):
        lines.append(f"scripts/data を読めない: {d}")
    if lines:
        out.append(("（起動: import → startup → worldLoad）", lines))
    if res.get("fileError"):
        fe = res["fileError"]
        out.append(("（テストファイルの読み込み）", [fe["msg"]] + [f"    at {s}" for s in fe.get("stack", [])[:3]]))
    for t in res.get("tests", []):
        if t["ok"]:
            continue
        lines = []
        if t.get("error"):
            e = t["error"]
            lines.append(f"{e['name']}: {e['msg']}" + (f"（{', '.join(e['stack'][:2])}）" if e.get("stack") else ""))
        for v in t.get("violations", []):
            lines.append(f"違反 {v['kind']}: {v['msg']}{_at(v)}")
        for e in t.get("errors", []):
            lines.append(f"捕まらない例外（{e['where']}）: {e['msg']}" + (f"（{', '.join(e['stack'][:2])}）" if e.get("stack") else ""))
        for c in t.get("consoleErrors", []):
            lines.append(f"console.error: {c['msg']}{_at(c)}")
        out.append((t["name"], lines))
    left = res.get("leftoverViolations") or []
    if left:
        out.append(("（テストの外）", [f"違反 {v['kind']}: {v['msg']}{_at(v)}" for v in left]))
    return out


def file_ok(res: dict) -> bool:
    return not failures(res)


def print_file(res: dict, label: str, verbose: bool, limit: int = 40) -> None:
    tests = res.get("tests", [])
    n_ok = sum(1 for t in tests if t["ok"])
    fails = failures(res)
    mark = "OK" if not fails else "FAIL"
    peak = f"、パーティクル最大 {res['maxPerTick']}/tick" if res.get("maxPerTick") else ""
    print(f"  [test] {mark} {label}: {n_ok} / {len(tests)}（{res.get('seconds', 0):.1f} 秒{peak}）")
    if verbose:
        for t in tests:
            print(f"      {'ok  ' if t['ok'] else 'FAIL'} {t['name']}（{t['ms']} ms）")
    shown = 0
    for title, lines in fails:
        print(f"      FAIL {title}")
        for ln in lines[:12]:
            print(f"          {ln}")
        if len(lines) > 12:
            print(f"          …ほか {len(lines) - 12} 行")
        shown += 1
        if shown >= limit:
            print(f"      …ほか {len(fails) - shown} 件")
            break


def merge_usage(results: list) -> dict:
    total: dict = {}
    for r in results:
        for k, v in (r.get("usage") or {}).items():
            if isinstance(v, dict):
                d = total.setdefault(k, {})
                for kk, n in v.items():
                    d[kk] = d.get(kk, 0) + n
            elif isinstance(v, (int, float)):
                total[k] = total.get(k, 0) + v
    return total


def coverage(usage: dict, defs: dict) -> dict:
    """RP / BP にある nr: の演出のうち、テストで一度でも使われたもの。"""
    def cov(have, used_keys):
        have = sorted(have)
        hit = [x for x in have if x in used_keys]
        return {"used": len(hit), "total": len(have), "unused": [x for x in have if x not in used_keys]}
    return {
        "particles": cov([p for p in defs["particles"] if p.startswith("nr:")], usage.get("particles", {})),
        "sounds": cov([s for s in defs["sounds"] if s.startswith("nr.")], usage.get("sounds", {})),
        "animations": cov([a for a in defs["animations"] if a.startswith("animation.nr.")], usage.get("anims", {})),
        "entities": cov([e for e in defs["entities"] if e.startswith("nr:")], usage.get("spawned", {})),
        "structures": cov(list(defs["structures"]), usage.get("structures", {})),
    }


def print_extras(results: list) -> None:
    lim: dict = {}
    notes: dict = {}
    warns = 0
    samples = []
    for r in results:
        for k, n in (r.get("limitations") or {}).items():
            lim[k] = lim.get(k, 0) + n
        for k, n in (r.get("notices") or {}).items():
            notes[k] = notes.get(k, 0) + n
        warns += r.get("warns", 0)
        samples += [w["msg"] for w in r.get("warnSamples", [])]
    if lim:
        print("  [test] 偽物の限界（アドオンが呼んだが偽物に無い。test_fakes/server.js に足すこと）: "
              + ", ".join(f"{k} ×{n}" for k, n in sorted(lim.items())))
    if notes:
        print("  [test] 注意: " + "; ".join(f"{k} ×{n}" for k, n in sorted(notes.items())[:12]))
    if warns:
        print(f"  [test] console.warn {warns} 件（例: {' / '.join(s[:80] for s in samples[:3])}）")


# ===========================================================================
#  自己テスト（小さな偽アドオンと、わざと壊した偽アドオン）
# ===========================================================================
def _nbt_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


def _nbt(tag: int, v) -> bytes:
    """little-endian NBT の中身。compound は {名前: (タグ, 値)}、list は (要素のタグ, [値...])。"""
    if tag == 1:
        return struct.pack("<b", int(v))
    if tag == 3:
        return struct.pack("<i", v)
    if tag == 8:
        return _nbt_str(v)
    if tag == 9:
        et, items = v
        return struct.pack("<bi", et, len(items)) + b"".join(_nbt(et, x) for x in items)
    if tag == 10:
        return b"".join(struct.pack("<b", t) + _nbt_str(k) + _nbt(t, x) for k, (t, x) in v.items()) + b"\x00"
    raise ValueError(tag)


def write_mcstructure(path: str, size, palette, indices) -> None:
    """自己テスト用の小さな .mcstructure（validate_nr.read_mcstructure で読み戻せる形）。"""
    def st(states):
        return {k: ((1, v) if isinstance(v, bool) else (3, v) if isinstance(v, int) else (8, str(v)))
                for k, v in states.items()}
    root = {
        "format_version": (3, 1),
        "size": (9, (3, list(size))),
        "structure": (10, {
            "block_indices": (9, (9, [(3, list(indices)), (3, [-1] * len(indices))])),
            "entities": (9, (10, [])),
            "palette": (10, {"default": (10, {
                "block_palette": (9, (10, [{"name": (8, n), "states": (10, st(s)), "version": (3, 18163713)}
                                           for n, s in palette])),
                "block_position_data": (10, {})})}),
        }),
        "structure_world_origin": (9, (3, [0, 0, 0])),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"\x0a" + _nbt_str("") + _nbt(10, root))


_LIMB = ["intact", "wounded", "broken", "cut_lower", "cut_upper"]


def _enum(values, default=None):
    return {"type": "enum", "values": values, "default": default or values[0], "client_sync": True}


def _int(lo, hi, default=0):
    return {"type": "int", "range": [lo, hi], "default": default, "client_sync": True}


def _despawn_parts():
    return ({"nr:despawn": {"minecraft:instant_despawn": {}}},
            {"nr:despawn": {"add": {"component_groups": ["nr:despawn"]}}})


def mini_pack_docs() -> dict:
    """自己テストの小さなパック {相対パス: JSON}（DESIGN.md の形に合わせた縮小版）。"""
    dg, de = _despawn_parts()
    zombie = {"format_version": "1.21.120", "minecraft:entity": {
        "description": {"identifier": "nr:z_test", "is_spawnable": True, "is_summonable": True, "properties": {
            "nr:head": _enum(["intact", "wounded", "jawless", "cracked", "severed", "crushed"]),
            "nr:arm_r": _enum(_LIMB), "nr:arm_l": _enum(_LIMB), "nr:leg_r": _enum(_LIMB), "nr:leg_l": _enum(_LIMB),
            "nr:torso": _enum(["intact", "slashed", "gutted", "halved"]),
            "nr:blood": _int(0, 3), "nr:burn": _int(0, 3), "nr:shock": _int(0, 1), "nr:armor": _int(0, 3, 3),
            "nr:state": _enum(["normal", "crawl", "climb", "stagger", "down", "special", "dead"]),
            "nr:pose": _int(0, 7), "nr:ability": _int(0, 7), "nr:variant": _int(0, 3)}},
        "component_groups": {
            "nr:dead": {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                        "minecraft:collision_box": {"width": 0.6, "height": 0.4}},
            "nr:crawler": {"minecraft:collision_box": {"width": 0.6, "height": 0.6}, "minecraft:movement": {"value": 0.08}},
            "nr:rooted": {"minecraft:movement": {"value": 0.0}},
            "nr:enraged": {"minecraft:movement": {"value": 0.3}},
            **dg},
        "components": {
            "minecraft:health": {"value": 1000, "max": 1000},
            "minecraft:collision_box": {"width": 0.6, "height": 1.9},
            "minecraft:physics": {}, "minecraft:pushable": {"is_pushable": True},
            "minecraft:type_family": {"family": ["nr_zombie", "zombie", "monster", "mob"]},
            "minecraft:movement": {"value": 0.22}},
        "events": {
            "minecraft:entity_spawned": {"set_property": {"nr:variant": "math.random_integer(0, 3)"}},
            "nr:on_death": {"add": {"component_groups": ["nr:dead"]},
                            "set_property": {"nr:state": "dead", "nr:pose": "math.random_integer(0, 7)"}},
            "nr:to_crawl": {"add": {"component_groups": ["nr:crawler"]}, "set_property": {"nr:state": "crawl"}},
            "nr:root_start": {"add": {"component_groups": ["nr:rooted"]}},
            "nr:root_end": {"remove": {"component_groups": ["nr:rooted"]}},
            "nr:enrage": {"add": {"component_groups": ["nr:enraged"]}},
            "nr:calm": {"remove": {"component_groups": ["nr:enraged"]}},
            **de}}}
    gib = {"format_version": "1.21.120", "minecraft:entity": {
        "description": {"identifier": "nr:gib", "is_spawnable": False, "is_summonable": True, "properties": {
            "nr:ztype": _int(0, 63), "nr:part": _int(0, 15), "nr:spin": _int(0, 7), "nr:rest": _int(0, 3),
            "nr:bleed": _int(0, 1), "nr:side": _int(0, 1)}},
        "component_groups": dict(dg),
        "components": {"minecraft:health": {"value": 5, "max": 5}, "minecraft:physics": {},
                       "minecraft:collision_box": {"width": 0.3, "height": 0.3},
                       "minecraft:type_family": {"family": ["nr_gib"]}},
        "events": dict(de)}}
    proj = {"format_version": "1.21.120", "minecraft:entity": {
        "description": {"identifier": "nr:proj_test", "is_spawnable": False, "is_summonable": True},
        "component_groups": dict(dg),
        "components": {"minecraft:projectile": {"on_hit": {"impact_damage": {"damage": 4}, "remove_on_hit": {}},
                                                "gravity": 0.03},
                       "minecraft:physics": {}, "minecraft:collision_box": {"width": 0.25, "height": 0.25}},
        "events": dict(de)}}

    def item(ident, comps):
        return {"format_version": "1.21.120", "minecraft:item": {"description": {"identifier": ident}, "components": comps}}

    def block(ident, comps, states=None, traits=None):
        desc = {"identifier": ident}
        if states:
            desc["states"] = states
        if traits:
            desc["traits"] = traits
        return {"format_version": "1.21.120", "minecraft:block": {"description": desc, "components": comps}}

    def particle(ident):
        return {"format_version": "1.10.0", "particle_effect": {
            "description": {"identifier": ident, "basic_render_parameters": {
                "material": "particles_alpha", "texture": "textures/particle/particles"}},
            "components": {"minecraft:emitter_rate_instant": {"num_particles": 1},
                           "minecraft:particle_lifetime_expression": {"max_lifetime": 0.5}}}}

    def snd(name):
        return {"category": "hostile", "sounds": [{"name": f"sounds/nr/test/{name}", "volume": 1.0}]}

    def anim():
        return {"animation_length": 0.5, "bones": {"head": {"rotation": {"0.0": [0, 0, 0], "0.25": [-10, 0, 0],
                                                                         "0.5": [0, 0, 0]}}}}
    return {
        "BP/entities/z_test.json": zombie,
        "BP/entities/gib.json": gib,
        "BP/entities/proj_test.json": proj,
        "BP/items/w_test.json": item("nr:w_test", {
            "minecraft:max_stack_size": 1, "minecraft:durability": {"max_durability": 50}, "minecraft:damage": 7,
            "nr:test_weapon": {"dtype": "slash", "weight": "medium"}}),
        "BP/items/test_terminal.json": item("nr:test_terminal", {"minecraft:max_stack_size": 1}),
        "BP/items/test_pebble.json": item("nr:test_pebble", {"minecraft:max_stack_size": 16}),
        "BP/blocks/test_trap.json": block("nr:test_trap", {
            "minecraft:tick": {"interval_range": [10, 10], "looping": True}, "nr:test_trap": {"damage": 2}}),
        "BP/blocks/test_lamp.json": block("nr:test_lamp", {"minecraft:light_emission": 15}),
        "BP/blocks/test_crate.json": block("nr:test_crate", {}, states={"nr:open": [False, True]},
                                           traits={"minecraft:placement_direction": {
                                               "enabled_states": ["minecraft:cardinal_direction"]}}),
        "RP/particles/test_blood.json": particle("nr:test_blood"),
        "RP/particles/test_spark.json": particle("nr:test_spark"),
        "RP/sounds/sound_definitions.json": {"format_version": "1.20.20", "sound_definitions": {
            "nr.test.hit": snd("hit"), "nr.test.swing": snd("swing"), "nr.test.ui": snd("ui")}},
        "RP/animations/test.animation.json": {"format_version": "1.10.0", "animations": {
            "animation.nr.z.test_react": anim(), "animation.nr.p.test_vault": anim()}},
    }


def write_mini_pack(root: str) -> tuple:
    for relp, doc in mini_pack_docs().items():
        p = os.path.join(root, *relp.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
    # 3x2x3 の小屋: 床が石、(0,1,0) にランプ、ほかは空き（-1）
    size = (3, 2, 3)
    idx = []
    for x in range(3):
        for y in range(2):
            for z in range(3):
                idx.append(0 if y == 0 else 1 if (x, y, z) == (0, 1, 0) else -1)
    write_mcstructure(os.path.join(root, "BP", "structures", "nr", "test_hut.mcstructure"), size,
                      [("minecraft:stone", {}), ("nr:test_lamp", {})], idx)
    return os.path.join(root, "BP"), os.path.join(root, "RP")


NOOP_TEST = 'import { test } from "nr-test";\ntest("noop", () => {});\n'


def _selftest_variants(tmp: str) -> list:
    noop = os.path.join(tmp, "noop.mjs")
    with open(noop, "w", encoding="utf-8") as fh:
        fh.write(NOOP_TEST)
    addon = os.path.join(SELF, "addon")
    return [
        dict(name="good", scripts=addon, tests=[(os.path.join(SELF, "selftest.mjs"), "selftest.mjs"),
                                                (os.path.join(FAKES, "builtin_smoke.mjs"), SMOKE_NAME)]),
        dict(name="bad", scripts=os.path.join(SELF, "addon_bad"),
             tests=[(os.path.join(SELF, "selftest_bad.mjs"), "selftest_bad.mjs")]),
        dict(name="boot_early", entry=os.path.join(SELF, "boot_early.js"), tests=[(noop, "noop.mjs")]),
        dict(name="boot_late", entry=os.path.join(SELF, "boot_late.js"), tests=[(noop, "noop.mjs")]),
        dict(name="boot_import", entry=os.path.join(SELF, "boot_import.js"), tests=[(noop, "noop.mjs")]),
        dict(name="boot_unregistered", scripts=addon, tests=[(noop, "noop.mjs")],
             extra_items={"nr:test_orphan": {"components": {"nr:nobody": {}}, "custom": {"nr:nobody": {}}}}),
    ]


def _check_bad_test(t: dict) -> str:
    """bad[種類] のテストが期待どおりに落ちたか。問題があれば説明、無ければ空。"""
    m = re.match(r"bad\[(\w+)\]", t["name"])
    if not m:
        return f"{t['name']}: 名前が bad[種類] の形でない"
    kind = m.group(1)
    if t["ok"]:
        return f"{t['name']}: 失敗するはずが通った"
    err = t.get("error") or {}
    ok = {
        "error": bool(t.get("errors")),
        "console": bool(t.get("consoleErrors")),
        "expect": err.get("name") == "ExpectError",
        "throw": "わざと" in err.get("msg", ""),
        "stuck": "止まった" in err.get("msg", ""),
    }.get(kind)
    if ok is None:
        ok = any(v["kind"] == kind for v in t.get("violations", []))
    if not ok:
        got = [v["kind"] for v in t.get("violations", [])] + (["error"] if t.get("errors") else []) + \
              ([err.get("name")] if err else [])
        return f"{t['name']}: 落ち方が違う（期待 {kind}、実際 {', '.join(got) or 'なし'}）"
    return ""


def run_selftest(node: str, api: dict, ui_api: dict, tmp: str, workers: int, verbose: bool):
    """偽物の自己テスト。戻り値 (ok, 問題の行, 結果の一覧, 数)。"""
    modules = fake_modules(api)
    bp, rp = write_mini_pack(os.path.join(tmp, "selfpack"))
    jobs, meta = [], []
    for v in _selftest_variants(tmp):
        work = os.path.join(tmp, "self_" + v["name"])
        notes: list = []
        defs = build_defs(bp, rp, work, notes)
        defs["items"].update(v.get("extra_items", {}))
        rels = prepare_work(work, scripts_src=v.get("scripts"), entry_file=v.get("entry"), tests=v["tests"],
                            defs=defs, api=api, ui_api=ui_api, modules=modules)
        for r in rels:
            jobs.append(dict(work=work, test=r, timeout=SELF_TIMEOUT, tag=f"self:{v['name']}", verbose=False))
            meta.append(v["name"])
    results = run_all(node, jobs, workers)
    problems, counts = [], {"good": 0, "bad": 0, "boot": 0}
    for name, res in zip(meta, results):
        label = f"自己テスト {name} {res['file']}"
        if res.get("crash"):
            problems.append(f"{label}: {res['crash']}")
            problems += [f"    {ln}" for ln in res.get("output", [])]
            continue
        boot = res["boot"]
        vk = [v["kind"] for v in boot.get("violations", [])]
        if name == "good":
            for title, lines in failures(res):
                problems.append(f"{label}: FAIL {title}")
                problems += [f"    {ln}" for ln in lines[:10]]
            if len(res["tests"]) != len(res["names"]) or not res["tests"]:
                problems.append(f"{label}: テストが {len(res['tests'])} / {len(res['names'])} しか走らない")
            counts["good"] += sum(1 for t in res["tests"] if t["ok"])
        elif name == "bad":
            if not boot.get("ok"):
                problems.append(f"{label}: 起動で落ちた（{failures(res)[:1]}）")
            for t in res["tests"]:
                msg = _check_bad_test(t)
                if msg:
                    problems.append(f"{label}: {msg}")
                else:
                    counts["bad"] += 1
            if len(res["tests"]) != len(res["names"]):
                problems.append(f"{label}: テストが {len(res['tests'])} / {len(res['names'])} しか走らない")
        else:
            want = {
                "boot_early": lambda: vk.count("early") >= 2,
                "boot_late": lambda: vk.count("startup") >= 3,
                "boot_import": lambda: any("AABB" in e.get("msg", "") for e in boot.get("errors", [])),
                "boot_unregistered": lambda: any("nr:nobody" in v["msg"] for v in boot.get("violations", [])),
            }[name]()
            if boot.get("ok") or not want:
                problems.append(f"{label}: 起動の失敗を見つけられない（違反 {vk}、例外 "
                                f"{[e.get('msg', '')[:60] for e in boot.get('errors', [])]}）")
            else:
                counts["boot"] += 1
        if verbose:
            print_file(res, label, True)
    return (not problems), problems, results, counts


# ===========================================================================
#  main
# ===========================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NIGHT RUNNER の手書き JS を偽の @minecraft/server で走らせてテストする")
    ap.add_argument("-k", dest="filt", default="", help="名前（かファイル名）にこれを含むテストだけ（自己テストは飛ばす）")
    ap.add_argument("--file", help="このテストファイルだけ（tools/nightrunner/ か今のフォルダからの相対）")
    ap.add_argument("--keep", action="store_true", help="作業フォルダを消さない")
    ap.add_argument("-v", "--verbose", action="store_true", help="テストごとの結果とアドオンの console.* を出す（1 並列）")
    ap.add_argument("--strict", action="store_true", help="main.js が無ければ失敗（最終・CI 用）")
    ap.add_argument("--json", help="結果を JSON に書く")
    ap.add_argument("--selftest", action="store_true", help="偽物の自己テストだけ")
    ap.add_argument("--no-selftest", action="store_true", help="自己テストを飛ばす")
    ap.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1), help="同時に走らせる node の数")
    ap.add_argument("--timeout", type=int, default=FILE_TIMEOUT, help="1 ファイルの上限（秒）")
    args = ap.parse_args(argv)

    if os.environ.get("NR_SKIP_TESTS") == "1":
        print("  [test] NR_SKIP_TESTS=1 なので挙動テストは飛ばす（Node が使えない時だけ）")
        return 0
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        print("  [test] node が見つからない（Node.js 18 以上を入れること）", file=sys.stderr)
        return 2
    workers = 1 if args.verbose else max(1, args.jobs)
    t_start = time.time()
    api = parse_dts(os.path.join(TYPINGS, "server", "index.d.ts"))
    ui_api = parse_dts(os.path.join(TYPINGS, "server-ui", "index.d.ts"))
    bad = api_problems(api, ui_api)
    if bad:
        for b in bad:
            print(f"  [test] d.ts を読めない: {b}", file=sys.stderr)
        return 2

    os.makedirs(SCRATCH, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="nr_test_", dir=SCRATCH)
    report = {"ok": True, "selftest": None, "files": [], "usage": {}, "coverage": {}}
    failed = False
    main_js = os.path.join(SCRIPTS, "main.js")
    has_main = os.path.isfile(main_js)
    try:
        # ---- 自己テスト ----
        do_self = args.selftest or (not args.file and not args.no_selftest and (not args.filt or not has_main))
        if do_self:
            t0 = time.time()
            ok, problems, sres, counts = run_selftest(node, api, ui_api, tmp, workers, args.verbose)
            report["selftest"] = {"ok": ok, "problems": problems, "counts": counts}
            if ok:
                print(f"  [test] 自己テスト OK: 正しい偽アドオンで {counts['good']} 件通過、壊れた偽アドオンで "
                      f"{counts['bad']} 件・起動 {counts['boot']} 種の失敗を検出（{time.time() - t0:.1f} 秒）")
            else:
                failed = True
                print(f"  [test] 自己テスト FAIL（偽物 test_fakes/*.js の不具合）: {len(problems)} 件")
                for p in problems[:60]:
                    print(f"      {p}")
        if args.selftest:
            return finish(report, failed, args, tmp, t_start)

        # ---- アドオンのテスト ----
        if not has_main:
            msg = f"{rel(main_js)} がまだ無い"
            if args.strict:
                print(f"  [test] FAIL {msg}（--strict）")
                failed = True
            else:
                print(f"  [test] {msg}ので、アドオンのテストは飛ばす（自己テストだけ。OK）")
                if not args.file:
                    return finish(report, failed, args, tmp, t_start)
        notes: list = []
        work = os.path.join(tmp, "addon")
        defs = build_defs(BP, RP, work, notes)
        if args.file:
            src = args.file if os.path.isabs(args.file) else next(
                (c for c in (os.path.join(HERE, args.file), os.path.abspath(args.file), os.path.join(TESTS_DIR, args.file))
                 if os.path.isfile(c)), None)
            if not src or not os.path.isfile(src):
                print(f"  [test] --file {args.file} が見つからない", file=sys.stderr)
                return 2
            helpers = [t for t in user_tests() if not t[1].endswith(".mjs")]
            tests = helpers + [(src, os.path.basename(src))]
        else:
            tests = [(os.path.join(FAKES, "builtin_smoke.mjs"), SMOKE_NAME)] + user_tests()
        rels = prepare_work(work, scripts_src=SCRIPTS if os.path.isdir(SCRIPTS) else None, tests=tests, defs=defs,
                            api=api, ui_api=ui_api, modules=fake_modules(api))
        for n in notes:
            print(f"  [test] 注意: {n}")
        jobs = [dict(work=work, test=r, filt=args.filt, verbose=args.verbose, timeout=args.timeout, tag="addon",
                     entry="scripts/main.js" if has_main else "-") for r in rels]
        results = run_all(node, jobs, workers)
        ran = 0
        for res in results:
            label = "組み込み smoke" if res["file"].endswith(SMOKE_NAME) else res["file"]
            if args.filt and not res.get("tests") and not failures(res):
                continue
            ran += len(res.get("tests", []))
            print_file(res, label, args.verbose)
            if not file_ok(res):
                failed = True
            report["files"].append(res)
        if args.filt and not ran:
            print(f"  [test] -k {args.filt} に当たるテストが無い")
        usage = merge_usage(results)
        report["usage"] = usage
        report["coverage"] = coverage(usage, defs)
        cv = report["coverage"]
        print("  [test] 使った演出（RP / BP にある nr: のうち）: " + "、".join(
            f"{k} {v['used']}/{v['total']}" for k, v in cv.items() if v["total"]))
        peak = max((r.get("maxPerTick", 0) for r in results), default=0)
        if peak:
            print(f"  [test] 1 tick のパーティクルの最大 {peak}（予算 {PARTICLE_BUDGET}）")
        print_extras(results)
        n_tests = sum(len(r.get("tests", [])) for r in results)
        n_ok = sum(1 for r in results for t in r.get("tests", []) if t["ok"])
        print(f"  [test] {'OK' if not failed else 'FAIL'}: {n_ok} / {n_tests} テスト（{len(results)} ファイル）")
        return finish(report, failed, args, tmp, t_start)
    finally:
        if args.keep:
            print(f"  [test] 作業フォルダ: {rel(tmp)}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def finish(report: dict, failed: bool, args, tmp: str, t_start: float) -> int:
    report["ok"] = not failed
    report["seconds"] = round(time.time() - t_start, 2)
    if args.json:
        path = os.path.abspath(args.json)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print(f"  [test] 結果: {rel(path)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
