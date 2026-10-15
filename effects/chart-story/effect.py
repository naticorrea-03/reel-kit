"""Chart card: a bar or line chart builds on the spoken word, every value printed exactly as given."""

META = {
    'id': 'chart-story', 'name': 'Chart', 'category': 'data',
    'when': 'The speaker compares a few numbers or describes a trend over time ("revenue doubled three years running"). The chart shows the exact values.',
    'never': 'Never invented or rounded data: print the values you were given. Never more than 7 points. Never a chart without a title saying what it measures.',
    'params': {'on': 'phrase that triggers it', 'chart': '"bar" (default; switches to horizontal rows when a column chart would cover the face), "hbar" or "line"', 'data': 'list of 2-7 numbers, zero or more (required)',
               'labels': 'one label per value (required)', 'title': 'what is measured (required)', 'prefix': 'e.g. "$"', 'suffix': 'e.g. "%", "K"',
               'emphasize': 'index of the value to color in the accent, default the last', 'source': 'optional small source line',
               'hold': 'seconds, default 3.0', 'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours',
    'credit': 'Idea from the chart-story motion in the HyperFrames registry (heygen-com/hyperframes, Apache-2.0), as listed in claude-reel-editor '
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


def build(g, ctx):
    _need(ctx, g, 'data', 'labels', 'title')
    kind = g.get('chart', 'bar')
    if kind not in ('bar', 'hbar', 'line'):
        ctx.fail(f'chart-story chart {kind!r}: use "bar", "hbar" or "line"')
    data, labels = list(g['data']), [str(x) for x in g['labels']]
    if not 2 <= len(data) <= 7 or len(labels) != len(data):
        ctx.fail(f'chart-story on {g["on"]!r} needs 2-7 values and one label per value (got {len(data)} values, {len(labels)} labels)')
    try:
        vals = [float(v) for v in data]
    except (TypeError, ValueError):
        ctx.fail(f'chart-story data must be numbers, got {data!r}')
    if min(vals) < 0:
        ctx.fail('chart-story draws values from zero; negative values are not supported')
    emph = int(g.get('emphasize', len(vals) - 1))
    pre, suf = str(g.get('prefix', '')), str(g.get('suffix', ''))
    shown = [f'{pre}{v}{suf}' for v in data]   # exactly as given, never re-rounded
    a, end = _window(ctx, g, 3.0)
    W, PAD = 860, 34
    CW = W - 2 * PAD
    n = len(vals)
    slot = CW / n
    top = max(vals) or 1
    tfs = _fit(ctx, 'chart-story title', [g['title']], CW, 44, 32, 2, .55)
    tl_n = len(_wrap(g['title'], CW, tfs, .55))
    sfs = 28
    pause = g.get('captions', 'pause') != 'keep'
    head = PAD + tl_n * tfs * 1.25 + 20
    foot = (sfs * 1.4 + 10 if g.get('source') else 0) + PAD + 10

    def clear(H):
        x, y = _spot(ctx, 'chart-story', W, H, a, end, _grid(W, H), None, pause, quiet=True)
        return (x, y) if ctx.face_hit(a, end, x, y, x + W, y + H) <= .02 else None

    spot, sc = None, 1.0
    if kind in ('bar', 'line'):
        vfs = _fit(ctx, 'chart-story values', shown, slot - 8, 40, 28, 1, .58)
        lfs = _fit(ctx, 'chart-story labels', labels, slot - 8, 32, 28, 1, .55)
        # the plot gets shorter before the card shrinks: a shrunk card takes the labels under readable size
        for CH in (340, 270, 210, 160):
            H = int(head + vfs * 1.3 + CH + 14 + lfs * 1.3 + foot)
            spot = clear(H)
            if spot:
                break
        if not spot and kind == 'bar':
            kind = 'hbar'
            ctx.note('chart-story switched to horizontal bars to clear the face')
    if kind == 'hbar':
        lfs = _fit(ctx, 'chart-story labels', labels, 260, 34, 28, 1, .55)
        vfs = _fit(ctx, 'chart-story values', shown, 200, 36, 28, 1, .58)
        lw = int(max(len(t) for t in labels) * lfs * .55) + 8
        vw = int(max(len(t) for t in shown) * vfs * .58) + 8
        rh = max(lfs, vfs) * 1.3
        H = int(head + n * (rh + 12) + foot)
        spot = clear(H)
    if spot:
        x, y = spot
    else:
        x, y, sc = _fitspot(ctx, 'chart-story', W, H, a, end, lambda W_, H_: _grid(W_, H_), None, pause)
        if min(vfs, lfs, sfs if g.get('source') else 99) * sc < 28:
            ctx.fail(f'chart-story on {g["on"]!r} only clears the face at {sc:.0%} size, where its labels are unreadable; '
                     'use fewer values or a moment with more room')
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    vh = vfs * 1.3
    if kind == 'hbar':
        bwid = CW - lw - vw - 2 * 16
        rows = ''.join(f'<div class="hr" style="height:{rh:.0f}px"><div class="hl" style="width:{lw}px;font-size:{lfs}px">{ctx.esc(lb)}</div>'
                       f'<div class="ht" style="width:{bwid}px"><div class="hb{" em" if k == emph else ""}" style="width:{max(1.5, 100 * v / top):.1f}%"></div></div>'
                       f'<div class="hv" style="width:{vw}px;font-size:{vfs}px">{ctx.esc(s)}</div></div>'
                       for k, (v, s, lb) in enumerate(zip(vals, shown, labels)))
        body = f'<div class="hrows">{rows}</div>'
    elif kind == 'bar':
        bw = min(140, slot * .62)
        cols = ''.join(f'<div class="col" style="width:{slot:.1f}px"><div class="val" style="font-size:{vfs}px;bottom:{max(6, CH * v / top) + 10:.0f}px">{ctx.esc(s)}</div>'
                       f'<div class="bar{" em" if k == emph else ""}" style="width:{bw:.0f}px;height:{max(6, CH * v / top):.0f}px"></div></div>'
                       for k, (v, s) in enumerate(zip(vals, shown)))
        labs = ''.join(f'<div class="lb" style="width:{slot:.1f}px;font-size:{lfs}px">{ctx.esc(lb)}</div>' for lb in labels)
        body = f'<div class="plot bars" style="height:{CH + vh:.0f}px">{cols}</div><div class="axis"></div><div class="lbs">{labs}</div>'
    else:
        pts = [((k + .5) * slot, vh + CH - CH * v / top * .92) for k, v in enumerate(vals)]
        L = sum(((pts[k + 1][0] - pts[k][0]) ** 2 + (pts[k + 1][1] - pts[k][1]) ** 2) ** .5 for k in range(n - 1)) + 20
        d = 'M' + ' L'.join(f'{px:.1f} {py:.1f}' for px, py in pts)
        dots = ''.join(f'<circle class="dot{" em" if k == emph else ""}" cx="{px:.1f}" cy="{py:.1f}" r="{12 if k == emph else 9}"/>' for k, (px, py) in enumerate(pts))
        vls = ''.join(f'<div class="pv" style="left:{px - slot / 2:.1f}px;width:{slot:.1f}px;top:{py - vh - 14:.0f}px;font-size:{vfs}px">{ctx.esc(s)}</div>'
                      for (px, py), s in zip(pts, shown))
        labs = ''.join(f'<div class="lb" style="width:{slot:.1f}px;font-size:{lfs}px">{ctx.esc(lb)}</div>' for lb in labels)
        body = (f'<div class="plot line" style="height:{CH + vh:.0f}px"><svg class="ln" width="{CW}" height="{CH + vh:.0f}" viewBox="0 0 {CW} {CH + vh:.0f}">'
                f'<path class="lp" d="{d}" style="stroke-dasharray:{L:.0f};stroke-dashoffset:{L:.0f}"/>{dots}</svg>{vls}</div><div class="axis"></div><div class="lbs">{labs}</div>')
    src = f'<div class="src" style="font-size:{sfs}px">{ctx.esc(g["source"])}</div>' if g.get('source') else ''
    html = (f'<div class="fx-chart-story" style="width:{W}px;padding:{PAD}px"><div class="ti" style="font-size:{tfs}px">{ctx.esc(g["title"])}</div>'
            f'{body}{src}</div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:50,scale:.95}},{{opacity:1,y:0,scale:1,duration:.35,ease:'power3.out',immediateRender:false}},{ctx.q(a - .05)});")
    step = min(.18, 1.0 / n)
    if kind in ('bar', 'hbar'):
        bar, val, axis = ('.bar', '.val', 'scaleY') if kind == 'bar' else ('.hb', '.hv', 'scaleX')
        ctx.tw(f"tl.fromTo('#{cid} {bar}',{{{axis}:0}},{{{axis}:1,duration:.4,ease:'power3.out',stagger:{step:.3f},immediateRender:false}},{ctx.q(a + .25)});")
        ctx.tw(f"gsap.set('#{cid} {val}',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} {val}',{{opacity:0}},{{opacity:1,duration:.2,stagger:{step:.3f},immediateRender:false}},{ctx.q(a + .5)});")
    else:
        ctx.tw(f"tl.to('#{cid} .lp',{{strokeDashoffset:0,duration:{.25 + step * n:.2f},ease:'power1.inOut'}},{ctx.q(a + .25)});")
        ctx.tw(f"gsap.set('#{cid} .dot, #{cid} .pv',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .dot',{{opacity:0}},{{opacity:1,duration:.12,stagger:{step:.3f},immediateRender:false}},{ctx.q(a + .25)});")
        ctx.tw(f"tl.fromTo('#{cid} .pv',{{opacity:0,y:10}},{{opacity:1,y:0,duration:.2,stagger:{step:.3f},immediateRender:false}},{ctx.q(a + .3)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    pairs = ', '.join(f'{lb} {g.get("prefix", "")}{v}{g.get("suffix", "")}' for lb, v in zip(g['labels'], g['data']))
    return f'On “{g["on"]}” a {g.get("chart", "bar")} chart builds: {g["title"]} ({pairs}). It holds {beat["hold"]:.1f} s.'
