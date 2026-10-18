// 自動生成（tools/astro/gen_astro_ui.py）。手で編集しない。説明は tools/astro/UI.md
// HUD のグリフ: RP の font/glyph_EA.png（U+EA00–EAFF、16 px セル = 約 16 GUI px）と
//               font/glyph_EB.png（U+EB00–EBFF、32 px セル、タイトル・カットイン用）。
// § の色コードはグリフを染めない（惑星ごとに色違いのグリフがある）。グリフの前は §r、§l（太字）を隣に置かない。

export const GLYPH_PAGES = { hud: "EA", art: "EB" };

export const G = {
  emblem: { mercury: "\uEA10", venus: "\uEA20", earth: "\uEA30", mars: "\uEA40", jupiter: "\uEA50", saturn: "\uEA60", uranus: "\uEA70", neptune: "\uEA80", sol: "\uEA90" },
  emblemBig: { mercury: "\uEB00", venus: "\uEB01", earth: "\uEB02", mars: "\uEB03", jupiter: "\uEB04", saturn: "\uEB05", uranus: "\uEB06", neptune: "\uEB07", sol: "\uEB08" },
  energy: {
    mercury: { full: "\uEA11", half: "\uEA12", empty: "\uEA13", capL: "\uEA00", capR: "\uEA01" },
    venus: { full: "\uEA21", half: "\uEA22", empty: "\uEA23", capL: "\uEA00", capR: "\uEA01" },
    earth: { full: "\uEA31", half: "\uEA32", empty: "\uEA33", capL: "\uEA00", capR: "\uEA01" },
    mars: { full: "\uEA41", half: "\uEA42", empty: "\uEA43", capL: "\uEA00", capR: "\uEA01" },
    jupiter: { full: "\uEA51", half: "\uEA52", empty: "\uEA53", capL: "\uEA00", capR: "\uEA01" },
    saturn: { full: "\uEA61", half: "\uEA62", empty: "\uEA63", capL: "\uEA00", capR: "\uEA01" },
    uranus: { full: "\uEA71", half: "\uEA72", empty: "\uEA73", capL: "\uEA00", capR: "\uEA01" },
    neptune: { full: "\uEA81", half: "\uEA82", empty: "\uEA83", capL: "\uEA00", capR: "\uEA01" },
    sol: { full: "\uEA91", half: "\uEA92", empty: "\uEA93", capL: "\uEA00", capR: "\uEA01" },
  },
  energyLow: { full: "\uEAA0", half: "\uEAA1", empty: "\uEAA2", capL: "\uEAA3", capR: "\uEAA4" },
  nova: { full: "\uEA02", empty: "\uEA03", flow: "\uEA04", capL: "\uEA05", capR: "\uEA06" },
  move: {
    mercury: {
      skill: { ready: "\uEA14", wait: "\uEA18" },
      dash: { ready: "\uEA15", wait: "\uEA19" },
      air: { ready: "\uEA16", wait: "\uEA1A" },
      ult: { ready: "\uEA17", wait: "\uEA1B" },
    },
    venus: {
      skill: { ready: "\uEA24", wait: "\uEA28" },
      dash: { ready: "\uEA25", wait: "\uEA29" },
      air: { ready: "\uEA26", wait: "\uEA2A" },
      ult: { ready: "\uEA27", wait: "\uEA2B" },
    },
    earth: {
      skill: { ready: "\uEA34", wait: "\uEA38" },
      dash: { ready: "\uEA35", wait: "\uEA39" },
      air: { ready: "\uEA36", wait: "\uEA3A" },
      ult: { ready: "\uEA37", wait: "\uEA3B" },
    },
    mars: {
      skill: { ready: "\uEA44", wait: "\uEA48" },
      dash: { ready: "\uEA45", wait: "\uEA49" },
      air: { ready: "\uEA46", wait: "\uEA4A" },
      ult: { ready: "\uEA47", wait: "\uEA4B" },
    },
    jupiter: {
      skill: { ready: "\uEA54", wait: "\uEA58" },
      dash: { ready: "\uEA55", wait: "\uEA59" },
      air: { ready: "\uEA56", wait: "\uEA5A" },
      ult: { ready: "\uEA57", wait: "\uEA5B" },
    },
    saturn: {
      skill: { ready: "\uEA64", wait: "\uEA68" },
      dash: { ready: "\uEA65", wait: "\uEA69" },
      air: { ready: "\uEA66", wait: "\uEA6A" },
      ult: { ready: "\uEA67", wait: "\uEA6B" },
    },
    uranus: {
      skill: { ready: "\uEA74", wait: "\uEA78" },
      dash: { ready: "\uEA75", wait: "\uEA79" },
      air: { ready: "\uEA76", wait: "\uEA7A" },
      ult: { ready: "\uEA77", wait: "\uEA7B" },
    },
    neptune: {
      skill: { ready: "\uEA84", wait: "\uEA88" },
      dash: { ready: "\uEA85", wait: "\uEA89" },
      air: { ready: "\uEA86", wait: "\uEA8A" },
      ult: { ready: "\uEA87", wait: "\uEA8B" },
    },
    sol: {
      skill: { ready: "\uEA94", wait: "\uEA98" },
      dash: { ready: "\uEA95", wait: "\uEA99" },
      air: { ready: "\uEA96", wait: "\uEA9A" },
      ult: { ready: "\uEA97", wait: "\uEA9B" },
    },
  },
  icon: { energy: "\uEAB0", nova: "\uEAB1", revert: "\uEAB2", overheat: "\uEAB3", barrier: "\uEAB4", sync: "\uEAB5", check: "\uEAB6", lock: "\uEAB7", warn: "\uEAB8", pipOn: "\uEAB9", pipOff: "\uEABA", sep: "\uEABB", arrow: "\uEABC" },
  iconBig: { energy: "\uEB20", nova: "\uEB21", revert: "\uEB22", overheat: "\uEB23", barrier: "\uEB24", sync: "\uEB25", check: "\uEB26", lock: "\uEB27", warn: "\uEB28" },
  sync: { full: "\uEA0C", empty: "\uEA0D", capL: "\uEA0E", capR: "\uEA0F" },
  progress: { full: "\uEA07", empty: "\uEA08", half: "\uEA09", capL: "\uEA0A", capR: "\uEA0B" },
  banner: { wingL: "\uEB10", wingR: "\uEB11", divider: "\uEB12", lineL: "\uEB13", lineR: "\uEB14" },
};

/** 各グリフの送り幅（GUI px。実際にはこの後に約 1 px の隙間が入る）。 */
export const WIDTH = new Map([["\uEA00", 4], ["\uEA01", 4], ["\uEA02", 6], ["\uEA03", 6], ["\uEA04", 6], ["\uEA05", 4], ["\uEA06", 4], ["\uEA07", 4], ["\uEA08", 4], ["\uEA09", 4], ["\uEA0A", 3], ["\uEA0B", 3], ["\uEA0C", 3], ["\uEA0D", 3], ["\uEA0E", 2], ["\uEA0F", 2], ["\uEA10", 16], ["\uEA11", 5], ["\uEA12", 5], ["\uEA13", 5], ["\uEA14", 16], ["\uEA15", 16], ["\uEA16", 16], ["\uEA17", 16], ["\uEA18", 16], ["\uEA19", 16], ["\uEA1A", 16], ["\uEA1B", 16], ["\uEA20", 16], ["\uEA21", 5], ["\uEA22", 5], ["\uEA23", 5], ["\uEA24", 16], ["\uEA25", 16], ["\uEA26", 16], ["\uEA27", 16], ["\uEA28", 16], ["\uEA29", 16], ["\uEA2A", 16], ["\uEA2B", 16], ["\uEA30", 16], ["\uEA31", 5], ["\uEA32", 5], ["\uEA33", 5], ["\uEA34", 16], ["\uEA35", 16], ["\uEA36", 16], ["\uEA37", 16], ["\uEA38", 16], ["\uEA39", 16], ["\uEA3A", 16], ["\uEA3B", 16], ["\uEA40", 16], ["\uEA41", 5], ["\uEA42", 5], ["\uEA43", 5], ["\uEA44", 16], ["\uEA45", 16], ["\uEA46", 16], ["\uEA47", 16], ["\uEA48", 16], ["\uEA49", 16], ["\uEA4A", 16], ["\uEA4B", 16], ["\uEA50", 16], ["\uEA51", 5], ["\uEA52", 5], ["\uEA53", 5], ["\uEA54", 16], ["\uEA55", 16], ["\uEA56", 16], ["\uEA57", 16], ["\uEA58", 16], ["\uEA59", 16], ["\uEA5A", 16], ["\uEA5B", 16], ["\uEA60", 16], ["\uEA61", 5], ["\uEA62", 5], ["\uEA63", 5], ["\uEA64", 16], ["\uEA65", 16], ["\uEA66", 16], ["\uEA67", 16], ["\uEA68", 16], ["\uEA69", 16], ["\uEA6A", 16], ["\uEA6B", 16], ["\uEA70", 16], ["\uEA71", 5], ["\uEA72", 5], ["\uEA73", 5], ["\uEA74", 16], ["\uEA75", 16], ["\uEA76", 16], ["\uEA77", 16], ["\uEA78", 16], ["\uEA79", 16], ["\uEA7A", 16], ["\uEA7B", 16], ["\uEA80", 16], ["\uEA81", 5], ["\uEA82", 5], ["\uEA83", 5], ["\uEA84", 16], ["\uEA85", 16], ["\uEA86", 16], ["\uEA87", 16], ["\uEA88", 16], ["\uEA89", 16], ["\uEA8A", 16], ["\uEA8B", 16], ["\uEA90", 16], ["\uEA91", 5], ["\uEA92", 5], ["\uEA93", 5], ["\uEA94", 16], ["\uEA95", 16], ["\uEA96", 16], ["\uEA97", 16], ["\uEA98", 16], ["\uEA99", 16], ["\uEA9A", 16], ["\uEA9B", 16], ["\uEAA0", 5], ["\uEAA1", 5], ["\uEAA2", 5], ["\uEAA3", 4], ["\uEAA4", 4], ["\uEAB0", 9], ["\uEAB1", 9], ["\uEAB2", 9], ["\uEAB3", 9], ["\uEAB4", 9], ["\uEAB5", 9], ["\uEAB6", 9], ["\uEAB7", 9], ["\uEAB8", 9], ["\uEAB9", 5], ["\uEABA", 5], ["\uEABB", 3], ["\uEABC", 4], ["\uEB00", 16], ["\uEB01", 16], ["\uEB02", 16], ["\uEB03", 16], ["\uEB04", 16], ["\uEB05", 16], ["\uEB06", 16], ["\uEB07", 16], ["\uEB08", 16], ["\uEB10", 16], ["\uEB11", 16], ["\uEB12", 16], ["\uEB13", 16], ["\uEB14", 16], ["\uEB20", 16], ["\uEB21", 16], ["\uEB22", 16], ["\uEB23", 16], ["\uEB24", 16], ["\uEB25", 16], ["\uEB26", 16], ["\uEB27", 16], ["\uEB28", 16]]);

const clamp01 = (v) => Math.max(0, Math.min(1, Number(v) || 0));

/**
 * セルを並べたバー。set = {full, half?, empty, capL?, capR?}（G.energy[key] / G.energyLow / G.nova /
 * G.progress / G.sync）。frac = 0..1、cells = セル数。half があれば半セル単位で丸める。
 * 0 より大きければ最低でも半セル（half が無ければ 1 セル）、1 未満なら最後のセルは満たさない。
 * caps = false で両端を付けない。
 */
export function bar(set, frac, cells, caps = true) {
  const f = clamp01(frac);
  const step = set.half ? 0.5 : 1;
  let units = Math.round((f * cells) / step) * step;
  if (f > 0 && units <= 0) units = step;
  if (f < 1 && units >= cells) units = cells - step;
  let s = caps && set.capL ? set.capL : "";
  for (let i = 0; i < cells; i++) {
    s += units >= i + 1 ? set.full : units >= i + 0.5 && set.half ? set.half : set.empty;
  }
  return s + (caps && set.capR ? set.capR : "");
}

/** 星力バー（惑星色。frac < 0.2 で赤と惑星色が 8 tick ごとに入れ替わって点滅）。tick = system.currentTick。 */
export function energyBar(key, frac, cells = 16, tick = 0) {
  const low = clamp01(frac) < 0.2 && Math.floor(tick / 8) % 2 === 0;
  return bar(low ? G.energyLow : G.energy[key] ?? G.energy.mercury, frac, cells);
}

/** 超新星バー。満タンの時は白熱のセル 3 つが左から右へ流れる（4 tick で 1 セル進む）。 */
export function novaBar(frac, cells = 10, tick = 0) {
  if (clamp01(frac) < 1) return bar(G.nova, frac, cells);
  const head = Math.floor(tick / 4) % (cells + 4);
  let s = G.nova.capL;
  for (let i = 0; i < cells; i++) {
    const d = head - i;
    s += d >= 0 && d < 3 ? G.nova.flow : G.nova.full;
  }
  return s + G.nova.capR;
}

/** 変身・解除の進み具合（CORE SYNC n%）。 */
export function progressBar(frac, cells = 20) {
  return bar(G.progress, frac, cells);
}

/** 同調率の XP（次の Lv までの割合）。 */
export function syncBar(frac, cells = 10) {
  return bar(G.sync, frac, cells);
}

/** 同調率 Lv の粒（◆◆◆◇◇）。 */
export function pips(n, max = 5) {
  const k = Math.max(0, Math.min(max, n | 0));
  return G.icon.pipOn.repeat(k) + G.icon.pipOff.repeat(max - k);
}

/** 技アイコン。ready = 使える（明るい枠）／ false = 待ち（灰色に惑星色の芯）。 */
export function moveIcon(key, kind, ready) {
  const m = (G.move[key] ?? G.move.mercury)[kind] ?? G.move.mercury.skill;
  return ready ? m.ready : m.wait;
}

/** グリフと ASCII の幅（GUI px）の目安。日本語は 1 字 9 px として数える。 */
export function textWidth(str) {
  let w = 0;
  const s = String(str).replace(/§./g, "");
  for (const ch of s) {
    const g = WIDTH.get(ch);
    if (g !== undefined) w += g + 1;
    else if (ch === " ") w += 4;
    else if (ch.charCodeAt(0) < 128) w += "il.,:;!'|".includes(ch) ? 2 : "It[]".includes(ch) ? 4 : 6;
    else w += 9;
  }
  return w;
}
