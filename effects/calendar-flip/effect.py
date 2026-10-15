"""Calendar flip: a tear-off desk calendar drops onto the speaker's head and its pages tear away, one per date said."""
import importlib.util, os, sys

META = {
    'id': 'calendar-flip', 'name': 'Tear-off calendar', 'category': 'data',
    'when': 'Days pass in the story: "over the weekend", "three days later", "by Monday". Each page is a real date or day.',
    'never': 'Never dates the story does not have. Never more than 4 pages. Never covers a face (it sits above the head or beside it).',
    'params': {'on': 'phrase that drops the calendar in', 'month': 'short month on every page, e.g. "OCT" (required)',
               'pages': '[{"day": "10", "label": "Saturday", "on": "phrase"}] 2 to 4; the first shows on arrival, each later one tears in on its phrase',
               'hold': 'seconds after the last page, default 1.2', 'sfx': 'sound per tear, default paper-tear ("none" for silence)'},
    'sfx': ['paper-tear'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


W, H = 320, 360


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'month', 'pages')
    pages = g['pages']
    if not 2 <= len(pages) <= 4 or not all(isinstance(p, dict) and p.get('day') for p in pages):
        ctx.fail(f'calendar-flip on {g["on"]!r} needs 2 to 4 pages, each with "day"')
    ts = L.times(ctx, g, pages, .9)
    ts = [ts[0]] + [max(t, ts[0] + .7 + .55 * k) for k, t in enumerate(ts[1:])]
    a, end = L.window(ctx, g, 1.2, last=ts[-1] + .6)
    x, y, sc = L.above_head(ctx, 'calendar-flip', W, H, a, end)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    lfs = L.fit(ctx, 'calendar-flip label', [p.get('label', '') for p in pages], W - 60, 34, 26, 1, .62)
    n = len(pages)
    leaves = ''
    for k, p in enumerate(pages):
        lab = f'<div class="lb" style="font-size:{lfs}px">{ctx.esc(p["label"])}</div>' if p.get('label') else ''
        leaves += (f'<div class="pg p{k}" style="z-index:{10 + n - k}"><div class="mo"><span>{ctx.esc(g["month"])}</span>'
                   f'<span>{ctx.esc(g.get("year", ""))}</span></div><div class="dy">{ctx.esc(p["day"])}</div>{lab}</div>')
    html = (f'<div class="fx-calendar-flip" style="width:{W}px;height:{H}px"><div class="bk"></div>{leaves}'
            f'<div class="bar"><i></i><i></i></div></div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .fx-calendar-flip',{{y:-{L.drop_from(y, H, sc)},rotation:-4,opacity:0}},{{y:0,rotation:0,opacity:1,duration:.5,ease:'back.out(1.6)',immediateRender:false}},{q(a)});")
    away = 1 if x + W * sc / 2 < 540 else -1   # torn pages fly toward the open side of the frame, away from the button rail
    for k in range(1, n):   # later pages wait hidden so two dates never read at once
        ctx.tw(f"gsap.set('#{cid} .p{k} > *',{{opacity:0}});")
    for k in range(1, n):
        t = ts[k]
        ctx.tw(f"tl.fromTo('#{cid} .p{k} > *',{{opacity:0}},{{opacity:1,duration:.12,immediateRender:false}},{q(t + .14)});")
        side = away
        ctx.tw(f"tl.fromTo('#{cid} .p{k - 1}',{{rotation:0,x:0,y:0,opacity:1}},{{keyframes:[{{rotation:{9 * side},x:{70 * side},y:16,duration:.08,ease:'power2.out'}},"
               f"{{rotation:{40 * side},x:{240 * side},y:260,opacity:0,duration:.4,ease:'power1.in'}}],immediateRender:false}},{q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .fx-calendar-flip',{{y:0}},{{y:6,duration:.06,yoyo:true,repeat:1,ease:'power1.out',immediateRender:false}},{q(t)});")
        ctx.sfx(g.get('sfx', 'paper-tear'), t, .45)
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-40,duration:.22,ease:'power2.in'}},{q(end - .22)});")


def describe(g, beat):
    days = ', '.join(f'{p["day"]} {p.get("label", "")}'.strip() for p in g['pages'])
    return f'On “{g["on"]}” a tear-off calendar drops onto the head and tears through {days}. It holds {beat["hold"]:.1f} s.'
