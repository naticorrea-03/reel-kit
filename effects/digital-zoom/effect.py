"""Digital zoom: a fast punch-in on the speaker's face on one word, the word big on screen, then an ease back out."""

META = {
    'id': 'digital-zoom', 'name': 'Digital zoom', 'category': 'text',
    'when': 'One word carries the line (a verdict, a number, a name). The frame punches in on the face as it is said.',
    'never': 'Never twice in a row. Never during a behind-the-head word or a wall window (those stay put while the footage zooms).',
    'params': {'on': 'the word (or phrase) it punches on', 'word': 'big text, default the on phrase', 'scale': 'punch amount, default 1.3 (capped so the face stays in frame)',
               'hold': 'seconds held in, default 0.7', 'sfx': 'optional sound name, literal only (none by default)'},
    'sfx': [], 'source': 'ours', 'credit': 'inspired by tenfoldmarc', 'license': 'MIT',
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


def build(g, ctx):
    a, b = ctx.at(g['on'])
    word = str(g.get('word') or g['on'])
    want = max(1.05, min(1.6, float(g.get('scale', 1.3))))
    t_in, t_out = .16, .38
    hold = max(b - a, float(g.get('hold', .7)))
    end = a + t_in + hold + t_out
    # the cut punches scale #stage; this zoom scales the footage inside it, so a cut in the window would stack two moves: stop short of it
    cuts = [s['frame'] / ctx.F for s in ctx.seg[1:] if a + .05 < s['frame'] / ctx.F < end + .05]
    if cuts:
        end = min(cuts) - .05
        hold = end - a - t_in - t_out
        if hold < .2:
            ctx.fail(f'digital-zoom on {g["on"]!r}: a shot cut lands {min(cuts) - a:.2f} s after the word; zoom on a word earlier in the shot')
        ctx.note(f'digital-zoom on {g["on"]!r} shortened to end before the cut at {min(cuts):.2f} s')
    later = [t for h in ctx.graphics if h is not g and h.get('on') for t in [ctx.at(h['on'])[0]] if t > a + .05]
    if later and min(later) < end:
        ctx.fail(f'digital-zoom on {g["on"]!r} overlaps the next graphic at {min(later):.2f} s; move one of them')
    faces = [f for f in (ctx.speaker_face(a + (end - a) * k / 4) for k in range(5)) if f]
    if not faces:
        ctx.fail(f'digital-zoom on {g["on"]!r}: no face to zoom on')
    f0 = faces[0]
    ox, oy = (f0[0] + f0[2]) / 2, (f0[1] + f0[3]) / 2
    # scaling around the face centre keeps it where it is; cap the scale so every padded face box stays in frame
    s = want
    for f in faces:
        for (v, o, lo, hi) in ((f[0], ox, 20, 1060), (f[2], ox, 20, 1060), (f[1], oy, 120, 1800), (f[3], oy, 120, 1800)):
            p = o + (v - o) * s
            if p < lo:
                s = min(s, (o - lo) / max(1, o - v))
            elif p > hi:
                s = min(s, (hi - o) / max(1, v - o))
    s = max(1.0, s)
    if s < 1.1:
        ctx.warn(f'digital-zoom on {g["on"]!r}: the face already fills the frame, punch is only {s:.2f}x')
    zf = [[ox + (f[0] - ox) * s, oy + (f[1] - oy) * s, ox + (f[2] - ox) * s, oy + (f[3] - oy) * s] for f in faces]
    # the word: biggest that fits, below the zoomed chin, else above the zoomed head
    fs = _fit(ctx, 'digital-zoom word', [word], 820, 190, 80, 1, k=.6)
    hh = int(fs * 1.1)
    clear = lambda y: all(min(1080, f[2]) <= 130 or max(0, f[0]) >= 950 or y + hh <= f[1] or y >= f[3] for f in zf)
    below = [y for y in range(int(max(f[3] for f in zf)) + 10, 1470 - hh, 10) if clear(y)]
    above = [y for y in range(240, int(min(f[1] for f in zf)) - hh, 10) if clear(y)]
    if below:
        wy = below[0]
    elif above:
        wy = above[-1]
    else:
        fs = _fit(ctx, 'digital-zoom word', [word], 820, 120, 60, 1, k=.6)
        hh = int(fs * 1.1)
        wy = next((y for y in range(240, 1470 - hh, 10) if clear(y)), None)
        if wy is None:
            ctx.fail(f'digital-zoom on {g["on"]!r}: no room for {word!r} beside the zoomed face; pass a shorter word or a smaller scale')
    lum, busy = ctx.bg_luma(a, end, 130, wy, 950, wy + hh)
    over = ctx.alpha_cover(a + .2, 130, wy, 950, wy + hh)   # letters over the speaker stay light
    tone = ' ink' if lum > .62 and busy < .12 and over < .15 else ''
    ctx.busy.append((a, end))
    if wy + hh > 1060:
        ctx.lowbusy.append((a, end))
    if wy < 400:
        ctx.topbusy.append((a, end))
    cid = ctx.clip(ctx.front, a, end, f'<div class="fx-digital-zoom"><div class="w{tone}" style="font-size:{fs}px">{ctx.esc(word)}</div></div>',
                   f'position:absolute;left:0;right:0;top:{wy}px;')
    org = f'{ox:.0f}px {oy:.0f}px'
    for el in ('#bgv', '#cutwrap'):   # footage and cutout scale together so the cutout stays on the face
        ctx.tw(f"tl.fromTo('{el}',{{scale:1,transformOrigin:'{org}'}},{{scale:{s:.3f},transformOrigin:'{org}',duration:{t_in},ease:'expo.out',immediateRender:false}},{ctx.q(a)});")
        ctx.tw(f"tl.to('{el}',{{scale:1,duration:{t_out},ease:'power2.inOut'}},{ctx.q(end - t_out)});")
    ctx.tw(f"tl.fromTo('#{cid} .w',{{opacity:0,scale:1.25}},{{opacity:1,scale:1,duration:.18,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.to('#{cid} .w',{{opacity:0,scale:.92,duration:.2,ease:'power2.in'}},{ctx.q(end - t_out)});")
    ctx.sfx(g.get('sfx'), a, .35)


def describe(g, beat):
    return (f'On “{g["on"]}” the frame punches in on the speaker\'s face with "{g.get("word") or g["on"]}" big on screen, '
            f'then eases back out. It holds {beat["hold"]:.1f} s.')
