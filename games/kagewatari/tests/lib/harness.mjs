// Playwright でゲームを開き、__game.debug を通して操作するための道具。
import { createRequire } from 'node:module';
import path from 'node:path';
import fs from 'node:fs';
import { startServer, GAME_DIR } from './server.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

export const OUT_DIR = path.join(GAME_DIR, 'tests', 'out');
const THREE_PREFIX = 'https://cdn.jsdelivr.net/npm/three@0.170.0/';
const THREE_DIR = path.join(GAME_DIR, 'node_modules', 'three');

export const VIEWPORTS = {
  phoneLandscape: { width: 844, height: 390, isMobile: true, hasTouch: true },
  phonePortrait: { width: 390, height: 844, isMobile: true, hasTouch: true },
  desktop: { width: 1280, height: 720, isMobile: false, hasTouch: false },
};

export async function launch() {
  if (!fs.existsSync(THREE_DIR)) throw new Error('three がありません。games/kagewatari で `npm install` を実行してください。');
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const { server, port } = await startServer(0);
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  return { browser, server, base: `http://127.0.0.1:${port}/index.html` };
}

// opts: { query: 'seed=1&quality=low', viewport: 'phoneLandscape' | {..}, test: true, scale: 1 }
export async function openGame(env, opts = {}) {
  const vp = typeof opts.viewport === 'object' ? opts.viewport : VIEWPORTS[opts.viewport || 'phoneLandscape'];
  const context = await env.browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: opts.scale || 1,
    isMobile: !!vp.isMobile,
    hasTouch: !!vp.hasTouch,
    locale: 'ja-JP',
  });
  await context.route(THREE_PREFIX + '**', (route) => {
    const rel = route.request().url().slice(THREE_PREFIX.length);
    const file = path.join(THREE_DIR, rel);
    if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: 'missing ' + rel });
    route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(file) });
  });
  await context.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
  const page = await context.newPage();
  const pageErrors = [];
  const consoleErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e && e.stack || e)));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  const q = new URLSearchParams(opts.query || '');
  if (opts.test !== false) q.set('test', '1');
  if (!q.has('quality')) q.set('quality', 'low');
  await page.goto(`${env.base}?${q}`, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__game && window.__game.ready, null, { timeout: opts.timeout || 90000 }).catch(async (e) => {
    const boot = await page.evaluate(() => document.getElementById('boot')?.innerText || '').catch(() => '');
    throw new Error(`ゲームが起動しませんでした: ${boot}\n${pageErrors.join('\n')}\n${consoleErrors.join('\n')}\n${e.message}`);
  });

  const h = {
    page, context, pageErrors, consoleErrors,
    evaluate: (fn, arg) => page.evaluate(fn, arg),
    step: (n = 1, dt = 1 / 60) => page.evaluate(([n, dt]) => window.__game.debug.step(n, dt), [n, dt]),
    snapshot: () => page.evaluate(() => window.__game.debug.snapshot()),
    inject: (input) => page.evaluate((i) => window.__game.debug.inject(i), input),
    clearInject: () => page.evaluate(() => window.__game.debug.clearInject()),
    teleport: (x, y, z, yaw = 0) => page.evaluate(([x, y, z, yaw]) => window.__game.debug.teleport(x, y, z, yaw), [x, y, z, yaw]),
    // 入力を注入したまま n フレーム進める
    hold: async (input, n, dt = 1 / 60) => {
      await page.evaluate((i) => window.__game.debug.inject(i), input);
      return page.evaluate(([n, dt]) => window.__game.debug.step(n, dt), [n, dt]);
    },
    // ボタンを 1 フレーム押して離す
    tap: async (button, base = {}) => {
      await page.evaluate((i) => window.__game.debug.inject(i), { ...base, buttons: { ...(base.buttons || {}), [button]: true } });
      await page.evaluate(() => window.__game.debug.step(1));
      await page.evaluate((i) => window.__game.debug.inject(i), { ...base, buttons: { ...(base.buttons || {}), [button]: false } });
      return page.evaluate(() => window.__game.debug.step(1));
    },
    render: () => page.evaluate(() => window.__game.debug.render()),
    screenshot: async (name) => {
      await page.evaluate(() => window.__game.debug.render());
      const file = path.join(OUT_DIR, `${name}.png`);
      await page.screenshot({ path: file });
      return file;
    },
    close: () => context.close(),
  };
  return h;
}
