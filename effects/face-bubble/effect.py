"""Face bubble: the speaker shrinks into a round picture-in-picture bubble with a gold ring while a brand plate fills the frame
with a screenshot (cards can swap on their phrases). The spoken words run above the bubble, then the bubble opens back to full frame."""
import importlib.util, math, os, sys

META = {
    'id': 'face-bubble', 'name': 'Face bubble', 'category': 'structure',
    'when': 'The thing on screen matters more than the face for a few seconds (a site, a tool, a feed), but the speaker should stay present.',
    'never': 'Never under 1.8 s. Never across a shot cut. Never twice in a row: the second one reads as a broken frame.',
    'params': {'on': 'phrase where the bubble closes', 'src': 'screenshot for the page (or use "cards")',
               'cards': '[{"src", "on", "crop"}] 1 to 3 screenshots; each swaps in on its phrase', 'crop': '[x, y, w, h] in image pixels for "src"',
               'corner': '"right" (default, bottom right) or "center" (bottom centre)', 'plate': '"dark" (default) or "light"',
               'words': 'true (default) runs the spoken words above the bubble', 'hold': 'seconds, default 3.0', 'until': 'phrase where it opens',
               'sfx': 'optional sound name'},
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
        ctx.fail(f'face-bubble on {g["on"]!r} needs "src" or 1 to 3 "cards" with "src"')
    a, end = L.window(ctx, g, 3.0, min_after=1.8)
    h = H.open(L, ctx, g, 'bubble', a, end, 'face-bubble')
    a, end, s0, s1 = h['a'], h['end'], h['c0'], h['c1']
    x0, y0, x1, y1 = h['region']
    built = [H.shot(ctx, c, x1 - x0, y1 - y0) for c in cards]
    hmax = max(hh for _, _, hh in built)
    top = y0 + (y1 - y0 - hmax) // 2
    for _, w, hh in built:
        box = ((1080 - w) / 2, top, (1080 + w) / 2, top + hh)
        if L.face_share(box, h['fz']) > .002 or L.unsafe(box):
            ctx.fail(f'face-bubble on {g["on"]!r}: the screenshot does not fit the bubble layout clear of the face')
    ts = [max(t, s0) for t in L.times(ctx, g, cards, (s1 - s0) / len(cards), key='on')]
    if any(t > s1 - .5 for t in ts[1:]):
        ctx.fail(f'face-bubble on {g["on"]!r}: a card swaps in under 0.5 s before the layout closes; move its "on" earlier')
    shots = ''.join(f'<div class="card k{k}" style="left:{(1080 - w) // 2}px;top:{top + (hmax - hh) // 2}px;width:{w}px">{html}</div>'
                    for k, (html, w, hh) in enumerate(built))
    ctx._uid += 1
    wrap = f'bubblec{ctx._uid}'
    ctx.clip(ctx.front, a, end, f'<div class="fx-face-bubble{" dark" if h["dark"] else ""}">{shots}</div>', 'position:absolute;inset:0;', wrap)
    q = ctx.q
    ctx.tw(f"gsap.set('.{wrap} .card',{{opacity:0}});")
    for k, t in enumerate(ts):
        if k == 0:
            ctx.tw(f"tl.fromTo('.{wrap} .k0',{{opacity:0,y:60,scale:.94}},{{opacity:1,y:0,scale:1,duration:.34,ease:'power3.out',immediateRender:false}},{q(t)});")
        else:
            ctx.tw(f"tl.to('.{wrap} .k{k - 1}',{{opacity:0,y:-50,scale:.94,duration:.2,ease:'power2.in'}},{q(t)});")
            ctx.tw(f"tl.fromTo('.{wrap} .k{k}',{{opacity:0,y:60,scale:.94}},{{opacity:1,y:0,scale:1,duration:.32,ease:'power3.out',immediateRender:false}},{q(t + .08)});")
    ctx.tw(f"tl.to('.{wrap} .k{len(cards) - 1}',{{opacity:0,duration:.14}},{q(s1 - .2)});")
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    n = len(g.get('cards') or [1])
    where = 'bottom centre' if g.get('corner') == 'center' else 'bottom right'
    return (f'On “{g["on"]}” the speaker shrinks into a round bubble at the {where} with a gold ring; '
            f'{"a screenshot" if n == 1 else f"{n} screenshots, swapping on their phrases,"} fill the {g.get("plate", "dark")} page above, '
            f'the spoken words between them. It holds {beat["hold"]:.1f} s, then the bubble opens back to full frame. Captions pause.')
