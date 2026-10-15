"""A single DM bubble that carries a link preview card: someone sent (or the speaker shared) a link."""

META = {
    'id': 'link-preview', 'name': 'DM with link preview', 'category': 'social',
    'when': 'The speaker says someone sent them a link, or that they sent one: an article, a listing, a product page. The card names the page.',
    'never': 'Never a page nobody describes. Never a plain text message (use popup-dm). One bubble only.',
    'params': {'on': 'phrase that triggers it', 'title': 'page title on the card (required)', 'domain': 'site, e.g. "nytimes.com" (required)',
               'text': 'optional message above the card', 'image': 'optional preview image, project-relative', 'from': '"them" (default) or "me"',
               'name': 'optional contact name in the header', 'hold': 'seconds, default 2.2', 'sfx': 'default message-receive (them) or message-send (me)'},
    'sfx': ['message-receive', 'message-send'], 'source': 'ours',
    'credit': 'Idea from the chat-message motion in the HyperFrames registry (heygen-com/hyperframes, Apache-2.0), as listed in claude-reel-editor '
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
    _need(ctx, g, 'title', 'domain')
    a, end = _window(ctx, g, 2.2)
    me = g.get('from', 'them') == 'me'
    W = 760
    TW = W - 2 * 30
    url = ctx.asset(g['image']) if g.get('image') else None
    FAV = 0 if url else 84 + 20   # no preview image: a site tile with the domain's initial sits beside the title
    tfs = _fit(ctx, 'link-preview title', [g['title']], TW - 2 * 26 - FAV, 38, 30, 3, .56)
    mfs = _fit(ctx, 'link-preview text', [g['text']], TW - 2 * 28, 38, 30, 3, .56) if g.get('text') else 0
    ih = 300 if url else 0
    H = int(2 * 30 + (90 if g.get('name') else 0) + (len(_wrap(g['text'], TW - 56, mfs, .56)) * mfs * 1.3 + 36 + 14 if g.get('text') else 0)
            + ih + 2 * 22 + max(84, len(_wrap(g['title'], TW - 52 - FAV, tfs, .56)) * tfs * 1.25 + 8 + 30 * 1.3)) + 12
    x, y, sc = _fitspot(ctx, 'link-preview', W, H, a, end, lambda W_, H_: _grid(W_, H_), None, False)
    _claim(ctx, x, y, W * sc, H * sc, a, end, False)
    hd = (f'<div class="hd"><div class="av">{ctx.esc(g["name"][:1].upper())}</div><div class="nm">{ctx.esc(g["name"])}</div></div>' if g.get('name') else '')
    msg = f'<div class="bub" style="font-size:{mfs}px">{ctx.esc(g["text"])}</div>' if g.get('text') else ''
    img = f'<div class="im" style="height:{ih}px;background-image:url(\'{url}\')"></div>' if url else ''
    fav = '' if url else f'<div class="fav">{ctx.esc(str(g["domain"]).removeprefix("www.")[:1].upper())}</div>'
    card = (f'<div class="lk">{img}<div class="lt">{fav}<div class="tt"><div class="ti" style="font-size:{tfs}px">{ctx.esc(g["title"])}</div>'
            f'<div class="dm">{ctx.esc(g["domain"])}</div></div></div></div>')
    html = f'<div class="fx-link-preview" style="width:{W}px">{hd}<div class="row {"me" if me else "them"}"><div class="stack">{msg}{card}</div></div></div>'
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:40,scale:.95}},{{opacity:1,y:0,scale:1,duration:.35,ease:'power3.out',immediateRender:false}},{ctx.q(a - .05)});")
    ctx.tw(f"gsap.set('#{cid} .stack',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .stack',{{opacity:0,y:24,scale:.92}},{{opacity:1,y:0,scale:1,duration:.3,ease:'back.out(1.8)',immediateRender:false}},{ctx.q(a + .15)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx', 'message-send' if me else 'message-receive'), a + .15, .45)


def describe(g, beat):
    who = 'the speaker sends' if g.get('from') == 'me' else f'{g.get("name") or "someone"} sends'
    return f'On “{g["on"]}” a DM pops up where {who} a link: "{g["title"]}" ({g["domain"]}). It holds {beat["hold"]:.1f} s.'
