"""Letter drop: a payoff word in big serif capitals behind the head, its letters dropping in one at a time from above."""
import importlib.util, os, sys

META = {
    'id': 'letter-drop', 'name': 'Letter drop', 'category': 'text',
    'when': 'One short payoff word lands the line ("money.", "time.", "soon."). Use it once or twice a reel, on the word itself.',
    'never': 'Never a filler word. Never more than 10 letters. Never on a wide shot.',
    'params': {'on': 'phrase the word lands on (usually the word itself)', 'word': 'the word, with its full stop if you want one (required)',
               'case': 'upper (default) or as-is', 'hold': 'seconds, default 1.4', 'sfx': 'optional sound name'},
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


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'word')
    word = str(g['word'])
    word = word.upper() if g.get('case', 'upper') == 'upper' else word
    if len(word) > 10:
        ctx.fail(f'letter-drop {word!r} is longer than 10 letters; use one short word')
    if ctx.has_cut and ctx.face_scale_at(ctx.at(g['on'])[0]) < .075:
        ctx.fail(f'letter-drop {word!r} lands on a wide shot; the heads cover the band')
    a, end = L.window(ctx, g, 1.4, min_after=.8)
    a -= .12
    layer, size, top = L.wall_band(ctx, f'letter-drop {word!r}', word, a, end, 250, 110, .68, .95)
    W = len(word) * .68 * size
    ink, tone = L.wall_ink(ctx, a, end, (540 - W / 2, top, 540 + W / 2, top + size))
    spans = ''.join(f'<span class="lt l{i}">{ctx.esc(c) if c != " " else "&nbsp;"}</span>' for i, c in enumerate(word))
    cid = ctx.clip(layer, a, end, f'<div class="fx-letter-drop {tone}" style="font-size:{size}px;color:{ink}">{spans}</div>',
                   f'position:absolute;left:0;right:0;top:{top}px;', 'wallz' if layer is ctx.wall else '')
    q = ctx.q
    n = len(word)
    step = min(.075, .5 / max(1, n))
    for i in range(n):
        r = (-1) ** i * (6 + 5 * (i % 3))
        ctx.tw(f"gsap.set('#{cid} .l{i}',{{opacity:0}});")
        t = a + i * step   # the letter falls in from half its height above; it turns opaque only as it lands (the top UI band stays clear)
        ctx.tw(f"tl.fromTo('#{cid} .l{i}',{{y:{-int(size * .55)},rotation:{r}}},{{y:0,rotation:0,duration:.42,ease:'back.out(1.6)',immediateRender:false}},{q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .l{i}',{{opacity:0}},{{opacity:1,duration:.16,ease:'power1.in',immediateRender:false}},{q(t + .1)});")
        ctx.tw(f"tl.to('#{cid} .l{i}',{{y:{int(size * .45)},opacity:0,rotation:{-r / 2:.0f},duration:.22,ease:'power2.in'}},{q(end - .3 + i * .02)});")
    ctx.topbusy.append((a, end))
    L.reserve(ctx, (540 - W / 2, top, 540 + W / 2, top + size), a, end)
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    where = 'behind the head' if beat['onwall'] else 'above the head'
    return f'On “{g["on"]}” the letters of "{g["word"]}" drop in one by one {where} and fall away after {beat["hold"]:.1f} s.'
