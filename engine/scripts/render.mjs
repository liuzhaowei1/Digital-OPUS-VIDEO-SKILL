#!/usr/bin/env node
// Offline renderer (Node port of mexicat/pdoom-video's Bun script). Drives the app in headless Chromium
// (?export=1) on the GPU and writes stills, contact sheets or an mp4.
//   gpu:     node scripts/render.mjs gpu                      (prints the WebGL renderer: should name your GPU, not SwiftShader)
//   stills:  node scripts/render.mjs stills --t 1.5,23,40.2 [--only id1,id2] [--out dir]
//   sheet:   node scripts/render.mjs sheet --from 0 --to 30 [--n 12] [--cols 4] [--out file.png]   (or --times a,b,c | --cuts)
//   perf:    node scripts/render.mjs perf --from 0 --to 5 [--samples 1] [--shutter 0.5]
//   video:   node scripts/render.mjs video [--from 0] [--to dur] [--fps 60] [--crf 16] [--samples auto] [--shutter 0.2] [--out out/video.mp4] [--noaudio]
//            --samples N averages N sub-frames per frame over shutter×(1/fps): motion blur + temporal AA;
//            --samples auto picks 4/12/36/108/324 per frame until the frame converges (--tol levels, default 3)
//   --scale N (all modes): render at N× the 1920x1080 layout (2 = true 4K).
//   --cpu: force SwiftShader (software) instead of the GPU (for comparison / when the GPU path breaks).
// Uses the Vite dev server at --url (default http://localhost:5173); starts a private one if unreachable.
//
// GPU flags below were measured on WSL2 + an NVIDIA laptop GPU (2026-09-29); other platforms: check `gpu`,
// add flags via OPUS_EXTRA_ARGS, or fall back to --cpu.
// GPU in WSL2: Chromium's default WebGL here is SwiftShader (CPU). ANGLE's GL backend
// goes through Mesa's D3D12 driver to a real GPU, but picks the integrated AMD one unless
// MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA. With both, a ray-marched frame drops from ~6 s to ~10-20 ms.
// Cost model (template demo, 1080p): ~22 ms per sub-frame with one full-screen Canvas2D text layer; export
// throughput is bounded by sub-frames: --samples 4 --fps 30 for drafts, --samples auto --fps 60 for finals.
import { chromium } from 'playwright-core';
import { WebSocketServer } from 'ws';
import { spawn } from 'node:child_process';
import { mkdirSync, existsSync, writeFileSync, readFileSync, readdirSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const argv = process.argv.slice(2);
const mode = argv[0] ?? 'stills';
const opt = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; };
const flag = (k) => argv.includes(`--${k}`);
const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SCALE = Math.max(1, Math.round(+opt('scale', '1')));
const OW = 1920 * SCALE, OH = 1080 * SCALE;
const SAMPLES = opt('samples', '1') === 'auto'
  ? { min: +opt('min-samples', '4'), max: +opt('max-samples', '324'), tol: +opt('tol', '3') }
  : +opt('samples', '1');
const SHUTTER = +opt('shutter', '0.5');
const hist = (h) => Object.entries(h).sort((a, b) => +a[0] - +b[0]).map(([k, v]) => `${k}:${v}`).join(' ');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function chromePath() {
  if (process.env.OPUS_CHROME) return process.env.OPUS_CHROME;
  const base = path.join(os.homedir(), '.cache/ms-playwright');
  const dirs = existsSync(base) ? readdirSync(base).filter((d) => /^chromium-\d+$/.test(d)).sort((a, b) => +b.split('-')[1] - +a.split('-')[1]) : [];
  for (const d of dirs) { const p = path.join(base, d, 'chrome-linux64/chrome'); if (existsSync(p)) return p; }
  throw new Error('no Chromium found: run `npx playwright-core install chromium` or set OPUS_CHROME');
}

async function reachable(url) {
  try { const r = await fetch(url, { signal: AbortSignal.timeout(1500) }); return r.ok; } catch { return false; }
}

async function ensureServer() {
  const url = opt('url', 'http://localhost:5173');
  if (await reachable(url)) return { url, stop: () => {} };
  const port = 5300 + Math.floor(Math.random() * 500);
  // no live reload: a file saved mid-render must not reload the page
  const proc = spawn('npx', ['vite', '--port', String(port), '--strictPort'], { cwd: APP, stdio: 'ignore', env: { ...process.env, OPUS_NO_HMR: '1' } });
  const u = `http://localhost:${port}`;
  for (let i = 0; i < 300 && !(await reachable(u)); i++) await sleep(100);
  return { url: u, stop: () => proc.kill() };
}

async function openPage(url) {
  const gpu = !flag('cpu');
  if (gpu) process.env.MESA_D3D12_DEFAULT_ADAPTER_NAME ??= 'NVIDIA';
  const browser = await chromium.launch({
    executablePath: chromePath(),
    headless: !flag('headed'),
    env: { ...process.env },
    args: [
      ...(gpu ? ['--use-gl=angle', '--use-angle=gl'] : ['--enable-unsafe-swiftshader']),
      // Canvas2D layers (Layer2D) are uploaded as textures every sub-frame; a GPU-backed canvas has to be read
      // back first on this D3D12 path (~30 ms per 1080p layer). CPU-backed canvases halve the frame time.
      '--disable-accelerated-2d-canvas',
      '--ignore-gpu-blocklist', '--enable-gpu-rasterization',
      ...(process.env.OPUS_EXTRA_ARGS ? process.env.OPUS_EXTRA_ARGS.split(' ') : []),
      '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
    ],
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const logs = [];
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push(`[${m.type()}] ${m.text()}`); });
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
  const only = opt('only');
  await page.goto(`${url}/?export=1${only ? `&only=${only}` : ''}${SCALE !== 1 ? `&scale=${SCALE}` : ''}`);
  await page.waitForFunction(() => window.__opus?.ready || window.__opus?.error, null, { timeout: 180000 });
  const err = await page.evaluate(() => window.__opus.error);
  if (err) throw new Error(`app failed to boot:\n${err}\n${logs.join('\n')}`);
  const renderer = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
  });
  if (gpu && !/NVIDIA/i.test(renderer)) console.error(`WARNING: WebGL is not on the NVIDIA GPU: ${renderer}`);
  const size = await page.evaluate(() => [window.__opus.width ?? 1920, window.__opus.height ?? 1080]);
  if (size[0] !== OW || size[1] !== OH) throw new Error(`app renders ${size[0]}x${size[1]}, expected ${OW}x${OH} (--scale ${SCALE})`);
  const sceneErrors = await page.evaluate(() => window.__opus.errors);
  if (sceneErrors.length) console.error('SCENE ERRORS:\n' + sceneErrors.join('\n'));
  return { browser, page, logs, renderer };
}

async function stills(page, times, outDir) {
  mkdirSync(outDir, { recursive: true });
  const files = [];
  for (const t of times) {
    const k = await page.evaluate(([t, s, sh]) => window.__opus.still(t, s, sh), [t, SAMPLES, SHUTTER]);
    const f = path.join(outDir, `f_${t.toFixed(2).padStart(7, '0')}.png`);
    if (typeof SAMPLES !== 'number') console.log(`t=${t}: ${k} sub-frames`);
    if (SCALE !== 1) writeFileSync(f, Buffer.from(await page.evaluate(() => window.__opus.png()), 'base64'));
    else await page.screenshot({ path: f, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
    files.push(f);
  }
  return files;
}

async function sheet(page, times, cols, out) {
  const dataUrl = await page.evaluate(async ({ times, cols }) => {
    const P = window.__opus;
    const cw = 480, ch = 270, pad = 4, lab = 18;
    const rows = Math.ceil(times.length / cols);
    const cv = document.createElement('canvas');
    cv.width = cols * (cw + pad) + pad; cv.height = rows * (ch + lab + pad) + pad;
    const c = cv.getContext('2d');
    c.fillStyle = '#222'; c.fillRect(0, 0, cv.width, cv.height);
    const src = document.getElementById('c');
    times.forEach((t, i) => {
      P.still(t);
      const x = pad + (i % cols) * (cw + pad), y = pad + Math.floor(i / cols) * (ch + lab + pad);
      c.drawImage(src, x, y + lab, cw, ch);
      c.fillStyle = '#ddd'; c.font = '13px monospace'; c.fillText(`${t.toFixed(2)}s`, x + 2, y + 13);
    });
    return cv.toDataURL('image/png');
  }, { times, cols });
  mkdirSync(path.dirname(out), { recursive: true });
  writeFileSync(out, Buffer.from(dataUrl.split(',')[1], 'base64'));
}

async function video(page, from, to, fps, out) {
  mkdirSync(path.dirname(out), { recursive: true });
  const project = JSON.parse(readFileSync(path.join(APP, 'public/project.json'), 'utf8'));
  const audio = project.audio ? path.join(APP, 'public', project.audio) : null;
  const withAudio = audio && existsSync(audio) && !flag('noaudio');
  const args = ['-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${OW}x${OH}`, '-r', String(fps), '-i', 'pipe:0'];
  if (withAudio) args.push('-ss', String(from), '-t', String(to - from), '-i', audio);
  // Frames are sRGB: convert with the BT.709 matrix and tag the stream (untagged HD decodes as BT.709 in players)
  args.push('-vf', 'vflip,scale=out_color_matrix=bt709,setparams=color_primaries=bt709:color_trc=bt709', '-c:v', 'libx264', '-preset', opt('preset', 'slow'), '-crf', opt('crf', '16'), '-pix_fmt', 'yuv420p', '-tune', 'grain', '-x264-params', opt('x264', 'aq-mode=3'));
  if (withAudio) args.push('-c:a', 'aac', '-b:a', '320k', '-shortest');
  args.push('-movflags', '+faststart', out);
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] });
  const ffDone = new Promise((r) => ff.on('close', r));
  let frames = 0;
  const total = Math.round(to * fps) - Math.round(from * fps);
  const t0 = performance.now();
  const wss = new WebSocketServer({ port: 0, maxPayload: Math.max(64 * 1024 * 1024, OW * OH * 4 + 1024) });
  await new Promise((r) => wss.on('listening', r));
  wss.on('connection', (ws) => {
    ws.on('message', async (msg, isBinary) => {
      if (!isBinary) return;
      if (!ff.stdin.write(msg)) await new Promise((r) => ff.stdin.once('drain', r));
      frames++;
      ws.send(String(frames)); // ack: the page keeps at most a few frames ahead of ffmpeg
      if (frames % 60 === 0 || frames === total) {
        const el = (performance.now() - t0) / 1000;
        process.stdout.write(`\r${frames}/${total} frames  ${(frames / el).toFixed(1)} fps  eta ${((total - frames) / (frames / el)).toFixed(0)}s   `);
      }
    });
  });
  const used = await page.evaluate((o) => window.__opus.stream(o), { from, to, fps, ws: `ws://localhost:${wss.address().port}`, samples: SAMPLES, shutter: SHUTTER, inflight: 4 });
  while (frames < total) await sleep(20);
  ff.stdin.end();
  await ffDone;
  wss.close();
  console.log(`\nwrote ${out} (${frames} frames in ${((performance.now() - t0) / 1000).toFixed(1)}s)`);
  console.log(`sub-frames per frame (count:frames): ${hist(used)}`);
}

const { url, stop } = await ensureServer();
const { browser, page, logs, renderer } = await openPage(url);
try {
  if (mode === 'gpu') {
    console.log(renderer);
  } else if (mode === 'stills') {
    const times = (opt('t') ?? '0').split(',').map(Number);
    console.log((await stills(page, times, opt('out', path.join(APP, 'out/stills')))).join('\n'));
  } else if (mode === 'sheet') {
    const from = +opt('from', '0'), to = +opt('to', '10'), n = +opt('n', '12');
    let times = Array.from({ length: n }, (_, i) => from + ((to - from) * i) / Math.max(1, n - 1));
    if (opt('times')) times = opt('times').split(',').map(Number);
    if (flag('cuts')) {
      const tl = await page.evaluate(() => window.__opus.timeline);
      times = tl.slice(1).flatMap((e) => [e.start - 0.1, e.start - 1 / 60, e.start + 1 / 60, e.start + 0.1]);
    }
    const out = opt('out', path.join(APP, `out/sheets/sheet_${from}-${to}.png`));
    await sheet(page, times, +opt('cols', '4'), out);
    console.log(out);
  } else if (mode === 'perf') {
    const from = +opt('from', '0'), to = +opt('to', '5');
    const r = await page.evaluate(async ({ from, to, samples, shutter }) => {
      const P = window.__opus;
      const ms = [];
      const buf = new Uint8Array(P.width * P.height * 4);
      P.still(from);
      const used = {};
      for (let t = from; t < to; t += 1 / 60) {
        const a = performance.now();
        const k = P.engine.render(t, 1 / 60, false, samples, shutter);
        used[k] = (used[k] ?? 0) + 1;
        await P.engine.readPixelsAsync(buf);
        ms.push(performance.now() - a);
      }
      ms.sort((a, b) => a - b);
      return { n: ms.length, avg: ms.reduce((a, b) => a + b, 0) / ms.length, p50: ms[ms.length >> 1], p95: ms[Math.floor(ms.length * 0.95)], max: ms[ms.length - 1], used };
    }, { from, to, samples: SAMPLES, shutter: SHUTTER });
    console.log(`${renderer}\nframes ${r.n}  avg ${r.avg.toFixed(1)}ms  p50 ${r.p50.toFixed(1)}  p95 ${r.p95.toFixed(1)}  max ${r.max.toFixed(1)}  sub-frames ${hist(r.used)}`);
  } else if (mode === 'video') {
    const dur = await page.evaluate(() => window.__opus.duration);
    await video(page, +opt('from', '0'), +opt('to', String(dur)), +opt('fps', '60'), path.resolve(opt('out', path.join(APP, 'out/video.mp4'))));
  } else throw new Error(`unknown mode: ${mode}`);
  if (logs.length) console.error('BROWSER LOG:\n' + logs.slice(0, 40).join('\n'));
} finally {
  await browser.close();
  stop();
}
