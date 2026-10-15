"""Big title card: a section or list name wipes on, line by line, in the band clear of the face."""
import re

META = {
    'id': 'title', 'name': 'Title card', 'category': 'text',
    'when': 'The speaker starts a new section or names what is coming: "step two", "the fix", "three rules". The title names it.',
    'never': 'Never the sentence being said, word for word (that is the serif effect). Never in the first two seconds (the hook owns them).',
    'params': {'on': 'phrase that triggers it', 'text': 'title, "line one / line two" for two lines (required, up to 3 lines)',
               'hold': 'seconds, default 1.8', 'captions': '"pause" or "keep", default pause', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'claude-reel-editor',
    'credit': 'Adapted from the "title" card in claude-reel-editor by Nicola Pocock (getgitgirl): line-by-line clip-path wipe, '
              'lines alternating left and right. Rewritten for the reel-kit contract.',
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
    _need(ctx, g, 'text')
    lines = [x.strip() for x in str(g['text']).split('/') if x.strip()]
    if len(lines) > 3:
        ctx.fail(f'title {g["text"]!r} has {len(lines)} lines; keep it to 3')
    a, end = _window(ctx, g, 1.8)
    if a < ctx.hook_end + .1:
        ctx.fail(f'title on {g["on"]!r} lands at {a:.2f} s, inside the hook; the hook card is the title there')
    tw = re.findall(r'[a-z0-9]+', g['text'].lower())
    said = {w for x in ctx.words if a - 2 <= x['start'] <= end for w in re.findall(r'[a-z0-9]+', x['text'].lower())}
    if tw and all(w in said for w in tw) and len(tw) > 3:
        ctx.fail(f'title {g["text"]!r} is the spoken sentence; use serif for that, or name the section instead')
    W = 860
    # every line is fitted on its own, one size for all so the block reads as one title
    fs = min(_fit(ctx, f'title line {ln!r}', [ln], W, 190, 70, 1, .64) for ln in lines)
    H = int(len(lines) * fs * .98) + 24
    pause = g.get('captions', 'pause') != 'keep'
    x, y, sc = _fitspot(ctx, 'title', W, H, a, end, lambda W, H: _grid(W, H, xs=(90,)), None, pause)
    _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    lc = ' on-light' if _on_light(ctx, a, end, x, y, W * sc, H * sc) else ''
    al = ['left', 'right', 'left'] if len(lines) > 1 else ['center']
    inner = ''.join(f'<div class="tl" style="text-align:{al[k]}"><span>{ctx.esc(ln)}</span></div>' for k, ln in enumerate(lines))
    cid = _zclip(ctx, sc, a, end, f'<div class="fx-title{lc}" style="width:{W}px;font-size:{fs}px">{inner}</div>', f'position:absolute;left:{x}px;top:{y}px;')
    ctx.tw(f"gsap.set('#{cid} .tl span',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .tl span',{{opacity:0,x:-30,clipPath:'inset(-30% 100% -30% 0%)'}},"
           f"{{opacity:1,x:0,clipPath:'inset(-30% 0% -30% 0%)',duration:.32,ease:'power3.out',stagger:.22,immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.2,ease:'power2.in'}},{ctx.q(end - .2)});")
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    return f'On “{g["on"]}” the title "{g["text"].replace(" / ", " ")}" wipes on line by line, clear of the face. It holds {beat["hold"]:.1f} s.'
