"""Swipe carousel: 3 to 5 cards slide past horizontally, each card landing on its own phrase."""

META = {
    'id': 'carousel-cards', 'name': 'Swipe carousel', 'category': 'carousel',
    'when': 'The speaker lists 3 to 5 parallel points (tips, options, reasons) one after another.',
    'never': 'Never points the speaker does not make. Never more than 5 cards. Never one line per card that only repeats the words.',
    'params': {'on': 'phrase that triggers it (the first card)', 'cards': '[{"title", "text", "on"}] 3 to 5 cards; text is one short line',
               'step': 'seconds between cards when a card has no "on", default 1.1', 'hold': 'seconds after the last card, default 1.6',
               'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound per swipe'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

VW, CWD, GAP = 860, 580, 28

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
    cards = g.get('cards') or []
    if not 3 <= len(cards) <= 5 or not all(isinstance(c, dict) and c.get('title') for c in cards):
        ctx.fail(f'carousel-cards on {g["on"]!r} needs 3 to 5 cards, each with "title"')
    times = _times(ctx, g, cards, float(g.get('step', 1.1)))
    a, end = _window(ctx, g, 1.6, last=times[-1])
    for k in range(1, len(times)):
        if times[k] - times[k - 1] < .6:
            ctx.fail(f'carousel-cards on {g["on"]!r}: card {k + 1} lands {times[k] - times[k - 1]:.2f} s after the one before; give each card 0.6 s or more')
    TW = CWD - 2 * 36 - 12
    tfs = _fit(ctx, 'carousel-cards titles', [c['title'] for c in cards], TW, 48, 32, 2)
    texts = [c.get('text', '') for c in cards]
    xfs = _fit(ctx, 'carousel-cards text', texts, TW, 36, 28, 3) if any(texts) else 0
    ch = 36 * 2 + 12 + _lines([c['title'] for c in cards], TW, tfs) * tfs * 1.2 + (14 + _lines(texts, TW, xfs) * xfs * 1.3 if xfs else 0)
    H = int(ch + 26 + 14) + 8
    pause = g.get('captions', 'pause') != 'keep'
    x, y, sc = _fitspot(ctx, 'carousel-cards', VW, H, a, end, lambda VW, H: _grid(VW, H, (90,)), None, pause)
    _claim(ctx, x, y, VW * sc, H * sc, a, end, pause)
    body = ''.join(f'<div class="cd" style="width:{CWD}px"><div class="tt" style="font-size:{tfs}px">{ctx.esc(c["title"])}</div>'
                   + (f'<div class="tx" style="font-size:{xfs}px">{ctx.esc(c.get("text", ""))}</div>' if xfs else '') + '</div>' for c in cards)
    dots = ''.join('<i><b></b></i>' for _ in cards)
    html = f'<div class="fx-carousel-cards" style="width:{VW}px"><div class="vp"><div class="tr">{body}</div></div><div class="dots">{dots}</div></div>'
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    pos = [(VW - CWD) // 2 - k * (CWD + GAP) for k in range(len(cards))]
    ctx.tw(f"gsap.set('#{cid} .tr',{{x:{pos[0]}}});")
    ctx.tw(f"gsap.set('#{cid} .cd',{{opacity:.3}});")
    ctx.tw(f"gsap.set('#{cid} .cd:nth-child(1)',{{opacity:1}});")
    ctx.tw(f"gsap.set('#{cid} .cd:nth-child(n+2) > *',{{opacity:0}});")   # peeking cards show their edge, never half a word
    ctx.tw(f"gsap.set('#{cid} .dots b',{{opacity:0}});")
    ctx.tw(f"gsap.set('#{cid} .dots i:nth-child(1) b',{{opacity:1}});")
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,x:120}},{{opacity:1,x:0,duration:.4,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    for k in range(1, len(cards)):
        t = times[k]
        ctx.tw(f"tl.fromTo('#{cid} .tr',{{x:{pos[k - 1]}}},{{x:{pos[k]},duration:.45,ease:'power3.inOut',immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .cd:nth-child({k})',{{opacity:1}},{{opacity:.3,duration:.3,immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .cd:nth-child({k + 1})',{{opacity:.3}},{{opacity:1,duration:.3,immediateRender:false}},{ctx.q(t + .15)});")
        ctx.tw(f"tl.fromTo('#{cid} .cd:nth-child({k}) > *',{{opacity:1}},{{opacity:0,duration:.15,immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .cd:nth-child({k + 1}) > *',{{opacity:0}},{{opacity:1,duration:.2,immediateRender:false}},{ctx.q(t + .3)});")
        ctx.tw(f"tl.fromTo('#{cid} .dots i:nth-child({k}) b',{{opacity:1}},{{opacity:0,duration:.2,immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .dots i:nth-child({k + 1}) b',{{opacity:0}},{{opacity:1,duration:.2,immediateRender:false}},{ctx.q(t)});")
        ctx.sfx(g.get('sfx'), t, .3)
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,x:-80,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")


def describe(g, beat):
    return (f'On “{g["on"]}” a swipe carousel slides through {len(g["cards"])} cards, one per phrase: '
            + ', '.join(f'"{c["title"]}"' for c in g['cards']) + f'. It holds {beat["hold"]:.1f} s.')
