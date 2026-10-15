"""Progress dots: a small segmented tracker pinned top right. One segment fills as each chapter starts, so the viewer
sees how far into the list they are."""
import importlib.util, os, sys

META = {
    'id': 'progress-dots', 'name': 'Progress dots', 'category': 'structure',
    'when': 'A reel built as a numbered list or steps ("five tools", "three rules"): it shows where the viewer is and how much is left.',
    'never': 'Never for fewer than 2 or more than 8 chapters. Never with chapters the speaker does not clearly start (a segment that fills on nothing reads as a glitch).',
    'params': {'on': 'phrase where it appears (default the first chapter)', 'chapters': '[{"on"}] 2 to 8 phrases; segment k fills on chapter k',
               'until': 'phrase where it leaves (default the end of the clip)', 'sfx': 'optional sound name on each fill'},
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


SW, SH, GAP, PAD = 34, 14, 8, 12


def build(g, ctx):
    L = _lib()
    chs = g.get('chapters') or []
    if not 2 <= len(chs) <= 8 or not all(isinstance(c, dict) and c.get('on') for c in chs):
        ctx.fail(f'progress-dots on {g.get("on")!r} needs 2 to 8 "chapters", each with "on"')
    ts = []
    after = 0.0
    for c in chs:
        t = ctx.at(c['on'], after)[0]
        ts.append(t)
        after = t
    a = ctx.at(g['on'])[0] if g.get('on') else ts[0]
    a = max(min(a, ts[0]), ctx.hook_end + .05)
    end = (ctx.at(g['until'], a)[0] - .05) if g.get('until') else ctx.DUR - .05
    if end - a < 1.0:
        ctx.fail(f'progress-dots: up for under a second')
    n = len(chs)
    W, H = n * SW + (n - 1) * GAP + 2 * PAD, SH + 2 * PAD
    fz = L.faces(ctx, a, end, n=max(10, int((end - a) * 3)))
    x = 950 - W
    y = next((yy for yy in range(250, 700, 10) if L.face_share((x, yy, x + W, yy + H), fz) <= .002 and L.taken(ctx, (x, yy, x + W, yy + H), a, end) < .01), None)
    if y is None:
        ctx.fail(f'progress-dots: the top right stays on a face for the whole run; shorten it with "until"')
    if y > 250:
        ctx.note(f'progress-dots pinned at y {y}: the faces reach the top right')
    segs = ''.join(f'<i class="sg s{k}"><b></b></i>' for k in range(n))
    cid = ctx.clip(ctx.front, a, end, f'<div class="fx-progress-dots">{segs}</div>', f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:-14}},{{opacity:1,y:0,duration:.25,ease:'power3.out',immediateRender:false}},{q(a)});")
    ctx.tw(f"gsap.set('#{cid} .sg b',{{scaleX:0}});")
    for k, t in enumerate(ts):
        t = max(t, a + .1)
        ctx.tw(f"tl.fromTo('#{cid} .s{k} b',{{scaleX:0}},{{scaleX:1,duration:.32,ease:'power2.out',immediateRender:false}},{q(t)});")
        ctx.tw(f"tl.fromTo('#{cid} .s{k}',{{scale:1.35}},{{scale:1,duration:.3,ease:'back.out(3)',immediateRender:false}},{q(t)});")
        ctx.sfx(g.get('sfx'), t, .25)
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.2}},{q(end - .2)});")
    L.reserve(ctx, (x, y, x + W, y + H), a, end)


def describe(g, beat):
    return f'A {len(g["chapters"])}-segment tracker is pinned top right; one segment fills as each chapter starts. It holds {beat["hold"]:.1f} s.'
