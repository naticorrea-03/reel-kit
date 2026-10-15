"""Receipt print: a printer slot lands above the head and a receipt prints out of it, each line typing on as it is said."""
import importlib.util, os, sys

META = {
    'id': 'receipt-print', 'name': 'Receipt print', 'category': 'ui',
    'when': 'The speaker gives an instruction, an order or a short list and the exact words matter ("I told it: take a pass at editing this").',
    'never': 'Never paraphrase: the lines are the real words. Never more than 4 lines. Never covers a face.',
    'params': {'on': 'phrase that brings the printer in', 'title': 'header on the left, e.g. "Instruction 01" (required)',
               'meta': 'small header on the right, optional', 'lines': 'list of short lines, or {"text", "on"}; 1 to 4',
               'total': '["left", "right"] last row, e.g. ["Total", "1 sentence"], optional', 'hold': 'seconds after the last line, default 1.4',
               'sfx': 'sound while it prints, default receipt-printer ("none" for silence)'},
    'sfx': ['receipt-printer'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


SW, PW = 580, 500   # slot width, paper width
CPS = 26            # characters typed per second


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'title', 'lines')
    lines = [x if isinstance(x, dict) else {'text': x} for x in g['lines']]
    if not 1 <= len(lines) <= 4:
        ctx.fail(f'receipt-print on {g["on"]!r} needs 1 to 4 lines')
    ts = L.times(ctx, g, lines, .8, key='on')
    ts[0] = max(ts[0], ctx.at(g['on'])[0] + .9)   # the slot lands and the header prints first
    fs = L.fit(ctx, 'receipt-print lines', [x['text'] for x in lines], PW - 60, 40, 30, 3, .62)
    wr = [L.wrap(x['text'].upper(), PW - 60, fs, .62) for x in lines]
    for k in range(1, len(ts)):
        ts[k] = max(ts[k], ts[k - 1] + len(lines[k - 1]['text']) / CPS + .1)
    done = ts[-1] + len(lines[-1]['text']) / CPS
    total = g.get('total')
    tt = done + .15 if total else done
    a, end = L.window(ctx, g, 1.4, last=tt)
    rowh = fs * 1.25
    head_h = 104
    body_h = sum(len(w) for w in wr) * rowh + 18 * (len(wr) - 1)
    tot_h = 64 if total else 0
    PH = int(head_h + body_h + tot_h + 40)
    H = 40 + PH
    x, y, sc = L.above_head(ctx, 'receipt-print', SW, H, a, end)
    L.claim(ctx, x, y, SW * sc, H * sc, a, end, pause=True)
    meta = f'<span class="mt">{ctx.esc(g["meta"])}</span>' if g.get('meta') else ''
    body = ''
    for k, w in enumerate(wr):
        body += f'<div class="ln n{k}" style="font-size:{fs}px">' + ''.join(f'<div>{ctx.typed(r)}</div>' for r in w) + '</div>'
    tot = (f'<div class="tot"><span>{ctx.esc(total[0])}</span><span>{ctx.esc(total[1])}</span></div>') if total else ''
    html = (f'<div class="fx-receipt-print" style="width:{SW}px;height:{H}px"><div class="pp" style="width:{PW}px;left:{(SW - PW) / 2:.0f}px;height:{PH}px">'
            f'<div class="hd"><span>{ctx.esc(g["title"])}</span>{meta}</div>{body}{tot}</div><div class="sl"></div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .sl',{{y:-{L.drop_from(y, 40, sc, 160)},opacity:0}},{{y:0,opacity:1,duration:.38,ease:'back.out(1.6)',immediateRender:false}},{q(a)});")
    # the paper grows out of the slot in steps, one step per line, and each line types on as it is said
    hs = [head_h + 30]
    acc = head_h + 22
    for w in wr:
        acc += len(w) * rowh + 18
        hs.append(acc)
    ctx.tw(f"gsap.set('#{cid} .pp',{{height:0}});")
    ctx.tw(f"gsap.set('#{cid} .hd',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .hd',{{opacity:0}},{{opacity:1,duration:.1,immediateRender:false}},{q(a + .58)});")
    ctx.tw(f"tl.fromTo('#{cid} .pp',{{height:0}},{{height:{hs[0]:.0f},duration:.3,ease:'power2.out',immediateRender:false}},{q(a + .3)});")
    for k, x_ in enumerate(lines):
        ctx.tw(f"gsap.set('#{cid} .n{k} .tc',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .pp',{{height:{hs[k]:.0f}}},{{height:{hs[k + 1]:.0f},duration:.22,ease:'steps(4)',immediateRender:false}},{q(ts[k] - .22)});")
        n = len(x_['text'].replace(' ', ''))
        ctx.tw(f"tl.to('#{cid} .n{k} .tc',{{opacity:1,duration:.01,stagger:{1 / CPS:.4f}}},{q(ts[k])});")
    if total:
        ctx.tw(f"gsap.set('#{cid} .tot',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .pp',{{height:{hs[-1]:.0f}}},{{height:{PH},duration:.2,ease:'steps(3)',immediateRender:false}},{q(tt - .2)});")
        ctx.tw(f"tl.fromTo('#{cid} .tot',{{opacity:0}},{{opacity:1,duration:.15,immediateRender:false}},{q(tt)});")
    ctx.tw(f"tl.fromTo('#{cid} .pp',{{rotation:0}},{{rotation:-1.5,duration:.6,yoyo:true,repeat:1,ease:'sine.inOut',immediateRender:false}},{q(tt + .1)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(end - .22)});")
    ctx.sfx(g.get('sfx', 'receipt-printer'), ts[0] - .2, .35, cap=done - ts[0] + .3)


def describe(g, beat):
    lines = ' / '.join(x if isinstance(x, str) else x['text'] for x in g['lines'])
    return f'On “{g["on"]}” a receipt prints out above the head: "{g["title"]}", then "{lines}" types on line by line. It holds {beat["hold"]:.1f} s; captions pause.'
