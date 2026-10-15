"""Flip clock: a split-flap clock above the head flips through the times the speaker walks through."""
import importlib.util, os, re, sys

META = {
    'id': 'flip-clock', 'name': 'Split-flap clock', 'category': 'data',
    'when': 'Hours pass or a schedule runs: "from six a.m. to midnight", "every waking hour", "it ran all night". The times are real.',
    'never': 'Never times the story does not give. Never more than 8 steps. Never covers a face.',
    'params': {'on': 'phrase that brings the clock in', 'steps': 'list of "HH:MM" strings, or {"time", "on"}; 2 to 8; the first shows on arrival',
               'step': 'seconds between steps without their own "on", default 0.32', 'label': 'small line under the clock, optional',
               'hold': 'seconds after the last flip, default 1.2', 'sfx': 'sound for the run of flips, default split-flap ("none" for silence)'},
    'sfx': ['split-flap'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


TW, TH = 96, 140    # one digit tile


def _digit(ch, cls):
    """one face of a tile: the glyph drawn as svg, split into a top and a bottom half."""
    svg = (f'<svg viewBox="0 0 {TW} {TH}" width="{TW}" height="{TH}"><text x="{TW / 2}" y="{TH * .5}" text-anchor="middle" '
           f'dominant-baseline="central">{ch}</text></svg>')
    return f'<div class="f {cls}"><div class="h t">{svg}</div><div class="h b">{svg}</div></div>'


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'steps')
    steps = [s if isinstance(s, dict) else {'time': s} for s in g['steps']]
    if not 2 <= len(steps) <= 8 or not all(re.fullmatch(r'\d\d:\d\d', str(s.get('time', ''))) for s in steps):
        ctx.fail(f'flip-clock on {g["on"]!r} needs 2 to 8 steps written "HH:MM"')
    st = float(g.get('step', .32))
    ts = L.times(ctx, g, steps, st, key='on')
    ts = [ts[0] + .45] + [max(t, ts[0] + .45 + st * (k + 1)) for k, t in enumerate(ts[1:])]
    for k in range(1, len(ts)):
        ts[k] = max(ts[k], ts[k - 1] + .3)
    a, end = L.window(ctx, g, 1.2, last=ts[-1] + .3)
    lab = g.get('label', '')
    lfs = L.fit(ctx, 'flip-clock label', [lab], 4 * TW + 120, 42, 34, 1, .55) if lab else 0
    W = 4 * (TW + 10) + 46 + 2 * 22
    H = TH + 2 * 22 + (int(lfs * 1.3) + 12 if lab else 0)
    x, y, sc = L.above_head(ctx, 'flip-clock', W, H, a, end)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    vals = [s['time'].replace(':', '') for s in steps]
    tiles, flips = '', []
    for p in range(4):
        faces, seq = '', [vals[0][p]]
        idx = [0]
        for k in range(1, len(vals)):
            if vals[k][p] != seq[-1]:
                seq.append(vals[k][p])
                flips.append((p, len(seq) - 1, ts[k]))
        for j, ch in enumerate(seq):
            faces += _digit(ch, f'f{j}')
        tiles += f'<div class="dg d{p}">{faces}<i class="ax"></i></div>' + ('<div class="cl"><b></b><b></b></div>' if p == 1 else '')
    html = (f'<div class="fx-flip-clock" style="width:{W}px"><div class="row">{tiles}</div>'
            + (f'<div class="lb" style="font-size:{lfs}px">{ctx.esc(lab)}</div>' if lab else '') + '</div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .fx-flip-clock',{{opacity:0,y:-40,scale:.94}},{{opacity:1,y:0,scale:1,duration:.4,ease:'back.out(1.7)',immediateRender:false}},{q(a)});")
    # stacking: older tops sit above newer tops; newer bottoms sit above older bottoms
    for p in range(4):
        n = 1 + sum(1 for f in flips if f[0] == p)
        for j in range(n):
            ctx.tw(f"gsap.set('#{cid} .d{p} .f{j} .t',{{zIndex:{100 - j},opacity:{1 if j == 0 else 0}}});")
            ctx.tw(f"gsap.set('#{cid} .d{p} .f{j} .b',{{zIndex:{j + 1},opacity:{1 if j == 0 else 0}}});")
    for p, j, t in flips:
        d = f'#{cid} .d{p}'
        ctx.tw(f"tl.fromTo('{d} .f{j} .t',{{opacity:0}},{{opacity:1,duration:.01,immediateRender:false}},{q(t)});")
        ctx.tw(f"tl.fromTo('{d} .f{j - 1} .t',{{rotationX:0,filter:'brightness(1)'}},{{rotationX:-90,filter:'brightness(.55)',duration:.11,ease:'power1.in',immediateRender:false}},{q(t)});")
        ctx.tw(f"tl.fromTo('{d} .f{j - 1} .t',{{opacity:1}},{{opacity:0,duration:.01,immediateRender:false}},{q(t + .11)});")
        ctx.tw(f"tl.fromTo('{d} .f{j} .b',{{opacity:0,rotationX:90,filter:'brightness(1.5)'}},{{opacity:1,rotationX:90,duration:.01,immediateRender:false}},{q(t + .1)});")
        ctx.tw(f"tl.fromTo('{d} .f{j} .b',{{rotationX:90,filter:'brightness(1.5)'}},{{rotationX:0,filter:'brightness(1)',duration:.15,ease:'bounce.out',immediateRender:false}},{q(t + .11)});")
        ctx.tw(f"tl.fromTo('{d} .f{j - 1} .b',{{opacity:1}},{{opacity:0,duration:.01,immediateRender:false}},{q(t + .27)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(end - .22)});")
    if flips:
        ctx.sfx(g.get('sfx', 'split-flap'), ts[1], .4, cap=ts[-1] - ts[1] + .4)


def describe(g, beat):
    st = [s if isinstance(s, str) else s['time'] for s in g['steps']]
    return f'On “{g["on"]}” a split-flap clock lands above the head and flips {" → ".join(st)}. It holds {beat["hold"]:.1f} s.'
