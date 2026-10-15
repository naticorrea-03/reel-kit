"""Before / after wipe: a vertical line sweeps across the frame. Behind it the footage is graded, ahead of it the raw look, and one big word is revealed."""

META = {
    'id': 'before-after-wipe', 'name': 'Before and after wipe', 'category': 'structure',
    'when': 'The speaker talks about the edit, the look, or a change they made ("what it sent back", "after", "edited").',
    'never': 'Never when nothing changed. The big word names the result; never a word the caption already shows on its own.',
    'params': {'on': 'phrase where the sweep starts', 'word': 'one big word revealed on the after side (required)',
               'before': 'left pill text, default "before"', 'after': 'right pill text, default "after"',
               'sweep': 'seconds the line takes to cross, default 1.1', 'hold': 'seconds the word holds after the sweep, default 1.0',
               'raw': 'CSS filter for the before side, default a flat washed-out log look', 'sfx': 'optional sound name (none by default)'},
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


def build(g, ctx):
    _need(ctx, g, 'word')
    a = ctx.at(g['on'])[0]
    sweep = float(g.get('sweep', 1.1))
    lead = .5                       # the raw look shows on its own first, so the change reads
    a, end = _window(ctx, g, float(g.get('hold', 1.0)), last=a + lead + sweep)
    ts, te = a + lead, a + lead + sweep
    raw = g.get('raw', 'saturate(.42) contrast(.74) brightness(1.1)')
    word = str(g['word'])
    ws = _fit(ctx, 'before-after-wipe word', [word], 860, 230, 90, 1, k=.6)
    wh = int(ws * 1.05)
    # the word sits where no face is during the whole wipe: above the heads first, then the chest band
    face_ok = lambda y: ctx.face_hit(a, end, 110, y, 970, y + wh) <= .005
    ys = [y for y in range(250, 1200 - wh, 20) if face_ok(y)]
    if not ys:
        ctx.fail(f'before-after-wipe: no band clear of the face for {word!r} at {ws}px; shorten the word')
    above = [y for y in ys if y < 700]
    wy = above[0] if above else ys[-1]
    # pills and the handle ride one row, kept off the faces too
    py = next((y for y in range(1120, 1300, 20) if ctx.face_hit(a, end, 90, y, 990, y + 70) <= .005), 1180)
    lum, busy = ctx.bg_luma(ts, end, 140, wy, 940, wy + wh)
    over = ctx.alpha_cover(ts + .2, 140, wy, 940, wy + wh)   # letters over the speaker stay light
    tone = ' ink' if lum > .62 and busy < .12 and over < .15 else ''   # light letters on a bright plain wall read as a smudge
    ctx.busy.append((a, end))
    ctx.lowbusy.append((a, end))
    if wy < 400:
        ctx.topbusy.append((a, end))
    html = (f'<div class="fx-before-after-wipe">'
            f'<div class="raw" style="--raw:{ctx.esc(raw)}"></div>'
            f'<div class="word{tone}" style="top:{wy}px;font-size:{ws}px;height:{wh}px">{ctx.esc(word)}</div>'
            f'<div class="line"><div class="knob" style="top:{py - 2}px"><svg viewBox="0 0 24 24"><path d="M9 6l-5 6 5 6M15 6l5 6-5 6"/></svg></div></div>'
            f'<div class="pill before" style="top:{py}px">{ctx.esc(g.get("before", "before"))}</div>'
            f'<div class="pill after" style="top:{py}px">{ctx.esc(g.get("after", "after"))}</div></div>')
    cid = ctx.clip(ctx.front, a, end, html, 'position:absolute;left:0;top:0;width:1080px;height:1920px;')
    S = f'#{cid}'
    X0, X1 = 1080, 0              # the line travels right to left; the after side grows from the right
    ctx.tw(f"gsap.set('{S} .raw',{{width:1080}});")
    ctx.tw(f"gsap.set('{S} .line',{{x:{X0}}});")
    ctx.tw(f"gsap.set('{S} .word',{{clipPath:'inset(0 0 0 100%)'}});")
    ctx.tw(f"gsap.set('{S} .pill.after',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('{S} .raw',{{opacity:0}},{{opacity:1,duration:.18,immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.fromTo('{S} .pill.before',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.25,ease:'power3.out',immediateRender:false}},{ctx.q(a + .1)});")
    ctx.tw(f"tl.fromTo('{S} .raw',{{width:1080}},{{width:0,duration:{sweep:.3f},ease:'power2.inOut',immediateRender:false}},{ctx.q(ts)});")
    ctx.tw(f"tl.fromTo('{S} .line',{{x:{X0}}},{{x:{X1},duration:{sweep:.3f},ease:'power2.inOut',immediateRender:false}},{ctx.q(ts)});")
    ctx.tw(f"tl.fromTo('{S} .word',{{clipPath:'inset(0 0 0 100%)'}},{{clipPath:'inset(0 0 0 0%)',duration:{sweep:.3f},ease:'power2.inOut',immediateRender:false}},{ctx.q(ts)});")
    # each pill shows only while its side covers it: before (left) leaves as the line reaches it, after (right) arrives once passed
    ctx.tw(f"tl.to('{S} .pill.before',{{opacity:0,duration:.15}},{ctx.q(ts + sweep * .55)});")
    ctx.tw(f"tl.fromTo('{S} .pill.after',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.25,ease:'power3.out',immediateRender:false}},{ctx.q(ts + sweep * .3)});")
    ctx.tw(f"tl.fromTo('{S} .word',{{scale:1.06}},{{scale:1,duration:{sweep + .3:.3f},ease:'power2.out',immediateRender:false}},{ctx.q(ts)});")
    # the handle shows only while the line is inside the safe zone (power2.inOut puts it there between 26% and 74% of the sweep)
    ctx.tw(f"gsap.set('{S} .knob',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('{S} .knob',{{opacity:0}},{{opacity:1,duration:.08,immediateRender:false}},{ctx.q(ts + sweep * .25)});")
    ctx.tw(f"tl.to('{S} .knob',{{opacity:0,duration:.08}},{ctx.q(ts + sweep * .68)});")
    ctx.tw(f"tl.to('{S} .line',{{opacity:0,duration:.2}},{ctx.q(te)});")
    ctx.tw(f"tl.to('{S} .word, {S} .pill',{{opacity:0,y:-20,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")
    ctx.sfx(g.get('sfx'), ts, .35)


def describe(g, beat):
    return (f'On “{g["on"]}” the frame drops to a flat raw look with a "{g.get("before", "before")}" pill, then a line sweeps across '
            f'and leaves the graded look behind it, revealing "{g["word"]}" big. It holds {beat["hold"]:.1f} s.')
