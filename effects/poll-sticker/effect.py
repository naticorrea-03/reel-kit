"""Instagram-style poll sticker: a question, two options, and the result bars fill toward the winner."""

META = {
    'id': 'poll-sticker', 'name': 'Poll sticker', 'category': 'social',
    'when': 'The speaker asks the audience a this-or-that question, or cites a split vote or survey.',
    'never': 'Never a made-up result presented as real data. Two options only.',
    'params': {'on': 'phrase that triggers it', 'question': 'the poll question (required)', 'options': '[option A, option B] (required)',
               'pick': 'index of the winning option, 0 or 1, default 0', 'percent': 'winner share 1-99, default 70',
               'vote_on': 'phrase where the bars fill, default 0.7 s in', 'hold': 'seconds, default 2.8',
               'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
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
    _need(ctx, g, 'question', 'options')
    opts = g['options']
    if len(opts) != 2 or not all(opts):
        ctx.fail(f'poll-sticker on {g["on"]!r} needs exactly two options')
    pick = int(g.get('pick', 0))
    pct = int(g.get('percent', 70))
    if pick not in (0, 1) or not 0 < pct < 100:
        ctx.fail(f'poll-sticker on {g["on"]!r}: pick must be 0 or 1 and percent 1-99')
    a, end = _window(ctx, g, 2.8)
    W = 680
    qfs = _fit(ctx, 'poll-sticker question', [g['question']], W - 2 * 36 - 12, 46, 32, 3)
    ofs = _fit(ctx, 'poll-sticker options', opts, W - 2 * 36 - 2 * 26 - 110 - 12, 36, 28, 1)
    H = int(36 * 2 + _lines([g['question']], W - 84, qfs) * qfs * 1.2 + 26 + 2 * 88 + 16) + 8
    face = ctx.speaker_face(a + .1)
    near = ((face[0] + face[2]) / 2, face[3] + 80) if face else None
    pause = g.get('captions', 'pause') != 'keep'
    x, y, sc = _fitspot(ctx, 'poll-sticker', W, H, a, end, lambda W, H: _grid(W, H), near, pause)
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    shares = [pct, 100 - pct] if pick == 0 else [100 - pct, pct]
    rows = ''.join(f'<div class="opt{" win" if k == pick else ""}"><div class="fill"></div><div class="lab" style="font-size:{ofs}px">{ctx.esc(o)}</div>'
                   f'<div class="pc" data-k="{k}">0%</div></div>' for k, o in enumerate(opts))
    html = (f'<div class="fx-poll-sticker" style="width:{W}px"><div class="q" style="font-size:{qfs}px">{ctx.esc(g["question"])}</div>{rows}</div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    tv = min(ctx.at(g['vote_on'], a)[0] if g.get('vote_on') else a + .7, end - 1.0)
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,scale:.6,rotation:-6}},{{opacity:1,scale:1,rotation:-2,duration:.4,ease:'back.out(1.7)',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"gsap.set('#{cid} .pc',{{opacity:0}});")
    for k, s in enumerate(shares):
        ctx.tw(f"tl.fromTo('#{cid} .opt:nth-of-type({k + 2}) .fill',{{scaleX:0}},{{scaleX:{s / 100:.2f},duration:.7,ease:'power2.out',immediateRender:false}},{ctx.q(tv)});")
        ctx.tw(f"tl.fromTo('#{cid} .pc[data-k=\"{k}\"]',{{opacity:0}},{{opacity:1,duration:.15,immediateRender:false}},{ctx.q(tv)});")
        ctx.tw(f"(function(){{const o={{v:0}};tl.to(o,{{v:{s},duration:.7,ease:'power2.out',onUpdate:function(){{"
               f"const el=document.querySelector('#{cid} .pc[data-k=\"{k}\"]');if(el)el.textContent=Math.round(o.v)+'%';}},immediateRender:false}},{ctx.q(tv)});}})();")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,scale:.9,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx'), tv, .4)


def describe(g, beat):
    o = g['options']
    p = int(g.get('pick', 0))
    return (f'On “{g["on"]}” a poll sticker asks "{g["question"]}" ({o[0]} vs {o[1]}). The bars fill to '
            f'{g.get("percent", 70)}% for {o[p]}. It holds {beat["hold"]:.1f} s.')
