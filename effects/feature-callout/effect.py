"""A screenshot with one region magnified in a lens circle, joined by a callout line, with a short label naming what it does."""
import os

META = {
    'id': 'feature-callout', 'name': 'Feature callout', 'category': 'ui',
    'when': 'The speaker points at one detail of an app or page that is too small to read at full size: a setting, a number, a button.',
    'never': 'Never a label that repeats the caption word for word. Never a region you could read without the lens.',
    'params': {'on': 'phrase that opens it', 'src': 'screenshot file, project-relative (required)',
               'zoom': '{"x", "y", "w", "h"}: the region to magnify, 0-1 of the image (x/y is its top-left corner)',
               'label': 'short label, up to 3 lines (required)', 'label_on': 'optional phrase where the lens and label land, default 0.4 s after on',
               'stage': 'auto (default), float or split', 'side': 'speaker card side in a split: right (default) or left',
               'colors': 'split background colors, default ["accent"]', 'hold': 'seconds after the lens lands, default 2.0',
               'until': 'close before this phrase', 'captions': '"keep" (default) or "pause"'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
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


def _layout(ctx, g, url, iw, ih, W=None, H=None):
    """(html, w, h). Row layout (screenshot, lens to its right, label under the lens) when W is None, else a column fitted to W x H."""
    z = g['zoom']
    rx, ry, rw, rh = [float(z[k]) for k in ('x', 'y', 'w', 'h')]
    if not (0 <= rx < 1 and 0 <= ry < 1 and 0 < rw <= 1 and 0 < rh <= 1):
        ctx.fail('feature-callout zoom x/y/w/h are 0-1 of the image')
    if W is None:
        sh = 520
        sw = sh * iw / ih
        if sw > 420:
            sw, sh = 420, 420 * ih / iw
        D = 330
        lw = 420
        lfs = _fit(ctx, 'feature-callout label', [g['label']], lw - 48, 44, 30, 3, .58)
        lh = _lines([g['label']], lw - 48, lfs, .58) * lfs * 1.2 + 36
        cw = max(D, lw)
        w, h = sw + 70 + cw, max(sh, D + 26 + lh)
        sx, sy = 0, (h - sh) / 2
        cx, cy = sw + 70 + cw / 2, (h - D - 26 - lh) / 2 + D / 2
        lx, ly = sw + 70 + (cw - lw) / 2, cy + D / 2 + 26
    else:   # column for a split: a big screenshot on the left, the lens floats over its right side under the region, label below
        w = W
        lw = W
        lfs = _fit(ctx, 'feature-callout label', [g['label']], lw - 48, 44, 30, 3, .58)
        lh = _lines([g['label']], lw - 48, lfs, .58) * lfs * 1.2 + 36
        D = min(W * .64, 300)
        sw = W * .66
        sh = sw * ih / iw
        if sh > H - lh - 40:
            sh = H - lh - 40
            sw = sh * iw / ih
        sx, sy = 0, 0
        cx = W - D / 2
        cy = min(max(sy + (ry + rh) * sh + D / 2 + 50, D / 2), sh - D / 2 + 40)
        h = max(sh, cy + D / 2) + 24 + lh
        lx, ly = 0, max(sh, cy + D / 2) + 24
    # the region on the displayed screenshot, and the lens zoom that fills the circle with it
    bx, by, bw, bh = sx + rx * sw, sy + ry * sh, rw * sw, rh * sh
    k = D * .86 / max(bw, bh)
    if k < 1.6:
        ctx.fail(f'feature-callout region is only magnified {k:.1f}x; pick a smaller region (it should be unreadable at full size)')
    bgw, bgh = sw * k, sh * k
    px, py = D / 2 - (bx + bw / 2 - sx) * k, D / 2 - (by + bh / 2 - sy) * k
    # callout line from the region's nearest edge to the lens rim
    ax, ay = (bx + bw, by + bh / 2) if W is None else (min(bx + bw, cx), by + bh)
    import math
    ang = math.atan2(ay - cy, ax - cx)
    ex, ey = cx + math.cos(ang) * D / 2, cy + math.sin(ang) * D / 2
    L = math.hypot(ex - ax, ey - ay)
    html = (f'<div class="fx-feature-callout" style="width:{w:.0f}px;height:{h:.0f}px">'
            f'<div class="sh" style="left:{sx:.0f}px;top:{sy:.0f}px;width:{sw:.0f}px;height:{sh:.0f}px"><img src="{url}"></div>'
            f'<i class="bx" style="left:{bx - 6:.0f}px;top:{by - 6:.0f}px;width:{bw + 12:.0f}px;height:{bh + 12:.0f}px"></i>'
            f'<svg class="ln" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}"><line x1="{ax:.0f}" y1="{ay:.0f}" x2="{ex:.0f}" y2="{ey:.0f}" '
            f'stroke-dasharray="{L:.0f}" stroke-dashoffset="{L:.0f}"/></svg>'
            f'<div class="lens" style="left:{cx - D / 2:.0f}px;top:{cy - D / 2:.0f}px;width:{D:.0f}px;height:{D:.0f}px">'
            f'<div class="lz" style="background-image:url({url});background-size:{bgw:.0f}px {bgh:.0f}px;background-position:{px:.0f}px {py:.0f}px"></div></div>'
            f'<div class="lb" style="left:{lx:.0f}px;top:{ly:.0f}px;width:{lw:.0f}px;font-size:{lfs}px">{ctx.esc(g["label"])}</div></div>')
    return html, int(w), int(h), L


def build(g, ctx):
    _need(ctx, g, 'src', 'zoom', 'label')
    url = ctx.asset(g['src'])
    iw, ih = ctx.image_size(url)
    a0 = ctx.at(g['on'])[0]
    tl_ = max(ctx.at(g['label_on'], a0 - .2)[0] if g.get('label_on') else a0 + .4, a0 + .4)
    a, end = _window(ctx, g, 2.0, tl_)
    pause = g.get('captions', 'keep') == 'pause'
    html, w, h, L = _layout(ctx, g, url, iw, ih)
    mode = _place_or_split(ctx, g, 'feature-callout', w, h, a, end, None, pause, .74)
    t_on = a + .3 if mode[0] == 'split' else a
    if mode[0] == 'split':
        reg, cend = _split(ctx, a - .05, end, g.get('side', 'right'), g.get('colors', ['accent']))
        rw, rh = reg[2] - reg[0], reg[3] - reg[1]
        html, w, h, L = _layout(ctx, g, url, iw, ih, rw, rh)
        sc = min(1.0, rh / h)
        x, y = reg[0] + (rw - w * sc) / 2, reg[1] + (rh - h * sc) / 2
        if pause:
            ctx.busy.append((a, end))
    else:
        _, x, y, sc = mode
        cend = end
        _claim(ctx, x, y, w * sc, h * sc, a, end, pause)
    tl_ = max(tl_, t_on + .4)
    cid = _zclip(ctx, sc, t_on, cend, html, f'position:absolute;left:{x:.0f}px;top:{y:.0f}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .sh',{{opacity:0,y:90,rotation:-3,scale:.94}},{{opacity:1,y:0,rotation:0,scale:1,duration:.5,ease:'back.out(1.4)',immediateRender:false}},{q(t_on)});")
    ctx.tw(f"tl.fromTo('#{cid} .bx',{{opacity:0,scale:1.25}},{{opacity:1,scale:1,duration:.24,ease:'back.out(2)',immediateRender:false}},{q(tl_ - .3)});")
    ctx.tw(f"tl.fromTo('#{cid} .ln line',{{strokeDashoffset:{L:.0f}}},{{strokeDashoffset:0,duration:.22,ease:'power2.out',immediateRender:false}},{q(tl_ - .14)});")
    ctx.tw(f"tl.fromTo('#{cid} .lens',{{opacity:0,scale:.2}},{{opacity:1,scale:1,duration:.46,ease:'back.out(1.6)',immediateRender:false}},{q(tl_)});")
    ctx.tw(f"tl.fromTo('#{cid} .lz',{{scale:.7}},{{scale:1,duration:.6,ease:'expo.out',immediateRender:false}},{q(tl_)});")
    ctx.tw(f"tl.fromTo('#{cid} .lb',{{opacity:0,y:24}},{{opacity:1,y:0,duration:.3,ease:'back.out(1.8)',immediateRender:false}},{q(tl_ + .18)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-40,duration:.25,ease:'power2.in'}},{q(cend - .27)});")


def describe(g, beat):
    return (f'On “{g["on"]}” the {os.path.splitext(os.path.basename(g["src"]))[0].replace("-", " ")} screenshot rises, one region gets an outline, '
            f'a line draws to a lens that magnifies it, and the label "{g["label"]}" lands under the lens. It holds {beat["hold"]:.1f} s.')
