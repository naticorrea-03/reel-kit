"""python3 analyze.py <probe_dir> <slug> [index.html]  ->  <probe_dir>/report.json + report.md + issues-sheet.jpg

Rules (1080x1920 coords). Every issue must persist >= MIN_RUN seconds so mid-animation frames don't fire.
  FACE      an overlay graphic (not behind the speakers) covers part of a face
  HIDDEN    a behind-the-speakers word is more than 8% hidden by a person (image-only tiles marked
            data-pass-behind are exempt: an orbit tile passing behind the head is the effect; approved by Nati 10/14)
  OVERLAP   two different graphics overlap each other (eyebrow and captions count)
  OVERFLOW  text runs outside its own card, is clipped by its box, or leaves the canvas
  SAFEZONE  a graphic sits where Instagram/TikTok UI covers it (top 220, bottom 450, right rail)
  SPACING   two words on one line touch (a missing space)
  EMPTY     a big card on screen with almost nothing in it (dead white box)
  CLIPPED   text cut off by a parent box that hides overflow
  TINY      text renders under 28 px (warning only; brand eyebrow and glyphs exempt)
  CUES      two caption cues share a frame (read from index.html; the probe is too coarse)
  ARROW     a hand-drawn note arrow lands more than 120 px from every face (points at nothing)
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw
import numpy as np

D, SLUG = sys.argv[1], sys.argv[2]
HTML = sys.argv[3] if len(sys.argv) > 3 else None    # the built composition, for the CUES rule
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from fxlib import ensure_faces  # noqa: E402  (compiles faces.swift on first use; fails loudly off macOS)
S = json.load(open(os.path.join(D, 'samples.json')))
K = 1 / S['scale']                     # screenshot px -> composition px
MIN_RUN = 0.30
SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE = 220, 1470, 40
RAIL = (980, 1155, 1470)               # x >= 980 between y 1155 and 1470 (like/comment/share)
TINY_PX = 28

def area(b): return max(0, b[2] - b[0]) * max(0, b[3] - b[1])
def inter(a, b): return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]

# ---- faces (macOS Vision on the stage-only frames) ----
fcache = os.path.join(D, 'faces.json')
if not os.path.exists(fcache):
    paths = [os.path.join(D, f'stage-{s["i"]:04d}.png') for s in S['samples']]
    raw = {}
    for k in range(0, len(paths), 60):
        raw.update(json.loads(subprocess.run([ensure_faces()] + paths[k:k + 60], capture_output=True, check=True).stdout))
    json.dump(raw, open(fcache, 'w'))
FACES = json.load(open(fcache))
FACES_BY_NAME = {os.path.basename(k): v for k, v in FACES.items()}   # cache keys are absolute; a relative probe dir still finds them

def faces_at(i):
    out = []
    for x, y, w, h in FACES.get(os.path.join(D, f'stage-{i:04d}.png')) or FACES_BY_NAME.get(f'stage-{i:04d}.png', []):
        x, y, w, h = x * K, y * K, w * K, h * K
        out.append([x - .12 * w, y - .30 * h, x + w * 1.12, y + h * 1.18])   # pad for hair and chin
    return out

def mask_at(i):
    a = np.array(Image.open(os.path.join(D, f'mask-{i:04d}.png')).convert('RGBA'))[:, :, 3]
    return a > 128

def mask_frac(m, b):
    x0, y0, x1, y1 = [int(round(v / K)) for v in b]
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(m.shape[1], x1), min(m.shape[0], y1)
    if x1 <= x0 or y1 <= y0: return 0.0
    return float(m[y0:y1, x0:x1].mean())

def label(it):
    txt = ' '.join(p['text'] for p in it['parts'] if p['t'] == 'text')[:42]
    return f"{it['kind'] or 'graphic'}" + (f' "{txt}"' if txt else '')

def boxes(it, kinds=('text', 'img', 'card')):
    return [p['box'] for p in it['parts'] if p['t'] in kinds and p['op'] > .5]

hits = []   # (rule, key, t, i, msg, boxes)
for s in S['samples']:
    i, t, items = s['i'], s['t'], s['items']
    vis = [it for it in items if it['op'] > .5]
    fz = faces_at(i)
    m = None
    for it in vis:
        bx = boxes(it)
        if it['layer'] == 'over' and it['kind'] != 'eyebrow':
            for f in fz:
                cov = sum(area(inter(b, f)) for b in bx) / max(1, area(f))
                if cov > .03:
                    # an image-only orbit tile may sweep across a face for under 0.4 s on close-ups, as creators do
                    # (approved by Nati 10/14); a longer pass, or any text, is still a FACE error
                    orb = (it.get('group') or '').startswith('orbit') and not any(p_['t'] == 'text' for p_ in it['parts'])
                    hits.append(('FACE_ORBIT' if orb else 'FACE', it['id'], t, i, f'{label(it)} covers {cov:.0%} of a face', bx + [f]))
        for tp in [p_ for p_ in it['parts'] if p_['t'] == 'tip' and p_['op'] > .5]:
            tx, ty = (tp['box'][0] + tp['box'][2]) / 2, (tp['box'][1] + tp['box'][3]) / 2
            gap = min([max(f[0] - tx, 0, tx - f[2]) ** 2 + max(f[1] - ty, 0, ty - f[3]) ** 2 for f in fz] or [1e9]) ** .5
            if gap > 120:
                hits.append(('ARROW', it['id'], t, i, f'{label(it)} arrow lands {gap:.0f} px from any face (points at nothing)', [[tx - 20, ty - 20, tx + 20, ty + 20]] + fz))
        if it['layer'] == 'wall':
            m = mask_at(i) if m is None else m
            tb = boxes(it, ('text',))             # judge each word/line on its own: one hidden word is unreadable
            for b in boxes(it, ('img',)):         # a screenshot's lines are pixels, so judge it in 44 px text-line bands
                tb += [[b[0], y, b[2], min(b[3], y + 44)] for y in range(int(b[1]), int(b[3]) - 10, 44)]
            hid, tb_worst = 0, tb
            for b in tb:
                fr = mask_frac(m, b)
                if fr > hid: hid, tb_worst = fr, [b]
            # an image-only tile marked pass-behind is SUPPOSED to go behind the head (orbit); text is still judged
            if hid > .08 and not (it.get('pass') and not any(p['t'] == 'text' for p in it['parts'])):
                tb = tb_worst
                hits.append(('HIDDEN', it['id'], t, i, f'{label(it)} is {hid:.0%} hidden behind a speaker', tb))
        for p in it['parts']:
            if p['t'] != 'text' or p['op'] < .5: continue
            b = p['box']
            if p.get('clipped'):
                hits.append(('OVERFLOW', it['id'] + p['text'][:12], t, i, f'"{p["text"]}" is clipped by its box', [b]))
            cb = p.get('clipbox')
            if cb and cb[2] - cb[0] < 1080 and (b[0] < cb[0] - 4 or b[2] > cb[2] + 4 or b[1] < cb[1] - 4 or b[3] > cb[3] + 4):
                hits.append(('CLIPPED', it['id'] + p['text'][:12], t, i, f'"{p["text"]}" is cut off by its box', [b, cb]))
            c = p.get('card')
            if c and (b[0] < c[0] - 3 or b[2] > c[2] + 3 or b[1] < c[1] - 6 or b[3] > c[3] + 6):
                hits.append(('OVERFLOW', it['id'] + p['text'][:12], t, i, f'"{p["text"]}" spills out of its card', [b, c]))
            if b[0] < 0 or b[2] > 1080 or b[1] < 0 or b[3] > 1920:
                hits.append(('OVERFLOW', it['id'] + p['text'][:12], t, i, f'"{p["text"]}" runs off the frame', [b]))
            if p['fs'] < TINY_PX and p['op'] > .9 and it['kind'] != 'eyebrow' and sum(ch.isalnum() for ch in p['text']) >= 3:
                hits.append(('TINY', it['id'] + p['text'][:12], t, i, f'"{p["text"]}" is {p["fs"]} px (min {TINY_PX})', [b]))
        cards = [p['box'] for p in it['parts'] if p['t'] == 'card' and p['op'] > .5 and area(p['box']) > 200 * 150]
        if cards:   # a big card with almost nothing in it reads as a dead white box
            big = max(cards, key=area)
            filled = sum(area(inter(p['box'], big)) for p in it['parts'] if p['t'] in ('text', 'img') and p['op'] > .5)
            if filled / area(big) < .04:
                hits.append(('EMPTY', it['id'], t, i, f'{label(it)} shows an empty card', [big]))
        tps = [p for p in it['parts'] if p['t'] == 'text' and p['op'] > .5]
        for x_, p1 in enumerate(tps):   # text colliding with other text inside the same graphic
            for p2 in tps[x_ + 1:]:
                ink = lambda p: [p['box'][0], p['box'][1] + .16 * p['fs'], p['box'][2], p['box'][3] - .2 * p['fs']]   # letters, not the font box
                ov = area(inter(ink(p1), ink(p2))) / max(1, min(area(ink(p1)), area(ink(p2))))
                if ov > .2 and not (p1['text'] in p2['text'] or p2['text'] in p1['text']):
                    hits.append(('OVERLAP', it['id'] + 'self', t, i, f'"{p1["text"]}" collides with "{p2["text"]}"', [p1['box'], p2['box']])); break
        for p in it['parts']:
            ws = p.get('words') or []
            if p['op'] < .5 or len(ws) < 2: continue
            for w1, w2 in zip(ws, ws[1:]):
                same_line = min(w1[3], w2[3]) - max(w1[1], w2[1]) > .5 * (w1[3] - w1[1])
                if same_line and 0 <= w2[0] - w1[2] < max(3, .12 * p.get('fs', 40)):
                    hits.append(('SPACING', it['id'], t, i, f'words touch in "{p["text"]}" (no visible space)', [w1, w2])); break
        ink = {tuple(p['box']): .14 * p['fs'] for p in it['parts'] if p['t'] == 'text'}   # font box has empty headroom above the letters
        # image-only orbit tiles may run big and partly off the frame on close-ups, as creators do (approved by Nati 10/14);
        # any text, and every other graphic, keeps the safe zone
        orbit_img = it.get('pass') or (it.get('group') or '').startswith('orbit')
        if orbit_img and not any(p['t'] == 'text' for p in it['parts']):
            bx = []
        for b in bx:
            out = []
            if b[1] + ink.get(tuple(b), 0) < SAFE_TOP: out.append('top')
            if b[3] > SAFE_BOTTOM: out.append('bottom')
            if b[0] < SAFE_SIDE or b[2] > 1080 - SAFE_SIDE: out.append('side')
            if b[2] > RAIL[0] and b[3] > RAIL[1] and b[1] < RAIL[2]: out.append('button rail')
            if out:
                hits.append(('SAFEZONE', it['id'], t, i, f'{label(it)} enters the {"/".join(out)} UI zone', [b])); break
    for a_ in range(len(vis)):
        for b_ in range(a_ + 1, len(vis)):
            A, B = vis[a_], vis[b_]
            if A.get('group') and A.get('group') == B.get('group'):
                continue   # the front and wall copies of one carousel crossing each other is the effect, not a collision
            best = 0; pair = None
            for ba in boxes(A):
                for bb in boxes(B):
                    ov = area(inter(ba, bb)) / max(1, min(area(ba), area(bb)))
                    if ov > best: best, pair = ov, [ba, bb]
            if best > .04:
                key = '|'.join(sorted([A['id'], B['id']]))
                hits.append(('OVERLAP', key, t, i, f'{label(A)} overlaps {label(B)} ({best:.0%})', pair))

# ---- collapse into runs ----
step = 1 / S['fps']
runs = {}
for rule, key, t, i, msg, bx in hits:
    k = (rule, key)
    r = runs.get(k)
    if r and t - r[-1]['t1'] <= step * 1.6:
        r[-1]['t1'] = t; r[-1]['n'] += 1
        if r[-1]['n'] == (r[-1]['n'] // 2) * 2: pass
    else:
        runs.setdefault(k, []).append({'rule': rule, 'key': key, 't0': t, 't1': t, 'n': 1, 'i': i, 'msg': msg, 'boxes': bx})
_seen = set()   # same rule + message + time from sibling elements = one issue
runs = {k: [r for r in v if not ((r['rule'], r['msg'], r['t0']) in _seen or _seen.add((r['rule'], r['msg'], r['t0'])))] for k, v in runs.items()}
MIN = {'EMPTY': .6, 'SPACING': .45, 'FACE_ORBIT': .4}   # entrances scale words up for a few frames   # a window may open a beat before its first message
issues = sorted([r for rs in runs.values() for r in rs if r['t1'] - r['t0'] + step >= MIN.get(r['rule'], MIN_RUN)], key=lambda r: (r['t0'], r['rule']))
for r in issues:   # an orbit pass that lingers on a face is a plain FACE error
    if r['rule'] == 'FACE_ORBIT':
        r['rule'] = 'FACE'
for r in issues:   # pick the middle sample as the evidence frame
    r['i'] = int(round((r['t0'] + r['t1']) / 2 * S['fps']))
    mid = next((h for h in hits if h[0] == r['rule'] and h[1] == r['key'] and abs(h[2] - (r['t0'] + r['t1']) / 2) <= step / 2 + 1e-6), None)
    if mid: r['boxes'], r['msg'] = mid[5], mid[4]

# CUES: two caption cues on screen in the same frame (too short for the 6/s probe; read straight from the composition)
import re as _re
_html = HTML
if _html and os.path.exists(_html):
    _c = sorted((float(a_), float(a_) + float(d_), _re.sub('<[^>]+>', ' ', t_).split())
                for a_, d_, t_ in _re.findall(r'data-start="([\d.]+)" data-duration="([\d.]+)"[^>]*><div id="e\d+" class="in"><div class="cap[^"]*">(.*?)</div></div></div>', open(_html).read()))
    for (a0, a1, w0), (b0, b1, w1) in zip(_c, _c[1:]):
        if a1 > b0 + 1e-3:
            fr = int(round(b0 * S['fps']))
            issues.append({'rule': 'CUES', 'key': f'cue{b0}', 't0': b0, 't1': min(a1, b1), 'n': 1, 'i': min(fr, len(S['samples']) - 1),
                           'msg': f'caption "{" ".join(w0)}" still on screen when "{" ".join(w1)}" starts ({(a1 - b0) * 1000:.0f} ms)', 'boxes': []})
    issues.sort(key=lambda r: (r['t0'], r['rule']))

# ---- evidence sheet: each issue frame with its boxes drawn ----
SEV = {'TINY': 'warn'}
COL = {'CUES': 'orange', 'ARROW': 'red', 'CLIPPED': 'cyan', 'EMPTY': 'white', 'SPACING': 'white', 'FACE': 'red', 'HIDDEN': 'orange', 'OVERLAP': 'magenta', 'OVERFLOW': 'cyan', 'SAFEZONE': 'yellow', 'TINY': 'lime'}
tiles = []
for n, r in enumerate(issues):
    im = Image.open(os.path.join(D, f'full-{r["i"]:04d}.jpg')).convert('RGB')
    dr = ImageDraw.Draw(im)
    for b in r['boxes']:
        dr.rectangle([v / K for v in b], outline=COL[r['rule']], width=3)
    dr.rectangle([0, 0, im.width, 34], fill='black'); dr.text((6, 8), f'#{n + 1} {r["rule"]} {r["t0"]:.1f}-{r["t1"]:.1f}s', fill=COL[r['rule']])
    tiles.append(im.resize((270, 480)))
if tiles:
    cols = 6; rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (270 * cols, 480 * rows), 'black')
    for n, im in enumerate(tiles): sheet.paste(im, ((n % cols) * 270, (n // cols) * 480))
    sheet.save(os.path.join(D, 'issues-sheet.jpg'), quality=82)

for r in issues: r['sev'] = SEV.get(r['rule'], 'error')
nerr = sum(r['sev'] == 'error' for r in issues)
json.dump({'slug': SLUG, 'errors': nerr, 'issues': issues}, open(os.path.join(D, 'report.json'), 'w'), indent=1)
lines = [f'# {SLUG}: {nerr} error(s), {len(issues) - nerr} warning(s)', '']
for n, r in enumerate(issues):
    lines.append(f'{n + 1}. {"" if r["sev"] == "error" else "(warn) "}**{r["rule"]}** {r["t0"]:.1f}-{r["t1"]:.1f}s: {r["msg"]}')
open(os.path.join(D, 'report.md'), 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
sys.exit(1 if nerr else 0)
