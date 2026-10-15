"""Sign-up sheet: a clipboard drops onto the head, a pen writes a name on the first line, and an optional price tag swings in."""
import importlib.util, os, sys

META = {
    'id': 'signup-sheet', 'name': 'Sign-up sheet', 'category': 'social',
    'when': 'Putting a name down: "put your name on the list", "sign up", "RSVP". The written word is who signs (you, a name) and the tag is the deal.',
    'never': 'Never a deal nobody offers (the tag is optional). Never covers a face.',
    'params': {'on': 'phrase that drops the clipboard in', 'title': 'sheet title, default "Waitlist"', 'name': 'word the pen writes on line 1 (required, short)',
               'write_on': 'phrase where the pen writes, default 0.5 s in', 'tag': 'short word on a swinging price tag, e.g. "Free" (optional)',
               'tag_on': 'phrase where the tag swings in, default after the name', 'hold': 'seconds after the last beat, default 1.4',
               'sfx': 'sound while the pen writes, default pen-scribble ("none" for silence)'},
    'sfx': ['pen-scribble'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


W, H = 470, 350
PEN = ('<svg class="pen" viewBox="0 0 40 200" width="44" height="220"><path d="M14 0h12v150l-6 26-6-26z" fill="var(--c-accent2)"/>'
       '<path d="M14 150h12l-6 26z" fill="var(--c-card)"/><path d="M18 168h4l-2 8z" fill="var(--c-ink)"/><rect x="12" y="8" width="16" height="30" rx="3" fill="var(--c-ink)" opacity=".5"/></svg>')


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'name')
    a = ctx.at(g['on'])[0]
    tw = max(a + .5, ctx.at(g['write_on'], a)[0]) if g.get('write_on') else a + .5
    wd = min(1.1, .25 + .09 * len(g['name']))
    tg = None
    if g.get('tag'):
        tg = max(tw + wd, ctx.at(g['tag_on'], a)[0]) if g.get('tag_on') else tw + wd + .1
    a, end = L.window(ctx, g, 1.4, last=(tg or tw + wd) + .2)
    TAGW = 140 if tg else 0
    TOP = 70   # headroom for the clip, the pen and the tag string
    x, y, sc = L.above_head(ctx, 'signup-sheet', W + TAGW, H + TOP, a, end)
    L.claim(ctx, x, y, (W + TAGW) * sc, (H + TOP) * sc, a, end)
    title = g.get('title', 'Waitlist')
    hfs = L.fit(ctx, 'signup-sheet title', [title], W - 32 - 52 - 170, 46, 30, 1, .56)
    tagfs = min(54, int(150 / max(1, len(g.get('tag', '') or 'x')) / .78)) if tg else 0
    nfs = L.fit(ctx, 'signup-sheet name', [g['name']], W - 150, 92, 60, 1, .5)
    rows = ''.join(f'<div class="rw"><span class="no">{k}.</span><span class="ru">'
                   + (f'<span class="nm" style="font-size:{nfs}px">{ctx.esc(g["name"])}</span>' if k == 1 else '') + '</span></div>' for k in (1, 2, 3))
    tag = (f'<div class="tg" style="left:{W - 16}px"><i class="str"></i><div class="tb"><b></b><span style="font-size:{tagfs}px">{ctx.esc(g["tag"])}</span></div></div>') if tg else ''
    html = (f'<div class="fx-signup-sheet" style="width:{W + TAGW}px;height:{H + TOP}px;padding-top:{TOP}px;box-sizing:border-box"><div class="in2"><div class="bd" style="width:{W}px;height:{H}px">'
            f'<div class="clip"></div><div class="pp"><div class="hd"><span class="tt" style="font-size:{hfs}px">{ctx.esc(title)}</span><span class="sm">Sign up</span></div>{rows}</div>'
            f'<div class="pw">{PEN}</div></div>{tag}</div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .bd',{{y:-{L.drop_from(y, H, sc)},rotation:-6,opacity:0}},{{y:0,rotation:0,opacity:1,duration:.48,ease:'back.out(1.4)',immediateRender:false}},{q(a)});")
    # the name writes on through a soft-edged mask (a clip box would cut the letters mid-stroke for the layout audit)
    ctx.tw(f"gsap.set('#{cid} .nm',{{'--p':'-12%'}});")
    ctx.tw(f"tl.fromTo('#{cid} .nm',{{'--p':'-12%'}},{{'--p':'118%',duration:{wd:.2f},ease:'none',immediateRender:false}},{q(tw)});")
    nw = len(g['name']) * nfs * .5
    ctx.tw(f"gsap.set('#{cid} .pw',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .pw',{{opacity:0,x:-20,y:-12,rotation:24}},{{opacity:1,x:0,y:0,rotation:24,duration:.18,ease:'power2.out',immediateRender:false}},{q(tw - .18)});")
    ctx.tw(f"tl.fromTo('#{cid} .pw',{{x:0}},{{x:{nw:.0f},duration:{wd:.2f},ease:'none',immediateRender:false}},{q(tw)});")
    ctx.tw(f"tl.fromTo('#{cid} .pw',{{y:0}},{{y:-10,duration:{wd / 6:.3f},yoyo:true,repeat:5,ease:'sine.inOut',immediateRender:false}},{q(tw)});")
    ctx.tw(f"tl.to('#{cid} .pw',{{opacity:0,x:{nw + 40:.0f},y:-14,duration:.25,ease:'power2.in'}},{q(tw + wd + .05)});")
    ctx.sfx(g.get('sfx', 'pen-scribble'), tw, .35, cap=wd + .1)
    if tg:
        ctx.tw(f"gsap.set('#{cid} .tg',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .tg',{{opacity:0,y:-30}},{{opacity:1,y:0,duration:.2,ease:'power2.out',immediateRender:false}},{q(tg)});")
        ctx.tw(f"tl.fromTo('#{cid} .tg',{{rotation:38}},{{keyframes:[{{rotation:-22,duration:.32,ease:'sine.inOut'}},{{rotation:12,duration:.3,ease:'sine.inOut'}},"
               f"{{rotation:-6,duration:.28,ease:'sine.inOut'}},{{rotation:2,duration:.26,ease:'sine.inOut'}},{{rotation:0,duration:.24,ease:'sine.inOut'}}],immediateRender:false}},{q(tg)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-40,duration:.22,ease:'power2.in'}},{q(end - .22)});")


def describe(g, beat):
    return (f'On “{g["on"]}” a "{g.get("title", "Waitlist")}" clipboard drops onto the head and a pen writes "{g["name"]}" on the first line'
            f'{", then a “" + g["tag"] + "” tag swings in" if g.get("tag") else ""}. It holds {beat["hold"]:.1f} s.')
