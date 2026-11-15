// ゲームのフォルダを配る小さな静的サーバ。`npm run serve` で単独でも動く。
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const GAME_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.md': 'text/plain; charset=utf-8',
};

export function startServer(port = 0) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    let rel = decodeURIComponent(url.pathname);
    if (rel.endsWith('/')) rel += 'index.html';
    // three はローカルの node_modules から配る（CDN に届かない環境でも遊べるように）
    let file;
    if (rel.startsWith('/vendor/three/')) file = path.join(GAME_DIR, 'node_modules/three', rel.slice('/vendor/three/'.length));
    else file = path.join(GAME_DIR, rel);
    if (!file.startsWith(GAME_DIR)) { res.writeHead(403); return res.end(); }
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404); return res.end('not found'); }
      let body = data;
      // 単独で遊ぶ時は import map を手元の three に向け直す
      if (rel === '/index.html' && url.searchParams.has('local')) {
        body = Buffer.from(data.toString().replaceAll('https://cdn.jsdelivr.net/npm/three@0.170.0/', '/vendor/three/'));
      }
      res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
      res.end(body);
    });
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve({ server, port: server.address().port })));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT) || 8642;
  startServer(port).then(() => console.log(`http://localhost:${port}/?local  （three は手元から配る）`));
}
