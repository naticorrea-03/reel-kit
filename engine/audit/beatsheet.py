"""python3 beatsheet.py <project_dir> <slug> [video]  ->  <project>/audits/<slug>/beats/sheet-NN.jpg + beats.json

One row per graphic (captions skipped): frames at entrance+0.35 s, midpoint, exit-0.25 s,
each labelled with time, graphic kind/text and the words spoken within +-1 s.
Read every sheet before a reel reaches Nati (gate 3). Produces sheets, never blocks.
"""
import json, os, re, subprocess, sys
from html.parser import HTMLParser
from PIL import Image, ImageDraw, ImageFont

if len(sys.argv) < 3:
    sys.exit(__doc__)
ROOT = os.path.abspath(os.path.expanduser(sys.argv[1]))
SLUG = sys.argv[2]
VID = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.join(ROOT, 'renders', f'{SLUG}.mp4')
D = os.path.join(ROOT, 'clips', SLUG)
OUT = os.path.join(ROOT, 'audits', SLUG, 'beats')
os.makedirs(OUT, exist_ok=True)
for _f in os.listdir(OUT):   # stale beats from an older cut would mix into the sheets: clear before writing
    if _f.endswith(('.jpg', '.png')):
        os.remove(os.path.join(OUT, _f))
W = 270
WORDS = json.load(open(os.path.join(D, 'cut.words.json')))['words']
DUR = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', VID],
                           capture_output=True, text=True, check=True).stdout)


class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.clips = []; self.cur = None; self.depth = 0
    def handle_starttag(self, tag, a):
        a = dict(a)
        if self.cur is None:
            if tag == 'div' and 'clip' in (a.get('class') or '').split() and 'data-start' in a:
                self.cur = {'t0': float(a['data-start']), 't1': float(a['data-start']) + float(a['data-duration']),
                            'kinds': [], 'text': [], 'imgs': []}
                self.depth = 1
            return
        if tag in ('img', 'br', 'i', 'path', 'circle', 'rect', 'line'):
            if tag == 'img': self.cur['imgs'].append(os.path.splitext(os.path.basename(a.get('src', '')))[0])
            if tag in ('img', 'br'): return
        self.depth += 1
        c = (a.get('class') or '').split()
        if c and c[0] not in ('in', 'w', 'sw', 'bw', 'w3w') and 'scrim' not in c[0]:
            self.cur['kinds'].append(c[0])
    def handle_endtag(self, tag):
        if self.cur is None or tag in ('img', 'br'): return
        self.depth -= 1
        if self.depth == 0:
            self.clips.append(self.cur); self.cur = None
    def handle_data(self, d):
        if self.cur is not None and d.strip(): self.cur['text'].append(d.strip())


p = P(); p.feed(open(os.path.join(D, 'index.html')).read())
beats = []
for c in p.clips:
    kind = c['kinds'][0] if c['kinds'] else 'graphic'
    if kind == 'cap': continue
    t0, t1 = c['t0'], min(c['t1'], DUR)
    if t1 - t0 < .15: continue
    toks = c['text']
    if toks and sum(len(x) == 1 for x in toks) > len(toks) / 2:   # typed text is one span per letter
        toks = [''.join(toks)]
    text = re.sub(r'\s*[\u2726]+', '', ' '.join(toks)).strip()[:80] or ' '.join(c['imgs'])[:80]
    said = ' '.join(w['text'] for w in WORDS if t0 - 1 <= w['start'] <= t1 + 1)
    ts = sorted({round(min(t1 - .05, t0 + .35), 2), round((t0 + t1) / 2, 2), round(max(t0 + .05, t1 - .25), 2)})
    beats.append({'id': f'b{len(beats) + 1:02d}', 't0': round(t0, 2), 't1': round(t1, 2), 'kind': kind, 'text': text,
                  'said': said, 'times': ts, 'frames': []})
beats.sort(key=lambda b: b['t0'])
for n, b in enumerate(beats): b['id'] = f'b{n + 1:02d}'
PL = os.path.join(D, 'plan.json')
if os.path.exists(PL):   # the build's storyboard plan is the source of beats, so ids match the review page
    beats = []
    for b in json.load(open(PL))['beats']:
        t0, t1 = b['t0'], min(b['t1'], DUR)
        ts = sorted({round(min(t1 - .05, t0 + .35), 2), round((t0 + t1) / 2, 2), round(max(t0 + .05, t1 - .25), 2)})
        beats.append({**b, 'text': b['text'][:80], 'times': ts, 'frames': []})

try:
    _fd = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'fonts')
    F = ImageFont.truetype(os.path.join(_fd, 'Inter-500-normal.woff2'), 13)
    FB = ImageFont.truetype(os.path.join(_fd, 'Inter-600-normal.woff2'), 14)
except OSError:
    F = FB = ImageFont.load_default()


def wrap(dr, s, f, w):
    out, cur = [], ''
    for word in s.split():
        if dr.textlength(cur + ' ' + word, font=f) > w and cur: out.append(cur); cur = word
        else: cur = (cur + ' ' + word).strip()
    return out + ([cur] if cur else [])


cells = []
for b in beats:
    for k, t in enumerate(b['times']):
        fp = os.path.join(OUT, f"{b['id']}-{k}.jpg")
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', VID, '-frames:v', '1', '-vf', f'scale={W}:-2', '-q:v', '3', fp], check=True)
        b['frames'].append(os.path.relpath(fp, ROOT))
        cells.append((b, k, t, fp))

for b in beats:   # one in/mid/out strip per beat for the review page storyboard
    fr = [Image.open(os.path.join(ROOT, f)) for f in b['frames']]
    st = Image.new('RGB', (W * len(fr), max(i.height for i in fr)), (20, 14, 12))
    for k, im in enumerate(fr): st.paste(im, (k * W, 0))
    sp = os.path.join(OUT, f"{b['id']}-strip.jpg"); st.save(sp, quality=82); b['strip'] = os.path.relpath(sp, ROOT)

LAB = 92
per = 6
sheets = []
for s in range(0, len(cells), per):
    chunk = cells[s:s + per]
    ims = [Image.open(c[3]) for c in chunk]
    h = max(i.height for i in ims)
    sheet = Image.new('RGB', (W * per, h + LAB), (20, 14, 12))
    dr = ImageDraw.Draw(sheet)
    for j, ((b, k, t, _), im) in enumerate(zip(chunk, ims)):
        x = j * W
        sheet.paste(im, (x, LAB))
        dr.text((x + 6, 4), f"{b['id']} {('IN', 'MID', 'OUT')[k] if len(b['times']) == 3 else k}  {t:.2f}s  {b['kind']}", font=FB, fill=(255, 210, 120))
        y = 22
        for ln in wrap(dr, b['text'], F, W - 12)[:2]:
            dr.text((x + 6, y), ln, font=F, fill=(255, 255, 255)); y += 15
        for ln in wrap(dr, 'said: ' + b['said'], F, W - 12)[:2]:
            dr.text((x + 6, y), ln, font=F, fill=(170, 200, 255)); y += 15
        dr.line([(x, 0), (x, h + LAB)], fill=(80, 60, 50), width=1)
    fp = os.path.join(OUT, f'sheet-{s // per + 1:02d}.jpg')
    sheet.save(fp, quality=85); sheets.append(os.path.relpath(fp, ROOT))

json.dump({'slug': SLUG, 'video': os.path.relpath(VID, ROOT), 'beats': beats, 'sheets': sheets},
          open(os.path.join(ROOT, 'audits', SLUG, 'beats.json'), 'w'), indent=1)
print(f'# {SLUG}: {len(beats)} beats, {len(cells)} frames, {len(sheets)} sheets -> audits/{SLUG}/beats/')
