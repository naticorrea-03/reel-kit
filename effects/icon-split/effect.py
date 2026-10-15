"""Icon split: an app icon sits above the head and cracks in two on the phrase where the speaker drops it."""
import importlib.util, os, sys

META = {
    'id': 'icon-split', 'name': 'Icon break-up', 'category': 'media',
    'when': 'The speaker quits, replaces or breaks up with a named tool ("you can break up with X", "I cancelled X", "X is done").',
    'never': 'Never a tool nobody names. Never a logo you have no rights to: use your own icon file or the letter tile. Never covers a face.',
    'params': {'on': 'phrase where the icon pops in', 'name': 'the tool name (required; the letter tile uses its first letter)',
               'src': 'icon image file (optional)', 'split_on': 'phrase where it cracks, default 0.8 s in', 'hold': 'seconds after the crack, default 1.0',
               'sfx': 'sound on the crack, default crack ("none" for silence)'},
    'sfx': ['crack'], 'source': 'ours', 'credit': 'Motion idea inspired by an Instagram reel on switching video tools (Oct 2026)', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


S = 210
CRACK = [(52, 0), (45, 18), (56, 37), (44, 58), (54, 78), (47, 100)]


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'name')
    a0 = ctx.at(g['on'])[0]
    ts = max(a0 + .5, ctx.at(g['split_on'], a0)[0]) if g.get('split_on') else a0 + .8
    a, end = L.window(ctx, g, 1.0, last=ts)
    W = S + 120
    x, y, sc = L.above_head(ctx, 'icon-split', W, S + 40, a, end)
    L.claim(ctx, x, y, W * sc, (S + 40) * sc, a, end)
    url = ctx.asset(g['src']) if g.get('src') else None
    face = f'<img src="{url}">' if url else f'<span>{ctx.esc(g["name"][:1].upper())}</span>'
    left = 'polygon(0 0,' + ','.join(f'{px}% {py}%' for px, py in CRACK) + ',0 100%)'
    right = 'polygon(100% 0,' + ','.join(f'{px}% {py}%' for px, py in CRACK) + ',100% 100%)'
    html = (f'<div class="fx-icon-split" style="width:{W}px;height:{S + 40}px"><div class="ic">'
            f'<div class="hf lf" style="clip-path:{left}"><div class="tile">{face}</div></div>'
            f'<div class="hf rt" style="clip-path:{right}"><div class="tile">{face}</div></div></div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .ic',{{opacity:0,scale:.3,rotation:-12}},{{opacity:1,scale:1,rotation:0,duration:.45,ease:'back.out(2.2)',immediateRender:false}},{q(a)});")
    ctx.tw(f"tl.fromTo('#{cid} .ic',{{y:0}},{{y:-8,duration:.45,yoyo:true,repeat:{max(0, int((ts - a - .45) / .45))},ease:'sine.inOut',immediateRender:false}},{q(a + .45)});")
    ctx.tw(f"tl.fromTo('#{cid} .ic',{{x:0}},{{x:6,duration:.04,yoyo:true,repeat:3,ease:'none',immediateRender:false}},{q(ts - .1)});")
    ctx.tw(f"tl.fromTo('#{cid} .lf',{{x:0,y:0,rotation:0}},{{x:-32,y:14,rotation:-16,duration:.34,ease:'power3.out',immediateRender:false}},{q(ts)});")
    ctx.tw(f"tl.fromTo('#{cid} .rt',{{x:0,y:0,rotation:0}},{{x:32,y:-6,rotation:15,duration:.34,ease:'power3.out',immediateRender:false}},{q(ts)});")
    ctx.tw(f"tl.to('#{cid} .lf',{{y:40,rotation:-24,duration:{end - ts - .3:.2f},ease:'power1.in'}},{q(ts + .34)});")
    ctx.tw(f"tl.to('#{cid} .rt',{{y:30,rotation:22,duration:{end - ts - .3:.2f},ease:'power1.in'}},{q(ts + .34)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.2}},{q(end - .2)});")
    ctx.sfx(g.get('sfx', 'crack'), ts, .4)


def describe(g, beat):
    return f'On “{g["on"]}” the {g["name"]} icon pops in above the head and cracks in two{" on “" + g["split_on"] + "”" if g.get("split_on") else ""}. It holds {beat["hold"]:.1f} s.'
