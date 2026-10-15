"""Instagram-style comment bubble that pops in near the speaker, clear of the face, and its heart gets liked."""

META = {
    'id': 'popup-comment', 'name': 'Comment popup', 'category': 'social',
    'when': 'The speaker quotes or reacts to a comment someone left. Show the comment and who wrote it.',
    'never': 'Never a comment the speaker does not mention. Never over a face. One comment at a time.',
    'params': {'on': 'phrase that triggers it', 'handle': 'commenter handle (required)', 'text': 'the comment (required, up to 3 lines)',
               'avatar': 'avatar image file (project-relative), optional; default the handle initial', 'time': 'age label like "2h", optional',
               'likes': 'like count label like "1,204 likes", optional', 'like_on': 'phrase where the heart fills, default 0.8 s in',
               'hold': 'seconds, default 2.6', 'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

HEART = 'M12 21s-7.4-4.5-9.6-9.1C.9 8.4 3.1 4.4 6.9 4.4c2.1 0 3.6 1.1 5.1 2.9 1.5-1.8 3-2.9 5.1-2.9 3.8 0 6 4 4.5 7.5C19.4 16.5 12 21 12 21z'

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
    _need(ctx, g, 'handle', 'text')
    a, end = _window(ctx, g, 2.6)
    TWMAX = 560
    fs = _fit(ctx, 'popup-comment', [g['text']], TWMAX, 40, 30, 3)
    lines = _wrap(g['text'], TWMAX, fs)
    head = f'{g["handle"]}  {g.get("time", "")}'.strip()
    tw = int(min(TWMAX, max(max(len(l) for l in lines) * fs * GLYPH, len(head) * 30 * GLYPH, len(g.get('likes', '')) * 28 * GLYPH) + 12))
    W = 28 * 2 + 88 + 22 + tw + 22 + 52 + 12   # + 12: a look's card border
    H = int(max(88, 30 * 1.3 + 6 + len(lines) * fs * 1.3 + (28 * 1.4 + 8 if g.get('likes') else 0)) + 52 + 10)
    face = ctx.speaker_face(a + .1)
    near = ((face[0] + face[2]) / 2, face[3] + 60) if face else None
    pause = g.get('captions', 'pause') != 'keep'
    x, y, sc = _fitspot(ctx, 'popup-comment', W, H, a, end, lambda W, H: _grid(W, H, (90, 160, (1080 - W) // 2, 950 - W)), near, pause)
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    url = ctx.asset(g['avatar']) if g.get('avatar') else None
    av = f'<img class="av" src="{url}">' if url else f'<div class="av txt">{ctx.esc(g["handle"].lstrip("@")[:1].upper())}</div>'
    tm = f' <span class="tm">{ctx.esc(g["time"])}</span>' if g.get('time') else ''
    lk = f'<div class="mt">{ctx.esc(g["likes"])}</div>' if g.get('likes') else ''
    heart = (f'<div class="hz"><svg class="ho" viewBox="0 0 24 24"><path d="{HEART}"/></svg>'
             f'<svg class="hf" viewBox="0 0 24 24"><path d="{HEART}"/></svg></div>')
    html = (f'<div class="fx-popup-comment"><div class="pc" style="width:{W}px">{av}<div class="bd" style="width:{tw}px">'
            f'<div class="hd">{ctx.esc(g["handle"])}{tm}</div><div class="tx" style="font-size:{fs}px">{ctx.esc(g["text"])}</div>{lk}</div>'
            f'{heart}</div></div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    tl = ctx.at(g['like_on'], a)[0] if g.get('like_on') else a + .8
    ctx.tw(f"tl.fromTo('#{cid} .pc',{{opacity:0,scale:.55,y:30}},{{opacity:1,scale:1,y:0,duration:.36,ease:'back.out(1.7)',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"gsap.set('#{cid} .hf',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .hf',{{opacity:0,scale:0}},{{opacity:1,scale:1,duration:.3,ease:'back.out(3)',immediateRender:false}},{ctx.q(min(tl, end - .5))});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    return (f'On “{g["on"]}” a comment from {g["handle"]} pops in near the speaker: "{g["text"]}". '
            f'Its heart fills, and it holds {beat["hold"]:.1f} s.')
