"""Score pins: a row of thumbnails, each one drops a pin onto a 0 to 100 scale at its real score."""
import importlib.util, os, sys

META = {
    'id': 'score-pins', 'name': 'Score pins', 'category': 'data',
    'when': 'The speaker scored or ranked a set of things ("I ran seven hooks through it and it scored every one between zero and 100").',
    'never': 'Never invented scores. Never more than 8 items. Never covers a face.',
    'params': {'on': 'phrase that brings the row in', 'items': '[{"title"?, "src"?, "score": 0-100}] 3 to 8; src is an image file, else a numbered tile',
               'pins_on': 'phrase where the pins drop, default 0.5 s in', 'scale_on': 'phrase where the 0-100 bar draws, default after the pins',
               'low': 'left label, default "0"', 'high': 'right label, default "100"', 'hold': 'seconds after the bar, default 1.4',
               'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by an Instagram reel on predicting virality (Oct 2026)', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


W = 860
TINTS = ['var(--c-accent2)', 'var(--c-accent)', 'color-mix(in srgb,var(--c-accent) 50%,var(--c-accent2))', 'var(--c-ink)']


def build(g, ctx):
    L = _lib()
    items = g.get('items') or []
    if not 3 <= len(items) <= 8 or not all(isinstance(i, dict) and 0 <= float(i.get('score', -1)) <= 100 for i in items):
        ctx.fail(f'score-pins on {g["on"]!r} needs 3 to 8 items, each with a "score" 0-100')
    n = len(items)
    a0 = ctx.at(g['on'])[0]
    tp = max(a0 + .5, ctx.at(g['pins_on'], a0)[0]) if g.get('pins_on') else a0 + .5
    pins_done = tp + .1 * n + .3
    tb = max(pins_done, ctx.at(g['scale_on'], a0)[0]) if g.get('scale_on') else pins_done + .1
    a, end = L.window(ctx, g, 1.4, last=tb + .5)
    gap = 14
    cw = min(110, (W - 40 - gap * (n - 1)) / n)
    ch = cw * 1.42
    x0 = (W - (n * cw + (n - 1) * gap)) / 2
    PY = ch + 92        # pin tip y
    BY = PY + 14        # bar y
    H = int(BY + 70)
    x, y, sc = L.above_head(ctx, 'score-pins', W, H, a, end)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    sx0, sx1 = 60, W - 60
    cards, pins, paths = '', '', ''
    for k, it in enumerate(items):
        cx = x0 + k * (cw + gap)
        url = ctx.asset(it['src']) if it.get('src') else None
        face = f'<img src="{url}">' if url else f'<span>{ctx.esc(it.get("title") or k + 1)}</span>'
        cards += f'<div class="cd c{k}" style="left:{cx:.0f}px;width:{cw:.0f}px;height:{ch:.0f}px;background:{TINTS[k % len(TINTS)]}">{face}</div>'
        px = sx0 + (sx1 - sx0) * float(it['score']) / 100
        mx, my = cx + cw / 2, ch + 6
        paths += (f'<path class="p{k}" d="M{mx:.0f} {my:.0f} C{mx:.0f} {my + 50:.0f} {px:.0f} {PY - 80:.0f} {px:.0f} {PY - 44:.0f}" '
                  f'style="stroke-dasharray:400;stroke-dashoffset:400"/>')
        pins += f'<div class="pn q{k}" style="left:{px - 22:.0f}px;top:{PY - 56:.0f}px;--t:{TINTS[k % len(TINTS)]}"><b>{int(round(float(it["score"])))}</b></div>'
    html = (f'<div class="fx-score-pins" style="width:{W}px;height:{H}px">{cards}'
            f'<svg class="ln" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{paths}</svg>{pins}'
            f'<div class="bar" style="left:{sx0}px;width:{sx1 - sx0}px;top:{BY}px"></div>'
            f'<div class="lb lo" style="left:{sx0 - 40}px;top:{BY + 14}px">{ctx.esc(g.get("low", "0"))}</div>'
            f'<div class="lb hi" style="left:{sx1 - 60}px;top:{BY + 14}px">{ctx.esc(g.get("high", "100"))}</div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .cd',{{opacity:0,y:30,filter:'blur(8px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.35,stagger:.05,ease:'power3.out',immediateRender:false}},{q(a)});")
    ctx.tw(f"gsap.set('#{cid} .pn',{{opacity:0}});")
    order = sorted(range(n), key=lambda k: float(items[k]['score']))
    for j, k in enumerate(order):
        t = tp + .1 * j
        ctx.tw(f"tl.to('#{cid} .p{k}',{{strokeDashoffset:0,duration:.3,ease:'power2.out'}},{q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .q{k}',{{opacity:0,y:-40,scale:.6}},{{opacity:1,y:0,scale:1,duration:.38,ease:'back.out(2.4)',immediateRender:false}},{q(t + .16)});")
    ctx.tw(f"gsap.set('#{cid} .bar',{{scaleX:0}});")
    ctx.tw(f"gsap.set('#{cid} .lb',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .bar',{{scaleX:0}},{{scaleX:1,duration:.45,ease:'power2.inOut',immediateRender:false}},{q(tb)});")
    ctx.tw(f"tl.fromTo('#{cid} .lo',{{opacity:0,y:10}},{{opacity:1,y:0,duration:.2,immediateRender:false}},{q(tb)});")
    ctx.tw(f"tl.fromTo('#{cid} .hi',{{opacity:0,scale:.6}},{{opacity:1,scale:1,duration:.3,ease:'back.out(2.5)',immediateRender:false}},{q(tb + .4)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.22,ease:'power2.in'}},{q(end - .22)});")
    ctx.sfx(g.get('sfx'), tp, .3)


def describe(g, beat):
    sc = ', '.join(str(i['score']) for i in g['items'])
    return f'On “{g["on"]}” a row of {len(g["items"])} thumbnails drops pins onto a {g.get("low", "0")} to {g.get("high", "100")} scale ({sc}). It holds {beat["hold"]:.1f} s.'
