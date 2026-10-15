"""Slot number: one huge number behind the head, every digit a slot-machine reel that spins and lands left to right."""
import importlib.util, os, random, sys

META = {
    'id': 'slot-number', 'name': 'Slot reel number', 'category': 'data',
    'when': 'One big round number is the whole point of the line ("a hundred thousand comments", "two million views"). The unit word says what it counts.',
    'never': 'Never a number nobody says. Never more than 9 characters. Never on a wide shot (the heads cover the band).',
    'params': {'on': 'phrase the number lands on', 'value': 'the number as it should read, e.g. "100,000" or "$2.4M" (required)',
               'unit': 'one or two words under it in italic, e.g. "comments." (optional)', 'hold': 'seconds, default 2.0',
               'sfx': 'optional sound name (cash-register only for money)'},
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


SPIN = 14   # glyphs a reel passes before it lands


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'value')
    val = str(g['value'])
    if len(val) > 9:
        ctx.fail(f'slot-number {val!r} is longer than 9 characters; round it')
    if ctx.has_cut and ctx.face_scale_at(ctx.at(g['on'])[0]) < .075:
        ctx.fail(f'slot-number {val!r} lands on a wide shot; the heads cover the band')
    a, end = L.window(ctx, g, 2.0, min_after=1.0)
    a = a - .05
    unit = g.get('unit', '')
    lh = 1.0 + (.5 if unit else 0)
    layer, size, top = L.wall_band(ctx, f'slot-number {val!r}', val, a, end, 230, 110, .6, lh)
    cw = {c: (.66 if c.isdigit() else .3 if c in ',.' else .66) for c in val}
    widths = [cw[c] * size for c in val]
    W = sum(widths)
    x0 = 540 - W / 2
    ink, tone = L.wall_ink(ctx, a, end, (x0, top, x0 + W, top + size * lh))
    H = size * 1.0
    rnd = random.Random(val)
    cells = ''
    for i, c in enumerate(val):
        w = widths[i]
        if c.isdigit():
            seq = [str(rnd.randrange(10)) for _ in range(SPIN)] + [c]
            texts = ''.join(f'<text x="{w / 2:.1f}" y="{H * (k + .5):.1f}" text-anchor="middle" dominant-baseline="central">{d}</text>' for k, d in enumerate(seq))
            cells += f'<svg class="cell" width="{w:.1f}" height="{H:.0f}" viewBox="0 0 {w:.1f} {H:.0f}"><g class="rl r{i}">{texts}</g></svg>'
        else:
            cells += (f'<svg class="cell st s{i}" width="{w:.1f}" height="{H:.0f}" viewBox="0 0 {w:.1f} {H:.0f}"><text x="{w / 2:.1f}" y="{H * .5:.1f}" '
                      f'text-anchor="middle" dominant-baseline="central">{ctx.esc(c)}</text></svg>')
    un = f'<div class="un" style="font-size:{int(size * .36)}px">{ctx.esc(unit)}</div>' if unit else ''
    cid = ctx.clip(layer, a, end, f'<div class="fx-slot-number {tone}" style="--sz:{size}px;--ink:{ink}"><div class="nm">{cells}</div>{un}</div>',
                   f'position:absolute;left:0;right:0;top:{top}px;', 'wallz' if layer is ctx.wall else '')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .nm',{{opacity:0}},{{opacity:1,duration:.12,immediateRender:false}},{q(a)});")
    k = 0
    for i, c in enumerate(val):
        if c.isdigit():
            d = .62 + .09 * k
            ctx.tw(f"tl.fromTo('#{cid} .r{i}',{{y:0,filter:'blur(7px)'}},{{y:{-H * SPIN:.0f},filter:'blur(0px)',duration:{d:.2f},ease:'back.out(.9)',immediateRender:false}},{q(a)});")
            k += 1
        else:
            ctx.tw(f"tl.fromTo('#{cid} .s{i}',{{opacity:0,y:20}},{{opacity:1,y:0,duration:.25,ease:'power2.out',immediateRender:false}},{q(a + .3)});")
    if unit:
        ctx.tw(f"tl.fromTo('#{cid} .un',{{opacity:0,y:24,filter:'blur(8px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.35,ease:'power3.out',immediateRender:false}},{q(a + .62 + .09 * k)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-20,filter:'blur(8px)',duration:.2,ease:'power2.in'}},{q(end - .2)});")
    ctx.topbusy.append((a, end))
    L.reserve(ctx, (x0, top, x0 + W, top + size * lh), a, end)
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    where = 'behind the head' if beat['onwall'] else 'above the head'
    return (f'On “{g["on"]}” "{g["value"]}" spins in {where}, each digit a slot reel landing left to right'
            f'{", then “" + g["unit"] + "” fades in under it" if g.get("unit") else ""}. It holds {beat["hold"]:.1f} s.')
