"""Freeze and label: the frame stops on a word, one to three labels point at things in it with thin leader lines, then the video runs on."""
import os, subprocess

META = {
    'id': 'freeze-label', 'name': 'Freeze and label', 'category': 'annotation',
    'when': 'The speaker says something about themselves or what is in frame that a label can name (a role, an object, a before state).',
    'never': 'Never labels that repeat the caption. Never more than three. Never on a cut (the frozen frame is the shot on the word).',
    'params': {'on': 'phrase where the frame freezes', 'labels': '[{"text", "at", "on"}] 1 to 3 (required). at: head, eyes, face, chin, chest, '
               'left, right (shoulders, as seen on screen), or [x, y] as fractions of the face box; on: phrase where it appears (default staggered)',
               'hold': 'seconds frozen, default 1.8', 'sfx': 'sound on the freeze, default camera-shutter ("none" for silence)'},
    'sfx': ['camera-shutter'], 'source': 'ours', 'credit': 'inspired by tenfoldmarc', 'license': 'MIT',
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


def _fitspot(ctx, what, w, h, t0, t1, cands, near=None, pause=False, scales=(1.0, .86, .74)):
    """(x, y, scale): full size where a spot clears the faces, else the card shrinks (0.86, 0.74) until one does."""
    tries = []
    for sc in scales:
        ws, hs = int(w * sc), int(h * sc)
        x, y = _spot(ctx, what, ws, hs, t0, t1, cands(ws, hs), near, pause, quiet=True)
        face = ctx.face_hit(t0, t1, x, y, x + ws, y + hs)
        tries.append((face, -sc, x, y))
        if face <= .02:
            break
    face, sc, x, y = min(tries)
    if face > .02:
        ctx.warn(f'{what} still covers {face:.0%} of a face even at {min(scales):.0%} size; pick another moment')
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

# points as fractions of the bare face box (detector box without the audit padding): 0,0 is the top left of the face
ANCHORS = {'head': (.5, -.22), 'hair': (.5, -.22), 'eyes': (.5, .4), 'face': (.5, .55), 'mouth': (.5, .78), 'chin': (.5, 1.02),
           'chest': (.5, 1.6), 'left': (-.55, 1.65), 'right': (1.55, 1.65)}


def _crosses(sx, sy, tx, ty, box):
    """True when the leader line runs over the face box before its last 18 % (a line through the face reads as a scratch)."""
    x0, y0, x1, y1 = box
    for k in range(0, 83, 3):
        px, py = sx + (tx - sx) * k / 100, sy + (ty - sy) * k / 100
        if x0 < px < x1 and y0 < py < y1:
            return True
    return False


def build(g, ctx):
    labels = [x if isinstance(x, dict) else {'text': x} for x in (g.get('labels') or [])]
    if not 1 <= len(labels) <= 3 or not all(l.get('text') for l in labels):
        ctx.fail(f'freeze-label on {g["on"]!r} needs 1 to 3 labels, each with "text"')
    a = ctx.at(g['on'])[0]
    for x in ctx.seg[1:]:
        if a - .02 < x['frame'] / ctx.F < a + float(g.get('hold', 1.8)):
            ctx.warn(f'freeze-label on {g["on"]!r}: a shot cut at {x["frame"] / ctx.F:.2f} s falls inside the freeze (the still hides it)')
    times = _times(ctx, g, labels, .45)
    times = [t + (.25 if k == 0 and not labels[0].get('on') else 0) for k, t in enumerate(times)]
    hold = float(g.get('hold', 1.8))
    a, end = _window(ctx, g, hold, last=max(a, times[-1] + 1.0 - hold))
    face = ctx.speaker_face(a + .02)
    if not face:
        ctx.fail(f'freeze-label on {g["on"]!r}: no face in the frozen frame to label around')
    # undo the detector padding (x - .12 w .. x + 1.12 w, y - .30 h .. y + 1.18 h) to get the bare face
    fw, fh = (face[2] - face[0]) / 1.24, (face[3] - face[1]) / 1.48
    fx0, fy0 = face[0] + .12 * fw, face[1] + .30 * fh
    fx1, fy1 = fx0 + fw, fy0 + fh
    core = (fx0 + .05 * fw, fy0 - .1 * fh, fx1 - .05 * fw, fy1)
    # the still: the a-roll frame on the word, laid over footage and cutout inside the stage so grade and punches match
    still = os.path.join(ctx.work, f'freeze-{a:.2f}.jpg')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{a:.3f}', '-i', os.path.join(ctx.D, 'assets', 'aroll.mp4'),
                    '-frames:v', '1', '-q:v', '2', still], check=True)
    url = ctx.asset(still)
    pid = ctx.clip(ctx.wall, a, end, f'<img class="rk-plate full g" src="{url}">', 'position:absolute;inset:0;')
    ctx.tw(f"tl.fromTo('#{pid} img',{{scale:1}},{{scale:1.025,duration:{end - a:.3f},ease:'sine.out',immediateRender:false}},{ctx.q(a)});")
    # labels: chip beside the face, line to the anchor point
    fs = _fit(ctx, 'freeze-label text', [l['text'] for l in labels], 520, 40, 30, 1)
    placed, html, lines = [], '', ''
    for k, l in enumerate(labels):
        at = l.get('at', ('head', 'chest', 'left')[k])
        ux, uy = at if isinstance(at, (list, tuple)) else ANCHORS.get(str(at), (None, None))
        if ux is None:
            ctx.fail(f'freeze-label: unknown anchor {at!r}; use {", ".join(ANCHORS)} or [x, y]')
        tx, ty = min(1000, max(80, fx0 + ux * fw)), min(1460, max(250, fy0 + uy * fh))
        w = int(len(l['text']) * fs * .58) + 70 + 44
        h = int(fs * 1.25) + 28
        cands = [(int(max(100, min(x, 940 - w))), y) for y in range(250, 1470 - h, 20)
                 for x in (face[0] - w - 30, 110, face[2] + 30, 940 - w, (1080 - w) // 2, tx - w / 2)]
        best = None
        for x, y in cands:
            c = 10 * ctx.face_hit(times[k], end, x - 36, y - 36, x + w + 36, y + h + 36)   # the speaker keeps moving under the still: wide margin
            if any(not (x + w + 20 < p[0] or p[2] + 20 < x or y + h + 16 < p[1] or p[3] + 16 < y) for p in placed):
                c += 5
            c += ((x + w / 2 - tx) ** 2 + (y + h / 2 - ty) ** 2) ** .5 / 900
            ex = x if tx < x else (x + w if tx > x + w else tx)
            ey = y + h / 2 if ex in (x, x + w) else (y + h if ty > y + h else y)
            if _crosses(ex, ey, tx, ty, core):
                c += 3
            if y + h > _cap_top(ctx) - 16:   # allowed (captions pause), but only when nothing clear sits higher
                c += .8
            if abs(y + h / 2 - ty) < h:   # a level line reads as a strike-through: prefer a slope
                c += .15
            if best is None or c < best[0]:
                best = (c, x, y)
        _, x, y = best
        if best[0] >= 5:
            ctx.warn(f'freeze-label {l["text"]!r} could not find a clear spot')
        placed.append((x, y, x + w, y + h))
        # the line leaves the chip from the edge nearest the target
        sx = x if tx < x else (x + w if tx > x + w else min(max(tx, x + 30), x + w - 30))
        sy = y + h / 2 if sx in (x, x + w) else (y + h if ty > y + h else y)
        L = int(((tx - sx) ** 2 + (ty - sy) ** 2) ** .5) + 4
        html += (f'<div class="chip c{k}" style="left:{x}px;top:{y}px;font-size:{fs}px"><span class="n">{k + 1:02d}</span>'
                 f'<span class="t">{ctx.esc(l["text"])}</span></div>')
        lines += (f'<path class="l{k}" style="stroke-dasharray:{L};stroke-dashoffset:{L}" d="M{sx:.0f} {sy:.0f} L{tx:.0f} {ty:.0f}"/>'
                  f'<circle class="d{k}" cx="{tx:.0f}" cy="{ty:.0f}" r="9"/>')
    cid = ctx.clip(ctx.front, a, end, f'<div class="fx-freeze-label"><svg class="arr" width="1080" height="1920" viewBox="0 0 1080 1920" '
                   f'style="position:absolute;left:0;top:0;overflow:visible">{lines}</svg>{html}</div>',
                   'position:absolute;left:0;top:0;width:1080px;height:1920px;')
    for k, t in enumerate(times):
        ctx.tw(f"gsap.set('#{cid} .c{k}, #{cid} .d{k}',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .c{k}',{{opacity:0,scale:.85}},{{opacity:1,scale:1,duration:.24,ease:'back.out(2)',immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.to('#{cid} .l{k}',{{strokeDashoffset:0,duration:.3,ease:'power2.out'}},{ctx.q(t + .08)});")
        ctx.tw(f"tl.fromTo('#{cid} .d{k}',{{opacity:0,scale:0,transformOrigin:'50% 50%'}},{{opacity:1,scale:1,duration:.18,ease:'back.out(3)',immediateRender:false}},{ctx.q(t + .32)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.18}},{ctx.q(end - .18)});")
    if any(p[1] < 400 for p in placed):
        ctx.topbusy.append((a, end))
    if any(p[3] > _cap_top(ctx) - 16 for p in placed):
        ctx.busy.append((a, end))
    ctx.sfx(g.get('sfx', 'camera-shutter'), a, .35)


def describe(g, beat):
    labs = [l['text'] if isinstance(l, dict) else l for l in g['labels']]
    return (f'On “{g["on"]}” the frame freezes for {beat["hold"]:.1f} s and labels point into it: '
            + ', '.join(f'"{t}"' for t in labs) + '. Then the video runs on.')
