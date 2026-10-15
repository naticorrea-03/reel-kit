"""A generic social post card: avatar, name, handle, text and counts. No platform logo."""

META = {
    'id': 'tweet-card', 'name': 'Post card', 'category': 'social',
    'when': 'The speaker cites a post someone wrote. Show the exact words and who posted them.',
    'never': 'Never a platform logo or trademark. Never invented counts presented as real.',
    'params': {'on': 'phrase that triggers it', 'name': 'display name (required)', 'handle': 'handle (required)', 'text': 'post text (required, up to 6 lines)',
               'avatar': 'avatar image file, optional; default the name initial', 'time': 'age label like "3h", optional',
               'verified': 'true for a check badge', 'counts': '{"replies", "reposts", "likes"} short labels, optional',
               'hold': 'seconds, default 3.2', 'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

ICONS = {
    'replies': '<path d="M4 5h16v11H9l-5 4z"/>',
    'reposts': '<path d="M5 9l3-3 3 3M8 6v10h7M19 15l-3 3-3-3M16 18V8H9"/>',
    'likes': '<path d="M12 20s-7-4.3-8.8-8.6C2 8.2 4 4.8 7.3 4.8c2 0 3.4 1 4.7 2.7 1.3-1.7 2.7-2.7 4.7-2.7 3.3 0 5.3 3.4 4.1 6.6C19 15.7 12 20 12 20z"/>',
}
CHECK = '<svg class="ck" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11"/><path d="M7 12.5l3.2 3.2L17 9"/></svg>'

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
    _need(ctx, g, 'name', 'handle', 'text')
    a, end = _window(ctx, g, 3.2)
    W = 860
    TW = W - 2 * 40 - 12   # - 12: a look's card border
    fs = _fit(ctx, 'tweet-card', [g['text']], TW, 44, 30, 6)
    sub = f'{g["handle"]} · {g["time"]}' if g.get('time') else g['handle']
    nfs = _fit(ctx, 'tweet-card name', [g['name'] + ('  ' if g.get('verified') else '')], TW - 112, 36, 30, 1)
    _fit(ctx, 'tweet-card handle', [sub], TW - 112, 30, 28, 1)
    counts = {k: v for k, v in (g.get('counts') or {}).items() if k in ICONS and v not in (None, '')}
    H = int(36 * 2 + 88 + 22 + _lines([g['text']], TW, fs) * fs * 1.3 + (24 + 44 if counts else 0)) + 10
    pause = g.get('captions', 'pause') != 'keep'
    x, y, sc = _fitspot(ctx, 'tweet-card', W, H, a, end, lambda W, H: _grid(W, H), None, pause)
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    url = ctx.asset(g['avatar']) if g.get('avatar') else None
    av = f'<img class="av" src="{url}">' if url else f'<div class="av txt">{ctx.esc(g["name"][:1].upper())}</div>'
    row = ''.join(f'<div class="ct"><svg viewBox="0 0 24 24">{ICONS[k]}</svg><span>{ctx.esc(v)}</span></div>' for k, v in counts.items())
    html = (f'<div class="fx-tweet-card" style="width:{W}px"><div class="hd">{av}<div><div class="nm" style="font-size:{nfs}px">{ctx.esc(g["name"])}'
            f'{CHECK if g.get("verified") else ""}</div><div class="hn">{ctx.esc(sub)}</div></div></div>'
            f'<div class="tx" style="font-size:{fs}px">{ctx.esc(g["text"])}</div>' + (f'<div class="cts">{row}</div>' if row else '') + '</div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:70,rotation:1.5}},{{opacity:1,y:0,rotation:0,duration:.4,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    if row:
        ctx.tw(f"gsap.set('#{cid} .ct',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .ct',{{opacity:0,y:12}},{{opacity:1,y:0,duration:.25,stagger:.08,ease:'power2.out',immediateRender:false}},{ctx.q(a + .35)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    return f'On “{g["on"]}” a post from {g["name"]} ({g["handle"]}) slides up: "{g["text"]}". It holds {beat["hold"]:.1f} s.'
