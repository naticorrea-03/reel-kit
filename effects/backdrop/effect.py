"""Backdrop: the room behind the speaker is swapped for a solid brand color or an image, with big words above and below."""

META = {
    'id': 'backdrop', 'name': 'Backdrop swap', 'category': 'structure',
    'when': 'A reveal or a turn in the story ("don\'t worry", "here is the fix"): the background drops to a brand color or a relevant image '
            'behind the speaker, with one or two big words.',
    'never': 'Never without a speaker cutout. Never more than once or twice a reel. Never words that only fill space: name the turn.',
    'params': {'on': 'phrase that triggers it', 'top': 'big word(s) in the band above the head (required)', 'bottom': 'optional second word(s), lower down',
               'bg': '"accent" (default), "accent2", "ink", "card", or an image file (project-relative)',
               'hold': 'seconds, default 2.0', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'claude-reel-editor',
    'credit': 'Adapted from the "block" and "page" cards in claude-reel-editor by Nicola Pocock (getgitgirl): a full-screen brand color or image '
              'with the speaker kept in frame and words wiping on. Here the speaker cutout stands in front of the color instead of a framed copy of the clip.',
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

SOLID = {'accent': 'var(--c-on-accent)', 'accent2': 'var(--c-text)', 'ink': 'var(--c-text)', 'card': 'var(--c-ink)'}


def _wall_y(ctx, h, t0, t1, ys):
    """first y in ys where a full-width line of height h stays clear of the speakers on the wall."""
    for y in ys:
        if max(ctx.alpha_cover(t0 + (t1 - t0) * k / 4, 90, y, 990, y + h) for k in range(5)) < .02 \
                and ctx.face_hit(t0, t1, 90, y, 950, y + h) <= .005:   # padded face boxes reach past the hair
            return y
    return None


def build(g, ctx):
    _need(ctx, g, 'top')
    if not ctx.has_cut:
        ctx.fail(f'backdrop on {g["on"]!r} needs the speaker cutout (assets/subject.webm); without it the color would hide the speaker')
    a, end = _window(ctx, g, 2.0)
    bg = g.get('bg', 'accent')
    if bg in SOLID:
        bgcss, ink = f'background:var(--c-{bg});', SOLID[bg]
    else:
        url = ctx.asset(bg)
        bgcss = (f"background:linear-gradient(180deg,color-mix(in srgb,var(--c-shadow) 60%,transparent) 0%,transparent 40%,transparent 60%,"
                 f"color-mix(in srgb,var(--c-shadow) 55%,transparent) 100%),url('{url}') center/cover;")
        ink = 'var(--c-text)'
    texts = [str(g['top'])] + ([str(g['bottom'])] if g.get('bottom') else [])
    fs = min(_fit(ctx, f'backdrop {t!r}', [t], 860, 210, 70, 1, .64) for t in texts)
    h = int(fs * 1.02) + 8
    ytop = _wall_y(ctx, h, a, end, range(250, 1471 - h, 10))
    spots = []   # (text, y, on the wall?)
    if ytop is not None:
        spots.append((texts[0], ytop, True))
    else:   # no clear band beside the heads: the word goes in front, under the face
        _, y = _spot(ctx, 'backdrop top', 860, h, a, end, [(90, y) for y in range(250, 1471 - h, 10)], None, True)
        spots.append((texts[0], y, False))
    if len(texts) > 1:
        lo = spots[0][1] + h + 30
        yb = _wall_y(ctx, h, a, end, range(1470 - h, lo - 1, -10))
        if yb is not None:
            spots.append((texts[1], yb, True))
        else:
            cands = [(90, y) for y in range(1470 - h, lo - 1, -10)]
            if not cands:
                ctx.fail(f'backdrop {texts!r}: no room for two lines at {fs}px; shorten them or drop "bottom"')
            _, y = _spot(ctx, 'backdrop bottom', 860, h, a, end, cands, None, True)
            spots.append((texts[1], y, False))
    for _t, y, _w in spots:
        if ctx.face_hit(a, end, 90, y, 950, y + h) > .005:
            ctx.fail(f'backdrop word {_t!r} lands on a face at every height; shorten it or pick another moment')
    ctx._uid += 1
    wrap = f'bd{ctx._uid}'
    wall_words = ''.join(f'<div class="bw" style="top:{y}px;font-size:{fs}px;color:{ink}"><span>{ctx.esc(t)}</span></div>' for t, y, w in spots if w)
    ctx.clip(ctx.wall, a, end, f'<div class="fx-backdrop">{wall_words}</div>', f'position:absolute;inset:0;{bgcss}', f'wallz {wrap}')
    ctx.tw(f"tl.fromTo('.{wrap}',{{clipPath:'inset(0% 0% 0% 100%)'}},{{clipPath:'inset(0% 0% 0% 0%)',duration:.24,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    wipe = "{clipPath:'inset(-20% 100% -20% 0%)'},{clipPath:'inset(-20% 0% -20% 0%)',duration:.32,ease:'power3.out',stagger:.28,immediateRender:false}"
    ctx.tw(f"tl.fromTo('.{wrap} .bw span',{wipe},{ctx.q(a + .12)});")
    for k, (t, y, w) in enumerate(spots):
        if w:
            continue
        fid = ctx.clip(ctx.front, a, end, f'<div class="fx-backdrop"><div class="bw" style="top:0;font-size:{fs}px;color:{ink}"><span>{ctx.esc(t)}</span></div></div>',
                       f'position:absolute;left:0;top:{y}px;width:1080px;height:{h}px;')
        ctx.tw(f"tl.fromTo('#{fid} .bw span',{wipe},{ctx.q(a + .12 + .28 * k)});")
        ctx.tw(f"tl.to('#{fid}',{{opacity:0,duration:.18}},{ctx.q(end - .2)});")
    ctx.tw(f"tl.to('.{wrap}',{{clipPath:'inset(0% 100% 0% 0%)',duration:.2,ease:'power3.in'}},{ctx.q(end - .2)});")
    ctx.busy.append((a, end))
    ctx.lowbusy.append((a, end))
    ctx.topbusy.append((a, end))
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    words = g['top'] + (f' / {g["bottom"]}' if g.get('bottom') else '')
    return (f'On “{g["on"]}” the room behind the speaker swaps to {g.get("bg", "accent")} and "{words}" wipes on in big type. '
            f'It holds {beat["hold"]:.1f} s; captions pause.')
