"""A live voice waveform drawn from the clip's own audio, with the speaker's words landing big, each on its own timing (voice features)."""
import array, os, subprocess

META = {
    'id': 'waveform', 'name': 'Voice waveform', 'category': 'ui',
    'when': 'A voice feature: the speaker talks to an app, dictates, records a note. The words she says become the transcript on screen.',
    'never': 'Never over a line that is not the voice input itself. Never over 6 seconds (it replaces the captions).',
    'params': {'on': 'first word of the voice input', 'until': 'phrase after the input ends (the window closes before it), optional',
               'label': 'recorder label, default "Recording"', 'hold': 'seconds, default 3.0 (max 6)', 'size': 'max word size in px, default 104'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

BAR, GAP, RATE = 8, 6, 15   # bar width, gap (px) and bars per second

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


def _levels(ctx, t0, t1):
    """loudness per 1/RATE s of the clip audio between t0 and t1, 0-1 (95th percentile = 1)."""
    raw = os.path.join(ctx.work, 'wave.raw')
    s0 = max(0.0, t0)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{max(.1, t1 - s0):.3f}', '-i', os.path.join(ctx.D, 'assets', 'aroll.mp4'),
                    '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', raw], check=True)
    pcm = array.array('h')
    with open(raw, 'rb') as fh:
        pcm.frombytes(fh.read())
    n = 8000 // RATE
    lv = [0.0] * int(round((s0 - t0) * RATE))   # before the clip starts: silence
    for k in range(0, len(pcm) - n + 1, n):
        ch = pcm[k:k + n]
        lv.append((sum(v * v for v in ch) / n) ** .5)
    top = sorted(lv)[int(len(lv) * .95)] if lv else 1
    return [min(1.0, v / max(top, 1)) ** .7 for v in lv]


def build(g, ctx):
    a, end = _window(ctx, g, min(6.0, float(g.get('hold', 3.0))))
    end = min(end, a + 6.0)
    words = [w for w in ctx.capwords if a - .05 <= w['start'] < end - .35 and ctx.disp(w['text'])]
    if len(words) < 2:
        ctx.fail(f'waveform on {g["on"]!r} has under two spoken words in its window; it shows the voice input, so give it a spoken line')
    # the big words: pages of up to two lines, each word lands on its own start time
    fs = int(g.get('size', 104))
    texts = [ctx.disp(w['text']) for w in words]
    TW = 800
    while fs > 56 and max(len(t) for t in texts) * fs * .6 > TW:
        fs -= 4
    pages, cur, line, nl = [], [], '', 1
    for w, t in zip(words, texts):
        nxt = f'{line} {t}'.strip()
        if line and len(nxt) * fs * .6 > TW:
            nl += 1
            line = t
            if nl > 2:
                pages.append(cur)
                cur, nl = [], 1
        else:
            line = nxt
        cur.append((w, t))
    if cur:
        pages.append(cur)
    WH = int(fs * 1.05 * 2 + 10)
    CH = 150
    # place the card low (under the chin), the words wherever they clear the faces and the card
    cx, cy = _spot(ctx, 'waveform card', 860, CH, a, end, [(90, y) for y in range(1470 - CH, 239, -30)], pause=True, quiet=True)
    if ctx.face_hit(a, end, cx, cy, cx + 860, cy + CH) > .02:
        ctx.warn('waveform card still touches a face')
    cands = [(90, y) for y in range(250, 1471 - WH, 20) if y + WH < cy - 16 or y > cy + CH + 16]
    if not cands:
        ctx.fail('waveform: no room for the words beside the card; shorten the window or lower size')
    wx, wy = _spot(ctx, 'waveform words', 860, WH, a, end, cands, (540, cy - WH / 2), pause=True, quiet=True)
    if ctx.face_hit(a, end, wx, wy, wx + 860, wy + WH) > .02:
        for f in (.85, .72):
            fs2 = int(fs * f)
            WH2 = int(fs2 * 1.05 * 2 + 10)
            c2 = [(90, y) for y in range(250, 1471 - WH2, 20) if y + WH2 < cy - 16 or y > cy + CH + 16]
            x2, y2 = _spot(ctx, 'waveform words', 860, WH2, a, end, c2, None, True, True) if c2 else (wx, wy)
            if c2 and ctx.face_hit(a, end, x2, y2, x2 + 860, y2 + WH2) <= .02:
                fs, WH, wx, wy = fs2, WH2, x2, y2
                break
        else:
            ctx.warn('waveform words still touch a face')
    ctx.busy.append((a, end))   # the transcript is the caption here
    _claim(ctx, 90, min(cy, wy), 860, max(cy + CH, wy + WH) - min(cy, wy), a, end, True)
    # the card: recording dot, label, a strip of real levels scrolling right to left, a timer that steps each second
    lv_t0 = a - 4.0
    lv = _levels(ctx, lv_t0, end)
    BW = 860 - 2 * 34 - 40 - 150
    step = BAR + GAP
    hh = CH - 66
    bars = ''.join(f'<rect x="{k * step}" y="{(CH - (10 + hh * v)) / 2:.0f}" width="{BAR}" height="{10 + hh * v:.0f}" rx="4"/>' for k, v in enumerate(lv))
    dur = end - a
    secs = int(dur) + 1
    timer = ''.join(f'<span class="s{k}">0:{k:02d}</span>' for k in range(secs + 1))
    label = g.get('label', 'Recording')
    card = (f'<div class="fx-waveform card" style="width:860px;height:{CH}px"><i class="dot"></i>'
            f'<div class="wv" style="width:{BW}px"><svg class="st" width="{BW}" height="{CH}" viewBox="0 0 {BW} {CH}" preserveAspectRatio="none">{bars}</svg></div>'
            f'<div class="rt"><small>{ctx.esc(label)}</small><b>{timer}</b></div></div>')
    kid = ctx.clip(ctx.front, a, end, card, f'position:absolute;left:{cx}px;top:{cy}px;')
    q = ctx.q
    x0 = (a - lv_t0) * RATE * step - BW   # the viewBox scrolls: the bar for time T sits at the right edge at T
    x1 = (end - lv_t0) * RATE * step - BW
    ctx.tw(f"tl.fromTo('#{kid}',{{opacity:0,y:60,scale:.9}},{{opacity:1,y:0,scale:1,duration:.4,ease:'back.out(1.6)',immediateRender:false}},{q(a - .12)});")
    ctx.tw(f"tl.fromTo('#{kid} .st',{{attr:{{viewBox:'{x0:.0f} 0 {BW} {CH}'}}}},{{attr:{{viewBox:'{x1:.0f} 0 {BW} {CH}'}},duration:{dur:.3f},ease:'none',immediateRender:false}},{q(a)});")
    for k in range(secs + 1):
        if k:
            ctx.tw(f"tl.fromTo('#{kid} .s{k}',{{opacity:0}},{{opacity:1,duration:.02,immediateRender:false}},{q(a + k)});")
            ctx.tw(f"tl.fromTo('#{kid} .s{k - 1}',{{opacity:1}},{{opacity:0,duration:.02,immediateRender:false}},{q(a + k)});")
    ctx.tw(f"tl.to('#{kid}',{{opacity:0,y:30,duration:.2,ease:'power2.in'}},{q(end - .2)});")
    # the words
    html = [f'<div class="fx-waveform words" style="width:860px;height:{WH}px;font-size:{fs}px">']
    for p, pg in enumerate(pages):
        html.append(f'<div class="pg p{p}">' + ' '.join(f'<span class="w w{p}_{j}">{ctx.esc(t)}</span>' for j, (_, t) in enumerate(pg)) + '</div>')
    html.append('</div>')
    wid = ctx.clip(ctx.front, a, end, ''.join(html), f'position:absolute;left:{wx}px;top:{wy}px;')
    for p, pg in enumerate(pages):
        for j, (w, _) in enumerate(pg):
            ctx.tw(f"tl.fromTo('#{wid} .w{p}_{j}',{{opacity:0,y:fs*.35,scale:1.25}},{{opacity:1,y:0,scale:1,duration:.22,ease:'back.out(2.4)',immediateRender:false}},{q(max(a, w['start'] - .03))});".replace('fs*.35', f'{fs * .35:.0f}'))
        if p + 1 < len(pages):
            t = pages[p + 1][0][0]['start'] - .06
            ctx.tw(f"tl.fromTo('#{wid} .p{p}',{{opacity:1,y:0}},{{opacity:0,y:-{fs * .4:.0f},duration:.14,ease:'power2.in',immediateRender:false}},{q(t - .1)});")
    ctx.tw(f"tl.to('#{wid}',{{opacity:0,y:-30,duration:.2,ease:'power2.in'}},{q(end - .2)});")


def describe(g, beat):
    return (f'From “{g["on"]}” a {g.get("label", "Recording").lower()} card shows the live waveform of the clip audio and a timer stepping '
            f'each second, while each spoken word lands big on its own timing. Captions pause. It holds {beat["hold"]:.1f} s.')
