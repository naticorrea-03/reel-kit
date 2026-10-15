// node probe.mjs <clipdir> <outdir> [fps=6]
// Steps a HyperFrames composition and, at each sample, records every visible graphic's real
// boxes plus three screenshots: full frame, stage only (faces), and speaker cutout only (mask).
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
// puppeteer-core comes from the hyperframes npx cache (audit.sh warms it with `npx hyperframes@HF_VERSION browser path`).
// HF_NM overrides: a node_modules folder that has puppeteer-core.
function findNM() {
  if (process.env.HF_NM) return process.env.HF_NM;
  const want = process.env.HF_VERSION || '0.8.61';
  const root = path.join(process.env.HOME || '', '.npm', '_npx');
  let any = null;
  for (const d of (fs.existsSync(root) ? fs.readdirSync(root) : [])) {
    const nm = path.join(root, d, 'node_modules');
    if (!fs.existsSync(path.join(nm, 'puppeteer-core'))) continue;
    try { if (JSON.parse(fs.readFileSync(path.join(nm, 'hyperframes', 'package.json'), 'utf8')).version === want) return nm; } catch {}
    any = any || nm;
  }
  if (!any) { console.error('probe: puppeteer-core not found. Run: npx --yes hyperframes@' + want + ' browser path   (or set HF_NM)'); process.exit(2); }
  return any;
}
const NM = findNM();
const puppeteer = require(`${NM}/puppeteer-core`);
const [dir, out, fpsArg] = process.argv.slice(2); const FPS = +(fpsArg || 6);
fs.mkdirSync(out, { recursive: true });
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webm': 'video/webm', '.mp4': 'video/mp4', '.woff2': 'font/woff2', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.json': 'application/json' };
// (runtime injection kept off: we seek directly)
const RUNTIME = `${NM}/hyperframes/dist/hyperframe.runtime.iife.js`;
const srv = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  if (u === '/__hf_runtime.js') { res.writeHead(200, { 'Content-Type': 'text/javascript' }); return res.end(fs.readFileSync(RUNTIME)); }
  if (u === '/' || u === '/index.html') { // inject the runtime the renderer would add
    const h = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
    res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end(h); }
  const p = path.join(dir, decodeURIComponent(req.url.split('?')[0]) === '/' ? 'index.html' : decodeURIComponent(req.url.split('?')[0]));
  fs.stat(p, (e, st) => {
    if (e || !st.isFile()) { res.writeHead(404); return res.end(); }
    const range = req.headers.range, type = MIME[path.extname(p)] || 'application/octet-stream';
    if (range) { const [a, b] = range.replace('bytes=', '').split('-'); const s = +a, en = b ? +b : st.size - 1;
      res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${s}-${en}/${st.size}`, 'Accept-Ranges': 'bytes', 'Content-Length': en - s + 1 });
      return fs.createReadStream(p, { start: s, end: en }).pipe(res); }
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size, 'Accept-Ranges': 'bytes' }); fs.createReadStream(p).pipe(res);
  });
}).listen(0);
const port = srv.address().port;
const exe = process.env.HF_CHROME; // chrome-headless-shell path
if (!exe) { console.error('probe: HF_CHROME is not set (audit.sh sets it from `npx hyperframes browser path`)'); process.exit(2); }
const browser = await puppeteer.launch({ executablePath: exe, headless: true, args: ['--autoplay-policy=no-user-gesture-required', '--hide-scrollbars'] });
const page = await browser.newPage();
page.on('pageerror', e => console.error('PAGEERR', e.message)); page.on('console', m => m.type() === 'error' && console.error('CONSOLE', m.text())); page.on('requestfailed', r => console.error('REQFAIL', r.url().slice(0, 120), r.failure()?.errorText));
await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 0.5 });
await page.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: 'load', timeout: 60000 });
await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), { timeout: 30000, polling: 200 });
await page.evaluate(() => { // our own seek: GSAP timeline + clip windows + media time (same rules as the renderer)
  const tl = window.__timelines.main; tl.pause();
  window.__auditSeek = t => {
    tl.seek(t, false);
    for (const c of document.querySelectorAll('.clip')) {
      const a = +c.dataset.start, d = +c.dataset.duration;
      c.style.setProperty('display', (t >= a && t < a + d) ? '' : 'none');
    }
    for (const v of document.querySelectorAll('video')) {
      const a = +(v.dataset.start || 0), ms = +(v.dataset.mediaStart || 0);
      v.pause(); v.currentTime = Math.max(0, t - a + ms);
    }
  };
});
await page.evaluate(() => document.fonts.ready);
await page.addStyleTag({ content: `
#root[data-audit=mask], html.audit-mask, html.audit-mask body {background:transparent!important}
#root[data-audit=mask] #bgv, #root[data-audit=mask] .clip, #root[data-audit=mask] .fx, #root[data-audit=mask] #eyebrow {visibility:hidden!important}
#root[data-audit=stage] .clip, #root[data-audit=stage] .fx, #root[data-audit=stage] #eyebrow {visibility:hidden!important}` });
const dur = await page.evaluate(() => +document.querySelector('[data-composition-id]').dataset.duration);
const settle = () => page.evaluate(async () => {
  const vids = [...document.querySelectorAll('video')];
  for (let i = 0; i < 40 && vids.some(v => v.seeking || v.readyState < 2); i++) await new Promise(r => setTimeout(r, 25));
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
});
const collect = () => page.evaluate(() => {
  const R = r => [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)];
  const op = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
  const hasBg = cs => (cs.backgroundColor && !/rgba\(0, 0, 0, 0\)|transparent/.test(cs.backgroundColor)) || cs.backgroundImage !== 'none';
  const roots = [...document.querySelectorAll('.clip'), document.getElementById('eyebrow')].filter(Boolean);
  const items = [];
  for (const c of roots) {
    const o = op(c); if (o < 0.05) continue;
    const id = c.id === 'eyebrow' ? 'eyebrow' : (c.querySelector('.in')?.id || '?');
    const kind = c.id === 'eyebrow' ? 'eyebrow' : (c.querySelector('.in > *')?.className?.baseVal ?? c.querySelector('.in > *')?.className ?? '').toString().split(' ')[0];
    const layer = c.closest('#stage') ? 'wall' : 'over';
    const parts = [];
    const walker = document.createTreeWalker(c, NodeFilter.SHOW_ELEMENT);
    for (let el = c; el; el = walker.nextNode()) {
      if (/scrim|rk-plate/.test(el.className && el.className.baseVal === undefined ? el.className : '')) continue;   // legibility glow or a still of the footage itself, not a graphic
      const cs = getComputedStyle(el); const eo = op(el); if (eo < 0.05) continue;
      const r = el.getBoundingClientRect(); if ((r.width < 2 || r.height < 2) && !(el.classList && el.classList.contains('arr-tip'))) continue;
      if (el.classList && el.classList.contains('arr-tip')) { parts.push({ t: 'tip', box: R(r), op: eo }); continue; }
      if (el.tagName === 'svg' && el.classList.contains('arr')) {   // full-canvas arrow layer: only its tip matters
        let n = walker.nextSibling(); while (!n && walker.parentNode()) n = walker.nextSibling(); if (!n) break; walker.previousNode(); continue;
      }
      const own = [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim());
      const wkids = [...el.children].filter(k => k.tagName === 'SPAN' && getComputedStyle(k).display.startsWith('inline'));
      if (!own.length && wkids.length > 1 && [...el.childNodes].some(n => n.nodeType === 3)) {
        parts.push({ t: 'words', box: R(r), op: eo, fs: Math.round(parseFloat(cs.fontSize) * (r.height / (el.offsetHeight || r.height))),
          text: el.textContent.trim().slice(0, 40), words: wkids.map(k => R(k.getBoundingClientRect())) });
      }
      if (own.length) {
        const rg = document.createRange(); rg.selectNodeContents(el); const tr = rg.getBoundingClientRect();
        const card = (() => { for (let a = el.parentElement; a && a !== c.parentElement; a = a.parentElement) { const s = getComputedStyle(a); if (hasBg(s)) return R(a.getBoundingClientRect()); } return null; })();
        const scale = r.height / (el.offsetHeight || r.height);
        const kids = [...el.children].filter(k => getComputedStyle(k).display.startsWith('inline'));
        const words = kids.length > 1 ? kids.map(k => R(k.getBoundingClientRect())) : null;
        const clipbox = (() => { for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) { const s = getComputedStyle(a); if (s.overflow !== 'visible' || s.overflowY !== 'visible' || s.clipPath !== 'none') return R(a.getBoundingClientRect()); } return null; })();
        parts.push({ t: 'text', box: R(tr), op: eo, words, clipbox, text: el.textContent.trim().slice(0, 40), fs: Math.round(parseFloat(cs.fontSize) * scale), card,
          clipped: (cs.overflow !== 'visible' && (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2)) });
      } else if (el.tagName === 'IMG' || el.tagName === 'svg' || el.tagName === 'VIDEO' || el.tagName === 'CANVAS') {
        parts.push({ t: 'img', box: R(r), op: eo });
      } else if (el !== c && cs.backgroundImage !== 'none' && /url\(/.test(cs.backgroundImage)) {
        parts.push({ t: 'img', box: R(r), op: eo });           // image drawn as a CSS background
      } else if (el !== c && hasBg(cs) && el.className !== 'in') {
        parts.push({ t: 'card', box: R(r), op: eo });
      }
      if (el.tagName === 'svg') { // skip svg internals
        let n = walker.nextSibling(); while (!n && walker.parentNode()) n = walker.nextSibling(); if (!n) break; walker.previousNode();
      }
    }
    // data-pass-behind: an image tile meant to travel behind the speaker (orbit carousels); data-fx-group: copies of one graphic
    const pass = !!c.querySelector('[data-pass-behind]');
    const group = c.querySelector('[data-fx-group]')?.getAttribute('data-fx-group') || null;
    if (parts.length) items.push({ id, kind, layer, op: o, parts, pass, group });
  }
  return items;
});
const samples = [];
const N = Math.floor(dur * FPS);
for (let i = 0; i <= N; i++) {
  const t = Math.min(dur - 0.02, i / FPS);
  await page.evaluate(t => window.__auditSeek(t), t);
  await settle();
  const items = await collect();
  const tag = String(i).padStart(4, '0');
  await page.screenshot({ path: `${out}/full-${tag}.jpg`, type: 'jpeg', quality: 70 });
  await page.evaluate(() => { document.querySelector('#root').dataset.audit = 'stage'; });
  await page.screenshot({ path: `${out}/stage-${tag}.png` });
  await page.evaluate(() => { document.querySelector('#root').dataset.audit = 'mask'; document.documentElement.classList.add('audit-mask'); });
  await page.screenshot({ path: `${out}/mask-${tag}.png`, omitBackground: true });
  await page.evaluate(() => { delete document.querySelector('#root').dataset.audit; document.documentElement.classList.remove('audit-mask'); });
  samples.push({ i, t: +t.toFixed(3), items });
}
fs.writeFileSync(`${out}/samples.json`, JSON.stringify({ dur, fps: FPS, scale: 0.5, samples }));
await browser.close(); srv.close();
console.log(`probed ${samples.length} samples over ${dur}s`);
