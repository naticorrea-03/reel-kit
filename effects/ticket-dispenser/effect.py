"""Ticket dispenser: a take-a-number dispenser drops onto the head and a numbered ticket slides out of it."""
import importlib.util, os, sys

META = {
    'id': 'ticket-dispenser', 'name': 'Take a number', 'category': 'social',
    'when': 'A waitlist, a queue or a place in line: "join the waitlist", "first in line", "you are number 12".',
    'never': 'Never a position nobody offers. Never covers a face.',
    'params': {'on': 'phrase that drops the dispenser in', 'number': 'the ticket number, e.g. "001" (required)',
               'title': 'label on the dispenser, default "Take a number"', 'line1': 'line under the number, e.g. "Waitlist" (optional)',
               'line2': 'small last line, e.g. "First in line" (optional)', 'ticket_on': 'phrase where the ticket slides out, default 0.5 s in',
               'hold': 'seconds after the ticket, default 1.6', 'sfx': 'sound when the ticket comes out, default ticket-tear ("none" for silence)'},
    'sfx': ['ticket-tear'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


DW, DH = 380, 104     # dispenser body
TW, TH = 300, 236     # ticket


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'number')
    a = ctx.at(g['on'])[0]
    tt = max(a + .45, ctx.at(g['ticket_on'], a)[0]) if g.get('ticket_on') else a + .5
    a, end = L.window(ctx, g, 1.6, last=tt)
    W, H = DW, DH + TH - 16
    x, y, sc = L.above_head(ctx, 'ticket-dispenser', W, H, a, end)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    title = g.get('title', 'Take a number')
    tfs = L.fit(ctx, 'ticket-dispenser title', [title], DW - 90, 32, 28, 1, .66)
    nfs = L.fit(ctx, 'ticket-dispenser number', [g['number']], TW - 40, 92, 52, 1, .62)
    l1fs = L.fit(ctx, 'ticket-dispenser line1', [g.get('line1', '')], TW - 36, 36, 26, 1, .72)
    l2fs = L.fit(ctx, 'ticket-dispenser line2', [g.get('line2', '')], TW - 36, 34, 26, 1, .7)
    l1 = f'<div class="l1" style="font-size:{l1fs}px">{ctx.esc(g["line1"])}</div>' if g.get('line1') else ''
    l2 = f'<div class="l2" style="font-size:{l2fs}px">{ctx.esc(g["line2"])}</div>' if g.get('line2') else ''
    html = (f'<div class="fx-ticket-dispenser" style="width:{W}px;height:{H}px">'
            f'<div class="tk" style="left:{(DW - TW) / 2:.0f}px;top:{DH - 16}px;width:{TW}px;height:{TH}px"><div class="tin">{l1}'
            f'<div class="nm" style="font-size:{nfs}px">{ctx.esc(g["number"])}</div>{l2}</div></div>'
            f'<div class="bd" style="height:{DH}px"><div class="lab" style="font-size:{tfs}px">{ctx.esc(title)}</div><div class="slot"></div></div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .bd',{{y:-{L.drop_from(y, DH, sc)},opacity:0}},{{y:0,opacity:1,duration:.42,ease:'back.out(1.5)',immediateRender:false}},{q(a)});")
    ctx.tw(f"gsap.set('#{cid} .tk',{{y:{-TH + 10},opacity:0}});")   # tucked behind the body and hidden until it comes out
    ctx.tw(f"tl.fromTo('#{cid} .tk',{{opacity:0}},{{opacity:1,duration:.06,immediateRender:false}},{q(tt + .04)});")
    ctx.tw(f"gsap.set('#{cid} .tin',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .tk',{{y:{-TH + 10}}},{{y:0,duration:.45,ease:'power3.out',immediateRender:false}},{q(tt)});")
    ctx.tw(f"tl.fromTo('#{cid} .tin',{{opacity:0}},{{opacity:1,duration:.18,immediateRender:false}},{q(tt + .14)});")
    ctx.tw(f"tl.fromTo('#{cid} .tk',{{rotation:0}},{{keyframes:[{{rotation:-3,duration:.25,ease:'sine.out'}},{{rotation:2,duration:.4,ease:'sine.inOut'}},{{rotation:0,duration:.4,ease:'sine.inOut'}}],immediateRender:false}},{q(tt + .45)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-40,duration:.22,ease:'power2.in'}},{q(end - .22)});")
    ctx.sfx(g.get('sfx', 'ticket-tear'), tt, .4)


def describe(g, beat):
    return f'On “{g["on"]}” a take-a-number dispenser drops onto the head and ticket {g["number"]} slides out. It holds {beat["hold"]:.1f} s.'
