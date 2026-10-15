"""Split screen: a hard half and half. The top half is a brand plate carrying a screenshot (cards can swap on their phrases),
the speaker slides into the bottom half with the face centred in it, and the spoken words run one at a time on the seam."""
import importlib.util, os, sys

META = {
    'id': 'split-screen', 'name': 'Split screen', 'category': 'structure',
    'when': 'The speaker walks through something you can show for a few seconds (a site, a tool, a doc) and the face should stay on screen the whole time.',
    'never': 'Never under 1.6 s (the slide in and out eats half of it). Never across a shot cut. Never a screenshot whose words are too small to read at half height.',
    'params': {'on': 'phrase where the split opens', 'src': 'screenshot for the top half (or use "cards")',
               'cards': '[{"src", "on", "crop"}] 1 to 3 screenshots; each swaps in on its phrase', 'crop': '[x, y, w, h] in image pixels for "src"',
               'plate': '"light" (default, cream) or "dark"', 'words': 'true (default) runs the spoken words on the seam; false leaves the seam bare',
               'hold': 'seconds, default 2.8', 'until': 'phrase where it closes', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by Instagram creator edits (reel DeR2ZTgtTp9, Oct 2026)', 'license': 'MIT',
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
    H = L.hosts()
    cards = g.get('cards') or ([{'src': g['src'], 'crop': g.get('crop')}] if g.get('src') else [])
    if not 1 <= len(cards) <= 3 or not all(isinstance(c, dict) and c.get('src') for c in cards):
        ctx.fail(f'split-screen on {g["on"]!r} needs "src" or 1 to 3 "cards" with "src"')
    a, end = L.window(ctx, g, 2.8, min_after=1.6)
    h = H.open(L, ctx, g, 'split', a, end, 'split-screen')
    a, end, s0, s1 = h['a'], h['end'], h['c0'], h['c1']
    x0, y0, x1, y1 = h['region']
    built = [H.shot(ctx, c, x1 - x0, y1 - y0) for c in cards]
    hmax = max(hh for _, _, hh in built)
    top = y0 + (y1 - y0 - hmax) // 2
    for _, w, hh in built:
        box = ((1080 - w) / 2, top, (1080 + w) / 2, top + hh)
        if L.face_share(box, h['fz']) > .002 or L.unsafe(box):
            ctx.fail(f'split-screen on {g["on"]!r}: the screenshot does not fit the split layout clear of the face')
    ts = [max(t, s0) for t in L.times(ctx, g, cards, (s1 - s0) / len(cards), key='on')]
    if any(t > s1 - .5 for t in ts[1:]):
        ctx.fail(f'split-screen on {g["on"]!r}: a card swaps in under 0.5 s before the layout closes; move its "on" earlier')
    shots = ''.join(f'<div class="card k{k}" style="left:{(1080 - w) // 2}px;top:{top + (hmax - hh) // 2}px;width:{w}px">{html}</div>'
                    for k, (html, w, hh) in enumerate(built))
    ctx._uid += 1
    wrap = f'splitc{ctx._uid}'
    ctx.clip(ctx.front, a, end, f'<div class="fx-split-screen{" dark" if h["dark"] else ""}">{shots}</div>', 'position:absolute;inset:0;', wrap)
    q = ctx.q
    ctx.tw(f"gsap.set('.{wrap} .card',{{opacity:0}});")
    for k, t in enumerate(ts):
        if k == 0:
            ctx.tw(f"tl.fromTo('.{wrap} .k0',{{opacity:0,y:40,scale:.96}},{{opacity:1,y:0,scale:1,duration:.32,ease:'power3.out',immediateRender:false}},{q(t)});")
        else:
            ctx.tw(f"tl.to('.{wrap} .k{k - 1}',{{opacity:0,x:-90,duration:.2,ease:'power2.in'}},{q(t)});")
            ctx.tw(f"tl.fromTo('.{wrap} .k{k}',{{opacity:0,x:90}},{{opacity:1,x:0,duration:.3,ease:'power3.out',immediateRender:false}},{q(t + .08)});")
    ctx.tw(f"tl.to('.{wrap} .k{len(cards) - 1}',{{opacity:0,duration:.14}},{q(s1 - .2)});")
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    n = len(g.get('cards') or [1])
    return (f'On “{g["on"]}” the frame splits in half: {"a screenshot" if n == 1 else f"{n} screenshots, swapping on their phrases,"} on a '
            f'{"dark" if g.get("plate") == "dark" else "cream"} plate up top, the speaker in the bottom half, the spoken words on the seam. '
            f'It holds {beat["hold"]:.1f} s. Captions pause.')
