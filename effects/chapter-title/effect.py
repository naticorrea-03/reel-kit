"""Chapter title: a pinned title sticker at the top of the frame, with a small chapter pill under it that swaps as the reel moves on."""
import importlib.util, os, sys

META = {
    'id': 'chapter-title', 'name': 'Pinned title + chapters', 'category': 'structure',
    'when': 'A reel built in parts ("levels of AI users": where it lives, how I build, how my team uses it) or a series tag that should stay up the whole time.',
    'never': 'Never a title that changes nothing about how the reel reads. Never more than 5 chapters. Keep other graphics out of the top band while it is pinned.',
    'params': {'on': 'phrase where it appears', 'title': 'the pinned title (required, up to ~40 characters)',
               'chapters': '[{"text", "on"}] 0 to 5 chapter pills; each swaps in on its phrase', 'until': 'phrase where it leaves (default the end of the clip)',
               'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by Instagram creator reels with pinned titles (Oct 2026)', 'license': 'MIT',
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
    L.need(ctx, g, 'title')
    chs = g.get('chapters') or []
    if len(chs) > 5 or not all(isinstance(c, dict) and c.get('text') for c in chs):
        ctx.fail(f'chapter-title on {g["on"]!r}: up to 5 chapters, each with "text"')
    a = max(ctx.at(g['on'])[0], ctx.hook_end + .05)   # the hook card owns the opening
    end = (ctx.at(g['until'], a)[0] - .05) if g.get('until') else ctx.DUR - .05
    ts = L.times(ctx, g, chs, .0, key='on') if chs else []
    if end - a < 1.0:
        ctx.fail(f'chapter-title on {g["on"]!r} is up for under a second')
    tfs = L.fit(ctx, 'chapter-title title', [g['title']], 620, 50, 34, 2, .52)
    tl_n = len(L.wrap(g['title'], 620, tfs, .52))
    cfs = L.fit(ctx, 'chapter-title chapters', [c['text'] for c in chs], 560, 32, 28, 1, .55) if chs else 0
    H = int(tl_n * tfs * 1.12 + 36 + (cfs * 1.3 + 40 if chs else 0))
    fz = L.faces(ctx, a, end, n=max(10, int((end - a) * 3)))
    # pinned at the top when the faces leave room, else the highest band that stays clear for the whole run
    y = next((yy for yy in range(250, 1471 - H, 10) if L.face_share((150, yy, 930, yy + H), fz) <= .002), None)
    if y is None:
        ctx.fail(f'chapter-title on {g["on"]!r}: no band stays clear of the faces for the whole run; shorten the run with "until"')
    if y > 250:
        ctx.note(f'chapter-title pinned at y {y}: the faces reach the top band')
    pills = ''.join(f'<div class="ch c{k}"><span style="font-size:{cfs}px">{ctx.esc(c["text"])}</span></div>' for k, c in enumerate(chs))
    html = (f'<div class="fx-chapter-title"><div class="tt" style="font-size:{tfs}px">{ctx.esc(g["title"])}</div>'
            + (f'<div class="chs" style="height:{int(cfs * 1.3 + 20)}px">{pills}</div>' if chs else '') + '</div>')
    cid = ctx.clip(ctx.front, a, end, html, f'position:absolute;left:0;right:0;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .tt',{{opacity:0,scale:.9}},{{opacity:1,scale:1,duration:.22,ease:'back.out(2)',immediateRender:false}},{q(a)});")
    for k, t in enumerate(ts):
        ctx.tw(f"gsap.set('#{cid} .c{k}',{{opacity:0}});")
        t = max(t, a + .1)
        ctx.tw(f"tl.fromTo('#{cid} .c{k}',{{opacity:0,y:18}},{{opacity:1,y:0,duration:.24,ease:'power3.out',immediateRender:false}},{q(t + (.1 if k else 0))});")
        if k + 1 < len(ts):
            ctx.tw(f"tl.to('#{cid} .c{k}',{{opacity:0,y:-18,duration:.12,ease:'power2.in'}},{q(max(ts[k + 1], a + .1) - .02)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.2}},{q(end - .2)});")
    ctx.topbusy.append((a, end))
    L.reserve(ctx, (150, y, 930, y + H), a, end)
    ctx.sfx(g.get('sfx'), a, .3)


def describe(g, beat):
    chs = ' → '.join(c['text'] for c in g.get('chapters', []))
    return f'From “{g["on"]}” the title "{g["title"]}" is pinned at the top{"; chapters swap under it: " + chs if chs else ""}. It holds {beat["hold"]:.1f} s.'
