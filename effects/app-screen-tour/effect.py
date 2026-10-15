"""A clean front-on phone steps through 2 to 4 app screens, each on its phrase. A touch dot taps the control that leads to the next screen."""
import os

META = {
    'id': 'app-screen-tour', 'name': 'App screen tour', 'category': 'ui',
    'when': 'The speaker walks through using an app: open it, tap, get the result. Each screen lands on the words that describe it.',
    'never': 'Never a screen nobody describes. Never more than four screens. Never stacked with a behind-the-head word (in a split the speaker moves into a card).',
    'params': {'on': 'phrase for the first screen', 'app': 'app name, shown small at the top of built screens',
               'screens': '2-4 of {"on", "title", "kicker", "rows": [text or {"text", "meta", "done"}], "big", "button", "tap": row index or "button"}, '
                          'or {"on", "src": image file, "tap_xy": [x, y] as 0-1 of the image}. Every screen after the first needs its own "on"',
               'stage': 'auto (default: float clear of faces, else split), float or split', 'side': 'speaker card side in a split: right (default) or left',
               'colors': 'split background colors, one hop per screen, default ["accent", "accent2", "ink"]',
               'hold': 'seconds after the last screen, default 1.6', 'until': 'close before this phrase', 'captions': '"keep" (default) or "pause"'},
    'sfx': ['tap'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

PW, PH, BZ = 400, 830, 14   # phone, px (front-on, flat)
PAD = 22

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


def _rows(r):
    return [x if isinstance(x, dict) else {'text': str(x)} for x in r]


def _screen(ctx, g, sc, k):
    """(html, has_tap) for one screen; built screens are fitted so nothing overflows the glass."""
    sw, sh = PW - 2 * BZ, PH - 2 * BZ
    inner = sw - 2 * PAD
    tap = sc.get('tap')
    hide = ' style="opacity:0"' if k else ''
    if sc.get('src'):
        url = ctx.asset(sc['src'])
        tx = ''
        if sc.get('tap_xy'):
            fx, fy = [float(v) for v in sc['tap_xy']]
            tx = _tap_html(f'left:{fx * 100:.1f}%;top:{fy * 100:.1f}%')
        return f'<div class="scr s{k} pic"{hide}><div class="im" style="background-image:url({url})"></div>{tx}</div>', bool(tx)
    title, rows, big, btn = sc.get('title', ''), _rows(sc.get('rows', [])), sc.get('big'), sc.get('button')
    what = f'app-screen-tour screen {k + 1}'
    if not (title or rows or big):
        ctx.fail(f'{what} on {sc.get("on", g["on"])!r} is empty; give it a title, rows or a big number (or a src image)')
    if len(rows) > 5:
        ctx.fail(f'{what} has {len(rows)} rows; four reads on a phone, five at most')
    kicker = sc.get('kicker', g.get('app', ''))
    tfs = _fit(ctx, f'{what} title', [title], inner, 60, 36, 1, .62) if title else 0
    mw = max([len(r.get('meta', '')) * 28 * .6 + 14 for r in rows] or [0])
    rw = inner - 32 - 44 - mw   # row padding, check circle and gap, meta
    texts = [r['text'] for r in rows]
    one = next((fs for fs in range(32, 27, -2) if _lines(texts, rw, fs) <= 1), None)   # one line per row reads fastest
    rfs = (one or _fit(ctx, f'{what} rows', texts, rw, 32, 28, 2)) if rows else 0
    bfs = _fit(ctx, f'{what} big', [big], inner, 150, 60, 1, .62) if big else 0
    if btn:
        _fit(ctx, f'{what} button', [btn], inner - 60, 32, 32, 1)
    h = 70 + (40 if kicker else 0) + (tfs * 1.2 + 22 if title else 0) + sum(36 + len(_wrap(r['text'], rw, rfs)) * rfs * 1.3 + 14 for r in rows)
    h += (bfs * 1.1 + 30 if big else 0) + (88 + 24 if btn else 0) + 30
    if h > sh:
        ctx.fail(f'{what} needs {h:.0f}px of a {sh}px screen; cut a row or shorten the text')
    if tap is not None and tap != 'button' and not (isinstance(tap, int) and 0 <= tap < len(rows)):
        ctx.fail(f'{what}: tap must be "button" or a row index 0-{len(rows) - 1} (got {tap!r})')
    if tap == 'button' and not btn:
        ctx.fail(f'{what}: tap is "button" but the screen has no button')
    out = [f'<div class="scr s{k}"{hide}><i class="bt"></i>']
    if kicker:
        out.append(f'<div class="kk">{ctx.esc(kicker)}</div>')
    if title:
        out.append(f'<div class="tt" style="font-size:{tfs}px">{ctx.esc(title)}</div>')
    if big:
        out.append(f'<div class="big" style="font-size:{bfs}px">{ctx.esc(big)}</div>')
    for j, r in enumerate(rows):
        tg = tap == j
        meta = f'<span class="mt">{ctx.esc(r["meta"])}</span>' if r.get('meta') else ''
        out.append(f'<div class="row{" done" if r.get("done") else ""}{" tg" if tg else ""}"><i class="hl"></i><i class="ck"><i class="ckf"></i></i>'
                   f'<span class="tx" style="font-size:{rfs}px">{ctx.esc(r["text"])}</span>{meta}{_tap_html("left:72%;top:50%") if tg else ""}</div>')
    out.append('<div class="sp"></div>')
    if btn:
        tg = tap == 'button'
        out.append(f'<div class="btn{" tg" if tg else ""}"><i class="hl"></i><span>{ctx.esc(btn)}</span>{_tap_html("left:50%;top:50%") if tg else ""}</div>')
    out.append('</div>')
    return ''.join(out), tap is not None


def build(g, ctx):
    _need(ctx, g, 'screens')
    scr = g['screens']
    if not 2 <= len(scr) <= 4:
        ctx.fail(f'app-screen-tour on {g["on"]!r} shows 2 to 4 screens (got {len(scr)})')
    for k, s in enumerate(scr[1:], 1):
        if not s.get('on'):
            ctx.fail(f'app-screen-tour screen {k + 1} needs its own "on" phrase (each screen lands on its words)')
    ts = _times(ctx, g, scr, 1.0, .05)
    for k in range(1, len(ts)):
        if ts[k] - ts[k - 1] < .8:
            ctx.fail(f'app-screen-tour screens {k} and {k + 1} are {ts[k] - ts[k - 1]:.2f} s apart; each needs 0.8 s or more')
    a, end = _window(ctx, g, 1.6, ts[-1])
    pause = g.get('captions', 'keep') == 'pause'
    built = [_screen(ctx, g, s, k) for k, s in enumerate(scr)]
    mode = _place_or_split(ctx, g, 'app-screen-tour', PW, PH, a, end, None, pause, 1.0)   # a shrunk phone is unreadable: full size or split
    t_on = a + .32 if mode[0] == 'split' else a
    taps, sws = [], []
    for k in range(1, len(ts)):
        tt = max(ts[k - 1] + (.75 if k == 1 else .5), ts[k] - .36) if built[k - 1][1] else None
        sw_t = max((tt + .24) if tt else ts[k] - .06, ts[k] - .06)
        taps.append(tt)
        sws.append(sw_t)
    if mode[0] == 'split':
        reg, cend = _split(ctx, a - .05, end, g.get('side', 'right'), g.get('colors', ['accent', 'accent2', 'ink']), sws)
        rw, rh = reg[2] - reg[0], reg[3] - reg[1]
        sc = min(1.15, rw / PW, rh / PH)
        x, y = reg[0] + (rw - PW * sc) / 2, reg[1] + (rh - PH * sc) / 2
        if pause:
            ctx.busy.append((a, end))
    else:
        _, x, y, sc = mode
        cend = end
        _claim(ctx, x, y, PW * sc, PH * sc, a, end, pause)
    last_tap = None
    if built[-1][1] and ts[-1] + .9 < cend - .45:
        last_tap = ts[-1] + .9
    html = (f'<div class="fx-app-screen-tour" style="width:{PW}px;height:{PH}px;padding:{BZ}px"><div class="gl">'
            + ''.join(h for h, _ in built) + '</div><i class="isl"></i></div>')
    cid = _zclip(ctx, sc, t_on, cend, html, f'position:absolute;left:{x:.0f}px;top:{y:.0f}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:170,rotation:-5,scale:.9}},{{opacity:1,y:0,rotation:0,scale:1,duration:.62,ease:'back.out(1.4)',immediateRender:false}},{ctx.q(t_on)});")
    for k in range(1, len(ts)):
        tt, sw_t = taps[k - 1], sws[k - 1]
        prev, cur = f'#{cid} .s{k - 1}', f'#{cid} .s{k}'
        if tt is not None:
            _tap_anim(ctx, f'{prev} .tp0', tt)
            ctx.tw(f"tl.fromTo('{prev} .tg .hl',{{opacity:0}},{{opacity:1,duration:.08,immediateRender:false}},{ctx.q(tt)});")
            ctx.tw(f"tl.fromTo('{prev} .tg .ckf',{{scale:0}},{{scale:1,duration:.22,ease:'back.out(2.5)',immediateRender:false}},{ctx.q(tt)});")
        ctx.tw(f"tl.fromTo('{prev}',{{opacity:1,x:0}},{{opacity:0,x:-40,duration:.22,ease:'power2.in',immediateRender:false}},{ctx.q(sw_t)});")
        ctx.tw(f"tl.fromTo('{cur}',{{opacity:0,x:46,scale:.97}},{{opacity:1,x:0,scale:1,duration:.42,ease:'expo.out',immediateRender:false}},{ctx.q(sw_t)});")
        ctx.tw(f"tl.fromTo('#{cid} .gl',{{scale:1}},{{scale:1.025,duration:.1,yoyo:true,repeat:1,ease:'power1.out',immediateRender:false}},{ctx.q(sw_t)});")
    if last_tap:
        lst = f'#{cid} .s{len(ts) - 1}'
        _tap_anim(ctx, f'{lst} .tp0', last_tap)
        ctx.tw(f"tl.fromTo('{lst} .tg .hl',{{opacity:0}},{{opacity:1,duration:.08,immediateRender:false}},{ctx.q(last_tap)});")
        ctx.tw(f"tl.fromTo('{lst} .tg .ckf',{{scale:0}},{{scale:1,duration:.22,ease:'back.out(2.5)',immediateRender:false}},{ctx.q(last_tap)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-50,scale:.96,duration:.25,ease:'power2.in'}},{ctx.q(cend - .27)});")


def describe(g, beat):
    names = [s.get('title') or os.path.splitext(os.path.basename(s.get('src', 'screen')))[0] for s in g['screens']]
    app = g.get('app') or 'an app'
    return (f'On “{g["on"]}” a phone shows {app} and steps through {len(names)} screens ({" > ".join(names)}), each on its phrase; '
            f'a touch dot taps the control that leads to the next one. It holds {beat["hold"]:.1f} s.')
