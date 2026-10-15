"""Oversized cursor: a big pointer glides to a button and clicks it on the spoken word; the button flips to its done state."""

META = {
    'id': 'oversized-cursor', 'name': 'Big cursor click', 'category': 'ui',
    'when': 'The speaker describes one click that changed something: "I hit approve", "one click and it sent". Shows the button and what it turned into.',
    'never': 'Never a click on nothing. Never ripples, rings or glows on the click: the button press and its new label are the feedback.',
    'params': {'on': 'phrase that triggers it', 'button': 'button label before the click (required)', 'done': 'label after the click, optional (e.g. "Sent")',
               'click_on': 'phrase the click lands on, default 0.7 s after "on"', 'hold': 'seconds after the click, default 1.2',
               'sfx': 'sound on the click, default mouse-click ("none" for silence)'},
    'sfx': ['mouse-click'], 'source': 'ours',
    'credit': 'Idea from the oversized-cursor motion in the HyperFrames registry (heygen-com/hyperframes, Apache-2.0), as listed in claude-reel-editor '
              'references/motions.md by Nicola Pocock (MIT). Written from scratch for reel-kit; the click ripple is dropped (house rule: no pulse rings).',
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

CURSOR = ('<svg class="cur" viewBox="0 0 64 80" width="{w}" height="{h}"><path d="M6 4 L6 64 L20 51 L30 74 L41 69 L31 47 L50 47 Z" '
          'fill="var(--c-ink)" stroke="var(--c-card)" stroke-width="5" stroke-linejoin="round"/></svg>')


def build(g, ctx):
    _need(ctx, g, 'button')
    a = ctx.at(g['on'])[0]
    tc = ctx.at(g['click_on'], a - .05)[0] if g.get('click_on') else a + .7
    a, end = _window(ctx, g, float(g.get('hold', 1.2)), last=tc)
    a = min(a, tc - .45)   # the cursor needs ~0.45 s of travel, so the click itself lands on its word
    labels = [g['button']] + ([g['done']] if g.get('done') else [])
    fs = _fit(ctx, 'oversized-cursor button', labels, 600, 60, 36, 1, .58)
    bw = int(max(len(t) for t in labels) * fs * .58) + 2 * 56
    bh = int(fs * 1.25) + 2 * 26
    cw, ch = 120, 150
    tw_ = max(len(t) for t in labels) * fs * .58
    tipx = min(bw - 34, bw / 2 + tw_ / 2 + 14)   # the tip lands just right of the label, so the label stays readable
    # the button plus the room the cursor travels in (below and to the right of it)
    W, H = bw + 150, bh + 190
    x, y, sc = _fitspot(ctx, 'oversized-cursor', W, H, a, end, lambda W_, H_: _grid(W_, H_), None, False)
    _claim(ctx, x, y, W * sc, H * sc, a, end, False)
    done = f'<span class="lb2">{ctx.esc(g["done"])}</span>' if g.get('done') else ''
    html = (f'<div class="fx-oversized-cursor" style="width:{W}px;height:{H}px">'
            f'<div class="btn" style="width:{bw}px;height:{bh}px;font-size:{fs}px"><span class="lb1">{ctx.esc(g["button"])}</span>{done}</div>'
            f'<div class="cw" style="left:{tipx - 6:.0f}px;top:{bh * .52:.0f}px">{CURSOR.format(w=cw, h=ch)}</div></div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"tl.fromTo('#{cid} .btn',{{opacity:0,y:30,scale:.92}},{{opacity:1,y:0,scale:1,duration:.3,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.fromTo('#{cid} .cw',{{opacity:0,x:120,y:130}},{{opacity:1,x:0,y:0,duration:{min(.5, tc - a - .08):.2f},ease:'power3.out',immediateRender:false}},{ctx.q(a + .05)});")
    ctx.tw(f"tl.to('#{cid} .cw',{{scale:.86,duration:.08,ease:'power2.in',yoyo:true,repeat:1}},{ctx.q(tc - .08)});")
    ctx.tw(f"tl.to('#{cid} .btn',{{scale:.94,duration:.08,ease:'power2.in',yoyo:true,repeat:1}},{ctx.q(tc - .08)});")
    if g.get('done'):
        ctx.tw(f"gsap.set('#{cid} .lb2',{{opacity:0}});")
        ctx.tw(f"tl.to('#{cid} .lb1',{{opacity:0,y:-20,duration:.14}},{ctx.q(tc)});")
        ctx.tw(f"tl.fromTo('#{cid} .lb2',{{opacity:0,y:20}},{{opacity:1,y:0,duration:.18,immediateRender:false}},{ctx.q(tc + .04)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-20,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx', 'mouse-click'), tc - .02, .5)


def describe(g, beat):
    after = f' and it turns into "{g["done"]}"' if g.get('done') else ''
    return f'On “{g["on"]}” a "{g["button"]}" button appears; a big cursor glides in and clicks it{after}. It holds {beat["hold"]:.1f} s.'
