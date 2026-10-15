"""hosts: the two full-frame layouts other effects can run inside.

split   the frame splits in half: a brand plate on top carries the graphic, the speaker slides into the bottom half with the
        face centred there, and the spoken words run one at a time on the seam (split-screen uses this).
bubble  the speaker shrinks into a round bubble with a gold ring at the bottom; the graphic fills the page above it, the spoken
        words sit between them (face-bubble uses this).

An effect opens a host, then draws its own graphic inside host['region'] (x0, y0, x1, y1) between host['c0'] and host['c1'].
The host owns the footage moves, the plate, the seam words, and the busy/reserve bookkeeping. Not an effect itself."""
import math

SEAM = 960        # split line
FACE_Y = 1290     # face centre in the bottom half
RB = 165          # bubble radius
WFS = 54          # seam word size
PLATES = {'dark': '#1F1814', 'light': '#F2EEE8'}
T = {'split': (.45, .38), 'bubble': (.55, .45)}
# style.css is only loaded for the effect types a reel uses, so the host carries its own rules (emitted once per page)
CSS = ('.rk-host-plate{position:absolute;inset:0}'
       '.rk-host-ring{position:absolute;display:block;box-sizing:border-box;border-radius:50%;border:7px solid #D9B26A;box-shadow:0 18px 50px rgba(0,0,0,.35)}'
       '.rk-seam-words,.rk-bubble-words{position:relative;display:flex;align-items:center;justify-content:center}'
       '.rk-seam-words .w{position:absolute;padding:4px 22px;border-radius:14px;background:var(--c-ink);color:var(--c-text);font-family:var(--f-display);'
       'font-weight:800;letter-spacing:.02em;line-height:1.2;white-space:nowrap}'
       '.rk-bubble-words .w{position:absolute;color:var(--c-ink);font-family:var(--f-display);font-weight:800;letter-spacing:.03em;line-height:1.2;white-space:nowrap}'
       '.rk-bubble-words.dark .w{color:#F4EEE4}')


def _css(ctx):
    if getattr(ctx, '_host_css', False):
        return ''
    ctx._host_css = True
    return f'<style>{CSS}</style>'


def _cut_end(ctx, a, end):
    cuts = [s['frame'] / ctx.F for s in ctx.seg[1:] if a + .05 < s['frame'] / ctx.F < end + .05]
    return (min(cuts) - .05) if cuts else end


def _split_geo(L, ctx, a, end):
    fb = L.speaker_box(ctx, a, end)
    if not fb:
        return None
    ty = int(max(0, min(SEAM, FACE_Y - (fb[1] + fb[3]) / 2)))
    fz = [[f[0], f[1] + ty, f[2], f[3] + ty] for f in L.faces(ctx, a, end, n=8)]
    face_top = min(f[1] for f in fz) - L.MARGIN if fz else fb[1] + ty
    if face_top < SEAM - 40:
        return None
    wh = int(WFS * 1.5)
    wy = SEAM - wh // 2
    if wy + wh > face_top - 12:
        wy = int(face_top - 12 - wh)
    return {'ty': ty, 'fz': fz, 'wy': wy, 'wh': wh, 'region': (130, 260, 950, wy - 30)}


def _bubble_geo(L, ctx, a, end, corner):
    fz0 = L.faces(ctx, a, end, n=8)
    fb = L.speaker_box(ctx, a, end)
    if not fb or not fz0:
        return None
    fz0 = [f for f in fz0 if abs((f[0] + f[2]) / 2 - (fb[0] + fb[2]) / 2) < 260] or [fb]
    fcx, fcy = (fb[0] + fb[2]) / 2, (fb[1] + fb[3]) / 2 + .06 * (fb[3] - fb[1])
    rl = max(math.hypot(px - fcx, py - fcy) for f in fz0 for px in (f[0], f[2]) for py in (f[1], f[3])) * 1.08
    s = RB / rl
    cx, cy = (760, 1290) if corner != 'center' else (540, 1290)
    tx, ty = cx - s * fcx, cy - s * fcy
    fz = [[tx + s * f[0], ty + s * f[1], tx + s * f[2], ty + s * f[3]] for f in fz0]
    wh = int(WFS * 1.4)
    wy = int(cy - RB - 40 - wh)
    return {'fcx': fcx, 'fcy': fcy, 'rl': rl, 's': s, 'cx': cx, 'cy': cy, 'tx': tx, 'ty': ty, 'fz': fz, 'wy': wy, 'wh': wh,
            'region': (130, 260, 950, wy - 30)}


def pick(L, ctx, g, a, end, fit=None):
    """the host this graphic runs in: g['host'] when set, else split when the room above the face is under 40% of the frame,
    else float (None). fit=(w, h, scales) also sends auto to a host when that float design does not fit above the head.
    Returns 'split', 'bubble' or None."""
    want = g.get('host', 'auto')
    if want in ('float', None):
        return None
    if want in ('split', 'bubble'):
        return want
    fz = L.faces(ctx, a, end)
    if not fz:
        return None
    ftop = min(f[1] for f in fz)
    if ftop >= .4 * 1920 and (not fit or L.above_head(ctx, 'host check', fit[0], fit[1], a, end, scales=fit[2], fallback=False)):
        return None
    if _split_geo(L, ctx, a, end):
        return 'split'
    if _bubble_geo(L, ctx, a, end, 'right'):
        return 'bubble'
    return None


def open(L, ctx, g, kind, a, end, what):
    """opens the host over [a, end] and returns {kind, region, c0, c1, end, fz}. The graphic should be fully on screen
    from c0 and gone by c1 (fade out before c1)."""
    t_in, t_out = T[kind]
    e2 = _cut_end(ctx, a, end)
    if e2 < end:
        ctx.note(f'{what} on {g["on"]!r} shortened to end before the shot cut at {e2 + .05:.2f} s')
        end = e2
    if end - a < t_in + t_out + .8:
        ctx.fail(f'{what} on {g["on"]!r}: {end - a:.2f} s is too short for the {kind} layout (a shot cut or the next graphic is close)')
    geo = _split_geo(L, ctx, a, end) if kind == 'split' else _bubble_geo(L, ctx, a, end, g.get('corner', 'right'))
    if not geo:
        ctx.fail(f'{what} on {g["on"]!r}: the face does not fit the {kind} layout; try host "bubble", "float", or a tighter shot')
    plate = PLATES.get(g.get('plate', 'light' if kind == 'split' else 'dark'), PLATES['light'])
    dark = plate == PLATES['dark']
    q = ctx.q
    s0, s1 = a + t_in, end - t_out
    ctx._uid += 1
    wrap = f'host{ctx._uid}'
    if kind == 'split':
        ty = geo['ty']
        ctx.clip(ctx.front, a, end, f'{_css(ctx)}<div class="rk-host-plate"></div>',
                 f'position:absolute;left:0;top:0;width:1080px;height:{SEAM}px;background:{plate};'
                 f'border-bottom:4px solid var(--c-accent);box-sizing:border-box;clip-path:inset(0px 0px {SEAM}px 0px);', wrap)
        ctx.tw(f"tl.fromTo('.{wrap}',{{clipPath:'inset(0px 0px {SEAM}px 0px)'}},{{clipPath:'inset(0px 0px 0px 0px)',duration:{t_in},ease:'power3.inOut',immediateRender:false}},{q(a)});")
        ctx.tw(f"tl.to('.{wrap}',{{clipPath:'inset(0px 0px {SEAM}px 0px)',duration:{t_out},ease:'power3.inOut'}},{q(s1)});")
        for el in ('#bgv', '#cutwrap') if ctx.has_cut else ('#bgv',):
            ctx.tw(f"tl.fromTo('{el}',{{y:0,transformOrigin:'0px 0px',clipPath:'inset(0px 0px 0px 0px)'}},"
                   f"{{y:{ty},clipPath:'inset({SEAM - ty}px 0px 0px 0px)',duration:{t_in},ease:'power3.inOut',immediateRender:false}},{q(a)});")
            ctx.tw(f"tl.to('{el}',{{y:0,clipPath:'inset(0px 0px 0px 0px)',duration:{t_out},ease:'power3.inOut'}},{q(s1)});")
        L.reserve(ctx, (0, 0, 1080, SEAM), a, end)
        wcls = 'rk-seam-words'
    else:
        G = geo
        ring = (f'<i class="rk-host-ring" style="left:{G["cx"] - RB - 7}px;top:{G["cy"] - RB - 7}px;'
                f'width:{2 * RB + 14}px;height:{2 * RB + 14}px"></i>')
        ctx.clip(ctx.front, a, end, _css(ctx) + ring, 'position:absolute;inset:0;', wrap)
        ctx.tw(f"tl.set('#root',{{backgroundColor:'{plate}'}},{q(a)});")
        ctx.tw(f"tl.set('#root',{{backgroundColor:'#000000'}},{q(end)});")
        for el in ('#bgv', '#cutwrap') if ctx.has_cut else ('#bgv',):
            ctx.tw(f"tl.fromTo('{el}',{{x:0,y:0,scale:1,transformOrigin:'0px 0px',clipPath:'circle(2300px at {G['fcx']:.0f}px {G['fcy']:.0f}px)'}},"
                   f"{{x:{G['tx']:.1f},y:{G['ty']:.1f},scale:{G['s']:.4f},clipPath:'circle({G['rl']:.0f}px at {G['fcx']:.0f}px {G['fcy']:.0f}px)',"
                   f"duration:{t_in},ease:'power3.inOut',immediateRender:false}},{q(a)});")
            ctx.tw(f"tl.to('{el}',{{x:0,y:0,scale:1,clipPath:'circle(2300px at {G['fcx']:.0f}px {G['fcy']:.0f}px)',duration:{t_out},ease:'power3.inOut'}},{q(s1)});")
        ctx.tw(f"gsap.set('.{wrap} .rk-host-ring',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('.{wrap} .rk-host-ring',{{opacity:0,scale:1.25}},{{opacity:1,scale:1,duration:.3,ease:'back.out(2)',immediateRender:false}},{q(s0 - .04)});")
        ctx.tw(f"tl.to('.{wrap} .rk-host-ring',{{opacity:0,duration:.12}},{q(s1)});")
        L.reserve(ctx, (0, 0, 1080, 1470), a, end)
        wcls = 'rk-bubble-words' + (' dark' if dark else '')
    # the spoken words, one at a time on the seam / above the bubble
    ws = [w for w in ctx.words if s0 - .3 <= w['start'] < s1 - .25] if g.get('words', True) is not False else []
    if ws:
        spans = ''.join(f'<span class="w w{k}">{ctx.esc(w["text"].strip(".,!?;:").upper())}</span>' for k, w in enumerate(ws))
        cid = ctx.clip(ctx.front, s0, s1, f'<div class="{wcls}" style="font-size:{WFS}px;height:{geo["wh"]}px">{spans}</div>',
                       f'position:absolute;left:90px;right:130px;top:{geo["wy"]}px;')
        ctx.tw(f"gsap.set('#{cid} .w',{{opacity:0}});")
        for k, w in enumerate(ws):
            t0 = max(s0, w['start'])
            t1 = min(s1 - .2, ws[k + 1]['start'] if k + 1 < len(ws) else s1 - .2)
            if t1 - t0 < .06:
                continue
            ctx.tw(f"tl.set('#{cid} .w{k}',{{opacity:1}},{q(t0)});")
            ctx.tw(f"tl.set('#{cid} .w{k}',{{opacity:0}},{q(t1)});")
    ctx.busy.append((a, end))
    ctx.lowbusy.append((a, end))
    ctx.topbusy.append((a, end))
    return {'kind': kind, 'region': geo['region'], 'c0': s0, 'c1': s1, 'a': a, 'end': end, 'fz': geo['fz'], 'dark': dark}


def place(L, ctx, h, w, hh, what):
    """(x, y, scale) that fits a w x hh design centred in the host region (scaled up or down), checked clear of the face."""
    x0, y0, x1, y1 = h['region']
    sc = min((x1 - x0) / w, (y1 - y0) / hh)
    x, y = x0 + ((x1 - x0) - w * sc) / 2, y0 + ((y1 - y0) - hh * sc) / 2
    box = (x, y, x + w * sc, y + hh * sc)
    if L.face_share(box, h['fz']) > .002 or L.unsafe(box):
        ctx.fail(f'{what}: the graphic does not fit the {h["kind"]} layout clear of the face')
    return int(x), int(y), sc


def shot(ctx, c, w, kmax):
    """(html, w, h) of one screenshot in a browser frame w px wide, never taller than kmax."""
    url = ctx.asset(c['src'])
    W, H = ctx.image_size(url)
    x0, y0, cw, ch = c.get('crop') or [0, 0, W, H]
    bar = 44
    ih = w * ch / cw
    if ih + bar > kmax:
        w = int((kmax - bar) * cw / ch)
        ih = w * ch / cw
    img = (f'<div class="pg" style="width:{w}px;height:{ih:.0f}px;background-image:url({url});background-size:{W * w / cw:.0f}px auto;'
           f'background-position:-{x0 * w / cw:.0f}px -{y0 * w / cw:.0f}px"></div>')
    return f'<div class="bar"><i></i><i></i><i></i></div>{img}', w, int(ih + bar)
