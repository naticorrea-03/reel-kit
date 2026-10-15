"""Stamp: a document card rises beside the speaker, then a rubber stamp slams onto it with the verdict."""
import importlib.util, os, sys

META = {
    'id': 'stamp', 'name': 'Rubber stamp', 'category': 'annotation',
    'when': 'A request, document or application gets a verdict the speaker names: approved, requested, rejected, signed, paid, sold out.',
    'never': 'Never a verdict nobody says or implies. Never a stamp on an empty card: the card names the document.',
    'params': {'on': 'phrase that brings the card in', 'title': 'what the document is (required, short)',
               'kicker': 'small line above the title, optional', 'quote': 'one line on the document, optional (a request, a line item)',
               'stamp': 'the verdict word (required, 1 or 2 words)', 'stamp_on': 'phrase where the stamp lands, default 0.9 s in',
               'hold': 'seconds after the stamp, default 1.6', 'sfx': 'sound on the stamp, default rubber-stamp ("none" for silence)'},
    'sfx': ['rubber-stamp'], 'source': 'ours', 'credit': 'Motion idea inspired by an Instagram explainer reel on SOC 2 (Oct 2026)', 'license': 'MIT',
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
    L.need(ctx, g, 'title', 'stamp')
    a = ctx.at(g['on'])[0]
    ts = ctx.at(g['stamp_on'], a)[0] if g.get('stamp_on') else a + .9
    ts = max(ts, a + .55)
    a, end = L.window(ctx, g, 1.6, last=ts)
    W, P = 660, 44
    TW = W - 2 * P - 12
    tfs = L.fit(ctx, 'stamp title', [g['title']], TW, 76, 44, 2, .5)
    qfs = L.fit(ctx, 'stamp quote', [g.get('quote', '')], TW, 46, 34, 3, .5) if g.get('quote') else 0
    sfs = L.fit(ctx, 'stamp word', [g['stamp']], W * .8, 84, 40, 1, .7)
    tl = len(L.wrap(g['title'], TW, tfs, .5))
    ql = len(L.wrap(g.get('quote', ''), TW, qfs, .5)) if qfs else 0
    H = int(2 * P + (50 if g.get('kicker') else 0) + tl * tfs * 1.08 + (ql * qfs * 1.32 + 22 if ql else 0) + 28 + max(3 * 12 + 2 * 26, sfs + 40))
    face = L.speaker_box(ctx, a, end)
    near = ((face[0] + face[2]) / 2, (face[1] + face[3]) / 2) if face else None
    x, y, sc = L.fitspot(ctx, 'stamp', W, H, a, end, near=near, scales=(1.0, .86, .74, .64, .56))
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    kick = f'<div class="kk">{ctx.esc(g["kicker"])}</div>' if g.get('kicker') else ''
    quote = f'<div class="qt" style="font-size:{qfs}px">{ctx.esc(g["quote"])}</div>' if qfs else ''
    rows = ''.join(f'<div class="ln" style="width:{w}%"></div>' for w in (92, 78, 60))
    html = (f'<div class="fx-stamp" style="width:{W}px;height:{H}px;padding:{P}px">{kick}'
            f'<div class="tt" style="font-size:{tfs}px">{ctx.esc(g["title"])}</div>{quote}<div class="lns">{rows}</div>'
            f'<div class="st"><span style="font-size:{sfs}px">{ctx.esc(g["stamp"])}</span></div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .fx-stamp',{{opacity:0,y:70,rotation:3,scale:.92}},{{opacity:1,y:0,rotation:-1.2,scale:1,duration:.5,ease:'power3.out',immediateRender:false}},{q(a)});")
    ctx.tw(f"tl.fromTo('#{cid} .fx-stamp',{{rotation:-1.2,x:0}},{{rotation:.8,x:-10,duration:{end - a - .5:.3f},ease:'sine.inOut',immediateRender:false}},{q(a + .5)});")
    ctx.tw(f"gsap.set('#{cid} .st',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .st',{{opacity:0,scale:1.75,rotation:-15}},{{opacity:1,scale:1,rotation:-6,duration:.15,ease:'power4.in',immediateRender:false}},{q(ts - .15)});")
    ctx.tw(f"tl.fromTo('#{cid} .st',{{scale:1}},{{scale:1.035,duration:.05,yoyo:true,repeat:1,ease:'power1.out',immediateRender:false}},{q(ts)});")
    ctx.tw(f"tl.fromTo('#{cid} .fx-stamp',{{scale:1}},{{scale:.972,duration:.06,ease:'power2.out',immediateRender:false}},{q(ts)});")
    ctx.tw(f"tl.to('#{cid} .fx-stamp',{{scale:1,duration:.32,ease:'back.out(3)'}},{q(ts + .06)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(end - .22)});")
    ctx.sfx(g.get('sfx', 'rubber-stamp'), ts - .02, .5)


def describe(g, beat):
    return (f'On “{g["on"]}” a card for "{g["title"]}" rises beside the speaker; a rubber stamp slams "{g["stamp"]}" onto it'
            f'{" on “" + g["stamp_on"] + "”" if g.get("stamp_on") else ""}. It holds {beat["hold"]:.1f} s.')
