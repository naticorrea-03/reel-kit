"""Keycap rain: keyboard keys (shortcuts) rain down and pile up above the speaker's head."""
import importlib.util, os, random, sys

META = {
    'id': 'keycap-rain', 'name': 'Keycap rain', 'category': 'media',
    'when': 'The speaker talks about keyboard work, shortcuts or hours of manual editing ("all the shortcuts", "I used to do it by hand").',
    'never': 'Never random letters: the keys are real shortcuts for the task. Never more than 18 keys. Never covers a face.',
    'params': {'on': 'phrase where the keys start falling', 'keys': 'list of 6 to 18 key labels, e.g. ["⌘K", "J", "K", "L", "space"]',
               'hold': 'seconds after the last key lands, default 1.0', 'sfx': 'sound for the pile landing, default keycaps ("none" for silence)'},
    'sfx': ['keycaps'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


K, GAP = 96, 12      # a 1u key and the gap between keys in the pile


def build(g, ctx):
    L = _lib()
    keys = [str(k) for k in (g.get('keys') or [])]
    if not 6 <= len(keys) <= 18:
        ctx.fail(f'keycap-rain on {g["on"]!r} needs 6 to 18 keys')
    n = len(keys)
    step = min(.07, 1.1 / n)
    a0 = ctx.at(g['on'])[0]
    a, end = L.window(ctx, g, 1.0, last=a0 + .5 + step * n)
    widths = [K * (2.4 if len(k) > 3 else 1.4 if len(k) > 1 else 1) for k in keys]
    # pile: rows of keys, widest row at the bottom, centred on the head
    W = 640
    rows, cur, cw = [], [], 0
    for i in sorted(range(n), key=lambda i: -widths[i]):
        if cur and cw + widths[i] + GAP > W:
            rows.append(cur)
            cur, cw = [], 0
        cur.append(i)
        cw += widths[i] + GAP
    rows.append(cur)
    H = len(rows) * (K + 6) + 20
    x, y, sc = L.above_head(ctx, 'keycap-rain', W + 40, H, a, end)
    L.claim(ctx, x, y, (W + 40) * sc, H * sc, a, end)
    rnd = random.Random(''.join(keys))
    pos = {}
    for r, row in enumerate(rows):
        rw = sum(widths[i] for i in row) + GAP * (len(row) - 1)
        cx = 20 + (W - rw) / 2 + rnd.uniform(-20, 20)
        for i in row:
            pos[i] = (cx, H - (r + 1) * (K + 6), rnd.uniform(-9, 9))
            cx += widths[i] + GAP
    caps = ''
    for i, k in enumerate(keys):
        px, py, rot = pos[i]
        dark = ' dk' if rnd.random() < .22 else ''
        fs = 40 if len(k) <= 2 else 30
        caps += (f'<div class="kc k{i}{dark}" style="left:{px:.0f}px;top:{py:.0f}px;width:{widths[i]:.0f}px;--r:{rot:.1f}deg">'
                 f'<span style="font-size:{fs}px">{ctx.esc(k)}</span></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, f'<div class="fx-keycap-rain" style="width:{W + 40}px;height:{H}px">{caps}</div>',
                  f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    order = sorted(range(n), key=lambda i: (-pos[i][1], rnd.random()))   # bottom row lands first
    for j, i in enumerate(order):
        px, py, rot = pos[i]
        t = a + j * step
        drop = py + K + 30   # falls from just above the pile box; turns opaque only on the way in
        ctx.tw(f"gsap.set('#{cid} .k{i}',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .k{i}',{{y:{-drop:.0f},rotation:{rot * 4:.0f}}},{{y:0,rotation:{rot:.1f},duration:.42,ease:'bounce.out',immediateRender:false}},{q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .k{i}',{{opacity:0}},{{opacity:1,duration:.12,immediateRender:false}},{q(t + .08)});")
    ctx.tw(f"tl.to('#{cid} .kc',{{y:-24,opacity:0,scale:.9,duration:.25,stagger:.012,ease:'power2.in'}},{q(end - .3)});")
    ctx.sfx(g.get('sfx', 'keycaps'), a + .3, .4, cap=step * n + .5)


def describe(g, beat):
    return f'On “{g["on"]}” keyboard keys ({", ".join(g["keys"][:5])}...) rain down and pile up above the head. It holds {beat["hold"]:.1f} s.'
