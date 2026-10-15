"""rk3d: shared helpers for the spinning and 3D effects (orbit-carousel, carousel-3d, carousel-*, phone-3d, card-fan).

Not an effect itself (no effect.py), so build.py and the guide skip this folder. Effects load it with load_lib().

Motion is computed here in Python, one pose per video frame, and emitted as GSAP keyframes with linear ease. The
frame-stepping renderer then lands every frame exactly on a precomputed pose, so renders are deterministic and the
layout audit sees the same frames the render does.
"""
import json, math, os, re

FPS = 30
DT = 1 / FPS
SAFE = (90, 240, 950, 1470)   # x0, y0, x1, y1
RAIL = (950, 1155)            # right rail: x > 950 below y 1155 is off limits


# ---------------- timing ----------------
def window(ctx, g, hold, last=None, min_after=.7):
    """(a, end): lands on its phrase, clears before the next graphic, the until phrase, or the end of the clip."""
    a = ctx.at(g['on'])[0]
    last = a if last is None else last
    end = min(ctx.DUR - .05, last + float(g.get('hold', hold)))
    if g.get('until'):
        end = min(end, ctx.at(g['until'], a)[0] - .05)
    later = [t for h in ctx.graphics if h is not g and h.get('on') for t in [ctx.at(h['on'])[0]] if t > a + .05]
    if later:
        end = min(end, min(later) - .15)
    if end - last < min_after:
        ctx.fail(f'{g["type"]} on {g["on"]!r} gets {end - last:.2f} s before the next graphic or the end; move it or the graphic after it')
    return fq(a), fq(end)


def fq(t):
    """snap a time to the frame grid, so keyframes fall exactly on rendered frames."""
    return round(t * FPS) / FPS


def frames(a, end):
    n = max(1, int(round((end - a) * FPS)))
    return [a + k * DT for k in range(n + 1)]


def item_times(ctx, g, items, step):
    """one time per item: its own "on" phrase (in order) or an even step after the graphic's word."""
    a = ctx.at(g['on'])[0]
    out, after = [], a - .2
    for it in items:
        t = ctx.at(it['on'], after)[0] if isinstance(it, dict) and it.get('on') else (out[-1] + step if out else a)
        out.append(fq(max(t, a)))
        after = t
    return out


# ---------------- easing ----------------
def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def out_cubic(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def in_cubic(u):
    u = clamp(u)
    return u ** 3


def inout_cubic(u):
    u = clamp(u)
    return 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2


def out_back(u, s=1.7):
    u = clamp(u) - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def in_back(u, s=1.7):
    u = clamp(u)
    return (s + 1) * u ** 3 - s * u ** 2


def spring(u, zeta=.42, w=11.0):
    """damped spring 0 -> 1 with a visible overshoot (u in seconds-ish units, settles by ~1)."""
    if u <= 0:
        return 0.0
    wd = w * math.sqrt(1 - zeta * zeta)
    return 1 - math.exp(-zeta * w * u) * (math.cos(wd * u) + zeta * w / wd * math.sin(wd * u))


# ---------------- faces ----------------
def face_track(ctx, a, end, step=.2):
    """f(t) -> padded face box [x0, y0, x1, y1] of the speaker, interpolated inside a shot, never across a cut."""
    ts = [a + k * step for k in range(int((end - a) / step) + 2)]
    raw = [ctx.speaker_face(min(t, ctx.DUR - .06)) for t in ts]
    if not any(raw):
        return None
    for i, b in enumerate(raw):   # fill misses from the nearest sample
        if b is None:
            raw[i] = min(((abs(i - j), r) for j, r in enumerate(raw) if r), key=lambda x: x[0])[1]
    cuts = sorted(s['frame'] / FPS for s in ctx.seg)

    def shot(t):
        return sum(1 for c in cuts if c <= t + 1e-3)
    sm = []   # 3-sample median inside a shot (the detector jitters a few px)
    for i in range(len(raw)):
        nb = [raw[j] for j in (i - 1, i, i + 1) if 0 <= j < len(raw) and shot(ts[j]) == shot(ts[i])]
        sm.append([sorted(b[k] for b in nb)[len(nb) // 2] for k in range(4)])

    def f(t):
        if t <= ts[0]:
            return sm[0]
        for i in range(len(ts) - 1):
            if ts[i] <= t <= ts[i + 1]:
                if shot(ts[i]) != shot(ts[i + 1]):
                    return sm[i] if shot(t) == shot(ts[i]) else sm[i + 1]
                u = (t - ts[i]) / step
                return [lerp(sm[i][k], sm[i + 1][k], u) for k in range(4)]
        return sm[-1]
    return f


def all_faces(ctx, t):
    return ctx.faces_at(min(t, ctx.DUR - .06))


def box_face_share(box, faces, margin=18):
    """share of the worst face covered by box. Faces grow by margin px first: the audit re-detects faces on the graded
    frame and lands up to ~20 px off, and it sums every stacked part of a card (card, image, label), so a graze here is
    a multi-percent hit there."""
    worst = 0.0
    for fx0, fy0, fx1, fy1 in faces:
        fx0, fy0, fx1, fy1 = fx0 - margin, fy0 - margin, fx1 + margin, fy1 + margin
        ix, iy = max(0, min(box[2], fx1) - max(box[0], fx0)), max(0, min(box[3], fy1) - max(box[1], fy0))
        worst = max(worst, ix * iy / max(1, (fx1 - fx0) * (fy1 - fy0)))
    return worst


def unsafe(box, pad=0):
    x0, y0, x1, y1 = box
    return x0 < SAFE[0] - pad or x1 > SAFE[2] + pad or y0 < SAFE[1] - pad or y1 > SAFE[3] + pad or (x1 > RAIL[0] and y1 > RAIL[1])


# ---------------- claims (captions, name tags, eyebrow make room) ----------------
def claim(ctx, top, bottom, t0, t1, pause=False):
    cap = int(ctx._caption_cfg().get('top', 1250))
    if pause or bottom > cap - 16:
        ctx.busy.append((t0, t1))
    if bottom > 1060:
        ctx.lowbusy.append((t0, t1))
    if top < 400:
        ctx.topbusy.append((t0, t1))


# ---------------- tiles ----------------
GLYPH = .56


def wrap(text, width, fs, k=GLYPH):
    lines, cur = [], ''
    for w in str(text).split():
        t = f'{cur} {w}'.strip()
        if cur and len(t) * fs * k > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def fit(ctx, what, texts, width, fmax, fmin, max_lines):
    texts = [str(t) for t in texts if t]
    if not texts:
        return fmin
    for fs in range(int(fmax), int(fmin) - 1, -2):
        if all(len(wrap(t, width, fs)) <= max_lines and max(len(w) for w in t.split()) * fs * GLYPH <= width for t in texts):
            return fs
    ctx.fail(f'{what}: {max(texts, key=len)!r} does not fit {max_lines} line(s) at {fmin}px inside a {width:.0f}px tile; shorten it')


def need_tiles(ctx, g, key, lo, hi):
    tiles = g.get(key) or []
    if not lo <= len(tiles) <= hi or not all(isinstance(t, dict) and (t.get('title') or t.get('src')) for t in tiles):
        ctx.fail(f'{g["type"]} on {g["on"]!r} needs {lo} to {hi} {key}, each with "title" (and optional "src", "sub")')
    for t in tiles:
        if not t.get('title'):
            ctx.fail(f'{g["type"]} on {g["on"]!r}: every tile needs a "title" that says what it shows (an image alone adds no information)')
    return tiles


def tiles_html(ctx, tiles, W, H, title_fs, sub_fs, label_cls='lb'):
    """inner html per tile: an image tile (cover image + label) or a generated text tile (kicker, title, sub)."""
    out = []
    for k, t in enumerate(tiles):
        title, sub = ctx.esc(t.get('title', '')), ctx.esc(t.get('sub', ''))
        if t.get('src'):
            url = ctx.asset(t['src'])
            body = (f'<img class="im" src="{url}">'
                    f'<div class="{label_cls}"><div class="lt" style="font-size:{title_fs}px">{title}</div></div>')
        else:
            kick = ctx.esc(t.get('kicker') or f'{k + 1:02d}')
            body = (f'<div class="tg v{k % 4}"><div class="kk" style="font-size:{sub_fs}px">{kick}</div>'
                    f'<div class="tt" style="font-size:{title_fs}px">{title}</div>'
                    + (f'<div class="sb" style="font-size:{sub_fs}px">{sub}</div>' if sub else '') + '</div>')
        out.append(body)
    return out


def tile_fonts(ctx, what, tiles, W, H, tmax=46, smin=28):
    """(title_fs, sub_fs) shared by every tile so parallel tiles read the same."""
    inner = W - 2 * max(10, W * .08) - 4
    tfs = fit(ctx, f'{what} titles', [t.get('title', '') for t in tiles], inner, tmax, smin, 3 if H > W * 1.3 else 2)
    sfs = max(smin, min(int(tfs * .7), 34))
    if any(t.get('sub') for t in tiles):
        sfs = fit(ctx, f'{what} subs', [t.get('sub', '') for t in tiles], inner, sfs, smin, 2)
    return tfs, sfs


# ---------------- emission ----------------
KF_HELPER = ("window.RKKF=window.RKKF||function(a,d){for(var i=0;i<a.length;i++){a[i].duration=d;a[i].ease='none';"
             "if('zIndex' in a[i])a[i].snap='zIndex';}return a;};")


def num(v):
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def js(d):
    return '{' + ','.join(f'{k}:{num(v) if isinstance(v, (int, float)) else json.dumps(v)}' for k, v in d.items()) + '}'


def emit_track(ctx, sel, t0, states):
    """states: one dict per frame from t0. Sets the first pose, then one keyframe tween across the rest."""
    if not getattr(ctx, '_rkkf', False):
        ctx.tw(KF_HELPER)
        ctx._rkkf = True
    keys = list(states[0].keys())
    ctx.tw(f"gsap.set('{sel}',{js(states[0])});")
    if len(states) < 2:
        return
    # drop keys that never change after the first pose (keeps the page small)
    live = [k for k in keys if any(k in s and abs(s[k] - states[0][k]) > 1e-3 for s in states[1:])]
    if not live:
        return
    body = ','.join(js({k: s[k] for k in live}) for s in states[1:])
    ctx.tw(f"tl.to('{sel}',{{keyframes:RKKF([{body}],{DT:.6f}),immediateRender:false}},{t0:.4f});")


def band_cover(ctx, t, box):
    """worst share of any 44 px horizontal band of box hidden by the speakers at t (the audit judges image tiles in 44 px bands)."""
    if not ctx.has_cut:
        return 0.0
    x0, y0, x1, y1 = box
    worst, y = 0.0, y0
    while y < y1 - 10:
        worst = max(worst, ctx.alpha_cover(t, x0, y, x1, min(y1, y + 44)))
        y += 44
    return worst


def overlap_share(a, b):
    ix, iy = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy / max(1, min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])))


def soft_min(vals, rate, hold=0):
    """each value becomes the min over its neighbours plus rate per frame of distance: a dim starts before an occlusion and
    ends after it, ramping instead of popping."""
    if hold:   # widen every dip by hold frames first, so the ramp happens outside it, never inside
        vals = [min(vals[max(0, i - hold):i + hold + 1]) for i in range(len(vals))]
    n, out = len(vals), []
    reach = int(math.ceil(1 / max(rate, 1e-3)))
    for i in range(n):
        out.append(min(vals[j] + abs(j - i) * rate for j in range(max(0, i - reach), min(n, i + reach + 1))))
    return out


DIM = .42   # opacity of a wall tile while the speaker or a front tile covers it (the receding depth look)


def wall_cls():
    return 'wallz'


def group_cls(ctx):
    ctx._rkgrp = getattr(ctx, '_rkgrp', 0) + 1
    return f'fxg{ctx._rkgrp}'
