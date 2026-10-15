"""Prompt card: a "Paste this into ___" card with a warm header bar, a monospace prompt that scrolls, and one line that gets
boxed while a red hand-drawn arrow points at it."""
import importlib.util, math, os, sys

META = {
    'id': 'prompt-card', 'name': 'Prompt card', 'category': 'ui',
    'when': 'The speaker gives the viewer a prompt to copy ("paste this into Claude") and one line of it is the part that matters.',
    'never': 'Never a prompt the speaker does not offer. Never a highlight on a line that is not the point. Never covers a face.',
    'params': {'on': 'phrase that brings the card in', 'tool': 'the app the prompt goes into, set in italic serif (required)',
               'lines': 'the prompt, as a list of lines or "text" with newlines (required, 4 or more lines)',
               'highlight': 'text of the line to box (a substring of one line)', 'highlight_on': 'phrase where the box and arrow draw in (default 1 s after on)',
               'label': 'small pill on the header, default "COPY"', 'hold': 'seconds after the highlight, default 1.4', 'captions': '"pause" or "keep", default pause',
               'sfx': 'optional sound when the arrow draws'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by a creator reel on Instagram (Oct 2026)', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


W, HDR, PAD = 860, 92, 22
FS, LH = 38, 54
CH = FS * .6                 # monospace advance
ARW = 96                     # right margin kept for the arrow


def _soft(lines, cols):
    """soft-wrap at word breaks; returns (source line index, text) rows."""
    out = []
    for i, ln in enumerate(lines):
        cur = ''
        for w in ln.split(' '):
            t = (cur + ' ' + w) if cur else w
            if len(t) > cols and cur:
                out.append((i, cur))
                cur = '  ' + w
            else:
                cur = t
        out.append((i, cur))
    return out


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'tool')
    lines = [str(x) for x in (g.get('lines') or str(g.get('text', '')).split('\n'))]
    if len([x for x in lines if x.strip()]) < 4:
        ctx.fail(f'prompt-card on {g["on"]!r} needs "lines": at least 4 lines of the prompt')
    a0 = ctx.at(g['on'])[0]
    th = max(ctx.at(g['highlight_on'], a0)[0] if g.get('highlight_on') else a0 + 1.0, a0 + .7)
    a, end = L.window(ctx, g, 1.4, last=th)
    cols = int((W - 2 * PAD - ARW) / CH)
    rows = _soft(lines, cols)
    hi = None
    if g.get('highlight'):
        hit = [i for i, ln in enumerate(lines) if g['highlight'] in ln]
        if not hit:
            ctx.fail(f'prompt-card: highlight {g["highlight"]!r} is not in any line')
        hi = [k for k, (i, _) in enumerate(rows) if i == hit[0]]
    pause = g.get('captions', 'pause') != 'keep'
    pick = None
    for vis in (6, 5, 4):
        H = HDR + 2 * PAD + vis * LH
        r = L.above_head(ctx, 'prompt-card', W, H, a, end, scales=(1.0, .86, .78), fallback=False)
        if r:
            pick = (vis, H) + r
            break
    if not pick:
        vis = 4
        H = HDR + 2 * PAD + vis * LH
        pick = (vis, H) + L.fitspot(ctx, 'prompt-card', W, H, a, end, pause=pause)
    vis, H, x, y, sc = pick
    vis = min(vis, len(rows))
    H = HDR + 2 * PAD + vis * LH
    L.claim(ctx, x, y, W * sc, H * sc, a, end, pause)
    # scroll so the highlighted rows sit in the middle of the view when the box draws
    first = 0
    if hi:
        first = max(0, min(len(rows) - vis, hi[0] - (vis - len(hi)) // 2))
    elif len(rows) > vis:
        first = len(rows) - vis
    dist = first * LH
    body = ''.join(f'<div class="ln r{k}">{ctx.esc(t) if t.strip() else "&#8203;"}</div>' for k, (_, t) in enumerate(rows))
    box = arrow = ''
    if hi:
        bt = PAD + (hi[0] - first) * LH - 4
        bh = len(hi) * LH + 8
        bw = max(len(rows[k][1]) for k in hi) * CH + 24
        box = f'<div class="hl" style="top:{HDR + bt:.0f}px;left:{PAD - 12}px;width:{bw:.0f}px;height:{bh:.0f}px"></div>'
        ty = HDR + bt + bh / 2
        tx = PAD - 12 + bw + 8
        sx, sy = W - 26, max(HDR + 8, ty - 120)
        d = f'M{sx:.0f},{sy:.0f} C{sx + 10:.0f},{(sy + ty) / 2:.0f} {tx + 70:.0f},{ty - 40:.0f} {tx + 6:.0f},{ty:.0f}'
        ang = math.atan2(ty - (ty - 40), tx + 6 - (tx + 70))
        hx = lambda s: tx + 6 + 26 * math.cos(ang + math.pi + s)
        hy = lambda s: ty + 26 * math.sin(ang + math.pi + s)
        head = f'M{hx(-.5):.0f},{hy(-.5):.0f} L{tx + 6:.0f},{ty:.0f} L{hx(.5):.0f},{hy(.5):.0f}'
        arrow = (f'<svg class="pa" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><path class="p1" d="{d}" pathLength="1"/>'
                 f'<path class="p2" d="{head}" pathLength="1"/></svg>')
    label = ctx.esc(g.get('label', 'COPY'))
    html = (f'<div class="fx-prompt-card" style="width:{W}px;height:{H}px"><div class="hd"><span class="ti">Paste this into <em>{ctx.esc(g["tool"])}</em></span>'
            f'<span class="pill">{label}</span></div>'
            f'<div class="vp" style="top:{HDR}px;height:{H - HDR}px"><div class="list" style="top:{PAD}px">{body}</div></div>{box}{arrow}</div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    S, q = f'#{cid}', ctx.q
    ctx.tw(f"tl.fromTo('{S} .fx-prompt-card',{{opacity:0,y:50,scale:.94}},{{opacity:1,y:0,scale:1,duration:.4,ease:'back.out(1.5)',immediateRender:false}},{q(a)});")
    # rows outside the view are hidden; as the list scrolls each row fades at the edge (a clipping box would cut text mid-line)
    for k in range(len(rows)):
        if not 0 <= k < vis:
            ctx.tw(f"gsap.set('{S} .r{k}',{{opacity:0}});")
    t0, T = a + .45, max(.35, th - a - .55)
    if dist > 0:
        ctx.tw(f"tl.fromTo('{S} .list',{{y:0}},{{y:{-dist},duration:{T:.3f},ease:'sine.inOut',immediateRender:false}},{q(t0)});")

        def when(s):
            p = min(1, max(0, s / dist))
            return t0 + T * math.acos(1 - 2 * p) / math.pi
        for k in range(len(rows)):
            top = k * LH
            if k < first:                                   # leaves at the top
                ta, tb = when(top - LH * .55), when(top + LH * .15)
                ctx.tw(f"tl.to('{S} .r{k}',{{opacity:0,duration:{max(.04, tb - ta):.3f},ease:'none'}},{q(ta)});")
            if vis <= k < first + vis:                      # arrives at the bottom
                s_in = (k + 1) * LH - vis * LH
                ta, tb = when(s_in - LH * .9), when(s_in - LH * .1)
                ctx.tw(f"tl.fromTo('{S} .r{k}',{{opacity:0}},{{opacity:1,duration:{max(.04, tb - ta):.3f},ease:'none',immediateRender:false}},{q(ta)});")
    if hi:
        ctx.tw(f"gsap.set('{S} .hl',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('{S} .hl',{{opacity:0,scaleX:.6,transformOrigin:'0% 50%'}},{{opacity:1,scaleX:1,duration:.22,ease:'power3.out',immediateRender:false}},{q(th)});")
        ctx.tw(f"gsap.set('{S} .pa path',{{strokeDasharray:1,strokeDashoffset:1}});")
        ctx.tw(f"tl.to('{S} .pa .p1',{{strokeDashoffset:0,duration:.3,ease:'power2.out'}},{q(th + .12)});")
        ctx.tw(f"tl.to('{S} .pa .p2',{{strokeDashoffset:0,duration:.12,ease:'power2.out'}},{q(th + .4)});")
        ctx.sfx(g.get('sfx'), th + .12, .35)
    ctx.tw(f"tl.to('{S} .fx-prompt-card',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(end - .22)});")


def describe(g, beat):
    hl = f'; the line “{g["highlight"]}” gets boxed and a red arrow points at it' if g.get('highlight') else ''
    return f'On “{g["on"]}” a “Paste this into {g["tool"]}” card drops in and its prompt scrolls{hl}. It holds {beat["hold"]:.1f} s.'
