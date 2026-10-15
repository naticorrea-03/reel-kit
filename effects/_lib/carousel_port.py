"""carousel_port: shared build for the four ported registry carousels (carousel-orbit, carousel-circle, carousel-vision,
carousel-path). Adapted from the HyperFrames registry (Copyright HeyGen, Apache-2.0); see carousel_rig.py for the change list.

Layout for 9:16: the rig's motion is scaled and centred on the speaker's head and drawn on the wall layer, so the head
sits in front of the carousel. Cards dim while the speaker covers them; labels show only on cards big enough to read and
not crossed by a bigger card.
"""
import math, os

FIT = 1500       # the registry's fitBox: a card's longest side at scale 1, in registry px
BASE = 320       # our tiles are built at this longest side and scaled by GSAP


def run(g, ctx, family, L, R, lo=6, hi=12):
    tiles = L.need_tiles(ctx, g, 'tiles', lo, hi)
    n = len(tiles)
    a, end = L.window(ctx, g, float(g.get('hold', 3.4)), min_after=2.0)
    T = L.frames(a, end)
    speed = float(g.get('speed', 1.0))
    pose = R.rig(family, n, speed)
    cam = R.PRESETS[family].get('cam', 5669.29)

    # ---- tile shapes: image tiles keep their aspect, word tiles are 4:5 ----
    shapes = []
    for t in tiles:
        if t.get('src'):
            w, h = ctx.image_size(ctx.asset(t['src']))
            ar = max(.5, min(1.6, w / h))
        else:
            ar = .8
        shapes.append((BASE * min(1, ar), BASE * min(1, 1 / ar)))

    # ---- fit the registry layout around the head ----
    track = L.face_track(ctx, a, end)
    raw = [pose(t - a) for t in T]

    def proj(p):
        f = cam / (cam + p['z']) if family in ('orbit', 'vision') else 1.0
        return p['x'] * f, p['y'] * f, p['scale'] * f
    xs = [proj(p)[0] for row in raw for p in row]
    ys = [proj(p)[1] for row in raw for p in row]
    smax = max(proj(p)[2] for row in raw for p in row)
    mnx, mny, mxx, mxy = min(xs), min(ys), max(xs), max(ys)
    heads = [h for h in (ctx.head_top(t) for t in (a, (a + end) / 2, end - .05)) if h is not None] if ctx.has_cut else []
    head = min(heads) if heads else 520
    fb = track((a + end) / 2) if track else [440, 520, 640, 780]
    fcx, fcy, fw, fh = (fb[0] + fb[2]) / 2, (fb[1] + fb[3]) / 2, fb[2] - fb[0], fb[3] - fb[1]
    user = float(g.get('size', 1.0))
    FACES = [L.all_faces(ctx, t) for t in T]
    ftop = min([f[1] for fz in FACES for f in fz] or [head])   # top of the highest face (padded) across the run
    # 9:16 re-layout: each family's motion is mapped into a portrait box around or above the head (non-uniform scale),
    # and card sizes keep the rig's depth gradient but never fall under a readable floor
    SIZE = {'orbit': 270, 'circle': 290, 'vision': 330, 'path': 290}[family] * user
    FLOOR = {'orbit': .45, 'circle': .5, 'vision': .6, 'path': .5}[family]

    def target(shrink, mode):
        cs = SIZE * (1 - (1 - shrink) * .5)   # when the layout has to shrink, cards shrink at half the rate (labels stay readable)
        if mode == 'above':        # in front, in the band above every face: the motion squashed into it, cards solid
            cs = min(cs, (ftop - 30 - L.SAFE[1] - 8) / 1.3)   # cards as tall as the band allows
            return 90 + cs * .55, L.SAFE[1] + 8 + cs * .62, 950 - cs * .55, max(L.SAFE[1] + 8 + cs * .62 + 40, ftop - 24 - cs * .62), cs
        if family == 'orbit':      # a sphere around the top of the head
            rx = max(fw / 2 + cs * .55, 300) * shrink
            return fcx - rx, fb[1] + .15 * fh - rx * 1.05, fcx + rx, fb[1] + .15 * fh + rx * 1.05, cs
        if family == 'circle':     # a tall loop around the head, centred above the eyes
            rx = max(fw / 2 + cs * .6, 300) * shrink
            return fcx - rx, fcy - .25 * fh - rx * 1.3, fcx + rx, fcy - .25 * fh + rx * 1.3, cs
        if family == 'vision':     # a wide ring in the band just behind the top of the head
            cy = head - cs * .3
            return 540 - 400 * shrink, cy - 70 * shrink, 540 + 400 * shrink, cy + 70 * shrink, cs
        top = head - cs * .55       # path: an arch over the head, shoulder to shoulder
        return fcx - 400 * shrink, top, fcx + 400 * shrink, fcy + .55 * fh, cs

    def layout(shrink, mode):
        X0, Y0, X1, Y1, cs = target(shrink, mode)
        # slide the box inside the safe zone (cards stay whole), never out of it
        padx, pady = cs * .55, cs * .62
        dx = max(0, L.SAFE[0] + padx - X0) - max(0, X1 - (L.SAFE[2] - padx))
        dy = max(0, L.SAFE[1] + 8 + pady - Y0) - max(0, Y1 - (L.SAFE[3] - 8 - pady))
        X0, X1, Y0, Y1 = X0 + dx, X1 + dx, Y0 + dy, Y1 + dy
        P = []
        for fi, row in enumerate(raw):
            t = T[fi] - a
            out = []
            for i, p in enumerate(row):
                x, y, s = proj(p)
                each = .45 / n
                st = i * each - .25
                e = 1 - (1 - L.clamp((t - st) / .55)) ** 3   # registry entrance: staggered fade + scale .72 -> 1, power3.out
                ex = L.clamp((T[-1] - T[fi]) / .3)           # our exit: everything fades in the last 0.3 s
                size = cs * max(FLOOR, s / smax) * (.72 + .28 * e) * (.9 + .1 * ex)
                w0, h0 = shapes[i]
                sc = size / BASE
                X = X0 + (x - mnx) / max(1e-6, mxx - mnx) * (X1 - X0)
                Y = Y0 + (y - mny) / max(1e-6, mxy - mny) * (Y1 - Y0)
                rz = math.radians(p['rotZ'])
                bw = (abs(w0 * math.cos(rz)) + abs(h0 * math.sin(rz))) * sc * 1.06 + 4
                bh = (abs(w0 * math.sin(rz)) + abs(h0 * math.cos(rz))) * sc * 1.06 + 4
                out.append({'X': X, 'Y': Y, 'sc': sc, 'rz': p['rotZ'], 'ry': p['rotY'], 'rx': p['rotX'], 'depth': p['depth'],
                            'op': p['alpha'] * e * ex, 'box': [X - bw / 2, Y - bh / 2, X + bw / 2, Y + bh / 2]})
            P.append(out)
        return P

    def fit(mode):
        K = 1.0
        if mode == 'above' and target(1.0, mode)[4] < 150:   # the band above the faces is too short for readable cards
            return None, K
        for _ in range(12):
            P = layout(K, mode)
            bad = any(p['op'] > .05 and p['sc'] > .05 and L.unsafe(p['box']) for row in P for p in row)
            if mode == 'above' and target(K, mode)[4] < 150:
                break
            if mode == 'above' and not bad:   # a front card never covers a face
                bad = any(p['op'] > .05 and L.box_face_share(p['box'], FACES[fi]) > .002 for fi, row in enumerate(P) for p in row)
            if not bad:
                return P, K
            K *= .93
        return None, K

    def hidden(P):
        """share of card area the speakers hide, sampled across the run: the layout that keeps the cards on open wall wins."""
        if not ctx.has_cut:
            return 0.0
        tot = hid = 0.0
        for fi in range(0, len(T), 6):
            for p in P[fi]:
                if p['op'] < .3:
                    continue
                b = p['box']
                ar = (b[2] - b[0]) * (b[3] - b[1])
                tot += ar
                hid += ar * ctx.alpha_cover(T[fi], *b)
        return hid / max(1, tot)
    modes = [m for m in (g.get('place'),) if m in ('around', 'above')] or ['around', 'above']
    cands = []
    for mode in modes:
        P, K = fit(mode)
        if P is not None:
            # around the head is the signature look; it wins unless the speakers would hide much more of it
            cands.append(((.12 + .2 * (1 - K)) if mode == 'above' else hidden(P), mode, P, K))
    if not cands:
        ctx.fail(f'{g["type"]} on {g["on"]!r}: the carousel does not fit the safe zone around this head; use fewer tiles or a wider shot')
    hid, mode, P, K = min(cands, key=lambda c: c[0])
    if mode == 'around' and hid > float(g.get('max_hidden', .2)):
        ctx.fail(f'{g["type"]} on {g["on"]!r}: the speakers would hide {hid:.0%} of the cards on this shot and there is no clear band '
                 'above the faces; use orbit-carousel (it passes in front of the chin) or a wider shot')
    ctx.note(f'{g["type"]}: {mode} the head' + (f', {hid:.0%} of card area behind the speakers' if mode == 'around' else ', in front, clear of every face'))
    front = mode == 'above'

    # ---- labels: only on cards big enough to read and not crossed by a bigger card ----
    tfs, sfs = L.tile_fonts(ctx, g['type'], tiles, BASE * .8, BASE, tmax=56, smin=30)
    lab = [[0.0] * len(T) for _ in range(n)]
    for fi, row in enumerate(P):
        order = sorted(range(n), key=lambda i: -row[i]['sc'])
        taken = []
        for i in order:
            p = row[i]
            if p['op'] < .6 or p['sc'] * tfs < 29 or abs(p['ry']) > 50:
                continue
            b = p['box']
            lb = [b[0], b[1] + (b[3] - b[1]) * .55, b[2], b[3]]
            if any(L.overlap_share(lb, q) > .12 for q in taken):   # two labels would collide: the smaller card's label waits
                continue
            taken.append(lb)
            lab[i][fi] = 1.0
    lab = [L.soft_min(v, .25) for v in lab]
    big = [[shapes[i][0] * shapes[i][1] * P[fi][i]['sc'] ** 2 for fi in range(len(T))] for i in range(n)]   # on-screen card area

    # ---- cards dim while the speaker covers them ----
    dim = [[1.0] * len(T) for _ in range(n)]
    if ctx.has_cut and not front:
        for fi in range(0, len(T), 2):
            for i, p in enumerate(P[fi]):
                if p['op'] < .05 or p['sc'] < .05:
                    continue
                if L.band_cover(ctx, T[fi], p['box']) > .05:   # a card that only touches the hair stays solid
                    for k in range(fi, min(len(T), fi + 2)):
                        dim[i][k] = L.DIM
        dim = [L.soft_min(v, .2, hold=3) for v in dim]

    # ---- markup and keyframes ----
    inner = L.tiles_html(ctx, tiles, BASE, BASE, tfs, sfs)
    cards = ''.join(f'<div class="tl t{i}" style="width:{w:.0f}px;height:{h:.0f}px;left:{-w / 2:.0f}px;top:{-h / 2:.0f}px">'
                    f'<div class="cd">{inner[i]}<div class="vl"></div></div></div>' for i, (w, h) in enumerate(shapes))
    layer = ctx.wall if ctx.has_cut and not front else ctx.front
    cid = ctx.clip(layer, a, end, f'<div class="fx-{g["type"]}">{cards}</div>', 'position:absolute;left:0;top:0;width:1080px;height:1920px;',
                   'wallz' if layer is ctx.wall else '')
    dmin, dmax = min(p['depth'] for row in P for p in row), max(p['depth'] for row in P for p in row)
    for i in range(n):
        mot, turn, veil, lbl = [], [], [], []
        for fi, row in enumerate(P):
            p = row[i]
            dn = (p['depth'] - dmin) / max(1e-6, dmax - dmin)
            mot.append({'x': round(p['X'], 1), 'y': round(p['Y'], 1), 'scale': round(p['sc'], 4), 'rotation': round(p['rz'], 2),
                        'zIndex': int(100 + 100 * (dn if family != 'circle' and family != 'path' else p['sc'] / 2)),
                        # a word card whose label must hide recedes too (a big coloured card with no words reads as an empty box)
                        'opacity': round(p['op'] * dim[i][fi] * (1 if tiles[i].get('src') or big[i][fi] < 26000 else L.lerp(.45, 1, lab[i][fi])), 3)})
            turn.append({'rotationY': round(max(-70, min(70, p['ry'])), 2), 'rotationX': round(max(-40, min(40, p['rx'])), 2),
                         **({'transformPerspective': 1600} if fi == 0 else {})})
            veil.append({'opacity': round(.3 * (1 - dn), 3)})
            lbl.append({'opacity': round(lab[i][fi], 3)})
        L.emit_track(ctx, f'#{cid} .t{i}', a, mot)
        L.emit_track(ctx, f'#{cid} .t{i} .cd', a, turn)
        L.emit_track(ctx, f'#{cid} .t{i} .vl', a, veil)
        L.emit_track(ctx, f'#{cid} .t{i} ' + ('.lb' if tiles[i].get('src') else '.tg > *'), a, lbl)
    tops = [p['box'][1] for row in P for p in row if p['op'] > .3]
    bots = [p['box'][3] for row in P for p in row if p['op'] > .3]
    L.claim(ctx, min(tops), max(bots), a, end)
    ctx.sfx(g.get('sfx'), a, .3)
    ctx.note(f'{g["type"]}: {n} cards, layout {K:.0%}, spans y {min(tops):.0f}-{max(bots):.0f}')
