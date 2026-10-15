"""Hand-drawn circle or underline that draws itself around a spot in the frame, with an optional handwritten label."""
import math, re

META = {
    'id': 'hw-underline', 'name': 'Hand-drawn circle', 'category': 'annotation',
    'when': 'The speaker refers to one thing in the shot or inside another graphic (a sign, a product, one line of a screenshot). '
            'A marker circle or underline picks it out.',
    'never': 'Never around a face. Never across a cut: the target moves when the shot changes. Never a label that repeats the spoken words.',
    'params': {'on': 'phrase that triggers it', 'box': '[x, y, w, h] of the target on the 1080x1920 canvas, read off a beat-sheet frame (required)',
               'mode': '"circle" (default) or "underline"', 'what': 'what sits in the box, for the plan (required)',
               'label': 'optional short handwritten label that adds information', 'color': '"accent" (default) or "text"',
               'hold': 'seconds, default 1.8', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours',
    'credit': 'Idea from the hw-underline motion in the HyperFrames registry (heygen-com/hyperframes, Apache-2.0), as listed in claude-reel-editor '
              'references/motions.md by Nicola Pocock (MIT). Written from scratch for reel-kit; no registry code copied.',
    'license': 'MIT',
}

# ---------- local helpers (proposed for fxlib: wrap, fit, window, spot, claim) ----------
GLYPH = .56   # average glyph width in em, on the wide side so an estimated box never comes up short


def _wrap(text, width, fs, k=GLYPH):
    """greedy word wrap estimate: the lines text breaks into at fs px inside width px."""
    lines, cur = [], ''
    for w in str(text).split():
        t = f'{cur} {w}'.strip()
        if cur and len(t) * fs * k > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def _fit(ctx, what, texts, width, fmax, fmin=30, max_lines=3, k=GLYPH):
    """one font size for every text (parallel items share a size), the largest that fits width in max_lines."""
    texts = [str(t) for t in texts if t]
    for fs in range(int(fmax), int(fmin) - 1, -2):
        if all(len(_wrap(t, width, fs, k)) <= max_lines and max(len(w) for w in t.split()) * fs * k <= width for t in texts):
            return fs
    ctx.fail(f'{what}: {max(texts, key=len)!r} does not fit {max_lines} line(s) at {fmin}px; shorten it')


def _lines(texts, width, fs, k=GLYPH):
    return max([len(_wrap(t, width, fs, k)) for t in texts if t] or [0])


def _window(ctx, g, hold, last=None):
    """(a, end): lands on its word, clears before the next graphic, the until phrase, or the end of the clip."""
    a = ctx.at(g['on'])[0]
    last = a if last is None else last
    end = min(ctx.DUR - .05, last + float(g.get('hold', hold)))
    if g.get('until'):
        end = min(end, ctx.at(g['until'], a)[0] - .05)
    later = [t for h in ctx.graphics if h is not g and h.get('on') for t in [ctx.at(h['on'])[0]] if t > a + .05]
    if later:
        end = min(end, min(later) - .15)
    if end - last < .7:
        ctx.fail(f'{g["type"]} on {g["on"]!r} gets {end - last:.2f} s after its last beat before the next graphic or the end; '
                 'move it or the graphic after it')
    return a, end


def _cap_top(ctx):
    return int(ctx._caption_cfg().get('top', 1250))


def _grid(w, h, xs=None, step=40):
    xs = xs or (90, (1080 - w) // 2, 950 - w)
    ys = list(range(250, 1471 - int(h), step)) + [1470 - int(h)]   # always try the lowest spot: under-chin bands are tight
    return [(int(x), int(y)) for y in ys for x in xs]


def _spot(ctx, what, w, h, t0, t1, cands, near=None, pause=False, quiet=False):
    """(x, y): the candidate that clears faces first, then the caption band, then hides the least of the speakers."""
    cap, best = _cap_top(ctx), None
    for x, y in cands:
        x, y = int(max(90, min(x, 950 - w))), int(max(250, min(y, 1470 - h)))
        face = ctx.face_hit(t0, t1, x, y, x + w, y + h)
        c = 10 * face + .3 * max(ctx.alpha_cover(t0 + (t1 - t0) * k / 3, x, y, x + w, y + h) for k in range(4))
        if not pause and y + h > cap - 16:
            c += .5
        if near:
            c += .3 * ((x + w / 2 - near[0]) ** 2 + (y + h / 2 - near[1]) ** 2) ** .5 / 1000
        if best is None or c < best[0] - .005:
            best = (c, x, y, face)
    if best is None:
        ctx.fail(f'{what}: a {w}x{h} box does not fit the safe zone (x 90-950, y 250-1470); make it smaller')
    if best[3] > .02 and not quiet:
        ctx.warn(f'{what} still covers {best[3]:.0%} of a face')
    return best[1], best[2]


def _fitspot(ctx, what, w, h, t0, t1, cands, near=None, pause=False):
    """(x, y, scale): full size where a spot clears the faces, else the card shrinks (0.86, 0.74) until one does."""
    tries = []
    for sc in (1.0, .86, .74):
        ws, hs = int(w * sc), int(h * sc)
        x, y = _spot(ctx, what, ws, hs, t0, t1, cands(ws, hs), near, pause, quiet=True)
        face = ctx.face_hit(t0, t1, x, y, x + ws, y + hs)
        tries.append((face, -sc, x, y))
        if face <= .02:
            break
    face, sc, x, y = min(tries)
    if face > .02:
        ctx.warn(f'{what} still covers {face:.0%} of a face even at 74% size; pick another moment')
    elif -sc < 1:
        ctx.note(f'{what} shrunk to {-sc:.0%} to clear a face')
    return x, y, -sc


def _zclip(ctx, sc, a, b, inner, style):
    """ctx.clip on the front layer, with the card zoomed when _fitspot had to shrink it."""
    return ctx.clip(ctx.front, a, b, inner if sc == 1 else f'<div class="rk-zoom" style="zoom:{sc}">{inner}</div>', style)


def _claim(ctx, x, y, w, h, t0, t1, pause):
    """captions pause when the effect carries its own text or reaches the caption band; name tags and eyebrow make room."""
    if pause or y + h > _cap_top(ctx) - 16:
        ctx.busy.append((t0, t1))
    if y + h > 1060:
        ctx.lowbusy.append((t0, t1))
    if y < 400:
        ctx.topbusy.append((t0, t1))


def _need(ctx, g, *keys):
    for k in keys:
        if g.get(k) in (None, '', []):
            ctx.fail(f'{g["type"]} on {g["on"]!r} needs "{k}"')


def _times(ctx, g, items, step):
    """one time per item: its own "on" phrase (in order, after the previous one) or an even step after the graphic's word."""
    a = ctx.at(g['on'])[0]
    out, after = [], a - .2
    for k, it in enumerate(items):
        t = ctx.at(it['on'], after)[0] if isinstance(it, dict) and it.get('on') else (out[-1] + step if out else a)
        out.append(max(t, a))
        after = t
    return out
# ---------- end of local helpers ----------


def _shot_end(ctx, a):
    """time of the next cut after a: a target fixed on the canvas drifts off its object when the shot changes."""
    cuts = [s['frame'] / ctx.F for s in ctx.seg if s['frame'] / ctx.F > a + .05]
    return min(cuts) - .05 if cuts else ctx.DUR


def _loop(x0, y0, x1, y1):
    """a marker loop around the box: a bit more than one turn, slightly tilted and uneven, like a pen circle."""
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    pts, n, tilt = [], 64, math.radians(-4)
    for k in range(n + 1):
        t = -2.2 + 2 * math.pi * 1.09 * k / n
        r = 1 + .045 * math.sin(3 * t + .7) + .02 * k / n
        px, py = rx * r * math.cos(t), ry * r * math.sin(t)
        pts.append((cx + px * math.cos(tilt) - py * math.sin(tilt), cy + px * math.sin(tilt) + py * math.cos(tilt)))
    return 'M' + ' L'.join(f'{p[0]:.1f} {p[1]:.1f}' for p in pts), sum(math.dist(pts[k], pts[k + 1]) for k in range(n))


def build(g, ctx):
    _need(ctx, g, 'box', 'what')
    bx, by, bw, bh = [float(v) for v in g['box']]
    mode = g.get('mode', 'circle')
    if mode not in ('circle', 'underline'):
        ctx.fail(f'hw-underline mode {mode!r}: use "circle" or "underline"')
    pad = 22 if mode == 'circle' else 0
    x0, y0, x1, y1 = bx - pad, by - pad, bx + bw + pad, by + bh + pad + (18 if mode == 'underline' else 0)
    if x0 < 90 or x1 > 950 or y0 < 240 or y1 > 1470:
        ctx.fail(f'hw-underline box {g["box"]} (with its stroke) leaves the safe zone (x 90-950, y 240-1470)')
    a, end = _window(ctx, g, 1.8)
    se = _shot_end(ctx, a)
    if se < end:
        if se - a < .9:
            ctx.fail(f'hw-underline on {g["on"]!r} gets {se - a:.2f} s before the next cut moves its target; pick a phrase earlier in the shot')
        end = se
    for k in range(5):
        for f in ctx.faces_at(a + (end - a) * k / 4):
            ix, iy = max(0, min(x1, f[2]) - max(x0, f[0])), max(0, min(y1, f[3]) - max(y0, f[1]))
            if ix * iy > .2 * (f[2] - f[0]) * (f[3] - f[1]):
                ctx.fail(f'hw-underline box {g["box"]} is around a face; circle the thing, not the speaker')
    col = 'var(--c-text)' if g.get('color') == 'text' else 'var(--c-accent)'
    if mode == 'circle':
        d, L = _loop(x0, y0, x1, y1)
        paths = [(d, int(L) + 20)]
    else:
        yb = by + bh + 12
        paths = [(f'M{bx - 6:.0f} {yb + 4:.0f} Q {bx + bw / 2:.0f} {yb - 8:.0f} {bx + bw + 6:.0f} {yb:.0f}', int(bw * 1.1) + 30),
                 (f'M{bx + bw * .12:.0f} {yb + 16:.0f} Q {bx + bw / 2:.0f} {yb + 8:.0f} {bx + bw * .9:.0f} {yb + 14:.0f}', int(bw) + 20)]
    svg = (f'<svg class="arr" width="1080" height="1920" viewBox="0 0 1080 1920" style="position:absolute;left:0;top:0;overflow:visible;stroke:{col}">'
           + ''.join(f'<path style="stroke-dasharray:{dl};stroke-dashoffset:{dl}" d="{d}" />' for d, dl in paths) + '</svg>')
    lab = ''
    if g.get('label'):
        tw = re.findall(r'[a-z0-9]+', str(g['label']).lower())
        said = {w for x in ctx.words if a - 2 <= x['start'] <= end + 1 for w in re.findall(r'[a-z0-9]+', x['text'].lower())}
        if tw and all(w in said for w in tw):
            ctx.fail(f'hw-underline label {g["label"]!r} only repeats what is said; make it add information or leave it out')
        best = None
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for fs in (72, 62, 54, 46):
            lw, lh = int(len(g['label']) * fs * .46) + 24, int(fs * 1.15) + 10
            if lw > 860:
                continue
            cands = [(cx - lw / 2, y1 + 14), (x0, y1 + 14), (x1 - lw, y1 + 14), (cx - lw / 2, y0 - lh - 14), (x0, y0 - lh - 14), (x1 - lw, y0 - lh - 14),
                     (x1 + 16, cy - lh / 2), (x0 - lw - 16, cy - lh / 2)]
            for x, y in cands:
                x, y = int(max(90, min(x, 950 - lw))), int(y)
                if not 250 <= y <= 1470 - lh or (x < x1 and x + lw > x0 and y < y1 and y + lh > y0):
                    continue
                if ctx.face_hit(a, end, x, y, x + lw, y + lh) > .005:
                    continue
                cost = max(ctx.alpha_cover(a + (end - a) * k / 2, x, y, x + lw, y + lh) for k in range(3)) + (72 - fs) / 150
                if best is None or cost < best[0]:
                    best = (cost, fs, lw, lh, x, y)
        if best is None:
            ctx.fail('hw-underline: no room for the label next to the box clear of the face; shorten it or leave it out')
        _, fs, lw, lh, lx, ly = best
        _claim(ctx, lx, ly, lw, lh, a, end, False)
        lab = f'<div class="lab" style="left:{lx}px;top:{ly}px;width:{lw}px;font-size:{fs}px;color:{col}">{ctx.esc(g["label"])}</div>'
    if y0 < 400:
        ctx.topbusy.append((a, end))
    cid = ctx.clip(ctx.front, a, end, f'<div class="fx-hw-underline">{svg}{lab}</div>', 'position:absolute;left:0;top:0;width:1080px;height:1920px;')
    ctx.tw(f"tl.to('#{cid} .arr path',{{strokeDashoffset:0,duration:.42,stagger:.18,ease:'power2.inOut'}},{ctx.q(a)});")
    if lab:
        ctx.tw(f"tl.fromTo('#{cid} .lab',{{opacity:0,y:12}},{{opacity:1,y:0,duration:.25,ease:'power2.out',immediateRender:false}},{ctx.q(a + .3)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.18}},{ctx.q(end - .18)});")
    ctx.sfx(g.get('sfx'), a, .35)


def describe(g, beat):
    lab = f' with "{g["label"]}" beside it' if g.get('label') else ''
    return f'On “{g["on"]}” a hand-drawn {g.get("mode", "circle")} draws around {g["what"]}{lab}. It holds {beat["hold"]:.1f} s, inside one shot.'
