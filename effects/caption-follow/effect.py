"""Follow caption: one sentence writes itself word by word in big type while the frame pulls back, then captions resume."""
import re

META = {
    'id': 'caption-follow', 'name': 'Follow caption', 'category': 'captions',
    'when': 'One short sentence that carries the reel (the hook line or the payoff) gets the full frame, each word landing as it is said.',
    'never': 'Never more than 12 words. Never twice in a row, and never next to a serif line (they do the same job). Never over a face.',
    'params': {'on': 'first words of the sentence', 'until': 'last word(s), default the end of that sentence', 'accent': 'list of words to color in the accent',
               'sfx': 'optional sound name'},
    'sfx': [], 'source': 'claude-reel-editor',
    'credit': 'Adapted from the "follow" card in claude-reel-editor by Nicola Pocock (getgitgirl), which mounts the caption-camera-follow motion from '
              'the HyperFrames registry (heygen-com/hyperframes, Apache-2.0): one sentence written word by word across a pull-back. '
              'Written from scratch for reel-kit, word-timed from the transcript; the smear is dropped.',
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


def build(g, ctx):
    a0, _ = ctx.at(g['on'])
    i0 = next(i for i, w in enumerate(ctx.words) if abs(w['start'] - a0) < 1e-6)
    if g.get('until'):
        u1 = ctx.at(g['until'], a0)[1]
        idx = [i for i in range(i0, len(ctx.words)) if ctx.words[i]['start'] < u1]
    else:
        idx = []
        for i in range(i0, len(ctx.words)):
            idx.append(i)
            if ctx.words[i]['text'][-1:] in '.!?':
                break
    ws = [(ctx.capwords[i], ctx.disp(ctx.capwords[i]['text'])) for i in idx]
    ws = [(w, d) for w, d in ws if d]
    if not ws:
        ctx.fail(f'caption-follow on {g["on"]!r} found no words')
    if len(ws) > 12:
        ctx.fail(f'caption-follow on {g["on"]!r} runs {len(ws)} words; 12 at most (set "until" earlier)')
    last = ws[-1][0]['start']
    # until names the last word shown (inclusive), not a phrase to close before, so _window must not see it
    a, end = _window(ctx, {k: v for k, v in g.items() if k != 'until'}, max(.8, ws[-1][0]['end'] - last + .35), last=last)
    acc = {re.sub(r"[^a-z0-9']", '', x.lower()) for x in g.get('accent', [])}
    text = ' '.join(d for _, d in ws)
    W, Z = 760, 1.14
    fmax = _fit(ctx, 'caption-follow', [text], W, 132, 64, 4, .6)
    cands = lambda W_, H_: [((1080 - W_) // 2, y) for y in range(250, 1471 - H_, 20)]
    for fs in range(fmax, 63, -6):   # the type gets smaller before it may touch a face
        nl = len(_wrap(text, W, fs, .6))
        H = int(nl * fs * 1.06) + 24
        Wb, Hb = int(W * Z) + 4, int(H * Z) + 4
        x, y = _spot(ctx, 'caption-follow', Wb, Hb, a, end, cands(Wb, Hb), None, True, quiet=True)
        if ctx.face_hit(a, end, x, y, x + Wb, y + Hb) <= .005:
            break
    else:
        ctx.fail(f'caption-follow {text!r} does not fit clear of the face even at 64px; shorten it with "until"')
    _claim(ctx, x, y, Wb, Hb, a, end, True)
    ctx.lowbusy.append((a, end))
    lc = ' on-light' if _on_light(ctx, a, end, x, y, Wb, Hb) else ''
    spans = ''.join(f'<span class="w{" ac" if re.sub(r"[^a-z0-9]", "", d.lower()) in acc else ""}">{ctx.esc(d)}</span>' for _, d in ws)
    html = (f'<div class="fx-caption-follow{lc}" style="width:{Wb}px;height:{Hb}px"><div class="cam" style="left:{(Wb - W) / 2:.0f}px;top:{(Hb - H) / 2:.0f}px;'
            f'width:{W}px;font-size:{fs}px"><div class="tx">{spans}</div></div></div>')
    cid = ctx.clip(ctx.front, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"gsap.set('#{cid} .w',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .cam',{{scale:{Z}}},{{scale:1,duration:{max(.4, end - a - .2):.2f},ease:'power1.out',immediateRender:false}},{ctx.q(a)});")
    for k, (w, _d) in enumerate(ws):
        ctx.tw(f"tl.fromTo('#{cid} .w:nth-child({k + 1})',{{opacity:0,y:26}},{{opacity:1,y:0,duration:.12,ease:'power3.out',immediateRender:false}},{ctx.q(max(a, w['start'] - .03))});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.18}},{ctx.q(end - .18)});")
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    return f'From “{g["on"]}” the sentence writes itself word by word in big type while the frame pulls back; captions pause for {beat["hold"]:.1f} s.'
