"""Retention drop: a retention graph draws itself, the cliff where viewers leave gets a marker, and the figures on the line fall off it."""
import importlib.util, os, sys

META = {
    'id': 'retention-drop', 'name': 'Retention cliff', 'category': 'data',
    'when': 'The speaker names the moment people drop off: viewers swiping, users churning, readers leaving ("it shows exactly where people would fall off").',
    'never': 'Never an invented curve: pass the real points or the real drop second. Never covers a face.',
    'params': {'on': 'phrase that brings the graph in', 'points': 'list of 6 to 30 values from 100 down (optional; else drop_at and floor shape it)',
               'drop_at': 'where the cliff is, 0-1 along the graph, default 0.72', 'floor': 'value after the cliff, default 18',
               'kicker': 'small line above the title, default "Predicted"', 'title': 'card title, default "Retention"',
               'label': 'note at the cliff marker, e.g. "0:11 they swipe" (optional)', 'mark_on': 'phrase where the marker drops, default after the line',
               'fall_on': 'phrase where the figures fall, default 0.4 s after the marker', 'hold': 'seconds after the fall, default 1.2', 'sfx': 'optional sound name'},
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


W, H = 780, 460
PX0, PX1, PY0, PY1 = 46, W - 46, 168, H - 64   # plot box inside the card
PERSON = ('<svg viewBox="0 0 30 46" width="42" height="64"><circle cx="15" cy="9" r="8"/><path d="M3 46V30a12 12 0 0 1 24 0v16z"/></svg>')


def build(g, ctx):
    L = _lib()
    drop = min(.92, max(.2, float(g.get('drop_at', .72))))
    floor = float(g.get('floor', 18))
    pts = [float(v) for v in g.get('points') or []]
    if pts and not 6 <= len(pts) <= 30:
        ctx.fail(f'retention-drop on {g["on"]!r}: points needs 6 to 30 values')
    if not pts:   # gentle decline, then the cliff, then a low tail
        N = 24
        k0 = int(drop * (N - 1))
        pts = [100 - 14 * (k / k0) ** .7 if k < k0 else max(floor - 3 * (k - k0 - 2) / N, floor * .8) if k > k0 + 1 else (100 - 14 + floor) / 2 if k == k0 else floor for k in range(N)]
    n = len(pts)
    xy = [(PX0 + (PX1 - PX0) * k / (n - 1), PY0 + (PY1 - PY0) * (1 - v / 100)) for k, v in enumerate(pts)]
    # the cliff: the biggest single step down
    ci = max(range(1, n), key=lambda k: pts[k - 1] - pts[k])
    cx = (xy[ci - 1][0] + xy[ci][0]) / 2
    a0 = ctx.at(g['on'])[0]
    tl_line = a0 + .35
    draw = 1.1
    tm = max(tl_line + draw, ctx.at(g['mark_on'], a0)[0]) if g.get('mark_on') else tl_line + draw + .05
    tf = max(tm + .3, ctx.at(g['fall_on'], a0)[0]) if g.get('fall_on') else tm + .4
    a, end = L.window(ctx, g, 1.2, last=tf + .6)
    face = L.speaker_box(ctx, a, end)
    near = ((face[0] + face[2]) / 2, face[1]) if face else None
    x, y, sc = L.fitspot(ctx, 'retention-drop', W, H, a, end, near=near)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    d = 'M' + ' L'.join(f'{px:.1f} {py:.1f}' for px, py in xy)
    area = d + f' L{PX1} {PY1} L{PX0} {PY1} Z'
    plen = sum(((xy[k][0] - xy[k - 1][0]) ** 2 + (xy[k][1] - xy[k - 1][1]) ** 2) ** .5 for k in range(1, n)) + 10
    grid = ''.join(f'<line x1="{PX0}" x2="{PX1}" y1="{PY0 + (PY1 - PY0) * f:.0f}" y2="{PY0 + (PY1 - PY0) * f:.0f}"/>' for f in (0, .5, 1))
    figs = ''
    fx_list = [PX0 + 34 + (cx - PX0 - 60) * k / 5 for k in range(6)]
    for k, fx in enumerate(fx_list):
        j = min(n - 1, int((fx - PX0) / (PX1 - PX0) * (n - 1)))
        fy = xy[j][1] + (xy[min(n - 1, j + 1)][1] - xy[j][1]) * (((fx - PX0) / (PX1 - PX0) * (n - 1)) - j)
        figs += f'<div class="fg g{k}" style="left:{fx - 21:.0f}px;top:{fy - 65:.0f}px">{PERSON}</div>'
    label = ''
    if g.get('label'):
        lw = len(g['label']) * 34 * .56 + 30
        lx = cx + 14 if cx + 14 + lw <= W - 24 else max(24, cx - 14 - lw)   # beside the marker, on whichever side has room
        label = f'<div class="lb" style="left:{lx:.0f}px;top:{PY0 + 6}px">{ctx.esc(g["label"])}</div>'
    html = (f'<div class="fx-retention-drop" style="width:{W}px;height:{H}px">'
            f'<div class="hd"><div class="kk">{ctx.esc(g.get("kicker", "Predicted"))}</div><div class="tt">{ctx.esc(g.get("title", "Retention"))}</div></div>'
            f'<svg class="pl" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><g class="gd">{grid}</g><path class="ar" d="{area}"/>'
            f'<path class="li" d="{d}" style="stroke-dasharray:{plen:.0f};stroke-dashoffset:{plen:.0f}"/>'
            f'<line class="mk" x1="{cx:.0f}" x2="{cx:.0f}" y1="{PY0 - 10}" y2="{PY1}"/><circle class="dt" cx="{xy[0][0]:.0f}" cy="{xy[0][1]:.0f}" r="10"/></svg>'
            f'{figs}{label}<div class="ax"><span>0s</span><span>end</span></div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .fx-retention-drop',{{opacity:0,y:40,scale:.95}},{{opacity:1,y:0,scale:1,duration:.4,ease:'power3.out',immediateRender:false}},{q(a)});")
    ctx.tw(f"tl.to('#{cid} .li',{{strokeDashoffset:0,duration:{draw},ease:'none'}},{q(tl_line)});")
    ctx.tw(f"gsap.set('#{cid} .ar',{{opacity:0}});")
    ctx.tw(f"tl.to('#{cid} .ar',{{opacity:1,duration:.5}},{q(tl_line + .4)});")
    # playhead dot rides the line while it draws (pose per step, linear between)
    cum, keys = [0.0], []
    for k in range(1, n):
        cum.append(cum[-1] + ((xy[k][0] - xy[k - 1][0]) ** 2 + (xy[k][1] - xy[k - 1][1]) ** 2) ** .5)
    for k in range(1, n):
        keys.append(f"{{attr:{{cx:{xy[k][0]:.1f},cy:{xy[k][1]:.1f}}},duration:{draw * (cum[k] - cum[k - 1]) / cum[-1]:.4f},ease:'none'}}")
    ctx.tw(f"tl.to('#{cid} .dt',{{keyframes:[{','.join(keys)}],immediateRender:false}},{q(tl_line)});")
    ctx.tw(f"gsap.set('#{cid} .mk',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .mk',{{opacity:0,attr:{{y2:{PY0 - 10}}}}},{{opacity:1,attr:{{y2:{PY1}}},duration:.3,ease:'power2.out',immediateRender:false}},{q(tm)});")
    if label:
        ctx.tw(f"gsap.set('#{cid} .lb',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .lb',{{opacity:0,x:-10}},{{opacity:1,x:0,duration:.25,immediateRender:false}},{q(tm + .15)});")
    ctx.tw(f"gsap.set('#{cid} .fg',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .fg',{{opacity:0,y:-14,scale:.6}},{{opacity:1,y:0,scale:1,duration:.25,stagger:.05,ease:'back.out(2.5)',immediateRender:false}},{q(tl_line + .5)});")
    drop_y = (PY1 - PY0) * .6
    for k in (3, 4, 5):   # the three nearest the cliff topple over it
        t = tf + (5 - k) * .1
        ctx.tw(f"tl.to('#{cid} .g{k}',{{color:'var(--c-accent)',duration:.08}},{q(t)});")
        ctx.tw(f"tl.to('#{cid} .g{k}',{{keyframes:[{{x:{cx - fx_list[k] + 6:.0f},rotation:20,duration:.22,ease:'power1.in'}},"
               f"{{x:{cx - fx_list[k] + 34:.0f},y:{drop_y:.0f},rotation:110,opacity:0,duration:.45,ease:'power2.in'}}]}},{q(t)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.22,ease:'power2.in'}},{q(end - .22)});")
    ctx.sfx(g.get('sfx'), tf, .3)


def describe(g, beat):
    return (f'On “{g["on"]}” a retention graph draws itself, a marker drops at the cliff'
            f'{" (“" + g["label"] + "”)" if g.get("label") else ""} and the figures on the line fall off it. It holds {beat["hold"]:.1f} s.')
