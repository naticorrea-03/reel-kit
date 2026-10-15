"""Headline wall: four to eight headline tiles stack up on the wall behind and above the speaker's head on the hook."""
import numpy as np

META = {
    'id': 'headline-wall', 'name': 'Headline wall', 'category': 'media',
    'when': 'The hook says everyone is talking about something. Real headlines or post titles prove it.',
    'never': 'Never invented headlines presented as real: use real titles and sources, or plainly generic ones. Never on a close shot with no wall above the head.',
    'params': {'on': 'phrase where the first tile lands', 'tiles': '[{"title", "source", "image", "on"}] 4 to 8 (required); source is the outlet or account, '
               'image an optional thumbnail file, on an optional phrase for that tile', 'stagger': 'seconds between tiles without their own on, default 0.14',
               'hold': 'seconds after the last tile, default 2.2', 'sfx': 'optional sound per tile (none by default)'},
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

TILTS = [-5, 4, -3, 6, -4, 3, -6, 2]


def _mask(ctx, a, end):
    """speaker pixels over the window (any frame), as a 480x270 0/1 array with a summed-area table."""
    m = np.zeros((480, 270), dtype=np.float32)
    if ctx.has_cut:
        for k in range(5):
            raw = ctx.alpha_frame(a + (end - a) * k / 4)
            m = np.maximum(m, (np.frombuffer(raw, dtype=np.uint8)[:270 * 480].reshape(480, 270) > 128).astype(np.float32))
    sat = np.zeros((481, 271), dtype=np.float64)
    sat[1:, 1:] = m.cumsum(0).cumsum(1)
    return sat


def _frac(sat, x0, y0, x1, y1):
    a0, b0, a1, b1 = int(max(0, y0) / 4), int(max(0, x0) / 4), int(min(1920, y1) / 4), int(min(1080, x1) / 4)
    if a1 <= a0 or b1 <= b0:
        return 0.0
    return float(sat[a1, b1] - sat[a0, b1] - sat[a1, b0] + sat[a0, b0]) / ((a1 - a0) * (b1 - b0))


def _ov(r, s):
    return max(0, min(r[2], s[2]) - max(r[0], s[0])) * max(0, min(r[3], s[3]) - max(r[1], s[1]))


def _layout(ctx, tiles, W0, fs, sat, faces, cap, thumbs=True):
    out = []
    for k, t in enumerate(tiles):
        W = max(W0, int(len(t.get('source', '')) * 28 * .58) + 24 + 44 + 8)   # a long source name widens its tile, never spills
        TW = W - 44
        tl = len(_wrap(t['title'], TW, fs, .62))
        if tl > 4:
            continue
        th = int(22 + (40 if t.get('source') else 0) + tl * fs * 1.12 + 6)        # source row + title: must stay in view
        H = th + ((96 if t.get('image') else 84) if thumbs else 0) + 18
        want_x = [540, 250, 830, 380, 700, 160, 920, 540][k % 8]
        best = None
        for y in range(250, cap - 30 - H, 15):
            for x in range(100, 941 - W, 15):
                r = (x - 12, y - 12, x + W + 12, y + H + 12)
                txt = (x - 10, y - 10, x + W + 10, y + (H if t.get('image') else th) + 10)
                if _frac(sat, *txt) > .015:
                    continue
                if any(_ov(txt, p['r']) or _ov(r, p['t']) for p in out):
                    continue
                if any(_ov(r, p['r']) > .3 * min(W * H, (p['r'][2] - p['r'][0]) * (p['r'][3] - p['r'][1])) for p in out):
                    continue
                c = (y - 250) / 900 + abs(x + W / 2 - want_x) / 1400 - .3 * min(.35, _frac(sat, *r))   # a tile tucked behind the head reads as a wall
                c += .3 * sum(_ov(r, p['r']) for p in out) / (W * H)
                if best is None or c < best[0]:
                    best = (c, x, y, r, txt, H, tl, W)
        if best:
            out.append({'k': k, 'x': best[1], 'y': best[2], 'r': best[3], 't': best[4], 'H': best[5], 'lines': best[6], 'W': best[7]})
    return out


def build(g, ctx):
    tiles = [t if isinstance(t, dict) else {'title': t} for t in (g.get('tiles') or [])]
    if not 4 <= len(tiles) <= 8 or not all(t.get('title') for t in tiles):
        ctx.fail(f'headline-wall on {g["on"]!r} needs 4 to 8 tiles, each with "title"')
    times = _times(ctx, g, tiles, float(g.get('stagger', .14)))
    a, end = _window(ctx, g, 2.2, last=times[-1])
    sat = _mask(ctx, a, end)
    faces = [f for k in range(5) for f in ctx.faces_at(a + (end - a) * k / 4)]
    cap = _cap_top(ctx)
    best = []
    for W, fs, thumbs in ((300, 36, True), (270, 34, True), (240, 30, True), (240, 30, False), (220, 28, False)):
        lay = _layout(ctx, tiles, W, fs, sat, faces, cap, thumbs)   # tight shots drop the thumbnails before dropping tiles
        if len(lay) > len(best):
            best, bw, bfs, bth = lay, W, fs, thumbs
        if len(lay) == len(tiles):
            break
    if len(best) < 3:
        ctx.fail(f'headline-wall on {g["on"]!r}: only {len(best)} tile(s) fit clear of the speaker; pick a wider shot or fewer tiles')
    if len(best) < len(tiles):
        ctx.warn(f'headline-wall: {len(tiles) - len(best)} tile(s) left out, no clear wall for them')
    W, fs = bw, bfs
    html = ''
    for p in best:
        t = tiles[p['k']]
        src = (f'<div class="src"><i></i>{ctx.esc(t["source"])}</div>') if t.get('source') else ''
        if not bth:
            th = ''
        elif t.get('image'):
            url = ctx.asset(t['image'])
            th = f'<img class="th" src="{url}">'
        else:
            th = f'<div class="th a{p["k"] % 4}"><b></b><b></b><b></b></div>'
        html += (f'<div class="tile v{p["k"] % 3} t{p["k"]}" style="left:{p["x"]}px;top:{p["y"]}px;width:{p["W"]}px">{src}'
                 f'<div class="hl" style="font-size:{fs}px">{ctx.esc(t["title"])}</div>{th}</div>')
    cid = ctx.clip(ctx.wall, a, end, f'<div class="fx-headline-wall">{html}</div>', 'position:absolute;left:0;top:0;width:1080px;height:1920px;', 'wallz')
    if min(p['y'] for p in best) < 400:
        ctx.topbusy.append((a, end))
    for n_, p in enumerate(best):
        k, r = p['k'], TILTS[p['k'] % 8]
        sel = f'#{cid} .t{k}'
        t = times[k]
        ctx.tw(f"gsap.set('{sel}',{{opacity:0,rotation:{r}}});")
        ctx.tw(f"tl.fromTo('{sel}',{{opacity:0,y:-70,scale:1.18,rotation:{r * 2.2:.1f}}},{{opacity:1,y:0,scale:1,rotation:{r},duration:.42,ease:'power3.out',immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.to('{sel}',{{opacity:0,y:-40,duration:.22,ease:'power2.in'}},{ctx.q(end - .26 + .03 * (len(best) - 1 - n_) / max(1, len(best) - 1))});")
        ctx.sfx(g.get('sfx'), t, .25)


def describe(g, beat):
    tl = [t['title'] if isinstance(t, dict) else t for t in g['tiles']]
    return (f'On “{g["on"]}” {len(tl)} headline tiles drop onto the wall behind and above the speaker, one after another: '
            + '; '.join(f'"{x}"' for x in tl[:3]) + (' and more' if len(tl) > 3 else '') + f'. They hold {beat["hold"]:.1f} s.')
