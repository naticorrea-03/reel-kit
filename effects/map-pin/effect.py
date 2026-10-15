"""A stylized map card (drawn shapes, no map tiles) with a pin dropping on a named place."""
import zlib

META = {
    'id': 'map-pin', 'name': 'Map pin', 'category': 'media',
    'when': 'The speaker names a city, neighborhood or venue where something happened.',
    'never': 'Never a place nobody names. The map is a sketch, not a real street layout; do not imply directions.',
    'params': {'on': 'the spoken place name', 'place': 'pin label (required)', 'sub': 'second line like a city or date, optional',
               'pin': '[x, y] pin spot as 0-1 fractions of the map, default [0.42, 0.55]', 'hold': 'seconds, default 2.6',
               'captions': '"pause" or "keep", default keep', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

MW, MH = 720, 440

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


def roads(seed):
    """a few roads, a river and a park, varied by the place name so two maps never look identical."""
    r = lambda k, lo, hi: lo + (zlib.crc32(f'{seed}{k}'.encode()) % 1000) / 1000 * (hi - lo)
    wy = r('w', 300, 380)
    water = f'<path class="water" d="M0 {wy:.0f} C {MW * .3:.0f} {wy - 50:.0f}, {MW * .6:.0f} {wy + 60:.0f}, {MW} {wy - 10:.0f} L {MW} {MH} L 0 {MH} Z"/>'
    px, py = r('px', 470, 600), r('py', 50, 150)
    park = f'<rect class="park" x="{px:.0f}" y="{py:.0f}" width="150" height="110" rx="22"/>'
    out = [water, park]
    for k in range(3):
        y = r(f'h{k}', 40 + k * 90, 110 + k * 90)
        out.append(f'<path class="road" d="M -20 {y:.0f} L {MW + 20} {y + r(f"hs{k}", -40, 40):.0f}"/>')
    for k in range(4):
        x = r(f'v{k}', 60 + k * 170, 150 + k * 170)
        out.append(f'<path class="street" d="M {x:.0f} -20 L {x + r(f"vs{k}", -60, 60):.0f} {MH + 20}"/>')
    out.append(f'<path class="road main" d="M -20 {r("m0", 180, 260):.0f} C {MW * .35:.0f} {r("m1", 120, 300):.0f}, {MW * .65:.0f} {r("m2", 160, 320):.0f}, {MW + 20} {r("m3", 150, 280):.0f}"/>')
    return ''.join(out)


def build(g, ctx):
    _need(ctx, g, 'place')
    a, end = _window(ctx, g, 2.6)
    fx, fy = (g.get('pin') or [.42, .55])[:2]
    if not (0.1 <= fx <= .9 and .25 <= fy <= .9):
        ctx.fail(f'map-pin on {g["on"]!r}: pin must stay inside the map, x 0.1-0.9 and y 0.25-0.9')
    pfs = _fit(ctx, 'map-pin place', [g['place']], 420, 40, 30, 1)
    sfs = _fit(ctx, 'map-pin sub', [g['sub']], 420, 30, 28, 1) if g.get('sub') else 0
    W, H = MW + 2 * 14 + 12, MH + 2 * 14 + 12   # + 12: a look's card border
    pause = g.get('captions', 'keep') == 'pause'
    x, y, sc = _fitspot(ctx, 'map-pin', W, H, a, end, lambda W, H: _grid(W, H), None, pause)
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    cx, cy = fx * MW, fy * MH
    chw = int(max(len(g['place']) * pfs * GLYPH, len(g.get('sub', '')) * sfs * GLYPH) + 2 * 22 + 8)
    chh = int(pfs * 1.25 + (sfs * 1.3 if sfs else 0) + 2 * 14)
    chx = cx + 40 if cx + 40 + chw <= MW - 16 else cx - 40 - chw
    chx = max(16, min(chx, MW - 16 - chw))
    chy = max(16, min(cy - 60 - chh / 2, MH - 16 - chh))
    sub = f'<div class="sb" style="font-size:{sfs}px">{ctx.esc(g["sub"])}</div>' if sfs else ''
    html = (f'<div class="fx-map-pin"><div class="map" style="width:{MW}px;height:{MH}px">'
            f'<svg class="bg" viewBox="0 0 {MW} {MH}" width="{MW}" height="{MH}"><rect class="land" width="{MW}" height="{MH}"/>{roads(g["place"])}</svg>'
            f'<div class="sh" style="left:{cx - 22:.0f}px;top:{cy - 8:.0f}px"></div>'
            f'<svg class="pin" viewBox="0 0 64 84" style="left:{cx - 32:.0f}px;top:{cy - 84:.0f}px"><path d="M32 82C32 82 4 50 4 30a28 28 0 0 1 56 0c0 20-28 52-28 52z"/>'
            f'<circle cx="32" cy="30" r="11"/></svg>'
            f'<div class="chip" style="left:{chx:.0f}px;top:{chy:.0f}px;width:{chw}px"><div class="pl" style="font-size:{pfs}px">{ctx.esc(g["place"])}</div>{sub}</div>'
            f'</div></div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,scale:.92,y:40}},{{opacity:1,scale:1,y:0,duration:.35,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"gsap.set('#{cid} .pin, #{cid} .chip, #{cid} .sh',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .pin',{{opacity:0,y:-260}},{{opacity:1,y:0,duration:.55,ease:'bounce.out',immediateRender:false}},{ctx.q(a + .1)});")
    ctx.tw(f"tl.fromTo('#{cid} .sh',{{opacity:0,scale:.2}},{{opacity:1,scale:1,duration:.45,ease:'power2.out',immediateRender:false}},{ctx.q(a + .2)});")
    ctx.tw(f"tl.fromTo('#{cid} .chip',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.25,ease:'power2.out',immediateRender:false}},{ctx.q(a + .55)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx'), a + .4, .35)


def describe(g, beat):
    sub = f', {g["sub"]}' if g.get('sub') else ''
    return f'On “{g["on"]}” a sketched map card drops in and a pin lands on {g["place"]}{sub}. It holds {beat["hold"]:.1f} s.'
