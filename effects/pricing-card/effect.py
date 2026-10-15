"""A plan card with 2 or 3 tiers. A tap flips the billing toggle and every price changes as one discrete state; a second tap picks the tier."""

META = {
    'id': 'pricing-card', 'name': 'Pricing card', 'category': 'ui',
    'when': 'The speaker names a price, a plan, or what the yearly plan saves. The prices on screen are the real ones.',
    'never': 'Never invented prices. Never a rolling counter: a price changes as a whole new state. Never more than three tiers.',
    'params': {'on': 'phrase that opens it', 'title': 'card title, default "Choose a plan"',
               'tiers': '2-3 of {"name", "price", "alt" (price after the toggle), "sub"}', 'per': 'unit after each price, default "/mo"',
               'toggle': '{"on", "labels": ["Monthly", "Yearly"], "badge": "-20%"}: optional, swaps every price to its alt',
               'pick': '{"on", "index"}: optional, taps that tier', 'button': 'optional button label, e.g. "Continue"',
               'stage': 'auto (default), float or split', 'side': 'speaker card side in a split: right (default) or left',
               'colors': 'split background colors, default ["accent2"]', 'hold': 'seconds after the last tap, default 1.5',
               'until': 'close before this phrase', 'captions': '"keep" (default) or "pause"'},
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


def _card(ctx, g, W):
    """(html, height) of the card laid out at width W."""
    pad = 30 if W < 560 else 36
    tiers, per = g['tiers'], g.get('per', '/mo')
    tg = g.get('toggle')
    title = g.get('title', 'Choose a plan')
    inner = W - 2 * pad
    tfs = _fit(ctx, 'pricing-card title', [title], inner, 46, 32, 1, .6)
    prices = [str(t['price']) for t in tiers] + [str(t.get('alt', '')) for t in tiers if tg]
    pfs = 48 if W >= 560 else 42
    pw = max(len(p) for p in prices) * pfs * .6 + 4
    perw = len(per) * 28 * .56 + 6
    nw = inner - 40 - 36 - 16 - pw - perw   # tier padding, radio and gap, price
    if nw < 110:
        ctx.fail(f'pricing-card: prices like {max(prices, key=len)!r} leave no room for the tier names at {W}px; shorten them')
    nfs = _fit(ctx, 'pricing-card tier names', [t['name'] for t in tiers], nw, 38, 28, 1, .6)
    subs = [t.get('sub', '') for t in tiers]
    sfs = _fit(ctx, 'pricing-card tier subs', subs, nw, 28, 28, 2) if any(subs) else 0
    out = [f'<div class="fx-pricing-card" style="width:{W}px;padding:{pad}px">', f'<div class="hd" style="font-size:{tfs}px">{ctx.esc(title)}</div>']
    H = 2 * pad + tfs * 1.2 + 22
    if tg:
        l0, l1 = (tg.get('labels') or ['Monthly', 'Yearly'])[:2]
        badge = f' <b class="sv">{ctx.esc(tg["badge"])}</b>' if tg.get('badge') else ''
        _fit(ctx, 'pricing-card toggle', [l0, l1 + (' ' + tg['badge'] if tg.get('badge') else '')], inner / 2 - 12, 30, 28, 1, .52)
        out.append(f'<div class="tg"><i class="kn"></i><span class="o0">{ctx.esc(l0)}</span><span class="o1">{ctx.esc(l1)}{badge}'
                   f'{_tap_html("left:50%;top:50%", 0)}</span></div>')
        H += 76 + 24
    pick = (g.get('pick') or {}).get('index')
    if pick is not None and not (isinstance(pick, int) and 0 <= pick < len(tiers)):
        ctx.fail(f'pricing-card pick index must be 0-{len(tiers) - 1} (got {pick!r})')
    for j, t in enumerate(tiers):
        alt = f'<span class="p1">{ctx.esc(t["alt"])}</span>' if tg else ''
        sub = f'<small style="font-size:{sfs}px">{ctx.esc(t["sub"])}</small>' if t.get('sub') else ''
        tap = _tap_html('left:45%;top:50%', 1) if j == pick else ''
        out.append(f'<div class="tr r{j}{" pk" if j == pick else ""}"><i class="hl"></i><i class="rd"><i class="rdf"></i></i>'
                   f'<div class="nm"><b style="font-size:{nfs}px">{ctx.esc(t["name"])}</b>{sub}</div>'
                   f'<div class="pr"><span class="pv" style="width:{pw:.0f}px;font-size:{pfs}px"><span class="p0">{ctx.esc(t["price"])}</span>{alt}</span>'
                   f'<small>{ctx.esc(per)}</small></div>{tap}</div>')
        H += 40 + max(nfs * 1.2 + (sfs * 1.35 * len(_wrap(t['sub'], nw, sfs)) if sub else 0), pfs * 1.1) + 14
    if g.get('button'):
        out.append(f'<div class="btn">{ctx.esc(g["button"])}</div>')
        H += 88 + 10
    out.append('</div>')
    return ''.join(out), int(H)


def build(g, ctx):
    _need(ctx, g, 'tiers')
    tiers = g['tiers']
    if not 2 <= len(tiers) <= 3:
        ctx.fail(f'pricing-card on {g["on"]!r} shows 2 or 3 tiers (got {len(tiers)})')
    tg, pk = g.get('toggle'), g.get('pick')
    if not tg and not pk:
        ctx.fail(f'pricing-card on {g["on"]!r} needs a toggle or a pick: a price card where nothing changes is a still image')
    if tg and not all(t.get('alt') for t in tiers):
        ctx.fail('pricing-card: a toggle needs an "alt" price on every tier')
    a0 = ctx.at(g['on'])[0]
    events = []
    if tg:
        events.append(('tg', max(ctx.at(tg['on'], a0 - .2)[0] if tg.get('on') else a0 + .9, a0 + .55)))
    if pk:
        t = ctx.at(pk['on'], a0 - .2)[0] if pk.get('on') else (events[-1][1] if events else a0) + .9
        events.append(('pk', max(t, (events[-1][1] + .6) if events else a0 + .55)))
    a, end = _window(ctx, g, 1.5, max(t for _, t in events))
    pause = g.get('captions', 'keep') == 'pause'
    html, H = _card(ctx, g, 640)
    mode = _place_or_split(ctx, g, 'pricing-card', 640, H, a, end, None, pause)
    t_on = a + .3 if mode[0] == 'split' else a
    if mode[0] == 'split':
        reg, cend = _split(ctx, a - .05, end, g.get('side', 'right'), g.get('colors', ['accent2']))
        rw, rh = reg[2] - reg[0], reg[3] - reg[1]
        W = min(640, rw)
        html, H = _card(ctx, g, W)
        sc = min(1.0, rh / H)
        x, y = reg[0] + (rw - W * sc) / 2, reg[1] + (rh - H * sc) / 2
        if pause:
            ctx.busy.append((a, end))
    else:
        _, x, y, sc = mode
        cend = end
        _claim(ctx, x, y, 640 * sc, H * sc, a, end, pause)
    cid = _zclip(ctx, sc, t_on, cend, html, f'position:absolute;left:{x:.0f}px;top:{y:.0f}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:140,rotation:3,scale:.92}},{{opacity:1,y:0,rotation:0,scale:1,duration:.55,ease:'back.out(1.5)',immediateRender:false}},{ctx.q(t_on)});")
    for kind, t in events:
        t = max(t, t_on + .5)
        if kind == 'tg':
            _tap_anim(ctx, f'#{cid} .tp0', t)
            ctx.tw(f"tl.fromTo('#{cid} .kn',{{xPercent:0}},{{xPercent:100,duration:.32,ease:'back.out(1.6)',immediateRender:false}},{ctx.q(t)});")
            ctx.tw(f"tl.fromTo('#{cid} .p0',{{opacity:1,y:0}},{{opacity:0,y:-34,duration:.14,ease:'power2.in',immediateRender:false}},{ctx.q(t + .04)});")
            ctx.tw(f"tl.fromTo('#{cid} .p1',{{opacity:0,y:34}},{{opacity:1,y:0,duration:.26,ease:'back.out(2)',immediateRender:false}},{ctx.q(t + .12)});")
            ctx.tw(f"tl.fromTo('#{cid} .sv',{{scale:1}},{{scale:1.18,duration:.12,yoyo:true,repeat:1,ease:'power1.out',immediateRender:false}},{ctx.q(t + .12)});")
        else:
            _tap_anim(ctx, f'#{cid} .tp1', t)
            ctx.tw(f"tl.fromTo('#{cid} .pk .hl',{{opacity:0}},{{opacity:1,duration:.08,immediateRender:false}},{ctx.q(t)});")
            ctx.tw(f"tl.fromTo('#{cid} .pk .rdf',{{scale:0}},{{scale:1,duration:.24,ease:'back.out(2.5)',immediateRender:false}},{ctx.q(t)});")
            ctx.tw(f"tl.fromTo('#{cid} .pk',{{scale:1}},{{scale:1.035,duration:.12,yoyo:true,repeat:1,ease:'power1.out',immediateRender:false}},{ctx.q(t)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-50,scale:.96,duration:.25,ease:'power2.in'}},{ctx.q(cend - .27)});")


def describe(g, beat):
    tiers = ', '.join(f'{t["name"]} {t["price"]}' + (f' (then {t["alt"]})' if g.get('toggle') else '') for t in g['tiers'])
    acts = []
    if g.get('toggle'):
        acts.append(f'a tap flips the toggle to {(g["toggle"].get("labels") or ["", "Yearly"])[1]} and the prices change')
    if g.get('pick'):
        acts.append(f'a tap picks {g["tiers"][g["pick"]["index"]]["name"]}')
    return f'On “{g["on"]}” a plan card shows {tiers}; ' + ', then '.join(acts) + f'. It holds {beat["hold"]:.1f} s.'
