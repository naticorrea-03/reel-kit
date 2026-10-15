"""A touch dot taps through 2 or 3 elements of a real screenshot, each tap on its phrase, with one ripple and a highlight that stays."""
import os

META = {
    'id': 'ui-tap-sequence', 'name': 'Tap sequence', 'category': 'ui',
    'when': 'The speaker says the exact steps in an app ("pick a day, pick a class, book"). Each tap lands on its step.',
    'never': 'Never taps the speaker does not describe. Never more than three taps. Never a screenshot with private data you have no right to show.',
    'params': {'on': 'phrase that opens it', 'src': 'screenshot file, project-relative (required)',
               'taps': '2-3 of {"on", "x", "y", "w", "h", "label"}: x/y is the centre of the element, w/h its size, all as 0-1 of the image; label is optional',
               'frame': 'phone, card or auto (default: phone when the image is portrait)', 'stage': 'auto (default), float or split',
               'side': 'speaker card side in a split: right (default) or left', 'colors': 'split background colors, default ["accent2"]',
               'hold': 'seconds after the last tap, default 1.4', 'until': 'close before this phrase', 'captions': '"keep" (default) or "pause"'},
    'sfx': ['tap'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

# ---------- local helpers (the product-demo effects share this block; keep the copies in sync) ----------
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


def _fit(ctx, what, texts, width, fmax, fmin=28, max_lines=3, k=GLYPH):
    """one font size for every text (parallel items share a size), the largest that fits width in max_lines."""
    texts = [str(t) for t in texts if t]
    if not texts:
        return int(fmax)
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
    """(x, y, scale, face): full size where a spot clears the faces, else the card shrinks until one does.
    face is the share of a face still covered (over 0.02 means no size cleared)."""
    tries = []
    for sc in scales:
        ws, hs = int(w * sc), int(h * sc)
        x, y = _spot(ctx, what, ws, hs, t0, t1, cands(ws, hs), near, pause, quiet=True)
        face = ctx.face_hit(t0, t1, x, y, x + ws, y + hs)
        tries.append((face, -sc, x, y))
        if face <= .02:
            break
    face, sc, x, y = min(tries)
    return x, y, -sc, face


def _zclip(ctx, sc, a, b, inner, style):
    """ctx.clip on the front layer, with the card zoomed when it had to shrink."""
    return ctx.clip(ctx.front, a, b, inner if sc == 1 else f'<div class="rk-zoom" style="zoom:{sc:.3f}">{inner}</div>', style)


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


def _times(ctx, g, items, step, gap=0.0):
    """one time per item: its own "on" phrase (in order, after the previous one) or an even step after the graphic's word."""
    a = ctx.at(g['on'])[0]
    out, after = [], a - .2
    for k, it in enumerate(items):
        t = ctx.at(it['on'], after + gap)[0] if isinstance(it, dict) and it.get('on') else (out[-1] + step if out else a)
        out.append(max(t, a))
        after = t
    return out


def _color(ctx, name):
    """a brand color as a literal ('accent' or '--c-accent'). GSAP tweens literals, not CSS vars.
    Same order as the page: project vars, then profile brand vars, then brand colors, then the look."""
    key = name if name.startswith('--') else f'--c-{name}'
    brand = ctx.profile.get('brand', {}) or {}
    cols = {f'--c-{k}': v for k, v in (brand.get('colors') or {}).items()}
    for _ in range(8):
        v = str((ctx.project.get('vars') or {}).get(key) or (brand.get('vars') or {}).get(key) or cols.get(key)
                or ctx.look.get('vars', {}).get(key) or '').strip()
        if v.startswith('var('):
            key = v[4:].split(')')[0].split(',')[0].strip()
            continue
        return v or '#000000'
    return '#000000'


# the stage split: the speaker's frame shrinks into a rounded card on one side and a flat brand color fills the rest
SPLIT_S, SPLIT_R = .44, 40


def _split_geo(side):
    """(X, Y, region): where the speaker card sits and the free box (x0, y0, x1, y1) the graphic gets, above the captions."""
    W, H = 1080 * SPLIT_S, 1920 * SPLIT_S
    X = 1040 - W if side == 'right' else 40
    Y = 855 - H / 2
    reg = (90, 250, int(X - 36), 1234) if side == 'right' else (int(X + W + 36), 250, 950, 1234)
    return X, Y, reg


def _bg_hops(ctx, hops, end, reset=True):
    """flat background color steps (discrete, on the beat): hops = [(t, color name)], black again at end."""
    prev = '#000000'   # each step starts from the color before it: a renderer that seeks back must land on that color, not black
    for t, c in hops:
        col = _color(ctx, c)
        ctx.tw(f"tl.fromTo('#root',{{backgroundColor:'{prev}'}},{{backgroundColor:'{col}',duration:.02,immediateRender:false}},{ctx.q(t)});")
        prev = col
    if reset:
        ctx.tw(f"tl.fromTo('#root',{{backgroundColor:'{prev}'}},{{backgroundColor:'#000000',duration:.02,immediateRender:false}},{ctx.q(end - .02)});")


def _stage_move(ctx, t_in, t_out, end, to_vars, from_vars="x:0,y:0,scale:1,borderRadius:0", out_vars="x:0,y:0,scale:1,borderRadius:0"):
    """move the base video (and hide the cutout) from t_in, back to full frame from t_out to end."""
    o = "transformOrigin:'0px 0px'"
    ctx.tw(f"tl.fromTo('#bgv',{{{from_vars},{o}}},{{{to_vars},{o},duration:.55,ease:'expo.inOut',immediateRender:false}},{ctx.q(t_in)});")
    if t_out < end:
        ctx.tw(f"tl.fromTo('#bgv',{{{to_vars},{o}}},{{{out_vars},{o},duration:{max(.2, end - t_out):.2f},ease:'expo.inOut',immediateRender:false}},{ctx.q(t_out)});")
    if ctx.has_cut:   # the cutout is the same picture; it would sit full size over the card
        ctx.tw(f"tl.fromTo('#cutwrap',{{opacity:1}},{{opacity:0,duration:.02,immediateRender:false}},{ctx.q(t_in)});")
        if t_out < end:
            ctx.tw(f"tl.fromTo('#cutwrap',{{opacity:0}},{{opacity:1,duration:.02,immediateRender:false}},{ctx.q(end - .03)});")
    # the grade overlays darken a flat brand color into mud: off while the color shows
    ctx.tw(f"tl.fromTo('.fx',{{opacity:1}},{{opacity:0,duration:.3,immediateRender:false}},{ctx.q(t_in)});")
    if t_out < end:
        ctx.tw(f"tl.fromTo('.fx',{{opacity:0}},{{opacity:1,duration:.3,immediateRender:false}},{ctx.q(t_out + .1)});")
    ctx.lowbusy.append((t_in, end))
    ctx.topbusy.append((t_in, end))


def _split(ctx, t_in, end, side='right', colors=('accent',), hop_times=()):
    """shrink the speaker into a card on `side`; returns (region, content_end). The graphic must be gone by content_end."""
    X, Y, reg = _split_geo(side)
    t_out = end - .5
    _stage_move(ctx, t_in, t_out, end, f'x:{X:.0f},y:{Y:.0f},scale:{SPLIT_S},borderRadius:{SPLIT_R / SPLIT_S:.0f}')
    hops = [(t_in, colors[0])] + [(t, colors[(k + 1) % len(colors)]) for k, t in enumerate(hop_times)]
    _bg_hops(ctx, hops, end)
    return reg, t_out - .02


def _place_or_split(ctx, g, what, w, h, a, end, near=None, pause=False, min_sc=.86):
    """float the graphic clear of the faces when it fits at min_sc or larger; otherwise split the stage.
    g['stage']: 'auto' (default), 'float' or 'split'. Returns ('float', x, y, sc) or ('split', region)."""
    mode = g.get('stage', 'auto')
    if mode not in ('auto', 'float', 'split'):
        ctx.fail(f'{g["type"]} on {g["on"]!r}: stage must be auto, float or split (got {mode!r})')
    if mode != 'split':
        scales = [s for s in (1.0, .86, .74, .62) if s >= (min_sc if mode == 'auto' else .62)]
        x, y, sc, face = _fitspot(ctx, what, w, h, a, end, lambda W, H: _grid(W, H), near, pause, scales)
        if face <= .02 or mode == 'float':
            if face > .02:
                ctx.warn(f'{what} still covers {face:.0%} of a face; try stage "split"')
            elif sc < 1:
                ctx.note(f'{what} shrunk to {sc:.0%} to clear a face')
            return ('float', x, y, sc)
    ctx.note(f'{what}: no spot clear of the face at {min_sc:.0%} size, so the speaker moves into a card and the graphic takes the other side')
    return ('split',)


def _tap_html(style, k=0):
    """a touch indicator (dot plus one ripple ring); style positions it (left/top), the ring centres on that point."""
    return f'<i class="tap tp{k}" style="{style}"><b class="rp"></b><b class="dt"></b></i>'


def _tap_anim(ctx, sel, t, sfx='tap'):
    """the dot lands, presses on t, one ripple, then lifts. One literal tap sound."""
    q = ctx.q
    ctx.tw(f"tl.fromTo('{sel} .dt',{{opacity:0,scale:1.6}},{{opacity:1,scale:1,duration:.2,ease:'power2.out',immediateRender:false}},{q(t - .26)});")
    ctx.tw(f"tl.fromTo('{sel} .dt',{{scale:1}},{{scale:.72,duration:.07,ease:'power2.in',immediateRender:false}},{q(t - .05)});")
    ctx.tw(f"tl.fromTo('{sel} .dt',{{scale:.72}},{{scale:1,duration:.22,ease:'back.out(3)',immediateRender:false}},{q(t + .02)});")
    ctx.tw(f"tl.fromTo('{sel} .rp',{{opacity:.9,scale:.4}},{{opacity:0,scale:2.3,duration:.5,ease:'power2.out',immediateRender:false}},{q(t)});")
    ctx.tw(f"tl.fromTo('{sel} .dt',{{opacity:1}},{{opacity:0,duration:.2,immediateRender:false}},{q(t + .34)});")
    ctx.sfx(sfx, t - .02, .5)
# ---------- end of local helpers ----------


def build(g, ctx):
    _need(ctx, g, 'src', 'taps')
    taps = g['taps']
    if not 2 <= len(taps) <= 3:
        ctx.fail(f'ui-tap-sequence on {g["on"]!r} shows 2 or 3 taps (got {len(taps)})')
    for k, tp in enumerate(taps):
        if not tp.get('on'):
            ctx.fail(f'ui-tap-sequence tap {k + 1} needs its own "on" phrase (each tap lands on its step)')
        if not (0 <= float(tp.get('x', -1)) <= 1 and 0 <= float(tp.get('y', -1)) <= 1):
            ctx.fail(f'ui-tap-sequence tap {k + 1}: x and y are 0-1 of the image (got {tp.get("x")}, {tp.get("y")})')
    url = ctx.asset(g['src'])
    iw, ih = ctx.image_size(url)
    ts = _times(ctx, g, taps, .9, .05)
    ts[0] = max(ts[0], ctx.at(g['on'])[0] + .45)   # the screenshot lands first, then the first tap
    for k in range(1, len(ts)):
        if ts[k] - ts[k - 1] < .55:
            ctx.fail(f'ui-tap-sequence taps {k} and {k + 1} are {ts[k] - ts[k - 1]:.2f} s apart; each needs 0.55 s or more')
    a, end = _window(ctx, g, 1.4, ts[-1])
    frame = g.get('frame', 'auto')
    phone = frame == 'phone' or (frame == 'auto' and ih / iw > 1.4)
    bz = 14 if phone else 12
    if phone:
        IW = 400 - 2 * bz
        IH = IW * ih / iw
        if IH > 950:
            ctx.fail(f'ui-tap-sequence {g["src"]!r} is too tall for a phone ({IH:.0f}px at phone width); crop it to one screen')
    else:
        IW = 760 - 2 * bz
        IH = IW * ih / iw
        if IH > 900:
            IH = 900
            IW = IH * iw / ih
    W, H = IW + 2 * bz, IH + 2 * bz
    pause = g.get('captions', 'keep') == 'pause'
    mode = _place_or_split(ctx, g, 'ui-tap-sequence', W, H, a, end, None, pause, 1.0 if phone else .86)
    t_on = a + .3 if mode[0] == 'split' else a
    if mode[0] == 'split':
        reg, cend = _split(ctx, a - .05, end, g.get('side', 'right'), g.get('colors', ['accent2']))
        rw, rh = reg[2] - reg[0], reg[3] - reg[1]
        sc = min(1.15, rw / W, rh / H)
        x, y = reg[0] + (rw - W * sc) / 2, reg[1] + (rh - H * sc) / 2
        if pause:
            ctx.busy.append((a, end))
    else:
        _, x, y, sc = mode
        cend = end
        _claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    over = []
    for k, tp in enumerate(taps):
        cx, cy = float(tp['x']) * IW, float(tp['y']) * IH
        if tp.get('w') and tp.get('h'):
            bw, bh = float(tp['w']) * IW + 16, float(tp['h']) * IH + 16
            over.append(f'<i class="hb hb{k}" style="left:{cx - bw / 2:.0f}px;top:{cy - bh / 2:.0f}px;width:{bw:.0f}px;height:{bh:.0f}px"></i>')
        if tp.get('label'):
            lfs = 30
            lw = min(IW - 24, len(tp['label']) * lfs * .58 + 44)
            if len(_wrap(tp['label'], IW - 68, lfs)) > 1:
                ctx.fail(f'ui-tap-sequence label {tp["label"]!r} is too long for one line on this screenshot')
            ly = cy - (float(tp.get('h', 0)) * IH / 2 + 8) - 60 if cy > IH * .25 else cy + float(tp.get('h', 0)) * IH / 2 + 18
            lx = max(12, min(IW - lw - 12, cx - lw / 2))
            over.append(f'<div class="lb lb{k}" style="left:{lx:.0f}px;top:{ly:.0f}px;font-size:{lfs}px">{ctx.esc(tp["label"])}</div>')
        over.append(_tap_html(f'left:{cx:.0f}px;top:{cy:.0f}px', k))
    html = (f'<div class="fx-ui-tap-sequence {"phone" if phone else "card"}" style="width:{W:.0f}px;height:{H:.0f}px;padding:{bz}px">'
            f'<div class="im" style="width:{IW:.0f}px;height:{IH:.0f}px"><img src="{url}">{"".join(over)}</div></div>')
    cid = _zclip(ctx, sc, t_on, cend, html, f'position:absolute;left:{x:.0f}px;top:{y:.0f}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:150,rotation:-4,scale:.92}},{{opacity:1,y:0,rotation:0,scale:1,duration:.58,ease:'back.out(1.4)',immediateRender:false}},{ctx.q(t_on)});")
    for k, t in enumerate(ts):
        t = max(t, t_on + .5)
        _tap_anim(ctx, f'#{cid} .tp{k}', t)
        ctx.tw(f"tl.fromTo('#{cid} .hb{k}',{{opacity:0,scale:1.2}},{{opacity:1,scale:1,duration:.24,ease:'back.out(2)',immediateRender:false}},{ctx.q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .lb{k}',{{opacity:0,y:14}},{{opacity:1,y:0,duration:.24,ease:'back.out(2)',immediateRender:false}},{ctx.q(t + .05)});")
        if k + 1 < len(ts):   # one label at a time
            ctx.tw(f"tl.fromTo('#{cid} .lb{k}',{{opacity:1}},{{opacity:0,duration:.15,immediateRender:false}},{ctx.q(max(t + .4, ts[k + 1] - .2))});")
        ctx.tw(f"tl.fromTo('#{cid} .im',{{scale:1}},{{scale:.985,duration:.07,yoyo:true,repeat:1,ease:'power1.out',immediateRender:false}},{ctx.q(t - .04)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-50,scale:.96,duration:.25,ease:'power2.in'}},{ctx.q(cend - .27)});")


def describe(g, beat):
    steps = [tp.get('label') or tp['on'] for tp in g['taps']]
    return (f'On “{g["on"]}” the {os.path.splitext(os.path.basename(g["src"]))[0].replace("-", " ")} screenshot rises and a touch dot taps '
            f'{len(steps)} elements in order ({" > ".join(steps)}), each on its phrase, with one ripple and a highlight. It holds {beat["hold"]:.1f} s.')
