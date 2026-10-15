"""One big number counts up to its value on the spoken word, with a label that says what it counts."""

META = {
    'id': 'count-up', 'name': 'Big count-up', 'category': 'data',
    'when': 'One number carries the line ("we hit 40,000 users", "it cut 90% of the work"). The hero number counts up; the label says what it counts.',
    'never': 'Never a number nobody says. Never two in a row (use stats for a set). Never glows on the number.',
    'params': {'on': 'phrase with the number', 'to': 'final value (required)', 'from': 'start value, default 0', 'prefix': 'e.g. "$"',
               'suffix': 'e.g. "%", "K", "x"', 'decimals': 'digits after the point, default from "to"', 'label': 'what it counts (required)',
               'hold': 'seconds, default 2.0', 'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound, e.g. cash-register for money'},
    'sfx': ['cash-register'], 'source': 'ours',
    'credit': 'Idea from the count-up motion in the HyperFrames registry (heygen-com/hyperframes, Apache-2.0), as listed in claude-reel-editor '
              'references/motions.md by Nicola Pocock (MIT). Written from scratch for reel-kit; the glow option is dropped.',
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


def _on_light(ctx, a, end, x, y, w, h):
    """plain bright wall behind the text: light text there reads as a smudge, so the effect switches to dark text (as serif does)."""
    lum, busy = ctx.bg_luma(a, end, x, y, x + w, y + h)
    return lum > .5 and busy < .08


def _fmt(v, dec):
    return f'{v:,.{dec}f}'


def build(g, ctx):
    _need(ctx, g, 'to', 'label')
    a, end = _window(ctx, g, 2.0)
    to, fr = float(g['to']), float(g.get('from', 0))
    dec = int(g['decimals']) if 'decimals' in g else (len(str(g['to']).split('.')[1]) if '.' in str(g['to']) else 0)
    pre, suf = str(g.get('prefix', '')), str(g.get('suffix', ''))
    final = f'{pre}{_fmt(to, dec)}{suf}'
    W = 860
    nfs = _fit(ctx, 'count-up number', [final], W, 230, 90, 1, .6)
    lfs = _fit(ctx, 'count-up label', [g['label']], W, 50, 34, 2, .52)
    ll = len(_wrap(g['label'], W, lfs, .52))
    H = int(nfs * 1.0 + 16 + ll * lfs * 1.25) + 16
    pause = g.get('captions', 'pause') != 'keep'
    x, y, sc = _fitspot(ctx, 'count-up', W, H, a, end, lambda W_, H_: _grid(W_, H_, xs=(90,)), None, pause)
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    lc = ' on-light' if _on_light(ctx, a, end, x, y, W * sc, H * sc) else ''
    html = (f'<div class="fx-count-up{lc}" style="width:{W}px"><div class="num" style="font-size:{nfs}px"><span class="v">{ctx.esc(f"{pre}{_fmt(fr, dec)}{suf}")}</span>'
            f'<span class="ghost">{ctx.esc(final)}</span></div><div class="lab" style="font-size:{lfs}px">{ctx.esc(g["label"])}</div></div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"tl.fromTo('#{cid} .num',{{opacity:0,y:40,scale:.9}},{{opacity:1,y:0,scale:1,duration:.3,ease:'power3.out',immediateRender:false}},{ctx.q(a - .05)});")
    ctx.tw(f"gsap.set('#{cid} .lab',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .lab',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.25,ease:'power2.out',immediateRender:false}},{ctx.q(a + .25)});")
    js_pre, js_suf = pre.replace("\\", "\\\\").replace("'", "\\'"), suf.replace("\\", "\\\\").replace("'", "\\'")
    ctx.tw(f"(function(){{const o={{v:{fr}}};tl.fromTo(o,{{v:{fr}}},{{v:{to},duration:.9,ease:'power2.out',onUpdate:function(){{"
           f"const el=document.querySelector('#{cid} .v');if(el)el.textContent='{js_pre}'+o.v.toLocaleString('en-US',{{minimumFractionDigits:{dec},maximumFractionDigits:{dec}}})+'{js_suf}';}},"
           f"immediateRender:false}},{ctx.q(a)});}})();")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx'), a, .45)


def describe(g, beat):
    final = f'{g.get("prefix", "")}{g["to"]}{g.get("suffix", "")}'
    return f'On “{g["on"]}” a big number counts up to {final}, labelled "{g["label"]}". It holds {beat["hold"]:.1f} s.'
