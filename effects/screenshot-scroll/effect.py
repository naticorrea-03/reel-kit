"""A tall screenshot scrolls inside a phone-shaped frame."""
import os

META = {
    'id': 'screenshot-scroll', 'name': 'Phone scroll', 'category': 'media',
    'when': 'The speaker talks about a feed, a long page, an app or a thread you can show scrolling.',
    'never': 'Never a short image (use screenshot). Never a page with private data you have no right to show.',
    'params': {'on': 'phrase that triggers it', 'src': 'tall image file, project-relative (required)', 'scroll': 'share of the page to scroll, 0-1, default 1',
               'side': 'left, right or auto, default auto', 'hold': 'seconds, default 3.4', 'captions': '"pause" or "keep", default keep',
               'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

PW, PH, BZ = 440, 880, 16   # phone frame and bezel, px

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


def build(g, ctx):
    _need(ctx, g, 'src')
    a, end = _window(ctx, g, 3.4)
    url = ctx.asset(g['src'])
    iw, ih = ctx.image_size(url)
    side = g.get('side', 'auto')
    pause = g.get('captions', 'keep') == 'pause'
    for sc in (1.0, .85, .72, .6, .5):   # a two-shot or a centred selfie leaves no 880 px column clear of faces: shrink the phone until one clears
        pw, ph, bz = int(PW * sc), int(PH * sc), int(BZ * sc)
        xs = {'left': (90, 160), 'right': (950 - pw, 880 - pw)}.get(side, (90, 160, (1080 - pw) // 2, 880 - pw, 950 - pw))
        x, y = _spot(ctx, 'screenshot-scroll', pw, ph, a, end, _grid(pw, ph, xs), None, pause, quiet=True)
        if ctx.face_hit(a, end, x, y, x + pw, y + ph) <= .02:
            break
    else:
        ctx.warn(f'screenshot-scroll {g["src"]!r} covers a face even at 50% size; pick another moment or side')
    sw, sh = pw - 2 * bz, ph - 2 * bz
    hs = sw * ih / iw
    if hs < sh * 1.15:
        ctx.fail(f'screenshot-scroll {g["src"]!r} is only {hs:.0f}px tall at phone width (needs {sh * 1.15:.0f}+); use the screenshot effect')
    dist = (hs - sh) * max(0.0, min(1.0, float(g.get('scroll', 1))))
    _claim(ctx, x, y, pw, ph, a, end, pause)
    html = (f'<div class="fx-screenshot-scroll" style="width:{pw}px;height:{ph}px;padding:{bz}px">'
            f'<div class="scr" style="background-image:url({url});background-size:{sw}px auto"></div><div class="nt"></div></div>')
    cid = ctx.clip(ctx.front, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    dy = int(min(120, max(0, 1470 - y - ph)))   # rise only as far as the room below it, never through the bottom UI zone
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:{dy},scale:.94,rotation:-3}},{{opacity:1,y:0,scale:1,rotation:0,duration:.45,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    d = max(.6, end - a - 1.1)
    ctx.tw(f"tl.fromTo('#{cid} .scr',{{backgroundPositionY:'0px'}},{{backgroundPositionY:'-{dist:.0f}px',duration:{d:.2f},ease:'power1.inOut',immediateRender:false}},{ctx.q(a + .55)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-40,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")
    ctx.sfx(g.get('sfx'), a, .35)


def describe(g, beat):
    name = os.path.splitext(os.path.basename(g['src']))[0].replace('-', ' ')
    return f'On “{g["on"]}” a phone slides up and the {name} page scrolls inside it. It holds {beat["hold"]:.1f} s.'
