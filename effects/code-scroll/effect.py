"""Code scroll: a dark editor shows a markdown file that scrolls smoothly, tilted back a little, under the speaker's face."""
import math, re

META = {
    'id': 'code-scroll', 'name': 'Code scroll', 'category': 'ui',
    'when': 'The speaker mentions a file, a prompt, a skill or instructions they wrote ("I wrote one file that tells it how").',
    'never': 'Never fake code that claims to be someone else\'s. Never a file nobody mentions. Lines must be real or plainly generic.',
    'params': {'on': 'phrase that brings the editor in', 'title': 'file name on the tab, default "README.md"',
               'lines': 'list of markdown lines (required, 8 or more for a scroll), or "text" with newlines', 'hold': 'seconds on screen, default 2.8',
               'tilt': 'degrees tilted back, default 14', 'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound name (none by default)'},
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

FS, LH, PAD = 34, 50, 22
CH = FS * .6          # JetBrains Mono advance


def _md(ctx, line):
    """one markdown line -> highlighted html (headings, list marks, bold, code spans, frontmatter keys)."""
    e = ctx.esc(line)
    if re.match(r'^#{1,6} ', line):
        return f'<span class="h">{e}</span>'
    if line.strip() == '---':
        return f'<span class="m">{e}</span>'
    m = re.match(r'^([a-z_-]+):( .*)?$', line)
    if m:
        return f'<span class="k">{ctx.esc(m.group(1))}:</span>{ctx.esc(m.group(2) or "")}'
    e = re.sub(r'^(\s*)([-*]|\d+\.) ', r'\1<span class="m">\2</span> ', e)
    e = re.sub(r'\*\*([^*]+)\*\*', r'<span class="b">**\1**</span>', e)
    e = re.sub(r'`([^`]+)`', r'<span class="c">`\1`</span>', e)
    return e


def _soft(lines, cols):
    """soft-wrap long lines at word breaks; continuation rows carry no line number."""
    out = []
    for n_, ln in enumerate(lines, 1):
        cur, first = '', True
        for w in ln.split(' '):
            t = (cur + ' ' + w) if cur else w
            if len(t) > cols and cur:
                out.append((n_ if first else None, cur))
                first, cur = False, '  ' + w
            else:
                cur = t
        out.append((n_ if first else None, cur))
    return out


def build(g, ctx):
    lines = g.get('lines') or str(g.get('text', '')).split('\n')
    lines = [str(x) for x in lines]
    if len([x for x in lines if x.strip()]) < 4:
        ctx.fail(f'code-scroll on {g["on"]!r} needs "lines": at least 4 lines of the file')
    a, end = _window(ctx, g, 2.8)
    W = 880
    GUT = 70
    cols = int((W - 2 * PAD - GUT - 10) / CH)
    rows = _soft(lines, cols)
    face = ctx.speaker_face(a + .1)
    near = ((face[0] + face[2]) / 2, face[3] + 300) if face else None
    pause = g.get('captions', 'pause') != 'keep'
    # the biggest editor that clears the faces: fewer visible rows first, then a smaller scale
    pick = None
    for sc_ in (1.0, .88):            # full size with fewer rows beats a shrunk editor: text stays readable on a phone
        for vis in (11, 9, 7, 6, 5):
            H = 64 + PAD * 2 + vis * LH
            sc = sc_
            x, y = _spot(ctx, 'code-scroll', int(W * sc), int(H * sc), a, end, _grid(int(W * sc), int(H * sc), xs=(int((1080 - W * sc) // 2),)), near, pause, quiet=True)
            if ctx.face_hit(a, end, x, y, x + W * sc, y + H * sc) <= .02:
                pick = (vis, H, x, y, sc)
                break
        if pick:
            break
    if not pick:
        x, y, sc = _fitspot(ctx, 'code-scroll', W, 64 + PAD * 2 + 5 * LH, a, end, lambda W, H: _grid(W, H, xs=((1080 - W) // 2,)), near, pause,
                            scales=(.76, .66))
        pick = (5, 64 + PAD * 2 + 5 * LH, x, y, sc)
    vis, H, x, y, sc = pick
    vis = min(vis, len(rows))
    H = 64 + PAD * 2 + vis * LH
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    body = ''.join(f'<div class="ln r{k}"><span class="no">{"" if n_ is None else n_}</span>'
                   f'<span class="tx">{_md(ctx, t) if t.strip() else "&#8203;"}</span></div>' for k, (n_, t) in enumerate(rows))
    tilt = float(g.get('tilt', 14))
    html = (f'<div class="fx-code-scroll" style="width:{W}px;--tilt:{tilt}deg"><div class="ed"><div class="bar"><span class="dots"><i></i><i></i><i></i></span>'
            f'<span class="tab">{ctx.esc(g.get("title", "README.md"))}</span></div>'
            f'<div class="vp" style="height:{vis * LH + PAD * 2}px"><div class="list">{body}</div></div></div></div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    S = f'#{cid}'
    ctx.tw(f"tl.fromTo('{S} .ed',{{opacity:0,y:60,rotationX:{tilt + 14:.0f}}},{{opacity:1,y:0,rotationX:{tilt},duration:.45,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"gsap.set('{S} .ed',{{rotationX:{tilt},transformPerspective:1600,transformOrigin:'50% 100%'}});")
    # smooth scroll: the list moves up on a sine ease; each row fades out as it reaches the top edge and in at the bottom edge,
    # so no row ever shows outside the editor (a clipping box would cut text mid-line)
    dist = max(0, len(rows) - vis) * LH
    t0, T = a + .55, max(.8, end - a - .55 - .45)
    for k in range(vis, len(rows)):
        ctx.tw(f"gsap.set('{S} .r{k}',{{opacity:0}});")
    if dist > 0:
        ctx.tw(f"tl.fromTo('{S} .list',{{y:0}},{{y:{-dist},duration:{T:.3f},ease:'sine.inOut',immediateRender:false}},{ctx.q(t0)});")

        def when(s):   # time the list has scrolled s px (inverse of sine.inOut)
            p = min(1, max(0, s / dist))
            return t0 + T * math.acos(1 - 2 * p) / math.pi
        for k in range(len(rows)):
            top = k * LH
            if top < dist + 1 and k < len(rows):        # leaves at the top
                ta, tb = when(top - LH * .55), when(top + LH * .15)
                if tb > t0 + .01:
                    ctx.tw(f"tl.to('{S} .r{k}',{{opacity:0,duration:{max(.04, tb - ta):.3f},ease:'none'}},{ctx.q(ta)});")
            if k >= vis:                                 # arrives at the bottom
                s_in = (k + 1) * LH - vis * LH
                ta, tb = when(s_in - LH * .9), when(s_in - LH * .1)
                ctx.tw(f"tl.fromTo('{S} .r{k}',{{opacity:0}},{{opacity:1,duration:{max(.04, tb - ta):.3f},ease:'none',immediateRender:false}},{ctx.q(ta)});")
    ctx.tw(f"tl.to('{S}',{{opacity:0,y:-24,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")
    ctx.sfx(g.get('sfx'), a, .3)


def describe(g, beat):
    lines = g.get('lines') or str(g.get('text', '')).split('\n')
    return (f'On “{g["on"]}” a dark editor tilted back under the face scrolls through {g.get("title", "README.md")} '
            f'({len(lines)} lines, starting "{str(lines[0])[:40]}"). It holds {beat["hold"]:.1f} s.')
