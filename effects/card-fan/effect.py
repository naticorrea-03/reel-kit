"""Card fan: cards deal out of a stack into a fanned arc with a spring overshoot, then each flips to its back on its phrase.

The front of each card names the thing; the back carries the reveal (a number, a verdict, the answer). Flips land on
their words. The fan is placed clear of every face and shrinks until it fits.
"""
import importlib.util, os, sys

META = {
    'id': 'card-fan', 'name': 'Card fan with flips', 'category': 'carousel',
    'when': 'The speaker reveals something about each of 3 to 5 things in turn (a result per option, an answer per question).',
    'never': 'Never a back that repeats the front or the caption. Never more than 5 cards. Never covers a face.',
    'params': {'on': 'phrase that deals the fan', 'cards': '[{"title", "back", "on", "kicker"?}] 3 to 5; each flips on its "on" phrase',
               'hold': 'seconds after the last flip, default 1.3', 'sfx': 'optional sound per flip (e.g. page-flip)'},
    'sfx': ['page-flip'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

CW, CH = 230, 320


def _lib():
    if 'rk3d' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'rk3d.py')
        spec = importlib.util.spec_from_file_location('rk3d', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['rk3d'] = mod
    return sys.modules['rk3d']


def build(g, ctx):
    L = _lib()
    cards = g.get('cards') or []
    if not 3 <= len(cards) <= 5 or not all(isinstance(c, dict) and c.get('title') and c.get('back') and c.get('on') for c in cards):
        ctx.fail(f'card-fan on {g["on"]!r} needs 3 to 5 cards, each with "title", "back" and "on"')
    for c in cards:
        if c['back'].strip().lower() == c['title'].strip().lower():
            ctx.fail(f'card-fan card {c["title"]!r}: the back repeats the front; the back must add the reveal')
    n = len(cards)
    a0 = L.fq(ctx.at(g['on'])[0])
    times = [max(t, a0 + .55 + .09 * n) for t in L.item_times(ctx, g, cards, 1.0)]
    for k in range(1, n):
        if times[k] - times[k - 1] < .45:
            ctx.fail(f'card-fan on {g["on"]!r}: flip {k + 1} lands {times[k] - times[k - 1]:.2f} s after the one before; give each 0.45 s or more')
    a, end = L.window(ctx, g, 1.3, last=times[-1], min_after=.8)
    inner = CW - 48
    tfs = L.fit(ctx, 'card-fan fronts', [c['title'] for c in cards], inner, 46, 30, 3)
    bfs = L.fit(ctx, 'card-fan backs', [c['back'] for c in cards], inner * .86, 52, 28, 4)   # the serif italic runs wider than the estimate
    gap = CW * .84                      # neighbours overlap a little; the words of one card never sit under the next
    mid = (n - 1) / 2
    poses = [((k - mid) * gap, abs(k - mid) ** 2 * 14, (k - mid) * 7) for k in range(n)]   # x, y, rotation
    GW, GH = CW + gap * (n - 1) + 60, CH + max(p[1] for p in poses) + 70

    # ---- placement: the whole fan clear of every face, as big as fits ----
    best = None
    for sc in (1.0, .9, .8, .72, .64, .58):
        w, h = GW * sc, GH * sc
        for y in range(L.SAFE[1] + 30, int(L.SAFE[3] - h) + 1, 16):
            for x in range(L.SAFE[0], int(L.SAFE[2] - w) + 1, 16):
                box = [x, y, x + w, y + h]
                if L.unsafe(box):
                    continue
                if max(L.box_face_share(box, L.all_faces(ctx, t)) for t in (a, (a + end) / 2, end - .05)) > .002:
                    continue
                cost = abs(x + w / 2 - 540) / 1000 + abs(y + h / 2 - 1000) / 3000
                if best is None or cost < best[0]:
                    best = (cost, sc, x, y)
        if best:
            break
    if not best:
        ctx.fail(f'card-fan on {g["on"]!r}: no spot clears the faces even at 58% size; use a wider shot')
    _, sc, gx, gy = best
    if sc < 1:
        ctx.note(f'card-fan placed at {sc:.0%} to clear the faces')
    if ctx.face_hit(a, end, gx, gy, gx + GW * sc, gy + GH * sc) > .005:
        ctx.warn(f'card-fan on {g["on"]!r} touches a face mid-hold')

    body = ''
    for k, c in enumerate(cards):
        body += (f'<div class="cf k{k}" style="width:{CW}px;height:{CH}px;left:{GW / 2 - CW / 2:.0f}px;top:30px;z-index:{10 + k}">'
                 f'<div class="fr v{k % 2}"><div class="kk">{ctx.esc(c.get("kicker") or f"{k + 1:02d}")}</div>'
                 f'<div class="tt" style="font-size:{tfs}px">{ctx.esc(c["title"])}</div></div>'
                 f'<div class="bk"><div class="kk">{ctx.esc(c["title"])}</div><div class="bt" style="font-size:{bfs}px">{ctx.esc(c["back"])}</div></div></div>')
    html = f'<div class="fx-card-fan" style="width:{GW:.0f}px;height:{GH:.0f}px;zoom:{sc:.3f}">{body}</div>'
    cid = ctx.clip(ctx.front, a, end, html, f'position:absolute;left:{gx}px;top:{gy}px;')
    for k, (x, y, r) in enumerate(poses):
        sel = f'#{cid} .k{k}'
        ctx.tw(f"gsap.set('{sel}',{{transformPerspective:1100,transformOrigin:'50% 120%'}});")
        ctx.tw(f"gsap.set('{sel} .bk',{{opacity:0}});")
        t = a + .08 * k
        # deal: out of a stack under the fan, springing past its slot and settling
        ctx.tw(f"tl.fromTo('{sel}',{{opacity:0,x:0,y:90,rotation:0,scale:.86}},{{opacity:1,x:{x:.0f},y:{y:.0f},rotation:{r:.1f},scale:1,"
               f"duration:.95,ease:'elastic.out(1,.62)',immediateRender:false}},{ctx.q(t)});")
        tf = times[k]
        # flip on the word in two halves: turn edge-on, swap faces, turn back. No backface tricks, so no mirrored words.
        ctx.tw(f"tl.fromTo('{sel}',{{rotationY:0}},{{rotationY:90,duration:.17,ease:'power2.in',immediateRender:false}},{ctx.q(tf - .17)});")
        ctx.tw(f"tl.fromTo('{sel} .fr',{{opacity:1}},{{opacity:0,duration:.02,immediateRender:false}},{ctx.q(tf - .01)});")
        ctx.tw(f"tl.fromTo('{sel} .bk',{{opacity:0}},{{opacity:1,duration:.02,immediateRender:false}},{ctx.q(tf - .01)});")
        ctx.tw(f"tl.fromTo('{sel}',{{rotationY:-90}},{{rotationY:0,duration:.45,ease:'back.out(1.7)',immediateRender:false}},{ctx.q(tf)});")
        ctx.tw(f"tl.fromTo('{sel}',{{y:{y:.0f},scale:1}},{{y:{y - 34:.0f},scale:1.07,duration:.2,ease:'power2.out',immediateRender:false}},{ctx.q(tf - .17)});")
        ctx.tw(f"tl.fromTo('{sel}',{{y:{y - 34:.0f},scale:1.07}},{{y:{y:.0f},scale:1,duration:.45,ease:'power3.out',immediateRender:false}},{ctx.q(tf + .05)});")
        ctx.sfx(g.get('sfx'), tf - .1, .3)
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:30,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")
    L.claim(ctx, gy, gy + GH * sc, a, end)


def describe(g, beat):
    flips = '; '.join(f'"{c["title"]}" flips to "{c["back"]}" on “{c["on"]}”' for c in g['cards'])
    return f'On “{g["on"]}” {len(g["cards"])} cards deal into a fan with a spring. {flips}. It holds {beat["hold"]:.1f} s.'
