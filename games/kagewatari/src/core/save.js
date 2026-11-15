// 進行の保存（端末のブラウザ内のみ）。ストレージが使えない環境でも落ちない。
const KEY = 'kagewatari.save.v1';
const SETTINGS_KEY = 'kagewatari.settings.v1';

function read(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export class SaveStore {
  constructor(disabled = false) {
    this.disabled = disabled;
  }
  load() {
    return this.disabled ? null : read(KEY);
  }
  store(data) {
    return this.disabled ? false : write(KEY, { ...data, savedAt: Date.now(), version: 1 });
  }
  clear() {
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* 何もしない */
    }
  }
  hasSave() {
    return !!this.load();
  }
  loadSettings() {
    return this.disabled ? null : read(SETTINGS_KEY);
  }
  storeSettings(s) {
    return this.disabled ? false : write(SETTINGS_KEY, s);
  }
}
