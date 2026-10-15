"""Film strip: sprocket borders slide in on both edges and the picture goes warm and faded, like old film, for a memory beat."""
import importlib.util, os, sys

META = {
    'id': 'film-strip', 'name': 'Film memory', 'category': 'structure',
    'when': 'A memory or a past moment the speaker tells as a story ("last Thanksgiving", "back in 2019", "when I was a kid"), or a line about film itself.',
    'never': 'Never for the present tense. Never more than once a reel. The date stamp, if any, is the real date or place.',
    'params': {'on': 'phrase where the film look starts', 'until': 'phrase where it ends (optional; else hold)',
               'stamp': 'small date stamp in the corner, e.g. "OCT 12 2019" (optional)', 'hold': 'seconds, default 2.4',
               'sfx': 'optional sound name (film-projector for a film reference)'},
    'sfx': ['film-projector'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


BAR = 64   # border width; it lives outside the text safe zone and carries no text, so it is drawn on the wrapper itself


def build(g, ctx):
    L = _lib()
    a, end = L.window(ctx, g, 2.4, min_after=1.0)
    ctx._uid += 1
    wrap = f'film{ctx._uid}'
    hole = 'color-mix(in srgb,var(--c-card) 70%,var(--c-ink))'
    bar = 'color-mix(in srgb,var(--c-ink) 92%,black)'
    bgs = (f"repeating-linear-gradient(180deg,transparent 0 14px,{hole} 14px 34px,transparent 34px 44px) left calc(var(--bx) + 22px) top var(--by) / 20px 200% no-repeat,"
           f"repeating-linear-gradient(180deg,transparent 0 14px,{hole} 14px 34px,transparent 34px 44px) right calc(var(--bx) + 22px) top var(--by) / 20px 200% no-repeat,"
           f"linear-gradient({bar},{bar}) left var(--bx) top 0 / {BAR}px 100% no-repeat,"
           f"linear-gradient({bar},{bar}) right var(--bx) top 0 / {BAR}px 100% no-repeat,"
           f"radial-gradient(120% 80% at 50% 45%,transparent 55%,color-mix(in srgb,var(--c-shadow) 45%,transparent) 100%)")
    stamp = ''
    if g.get('stamp'):
        fs = 46
        w = len(g['stamp']) * fs * .62
        sx, sy = 120, 1380
        if L.face_share((sx, sy, sx + w, sy + fs * 1.3), L.faces(ctx, a, end)) > .002:
            sx, sy = 120, 270
        stamp = f'<div class="ds" style="left:{sx}px;top:{sy}px;font-size:{fs}px">{ctx.esc(g["stamp"])}</div>'
        if sy > 1200:
            ctx.lowbusy.append((a, end))
    ctx.clip(ctx.front, a, end, f'<div class="fx-film-strip"><div class="gr"></div>{stamp}</div>',
             f'position:absolute;inset:0;--bx:-{BAR + 10}px;--by:0px;background:{bgs};', wrap)
    q = ctx.q
    ctx.tw(f"tl.fromTo('.{wrap}',{{'--bx':'-{BAR + 10}px'}},{{'--bx':'0px',duration:.32,ease:'power3.out',immediateRender:false}},{q(a)});")
    ctx.tw(f"tl.fromTo('.{wrap}',{{'--by':'0px'}},{{'--by':'{int((end - a) * 90)}px',duration:{end - a:.2f},ease:'none',immediateRender:false}},{q(a)});")
    ctx.tw(f"tl.fromTo('.{wrap} .gr',{{opacity:0}},{{opacity:1,duration:.3,immediateRender:false}},{q(a)});")
    if stamp:
        ctx.tw(f"gsap.set('.{wrap} .ds',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('.{wrap} .ds',{{opacity:0}},{{opacity:1,duration:.05,immediateRender:false}},{q(a + .35)});")
    ctx.tw(f"tl.to('.{wrap}',{{'--bx':'-{BAR + 10}px',duration:.25,ease:'power2.in'}},{q(end - .25)});")
    ctx.tw(f"tl.to('.{wrap} .gr, .{wrap} .ds',{{opacity:0,duration:.25}},{q(end - .25)});")
    ctx.sfx(g.get('sfx'), a, .3, cap=end - a)


def describe(g, beat):
    return (f'On “{g["on"]}” film sprocket borders slide in on both edges and the picture goes warm and faded'
            f'{" with a “" + g["stamp"] + "” date stamp" if g.get("stamp") else ""}. It holds {beat["hold"]:.1f} s.')
