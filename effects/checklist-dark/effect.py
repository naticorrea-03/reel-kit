"""Dark-mode app checklist: a glassy app card lists the steps dimmed, and each one lights up and ticks off on its phrase."""
import re

META = {
    'id': 'checklist-dark', 'name': 'Dark app checklist', 'category': 'ui',
    'when': 'The speaker walks through how to do something in steps ("just record, drop the clips in, tell it...").',
    'never': 'Never steps the speaker does not say. Two to five steps, each ticked on its own phrase. Use the light checklist for a plain list of things.',
    'params': {'on': 'phrase that brings the card in', 'title': 'small caps header, optional (default "Steps")',
               'items': '[{"text", "on"}] 2 to 5 (required); wrap one word in *stars* to colour it', 'hold': 'seconds after the last tick, default 1.4',
               'captions': '"pause" or "keep", default keep', 'sfx': 'optional sound per tick (none by default)'},
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


def _rich(ctx, text):
    return re.sub(r'\*([^*]+)\*', r'<em>\1</em>', ctx.esc(text))


def build(g, ctx):
    items = [it if isinstance(it, dict) else {'text': it} for it in (g.get('items') or [])]
    if not 2 <= len(items) <= 5 or not all(it.get('text') for it in items):
        ctx.fail(f'checklist-dark on {g["on"]!r} needs 2 to 5 items, each with "text"')
    times = _times(ctx, g, items, .9)
    times = [t + (.35 if k == 0 and not items[0].get('on') else 0) for k, t in enumerate(times)]
    a, end = _window(ctx, g, 1.4, last=times[-1] + .3)
    n_ = len(items)
    W = 600
    TW = W - 2 * 30 - 52 - 22 - 24
    plain = [it['text'].replace('*', '') for it in items]
    fs = _fit(ctx, 'checklist-dark items', plain, TW, 40, 30, 2)
    nl = sum(max(1, len(_wrap(t, TW, fs))) for t in plain)
    H = int(30 + 52 + 18 + 8 + 22 + nl * fs * 1.25 + n_ * 40 + 24) + 8
    pause = g.get('captions', 'keep') == 'pause'
    face = ctx.speaker_face(a + .1)
    near = (180 if face and (face[0] + face[2]) / 2 > 540 else 900, 420)   # beside the head, on the side with more wall
    x, y, sc = _fitspot(ctx, 'checklist-dark', W, H, a, end, lambda W, H: _grid(W, H), near, pause, scales=(1.0, .86, .74, .64))
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    title = ctx.esc(g.get('title', 'Steps'))
    counts = ''.join(f'<span class="ct k{k}">{k} of {n_}</span>' for k in range(n_ + 1))
    bars = ''.join(f'<i class="b{k}"><u></u></i>' for k in range(n_))
    rows = ''.join(f'<div class="it r{k}"><div class="bx"><svg viewBox="0 0 24 24"><path d="M6 12.5l4 4L18 8.5"/></svg></div>'
                   f'<div class="tx" style="font-size:{fs}px">{_rich(ctx, it["text"])}</div></div>' for k, it in enumerate(items))
    html = (f'<div class="fx-checklist-dark" style="width:{W}px"><div class="hd"><span class="dots"><i></i><i></i><i></i></span>'
            f'<span class="tt">{title}</span><span class="cts">{counts}</span></div><div class="bars">{bars}</div>{rows}</div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    S = f'#{cid}'
    ctx.tw(f"tl.fromTo('{S}',{{opacity:0,y:30,scale:.96}},{{opacity:1,y:0,scale:1,duration:.34,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"gsap.set('{S} .ct',{{opacity:0}});")
    ctx.tw(f"gsap.set('{S} .ct.k0',{{opacity:1}});")
    ctx.tw(f"gsap.set('{S} .it',{{opacity:.38}});")
    ctx.tw(f"gsap.set('{S} .bars u',{{scaleX:0}});")
    ctx.tw(f"gsap.set('{S} .bx',{{'--on':0}});")
    for k, t in enumerate(times):
        r = f'{S} .r{k}'
        tk = ctx.at(items[k]['tick_on'], t)[0] if items[k].get('tick_on') else t + .35
        ctx.tw(f"tl.fromTo('{r}',{{opacity:.38,x:0}},{{opacity:1,x:6,duration:.22,ease:'power2.out',immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.fromTo('{r} .bx',{{'--on':0}},{{'--on':1,duration:.16,ease:'power2.out',immediateRender:false}},{ctx.q(tk)});")
        ctx.tw(f"tl.fromTo('{r} path',{{strokeDashoffset:24}},{{strokeDashoffset:0,duration:.26,ease:'power2.out',immediateRender:false}},{ctx.q(tk + .04)});")
        ctx.tw(f"tl.to('{r}',{{x:0,duration:.25,ease:'power2.out'}},{ctx.q(tk + .1)});")
        ctx.tw(f"tl.fromTo('{S} .b{k} u',{{scaleX:0}},{{scaleX:1,duration:.3,ease:'power2.out',immediateRender:false}},{ctx.q(tk)});")
        ctx.tw(f"tl.to('{S} .ct.k{k}',{{opacity:0,duration:.08}},{ctx.q(tk)});")
        ctx.tw(f"tl.fromTo('{S} .ct.k{k + 1}',{{opacity:0}},{{opacity:1,duration:.08,immediateRender:false}},{ctx.q(tk + .08)});")
        ctx.sfx(g.get('sfx'), tk, .3)
    ctx.tw(f"tl.to('{S}',{{opacity:0,y:-20,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")


def describe(g, beat):
    items = [(it['text'] if isinstance(it, dict) else it).replace('*', '') for it in g['items']]
    return (f'On “{g["on"]}” a dark app card lists {len(items)} steps dimmed, and each lights up and ticks off as it is said: '
            + ', '.join(f'"{t}"' for t in items) + f'. It holds {beat["hold"]:.1f} s.')
