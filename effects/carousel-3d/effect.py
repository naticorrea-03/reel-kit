"""3D cylinder carousel: 6 to 10 cards on a cylinder that turns in true CSS 3D behind the head, above the shoulders.

The cylinder sits on the wall layer so the speaker's head is in front of it. Each card's words sit in its top band, which
is placed above the head, so the card facing camera stays readable. With per-card "on" phrases the cylinder steps to
bring each card to the front on its word; otherwise it spins and, with "stop", settles on one card on that phrase.
Poses are computed per frame and baked into GSAP keyframes (deterministic under the frame-stepping renderer).
"""
import importlib.util, math, os, sys

META = {
    'id': 'carousel-3d', 'name': '3D cylinder carousel', 'category': 'carousel',
    'when': 'The speaker runs through a set of options, steps or names; the cylinder turns to each one as it is said.',
    'never': 'Never cards the speaker does not name or imply. Never on a close-up where the head fills the top of the frame '
             '(there is no band above the head; the build moves it under the chin or refuses).',
    'params': {'on': 'phrase that brings the cylinder in', 'cards': '[{"title", "sub"?, "kicker"?, "on"?}] 6 to 10',
               'stop': 'optional {"on": phrase, "card": index}: spin, then settle with that card facing camera (spin mode only)',
               'hold': 'seconds after the last beat, default 1.6', 'speed': 'spin in degrees per second, default 40',
               'until': 'optional phrase to clear before', 'sfx': 'optional sound per step (e.g. swipe)'},
    'sfx': ['swipe'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

P = 1600   # perspective in px


def _lib():
    if 'rk3d' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'rk3d.py')
        spec = importlib.util.spec_from_file_location('rk3d', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['rk3d'] = mod
    return sys.modules['rk3d']


def project(cx, cy, Rc, W, H, phi, k=1.0):
    """projected bounding box of a card at angle phi on the cylinder (perspective P from the cylinder's front)."""
    xs, ys = [], []
    for sx in (-1, 1):
        x = Rc * math.sin(phi) + sx * W / 2 * math.cos(phi)
        z = Rc * math.cos(phi) - Rc - sx * W / 2 * math.sin(phi)
        f = P / (P - z)
        for sy in (-1, 1):
            xs.append(cx + x * f * k)
            ys.append(cy + sy * H / 2 * f * k)
    return [min(xs), min(ys), max(xs), max(ys)]


def build(g, ctx):
    L = _lib()
    cards = g.get('cards') or []
    if not 6 <= len(cards) <= 10 or not all(isinstance(c, dict) and c.get('title') for c in cards):
        ctx.fail(f'carousel-3d on {g["on"]!r} needs 6 to 10 cards, each with "title"')
    n = len(cards)
    stepped = any(c.get('on') for c in cards)
    times = L.item_times(ctx, g, [c for c in cards if c.get('on')], 1.0) if stepped else []
    stop_t = None
    if g.get('stop') and not stepped:
        st = g['stop'] if isinstance(g['stop'], dict) else {'on': g['stop'], 'card': 0}
        stop_t = L.fq(ctx.at(st['on'], ctx.at(g['on'])[0])[0])
        stop_card = int(st.get('card', 0)) % n
    last = max(times + ([stop_t] if stop_t else []) + [ctx.at(g['on'])[0]])
    a, end = L.window(ctx, g, 1.6, last=last, min_after=.9 if (stepped or stop_t) else 2.0)
    for k in range(1, len(times)):
        if times[k] - times[k - 1] < .55:
            ctx.fail(f'carousel-3d on {g["on"]!r}: card {k + 1} lands {times[k] - times[k - 1]:.2f} s after the one before; give each 0.55 s or more')
    T = L.frames(a, end)
    step_deg = 360 / n
    speed = float(g.get('speed', 40))

    # ---- rotation (degrees the cylinder has turned; card i faces camera when rot + i*step = 0 mod 360) ----
    IN = .9
    def rot_at(t):
        u = t - a
        if stepped:
            on_idx = [i for i, c in enumerate(cards) if c.get('on')]
            r = -on_idx[0] * step_deg + 140 * (1 - L.out_cubic(u / IN))   # swings in onto the first card
            # each later card turns to the front over 0.5 s, arriving just as its word lands
            for j in range(1, len(times)):
                d = (on_idx[j] - on_idx[j - 1]) % n
                d = d - n if d > n / 2 else d
                r -= d * step_deg * L.inout_cubic((t - (times[j] - .42)) / .5)
            return r
        if stop_t is not None:
            # spin, then decelerate so stop_card faces camera exactly at stop_t
            dec = 1.0
            t0 = stop_t - dec
            base = speed * (t0 - a) + 140 * (1 - L.out_cubic((t0 - a) / IN))
            free = base + speed * dec / 2          # where a linear brake from speed lands
            target = -stop_card * step_deg
            target += 360 * math.ceil((free - target) / 360)
            if t <= t0:
                return speed * u + 140 * (1 - L.out_cubic(u / IN))
            v = (t - t0) / dec
            # quadratic brake bent onto the target: position = base + (target - base) * (2v - v^2)
            return base + (target - base) * (2 * min(v, 1) - min(v, 1) ** 2)
        return speed * u + 140 * (1 - L.out_cubic(u / IN))

    def k_at(t):
        if t < a + IN * .7:
            return .82 + .18 * L.out_back((t - a) / (IN * .7), 1.2)
        if t > end - .35:
            return 1 - .12 * L.in_cubic((t - (end - .35)) / .35)
        return 1.0

    # ---- geometry: cylinder width and the band above the head ----
    track = L.face_track(ctx, a, end)
    heads = [ctx.head_top(t) for t in (a + (end - a) * k / 6 for k in range(7))] if ctx.has_cut else []
    heads = [h for h in heads if h is not None]
    head = min(heads) if heads else None
    fcx = sorted((track(t)[0] + track(t)[2]) / 2 for t in T[::6])[len(T[::6]) // 2] if track else 540
    Rc = 330 if n <= 7 else 380 if n <= 8 else 420
    W = 2 * Rc * math.tan(math.pi / n) * .9
    Hc = min(380, max(260, W * 1.15))
    cx = 520
    tfs, sfs = L.tile_fonts(ctx, 'carousel-3d', cards, W, Hc, tmax=54, smin=30)
    text_h = 40 + tfs * 1.1 * 2 + (sfs * 1.25 * 2 if any(c.get('sub') for c in cards) else 0) + sfs * 1.2   # kicker + title + sub
    if text_h > Hc - 30:
        Hc = text_h + 30
    layer, front = ctx.wall, False
    cy = None
    if head is not None:
        # the words band (top of the card) ends 24 px above the head; the head may cover the lower part of the card
        cy = head - 24 - text_h + Hc / 2
        top = cy - Hc / 2 * P / (P - 0) * 1.0
        if top < L.SAFE[1] + 6:
            cy = L.SAFE[1] + 6 + Hc / 2
        # check the words of every card that faces the camera stay clear of the speaker
        worst = 0.0
        for t in T[::5]:
            for i in range(n):
                phi = math.radians(rot_at(t) + i * step_deg)
                if math.cos(phi) < .6:
                    continue
                b = project(cx, cy, Rc, W, Hc, phi, k_at(t))
                worst = max(worst, ctx.alpha_cover(t, b[0] + 10, b[1], b[2] - 10, b[1] + text_h))
        if worst > .03:
            front = True
    else:
        cy = 300 + Hc / 2
    if front:
        # close-up: no band above the head. Bring it in front, under the chin, scaled to fit.
        chin = max(track(t)[3] for t in T[::3]) if track else 1000
        sc = min(1.0, (L.SAFE[3] - 10 - chin - 20) / (Hc * 1.12))
        if sc < .6:
            ctx.fail(f'carousel-3d on {g["on"]!r}: no room above the head or under the chin on this shot; move it to a wider shot')
        Rc, W, Hc, tfs, sfs = Rc * sc, W * sc, Hc * sc, max(28, int(tfs * sc)), max(28, int(sfs * sc))
        text_h *= sc
        cy = chin + 20 + Hc * 1.06 / 2
        layer = ctx.front
        ctx.note(f'carousel-3d moved in front under the chin at {sc:.0%} (no room above the head)')

    # ---- per-frame poses ----
    poses = []
    for t in T:
        r, k = rot_at(t), k_at(t)
        row = []
        for i in range(n):
            phi = math.radians(r + i * step_deg)
            c = math.cos(phi)
            row.append({'x': Rc * math.sin(phi) * k, 'z': (Rc * c - Rc) * k, 'ry': math.degrees(phi), 'c': c, 's': k,
                        'box': project(cx, cy, Rc, W, Hc, phi, k)})
        poses.append(row)
    for fi, row in enumerate(poses):
        for p in row:
            if p['c'] > .05 and L.unsafe(p['box']):
                ctx.fail(f'carousel-3d on {g["on"]!r}: the cylinder leaves the safe zone at {T[fi]:.2f} s ({[round(v) for v in p["box"]]}); use fewer cards')

    # wall cards dim while the speaker covers their words (the cylinder recedes behind the head)
    dim = [[1.0] * len(T) for _ in range(n)]
    if layer is ctx.wall:
        for fi in range(0, len(T), 2):
            for i, p in enumerate(poses[fi]):
                if p['c'] < .05:
                    continue
                b = p['box']
                cov = ctx.alpha_cover(T[fi], b[0], b[1], b[2], min(b[3], b[1] + text_h * (b[3] - b[1]) / Hc))
                if cov > .02:
                    for k2 in range(fi, min(len(T), fi + 2)):
                        dim[i][k2] = L.DIM
        dim = [L.soft_min(d, .2, hold=3) for d in dim]

    # ---- markup ----
    sub_html = lambda c: f'<div class="sb" style="font-size:{sfs}px">{ctx.esc(c["sub"])}</div>' if c.get('sub') else ''
    body = ''.join(f'<div class="cr c{i} v{i % 4}" style="width:{W:.0f}px;height:{Hc:.0f}px;left:{-W / 2:.0f}px;top:{-Hc / 2:.0f}px">'
                   f'<div class="kk" style="font-size:{sfs}px">{ctx.esc(c.get("kicker") or f"{i + 1:02d}")}</div>'
                   f'<div class="tt" style="font-size:{tfs}px">{ctx.esc(c["title"])}</div>{sub_html(c)}<div class="vl"></div></div>'
                   for i, c in enumerate(cards))
    html = f'<div class="fx-carousel-3d"><div class="cy" style="left:{cx:.0f}px;top:{cy:.0f}px;perspective:{P}px">{body}</div></div>'
    cid = ctx.clip(layer, a, end, html, 'position:absolute;left:0;top:0;width:1080px;height:1920px;', 'wallz' if layer is ctx.wall else '')
    fade = [min(1.0, (t - a) / .25, (end - t) / .25) for t in T]
    for i in range(n):
        mot, veil = [], []
        for fi, row in enumerate(poses):
            p = row[i]
            face = L.clamp((p['c'] - .05) / .3)   # cards turned away vanish (their mirrored words never show)
            mot.append({'x': round(p['x'], 1), 'z': round(p['z'], 1), 'rotationY': round(p['ry'], 2), 'zIndex': int(100 + 80 * p['c']),
                        'opacity': round(face * fade[fi] * dim[i][fi], 3)})
            veil.append({'opacity': round(.4 * (1 - L.clamp(p['c'])), 3)})
        L.emit_track(ctx, f'#{cid} .c{i}', a, mot)
        L.emit_track(ctx, f'#{cid} .c{i} .vl', a, veil)
    for t in times[1:]:
        ctx.sfx(g.get('sfx'), t - .42, .25)
    if not times:
        ctx.sfx(g.get('sfx'), a, .25)
    tops = [p['box'][1] for row in poses for p in row if p['c'] > .3]
    bots = [p['box'][3] for row in poses for p in row if p['c'] > .3]
    L.claim(ctx, min(tops), max(bots) if layer is ctx.front else min(tops) + text_h, a, end, pause=front)


def describe(g, beat):
    names = ', '.join(f'"{c["title"]}"' for c in g['cards'])
    how = 'turns to each card on its word' if any(c.get('on') for c in g['cards']) else 'spins' + (' and settles on one card' if g.get('stop') else '')
    return f'On “{g["on"]}” a 3D cylinder of {len(g["cards"])} cards rises behind the head and {how}: {names}. It holds {beat["hold"]:.1f} s.'
