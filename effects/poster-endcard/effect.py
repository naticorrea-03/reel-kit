"""Poster end card: the room drops away to a dark plate, the speaker turns black and white and steps left, a big colour circle
lands behind them, a stacked sign-off builds word by word beside the head, a name tag slides in, and a Follow button pops."""
import importlib.util, os, sys

META = {
    'id': 'poster-endcard', 'name': 'Poster end card', 'category': 'structure',
    'when': 'The sign-off: "see you tomorrow", "follow for part two", "that is the whole system". Last thing in the reel.',
    'never': 'Never mid-reel (it reads as the end). Never a sign-off over 3 short lines. Never on footage without a cutout.',
    'params': {'on': 'phrase where it starts', 'lines': 'the sign-off, 1 to 3 short lines (required), e.g. ["See you", "tomorrow."]',
               'name': 'name on the tag, default the speaker\'s name', 'handle': 'handle under the name, optional',
               'button': 'button label, default "Follow"', 'circle': '"accent" (default) or "accent2"', 'hold': 'seconds, default 2.8',
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


PLATE = '#16110E'
FACE_X = 330      # where the face centre moves to
TAG_Y = 1320      # name tag top
K = .64           # glyph width of the heavy display caps


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'lines')
    lines = g['lines'] if isinstance(g['lines'], list) else [g['lines']]
    if not 1 <= len(lines) <= 3:
        ctx.fail(f'poster-endcard on {g["on"]!r} needs 1 to 3 "lines"')
    if not ctx.has_cut:
        ctx.fail(f'poster-endcard on {g["on"]!r} needs the speaker cutout (run engine/cutout.sh)')
    a, end = L.window(ctx, g, 2.8, min_after=1.6)
    fb = L.speaker_box(ctx, a, end)
    if not fb:
        ctx.fail(f'poster-endcard on {g["on"]!r}: no face found')
    fz0 = [f for f in L.faces(ctx, a, end, n=8) if abs((f[0] + f[2]) / 2 - (fb[0] + fb[2]) / 2) < 260] or [fb]
    dx = int(max(-320, min(0, FACE_X - (fb[0] + fb[2]) / 2)))
    fz = [[f[0] + dx, f[1], f[2] + dx, f[3]] for f in fz0]
    x0 = int(max(f[2] for f in fz) + L.MARGIN + 24)
    width = 950 - x0
    if width < 320:
        ctx.fail(f'poster-endcard on {g["on"]!r}: no room beside the head for the sign-off; the face fills the frame')
    fs = L.fit(ctx, 'poster-endcard lines', [t.upper() for t in lines], width, 150, 64, 1, K)
    lh = int(fs * 1.02)
    block = lh * len(lines)
    bh = 76   # the button under the lines
    stack = block + 28 + bh
    samples = [a + .5 + (end - a - .5) * k / 3 for k in range(4)]

    def hidden(y):   # share of the text column the shifted speaker covers (the cutout moves by dx; the alpha frames do not)
        return max(ctx.alpha_cover(t, x0 - dx, y, 950 - dx, y + stack) for t in samples)
    fcy = sum((f[1] + f[3]) / 2 for f in fz) / len(fz)
    ys = sorted(range(260, TAG_Y - 60 - stack, 10), key=lambda y: abs(y + stack / 2 - fcy))
    y0 = next((y for y in ys if hidden(y) < .015 and L.face_share((x0, y, 950, y + stack), fz) <= .002), None)
    if y0 is None:
        ctx.fail(f'poster-endcard on {g["on"]!r}: the sign-off would sit behind the speaker; shorten the lines')
    # the circle centres on the sign-off and stays inside the frame's safe edges and clear of the name tag
    ccx, ccy = x0 + width / 2, y0 + block / 2 + 10
    rc = int(min(max(width * .62, block * .8), ccx - 60, 1030 - ccx, ccy - 230, TAG_Y - 30 - ccy, 360))
    if rc < 170:
        ctx.fail(f'poster-endcard on {g["on"]!r}: no room for the circle; use fewer lines')
    circ = 'var(--c-accent2)' if g.get('circle') == 'accent2' else 'var(--c-accent)'
    q = ctx.q
    words = []
    for li, t in enumerate(lines):
        ws = t.upper().split()
        words.append(' '.join(f'<span class="wd">{ctx.esc(w)}</span>' for w in ws))
    rows = ''.join(f'<div class="ln" style="height:{lh}px">{w}</div>' for w in words)
    btn = ctx.esc(g.get('button') or 'Follow')
    html = (f'<div class="fx-poster-endcard">'
            f'<i class="circ" style="left:{ccx - rc:.0f}px;top:{ccy - rc:.0f}px;width:{2 * rc}px;height:{2 * rc}px;background:{circ}"></i>'
            f'<div class="lines" style="left:{x0}px;top:{y0}px;width:{width}px;font-size:{fs}px">{rows}</div>'
            f'<div class="btn" style="left:{x0}px;top:{y0 + block + 28}px"><span>{btn}</span></div></div>')
    revert = end < ctx.DUR - .35
    wall_end = end
    cid = ctx.clip(ctx.wall, a, wall_end, html, 'position:absolute;inset:0;', 'wallz')
    # the room goes, the speaker turns black and white and steps left
    ctx.tw(f"tl.set('#root',{{backgroundColor:'{PLATE}'}},{q(a)});")
    ctx.tw(f"tl.to('#bgv',{{opacity:0,duration:.3,ease:'power2.out'}},{q(a)});")
    ctx.tw(f"tl.fromTo('#cutwrap',{{x:0,filter:'grayscale(0) contrast(1)'}},{{x:{dx},filter:'grayscale(1) contrast(1.15)',duration:.5,ease:'power3.inOut',immediateRender:false}},{q(a)});")
    # the circle and the first word land together: a big empty colour disc reads as a dead card
    ctx.tw(f"gsap.set('#{cid} .circ',{{scale:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .circ',{{scale:0}},{{scale:1,duration:.45,ease:'back.out(1.6)',immediateRender:false}},{q(a + .32)});")
    ctx.tw(f"gsap.set('#{cid} .wd',{{opacity:0}});")
    nwd = sum(len(t.split()) for t in lines)
    step = min(.26, max(.12, (end - a - 1.4) / max(1, nwd)))
    ctx.tw(f"tl.fromTo('#{cid} .wd',{{opacity:0,yPercent:60}},{{opacity:1,yPercent:0,duration:.22,stagger:{step:.3f},ease:'power3.out',immediateRender:false}},{q(a + .3)});")
    tbtn = max(a + .4 + step * nwd, end - 1.0)
    ctx.tw(f"gsap.set('#{cid} .btn',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('#{cid} .btn',{{opacity:0,scale:.4}},{{opacity:1,scale:1,duration:.35,ease:'back.out(3)',immediateRender:false}},{q(tbtn)});")
    # name tag on the chest
    name = g.get('name') or ctx.speaker_name(ctx.speaker_at(a))
    if name and name != ctx.speaker_at(a):
        hd = f'<div class="hd">{ctx.esc(g["handle"])}</div>' if g.get('handle') else ''
        tag_box = (90, TAG_Y, 90 + 560, TAG_Y + (122 if hd else 74))
        if L.face_share(tag_box, fz) > .002:
            ctx.fail(f'poster-endcard on {g["on"]!r}: the name tag would cover the face')
        tid = ctx.clip(ctx.front, a + .55, end, f'<div class="fx-poster-tag"><div class="nm">{ctx.esc(name.upper())}</div>{hd}</div>',
                       f'position:absolute;left:90px;top:{TAG_Y}px;')
        ctx.tw(f"tl.fromTo('#{tid}',{{opacity:0,x:-80}},{{opacity:1,x:0,duration:.35,ease:'power3.out',immediateRender:false}},{q(a + .55)});")
        if revert:
            ctx.tw(f"tl.to('#{tid}',{{opacity:0,duration:.18}},{q(end - .2)});")
    if revert:   # a sign-off before the last second: hand the frame back
        ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.18}},{q(end - .2)});")
        ctx.tw(f"tl.to('#bgv',{{opacity:1,duration:.25}},{q(end - .2)});")
        ctx.tw(f"tl.to('#cutwrap',{{x:0,filter:'grayscale(0) contrast(1)',duration:.3,ease:'power2.inOut'}},{q(end - .25)});")
        ctx.tw(f"tl.set('#root',{{backgroundColor:'#000000'}},{q(end)});")
    ctx.busy.append((a, end))
    ctx.lowbusy.append((a, end))
    ctx.topbusy.append((a, end))
    L.reserve(ctx, (0, 220, 1080, 1470), a, end)
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    lines = g['lines'] if isinstance(g['lines'], list) else [g['lines']]
    return (f'On “{g["on"]}” the room drops to a dark plate, the speaker turns black and white and steps left, a colour circle lands behind '
            f'"{" ".join(lines)}" as it builds word by word, a name tag slides in and a {g.get("button") or "Follow"} button pops. '
            f'It holds {beat["hold"]:.1f} s. Captions pause.')
