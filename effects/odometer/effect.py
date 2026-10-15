"""Odometer: a live counter pill (comments, views, sign-ups) whose digits roll like a mechanical counter while the speaker talks."""
import importlib.util, math, os, sys

META = {
    'id': 'odometer', 'name': 'Live counter', 'category': 'data',
    'when': 'A count that is still climbing matters to the line: comments pouring in, sign-ups ticking, views running up. The numbers are real.',
    'never': 'Never an invented count. Never for a fixed number (use count-up). Never covers a face.',
    'params': {'on': 'phrase that brings the counter in', 'from': 'start value (required)', 'to': 'value it reaches (required)',
               'icon': 'comment (default), heart, eye or share', 'run': 'seconds to climb from "from" to "to", default the whole hold',
               'stats': 'up to 2 small pills [{"icon", "text"}] that pop under the counter, optional',
               'hold': 'seconds, default 3.0', 'sfx': 'optional sound name (none by default: a ticking count has no literal sound)'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


DW, DH = 62, 88    # one digit window
FPS = 30


def _strip():
    """0..9 then 0 again, stacked, so a wheel can roll past 9 without a jump."""
    return ''.join(f'<text x="{DW / 2}" y="{DH * (k + .5)}" text-anchor="middle" dominant-baseline="central">{k % 10}</text>' for k in range(11))


def _wheel(v, p):
    """position (0-10) of the wheel for place p at value v: the ones wheel rolls continuously, higher wheels turn over only
    while every wheel below rolls from 9 to 0, like a real odometer."""
    unit = 10 ** p
    if p == 0:
        return v % 10
    base = math.floor(v / unit) % 10
    carry = min(1.0, max(0.0, (v % unit) - (unit - 1)))   # turns over only while the wheels below roll from 9 to 0
    return base + carry * carry * (3 - 2 * carry)


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'from', 'to')
    v0, v1 = float(g['from']), float(g['to'])
    if v1 < v0 or v1 >= 10 ** 9:
        ctx.fail(f'odometer on {g["on"]!r}: "to" must be at least "from" and under a billion')
    a, end = L.window(ctx, g, 3.0, min_after=1.2)
    a, end = round(a * FPS) / FPS, round(end * FPS) / FPS
    run = min(float(g.get('run', end - a - .4)), end - a - .3)
    nd = len(str(int(v1)))
    groups = [(nd - 1 - k) for k in range(nd)]   # place of each wheel, left to right
    stats = (g.get('stats') or [])[:2]
    icon = L.icon_svg(g.get('icon', 'comment'), 52)
    wheels = ''
    for i, p in enumerate(groups):
        wheels += f'<div class="wl"><svg viewBox="0 0 {DW} {DH}" width="{DW}" height="{DH}"><g class="sp p{p}">{_strip()}</g></svg></div>'
        if p and p % 3 == 0:
            wheels += '<div class="cm"></div>'
    W = 26 + 52 + 18 + nd * (DW + 8) + (nd - 1) // 3 * 14 + 26
    sh = 0
    pills = ''
    if stats:
        sfs = 30
        pills = '<div class="ss">' + ''.join(f'<div class="st s{k}">{L.icon_svg(s.get("icon", "heart"), 32)}<span style="font-size:{sfs}px">{ctx.esc(s["text"])}</span></div>'
                                              for k, s in enumerate(stats)) + '</div>'
        sh = 74
    H = DH + 2 * 14 + sh
    x, y, sc = L.above_head(ctx, 'odometer', W, H, a, end)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    html = f'<div class="fx-odometer" style="width:{W}px"><div class="pl"><div class="ic">{icon}</div>{wheels}</div>{pills}</div>'
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .pl',{{opacity:0,y:-30,scale:.9}},{{opacity:1,y:0,scale:1,duration:.38,ease:'back.out(1.8)',immediateRender:false}},{q(a)});")
    for k in range(len(stats)):
        ctx.tw(f"gsap.set('#{cid} .s{k}',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .s{k}',{{opacity:0,y:-16,scale:.8}},{{opacity:1,y:0,scale:1,duration:.3,ease:'back.out(2)',immediateRender:false}},{q(a + .5 + .18 * k)});")
    # one pose per frame for every wheel, baked into keyframes (deterministic under the frame-stepping renderer)
    n = int(round((end - a) * FPS))

    def val(t):
        u = min(1.0, max(0.0, (t - a - .15) / max(.3, run)))
        return v0 + (v1 - v0) * (1 - (1 - u) ** 2.2)
    for p in set(groups):
        poses = [_wheel(val(a + k / FPS), p) for k in range(n + 1)]
        keys = []
        for k, pos in enumerate(poses):
            speed = abs(pos - poses[k - 1]) if k else 0
            speed = min(speed, 10 - speed)
            keys.append(f"{{y:{-pos * DH:.1f},filter:'blur({min(3.0, speed * 1.4):.2f}px)'}}")
        ctx.tw(f"gsap.set('#{cid} .p{p}',{{y:{-poses[0] * DH:.1f}}});")
        body = ','.join(f"{{y:{k.split('y:')[1].split(',')[0]},filter:{k.split('filter:')[1][:-1]},duration:{1 / FPS:.5f},ease:'none'}}" for k in keys[1:])
        ctx.tw(f"tl.to('#{cid} .p{p}',{{keyframes:[{body}],immediateRender:false}},{q(a)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-24,duration:.22,ease:'power2.in'}},{q(end - .22)});")
    ctx.sfx(g.get('sfx'), a, .3)


def describe(g, beat):
    return f'On “{g["on"]}” a live {g.get("icon", "comment")} counter rolls from {g["from"]} to {g["to"]} above the head. It holds {beat["hold"]:.1f} s.'
