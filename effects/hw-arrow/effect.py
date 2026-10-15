"""Hand-drawn arrow: a short handwritten label and an arrow that draws itself to a spot in the frame."""
import math, re

META = {
    'id': 'hw-arrow', 'name': 'Hand-drawn arrow', 'category': 'annotation',
    'when': 'The speaker refers to something visible in the shot (an object, a sign, a part of the room, a line inside another graphic). '
            'The arrow points at it and the label adds what it is.',
    'never': 'Never at the speaker\'s face (that is the note effect). Never across a cut: the target moves when the shot changes. '
             'Never a label that repeats the spoken words.',
    'params': {'on': 'phrase that triggers it', 'target': '[x, y] on the 1080x1920 canvas, read off a beat-sheet frame (required)',
               'label': 'short handwritten label, adds information (required)', 'what': 'what sits at the target, for the plan (required)',
               'color': '"accent" (default) or "text"', 'hold': 'seconds, default 1.8', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours',
    'credit': 'Idea from the hw-arrow motion in the HyperFrames registry (heygen-com/hyperframes, Apache-2.0), as listed in claude-reel-editor '
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


def _echo(ctx, text, a, b):
    tw = re.findall(r'[a-z0-9]+', str(text).lower())
    said = {w for x in ctx.words if a - 2 <= x['start'] <= b + 1 for w in re.findall(r'[a-z0-9]+', x['text'].lower())}
    return bool(tw) and all(w in said for w in tw)


def _arrow(x, y, lw, lh, tx, ty, bend):
    """curve from the label edge facing the target to 18 px short of it (the head never covers what it points at)."""
    sx = min(max(tx, x + 20), x + lw - 20)
    sy = y + lh + 8 if ty > y + lh else (y - 8 if ty < y else y + lh / 2)
    if y <= ty <= y + lh:
        sx = x + lw + 10 if tx > x + lw else x - 10
    dx, dy = tx - sx, ty - sy
    L = max(1.0, math.hypot(dx, dy))
    ex, ey = tx - dx / L * 18, ty - dy / L * 18
    qx, qy = (sx + ex) / 2 - dy * bend, (sy + ey) / 2 + dx * bend
    pts = [((1 - u) ** 2 * sx + 2 * (1 - u) * u * qx + u * u * ex, (1 - u) ** 2 * sy + 2 * (1 - u) * u * qy + u * u * ey) for u in [k / 20 for k in range(21)]]
    return sx, sy, qx, qy, ex, ey, pts


def build(g, ctx):
    _need(ctx, g, 'target', 'label', 'what')
    tx, ty = [float(v) for v in g['target']]
    if not (90 <= tx <= 950 and 240 <= ty <= 1470):
        ctx.fail(f'hw-arrow target {g["target"]} is outside the safe zone (x 90-950, y 240-1470); viewers will not see it under the app UI')
    a, end = _window(ctx, g, 1.8)
    se = _shot_end(ctx, a)
    if se < end:
        if se - a < .9:
            ctx.fail(f'hw-arrow on {g["on"]!r} gets {se - a:.2f} s before the next cut moves its target; pick a phrase earlier in the shot')
        end = se
    for k in range(5):
        for f in ctx.faces_at(a + (end - a) * k / 4):
            if f[0] <= tx <= f[2] and f[1] <= ty <= f[3]:
                ctx.fail(f'hw-arrow target {g["target"]} is on a face; use the note effect to point at the speaker')
    if _echo(ctx, g['label'], a, end):
        ctx.fail(f'hw-arrow label {g["label"]!r} only repeats what is said; make it add information')
    best = None
    fboxes = [f for k in range(4) for f in ctx.faces_at(a + (end - a) * k / 3)]
    for fs in (76, 64, 54, 46):
        if len(g['label']) * fs * .46 > 1200:
            continue
        lines = _wrap(g['label'], 560, fs, .46)
        if len(lines) > 2:
            continue
        lw = int(max(len(l) for l in lines) * fs * .46) + 24
        lh = int(len(lines) * fs * 1.1) + 12
        for x, y in _grid(lw, lh, xs=(90, 220, 350, 480, 610, 950 - lw), step=30):
            x = max(90, min(x, 950 - lw))
            d = math.hypot(x + lw / 2 - tx, y + lh / 2 - ty)
            if not 220 <= d <= 620 or (x - 60 <= tx <= x + lw + 60 and y - 60 <= ty <= y + lh + 60):
                continue
            if ctx.face_hit(a, end, x, y, x + lw, y + lh) > .005:
                continue
            for bend in (.2, -.2):
                path = _arrow(x, y, lw, lh, tx, ty, bend)
                if not any(f[0] <= px <= f[2] and f[1] <= py <= f[3] for px, py in path[-1] for f in fboxes):
                    break
            else:
                continue   # every curve crosses a face
            cov = max(ctx.alpha_cover(a + (end - a) * k / 2, x, y, x + lw, y + lh) for k in range(3))
            cost = cov + abs(d - 360) / 1000 + (76 - fs) / 150
            if best is None or cost < best[0]:
                best = (cost, fs, lines, lw, lh, x, y, path)
    if best is None:
        ctx.fail(f'hw-arrow: no spot for the label near {g["target"]} where it and its arrow clear the face; shorten the label or pick another moment')
    _, fs, lines, lw, lh, x, y, (sx, sy, qx, qy, ex, ey, _pts) = best
    _claim(ctx, x, y, lw, lh, a, end, False)
    L = max(1.0, math.hypot(ex - sx, ey - sy))
    ang = math.atan2(ey - qy, ex - qx)
    hd = [(ex - 34 * math.cos(ang + d), ey - 34 * math.sin(ang + d)) for d in (.5, -.5)]
    dl = int(L * 1.4) + 40
    col = 'var(--c-text)' if g.get('color') == 'text' else 'var(--c-accent)'
    svg = (f'<svg class="arr" width="1080" height="1920" viewBox="0 0 1080 1920" style="position:absolute;left:0;top:0;overflow:visible;stroke:{col}">'
           f'<path style="stroke-dasharray:{dl};stroke-dashoffset:{dl}" d="M{sx:.0f} {sy:.0f} Q {qx:.0f} {qy:.0f} {ex:.0f} {ey:.0f}" />'
           f'<path style="stroke-dasharray:90;stroke-dashoffset:90" d="M{hd[0][0]:.0f} {hd[0][1]:.0f} L {ex:.0f} {ey:.0f} L {hd[1][0]:.0f} {hd[1][1]:.0f}" /></svg>')
    lab = ''.join(f'<div>{ctx.esc(l)}</div>' for l in lines)
    cid = ctx.clip(ctx.front, a, end, f'<div class="fx-hw-arrow">{svg}<div class="lab" style="left:{x}px;top:{y}px;width:{lw}px;font-size:{fs}px;color:{col}">{lab}</div></div>',
                   'position:absolute;left:0;top:0;width:1080px;height:1920px;')
    ctx.tw(f"tl.fromTo('#{cid} .lab',{{opacity:0,scale:.85,rotation:-6}},{{opacity:1,scale:1,rotation:-3,duration:.28,ease:'back.out(2)',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.to('#{cid} .arr path',{{strokeDashoffset:0,duration:.4,stagger:.32,ease:'power2.out'}},{ctx.q(a + .12)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.18}},{ctx.q(end - .18)});")
    ctx.sfx(g.get('sfx'), a, .35)


def describe(g, beat):
    return f'On “{g["on"]}” a handwritten "{g["label"]}" appears and an arrow draws to {g["what"]}. It holds {beat["hold"]:.1f} s, inside one shot.'
