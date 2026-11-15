// 影渡り — 起動とゲームループ。各モジュールの組み立て順と呼び出し順はここが正。
// 契約の詳細は ARCHITECTURE.md を参照。
import * as THREE from 'three';
import { CONFIG, defaultQuality } from './config.js';
import { Events } from './core/events.js';
import { makeRng } from './core/math.js';
import { SaveStore } from './core/save.js';

const params = new URLSearchParams(location.search);
const TEST = params.has('test');            // 自動テスト: 自走ループを止め、debug.step() で進める
const DEBUG = TEST || params.has('debug');

// [名前, パス, export 名]。この順に constructor → init() が呼ばれる。
const MODULES = [
  ['collision', './world/collision.js', 'CollisionWorld'],
  ['city', './world/city.js', 'City'],
  ['sky', './world/sky.js', 'Sky'],
  ['audio', './core/audio.js', 'AudioSystem'],
  ['input', './core/input.js', 'Input'],
  ['fx', './view/fx.js', 'Fx'],
  ['player', './actors/player.js', 'Player'],
  ['npcs', './actors/npcs.js', 'NpcManager'],
  ['combat', './combat/combat.js', 'Combat'],
  ['missions', './game/missions.js', 'Missions'],
  ['camRig', './view/camera.js', 'CameraRig'],
  ['hud', './view/hud.js', 'Hud'],
];

const bootEl = document.getElementById('boot');
const bootMsg = document.getElementById('boot-msg');
const bootBar = document.getElementById('boot-bar');

function setLoading(text, progress) {
  if (bootMsg && text != null) bootMsg.textContent = text;
  if (bootBar && progress != null) bootBar.style.transform = `scaleX(${Math.max(0, Math.min(1, progress))})`;
}

function showFatal(err) {
  console.error(err);
  if (!bootEl) return;
  bootEl.hidden = false;
  bootEl.classList.add('is-error');
  setLoading('起動できませんでした。ページを再読み込みしてください。');
  const pre = document.createElement('pre');
  pre.className = 'boot-error';
  pre.textContent = String((err && err.stack) || err);
  bootEl.appendChild(pre);
}

async function loadModule(name, path, exportName) {
  try {
    const m = await import(path);
    if (typeof m[exportName] !== 'function') throw new Error(`${path} に ${exportName} がありません`);
    return { cls: m[exportName], stub: false };
  } catch (err) {
    console.error(`[boot] ${name}: ${path} を読めませんでした。仮モジュールで動かします。`, err);
    const m = await import(`./stubs/${name}.js`);
    return { cls: m[exportName], stub: true, error: String((err && err.stack) || err) };
  }
}

function loadSettings(store) {
  const base = {
    quality: params.get('quality') || defaultQuality(),
    sensitivity: 1,
    invertY: false,
    viewMode: 'third',
    sfxVolume: 0.8,
    musicVolume: 0.5,
    showFps: false,
    autoParkour: true,
    vibration: true,
  };
  const saved = TEST ? null : store.loadSettings();
  const s = { ...base, ...(saved || {}) };
  if (params.get('quality')) s.quality = params.get('quality');
  if (!CONFIG.render.quality[s.quality]) s.quality = 'medium';
  if (params.get('view') === 'first') s.viewMode = 'first';
  return s;
}

async function boot(hotData = {}) {
  setLoading('街を描いています…', 0.02);
  const seed = Number(params.get('seed')) || CONFIG.seed;
  const saveStore = new SaveStore(TEST);
  const settings = loadSettings(saveStore);
  const q0 = CONFIG.render.quality[settings.quality];

  const canvas = document.getElementById('view');
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: q0.antialias,
    powerPreference: 'high-performance',
    preserveDrawingBuffer: TEST,
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = q0.shadows;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(CONFIG.render.fov, innerWidth / innerHeight, CONFIG.render.near, CONFIG.render.far);
  scene.add(camera); // 一人称の手元モデルはカメラの子にする

  const game = {
    THREE,
    cfg: CONFIG,
    params,
    isTest: TEST,
    isDebug: DEBUG,
    isTouch: matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window,
    events: new Events(),
    rng: makeRng(seed),
    seed,
    clock: { time: 0, realTime: 0, dt: 0, realDt: 0, timeScale: 1, frame: 0 },
    settings,
    state: 'boot',
    saveStore,
    renderer,
    scene,
    camera,
    canvas,
    errors: [],
    fallbacks: [],
    stats: { fps: 60, frameMs: 16, drawCalls: 0, triangles: 0, pixelRatio: 1 },
    dynScale: 1,
    setLoading,
  };
  game.quality = () => CONFIG.render.quality[game.settings.quality];
  window.__game = game;

  // ---- モジュールの読み込みと組み立て ----
  const loaded = [];
  for (let i = 0; i < MODULES.length; i++) {
    const [name, path, exp] = MODULES[i];
    setLoading(null, 0.05 + 0.25 * (i / MODULES.length));
    const r = await loadModule(name, path, exp);
    if (r.stub) game.fallbacks.push({ name, error: r.error });
    loaded.push([name, r.cls]);
  }
  for (const [name, Cls] of loaded) game[name] = new Cls(game);
  for (let i = 0; i < loaded.length; i++) {
    const [name] = loaded[i];
    setLoading(null, 0.3 + 0.65 * (i / loaded.length));
    await game[name].init?.();
  }

  // ---- 状態の切り替え ----
  game.setState = (to) => {
    const from = game.state;
    if (from === to) return;
    game.state = to;
    game.events.emit('state:changed', { from, to });
  };
  game.collectSave = () => ({
    missions: game.missions.saveState?.() ?? null,
    player: game.player.saveState?.() ?? null,
    dayTime: game.sky.dayTime ?? null,
  });
  game.saveNow = () => {
    if (game.state === 'title' || game.state === 'boot') return false;
    return saveStore.store(game.collectSave());
  };
  const enterWorld = (data) => {
    game.npcs.reset?.();
    game.missions.loadState?.(data?.missions ?? null);
    if (data?.player) game.player.loadState?.(data.player);
    const spawn = data ? game.missions.respawnPoint?.() ?? game.city.spawnPoints.player : game.city.spawnPoints.player;
    game.player.spawnAt(spawn);
    if (data?.dayTime != null) game.sky.setDayTime?.(data.dayTime);
    game.camRig.snapBehindPlayer?.();
    game.setState('playing');
  };
  game.startNewGame = () => {
    enterWorld(null);
    game.events.emit('game:started', { fresh: true });
    game.saveNow();
  };
  game.hasSave = () => saveStore.hasSave();
  game.continueGame = (data) => {
    const d = data || saveStore.load();
    if (!d) return game.startNewGame();
    enterWorld(d);
    game.events.emit('game:started', { fresh: false });
  };
  game.respawn = () => {
    const p = game.missions.respawnPoint?.() ?? game.city.spawnPoints.player;
    game.npcs.calmDown?.();
    game.player.respawn(p);
    game.camRig.snapBehindPlayer?.();
    game.setState('playing');
    game.events.emit('player:respawn', {});
  };
  game.pause = () => game.state === 'playing' && game.setState('paused');
  game.resume = () => (game.state === 'paused' || game.state === 'map') && game.setState('playing');
  game.openMap = () => (game.state === 'playing' || game.state === 'paused') && game.setState('map');
  game.toTitle = () => {
    game.saveNow();
    game.setState('title');
  };
  game.applySettings = (partial) => {
    const prev = { ...game.settings };
    Object.assign(game.settings, partial);
    if (!TEST) saveStore.storeSettings(game.settings);
    if (prev.quality !== game.settings.quality) {
      const q = game.quality();
      renderer.shadowMap.enabled = q.shadows;
      scene.traverse((o) => {
        if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => (m.needsUpdate = true));
      });
      game.dynScale = 1;
      resize();
    }
    if (prev.viewMode !== game.settings.viewMode) game.camRig.setMode?.(game.settings.viewMode);
    game.events.emit('settings:changed', { prev, settings: game.settings });
  };
  game.vibrate = (ms) => {
    if (!game.settings.vibration) return;
    try {
      navigator.vibrate?.(ms);
    } catch {
      /* 対応していない端末 */
    }
  };
  game.toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
      await screen.orientation?.lock?.('landscape').catch(() => {});
    } catch {
      /* 全画面に対応していない（iPhone の Safari など） */
    }
  };
  let wakeLock = null;
  game.requestWakeLock = async () => {
    try {
      wakeLock = await navigator.wakeLock?.request('screen');
    } catch {
      wakeLock = null;
    }
  };

  // 進行が変わる出来事で自動保存
  for (const ev of ['tower:synced', 'contract:completed', 'chest:opened', 'collectible:picked', 'upgrade:bought', 'race:finished']) {
    game.events.on(ev, () => game.saveNow());
  }

  // ---- 画面サイズ ----
  function resize() {
    const w = innerWidth, h = innerHeight;
    const q = game.quality();
    const pr = Math.max(CONFIG.render.minPixelRatio, Math.min(devicePixelRatio || 1, q.pixelRatio) * game.dynScale);
    game.stats.pixelRatio = pr;
    renderer.setPixelRatio(pr);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    game.events.emit('resize', { width: w, height: h });
  }
  game.resize = resize;
  addEventListener('resize', resize);
  addEventListener('orientationchange', () => setTimeout(resize, 200));
  resize();

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      game.pause();
      game.saveNow();
    } else if (wakeLock === null && game.state === 'playing') game.requestWakeLock();
  });
  // スクロール・ピンチ拡大・長押しメニューを止める
  const stop = (e) => e.preventDefault();
  document.addEventListener('touchmove', stop, { passive: false });
  document.addEventListener('gesturestart', stop);
  document.addEventListener('contextmenu', stop);
  document.addEventListener('dblclick', stop);

  // ---- 1 フレーム ----
  const seen = new Set();
  function safe(name, fn) {
    try {
      fn();
    } catch (err) {
      const key = `${name}:${err && err.message}`;
      if (!seen.has(key)) {
        seen.add(key);
        console.error(`[${name}]`, err);
        if (game.errors.length < 50) game.errors.push({ module: name, message: String(err && err.message), stack: String(err && err.stack) });
      }
    }
  }

  function frame(rawDt) {
    const real = Math.min(Math.max(rawDt, 0), CONFIG.time.maxDt);
    const c = game.clock;
    c.realDt = real;
    c.realTime += real;
    let ts = 1;
    safe('fx', () => (ts = game.fx.computeTimeScale ? game.fx.computeTimeScale(real) : 1));
    c.timeScale = ts;
    const dt = real * ts;
    c.dt = dt;
    const sim = game.state === 'playing' || game.state === 'dead';

    safe('input', () => game.input.update(real));
    if (sim) {
      c.time += dt;
      safe('player', () => game.player.update(dt));
      safe('combat', () => game.combat.update(dt));
      safe('npcs', () => game.npcs.update(dt));
      safe('missions', () => game.missions.update(dt));
    }
    safe('city', () => game.city.update(real));
    safe('sky', () => game.sky.update(sim ? dt : 0));
    safe('fx', () => game.fx.update(sim ? dt : real));
    safe('camRig', () => game.camRig.update(real));
    safe('audio', () => game.audio.update(real));
    safe('hud', () => game.hud.update(real));
    c.frame++;
  }

  function render() {
    renderer.render(scene, camera);
    game.stats.drawCalls = renderer.info.render.calls;
    game.stats.triangles = renderer.info.render.triangles;
  }

  // ---- テスト・デバッグ用の窓口 ----
  game.debug = {
    step(n = 1, dt = 1 / 60) {
      for (let i = 0; i < n; i++) frame(dt);
      return game.debug.snapshot();
    },
    render,
    frame,
    snapshot() {
      const p = game.player;
      const list = game.npcs.list || [];
      return {
        state: game.state,
        frame: game.clock.frame,
        time: +game.clock.time.toFixed(3),
        player: p.position
          ? {
              x: +p.position.x.toFixed(3),
              y: +p.position.y.toFixed(3),
              z: +p.position.z.toFixed(3),
              yaw: +(p.yaw || 0).toFixed(3),
              state: p.state,
              hp: p.hp,
              onGround: p.onGround,
            }
          : null,
        cam: { mode: game.camRig.mode, yaw: game.camRig.yaw, pitch: game.camRig.pitch },
        npcs: {
          total: list.length,
          alive: list.filter((n) => n.alive).length,
          alerted: list.filter((n) => n.alive && n.state === 'combat').length,
        },
        stats: { ...game.stats },
        errors: game.errors.map((e) => `${e.module}: ${e.message}`),
        fallbacks: game.fallbacks.map((f) => f.name),
      };
    },
    inject(partial) {
      game.input.setOverride?.(partial);
    },
    clearInject() {
      game.input.setOverride?.(null);
    },
    teleport(x, y, z, yaw) {
      game.player.teleport(new THREE.Vector3(x, y, z), yaw);
      game.camRig.snapBehindPlayer?.();
    },
  };

  // ---- 開始 ----
  game.setState('title');
  if (bootEl) bootEl.hidden = true;
  if (hotData && hotData.save) game.continueGame(hotData.save);
  else if (TEST || params.has('skipTitle')) {
    if (params.get('continue') && game.hasSave()) game.continueGame();
    else game.startNewGame();
  }
  window.claude?.hot?.snapshot?.(() => (game.state === 'title' ? {} : { save: game.collectSave() }));

  game.ready = true;
  game.events.emit('game:ready', {});

  // 自動保存
  setInterval(() => game.state === 'playing' && game.saveNow(), 30000);

  if (TEST && !params.has('live')) {
    render();
    return game;
  }

  // ---- 自走ループ（fps 計測と描画解像度の自動調整つき） ----
  let last = performance.now();
  let acc = 0, frames = 0, low = 0, high = 0;
  function loop(now) {
    const raw = (now - last) / 1000;
    last = now;
    frame(raw);
    safe('render', render);
    acc += raw;
    frames++;
    if (acc >= 1) {
      const fps = frames / acc;
      game.stats.fps = Math.round(fps);
      game.stats.frameMs = +(1000 / fps).toFixed(1);
      acc = 0;
      frames = 0;
      if (CONFIG.render.dynamicResolution && game.state === 'playing') {
        if (fps < 38) {
          low++;
          high = 0;
        } else if (fps > 56) {
          high++;
          low = 0;
        } else {
          low = high = 0;
        }
        if (low >= 2 && game.dynScale > 0.55) {
          game.dynScale = Math.max(0.55, game.dynScale - 0.15);
          low = 0;
          resize();
        } else if (high >= 6 && game.dynScale < 1) {
          game.dynScale = Math.min(1, game.dynScale + 0.1);
          high = 0;
          resize();
        }
      }
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
  return game;
}

const start = (data) => boot(data || {}).catch(showFatal);
if (window.claude?.hot?.ready) window.claude.hot.ready(start);
else start(window.claude?.hot?.data ?? {});
