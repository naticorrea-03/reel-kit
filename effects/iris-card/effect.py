"""Iris card: the frame irises down to a circle around the speaker's face; a colour plate fills the rest and carries a title
(with an optional ticking timecode), then the iris opens back up."""
import importlib.util, math, os, sys

META = {
    'id': 'iris-card', 'name': 'Iris card', 'category': 'structure',
    'when': 'A chapter turn or a time skip: "a few minutes later", "so here is what I am doing", "and the captions read like a movie script".',
    'never': 'Never more than once or twice a reel. Never a title that only repeats the caption with nothing added (a timecode or a chapter name adds).',
    'params': {'on': 'phrase where the iris closes', 'lines': 'title lines, 1 to 3 short lines (required)', 'italic': 'one more line in italic, optional',
               'timecode': 'start timecode "HH:MM:SS:FF" that ticks while the card holds, optional',
               'bg': '"accent2" (default), "accent" or "ink"', 'hold': 'seconds, default 1.8', 'sfx': 'optional sound name (a film projector for a movie reference)'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


FPS = 30
DW, DH = 22, 34   # one timecode wheel digit


def _wheel(ctx, sel, digits, t0):
    """a single digit drawn as svg that steps through the given values, one per video frame."""
    ctx.tw(f"gsap.set('{sel}',{{y:{-digits[0] * DH}}});")
    body = ','.join(f"{{y:{-d * DH},duration:{1 / FPS:.5f},ease:'steps(1)'}}" for d in digits[1:])
    if body:
        ctx.tw(f"tl.to('{sel}',{{keyframes:[{body}],immediateRender:false}},{ctx.q(t0)});")


def build(g, ctx):
    L = _lib()
    lines = g.get('lines') or []
    if isinstance(lines, str):
        lines = [lines]
    if not 1 <= len(lines) <= 3:
        ctx.fail(f'iris-card on {g["on"]!r} needs 1 to 3 "lines"')
    a, end = L.window(ctx, g, 1.8, min_after=1.0)
    a, end = round(a * FPS) / FPS, round(end * FPS) / FPS
    # the hole: centred on the speaker's face, wide enough for every face box across the hold (the audit cannot see this mask,
    # so this guard is the face check)
    fb = L.speaker_box(ctx, a, end)
    if not fb:
        ctx.fail(f'iris-card on {g["on"]!r}: no face to iris onto')
    fz = [f for f in L.faces(ctx, a, end) if abs((f[0] + f[2]) / 2 - (fb[0] + fb[2]) / 2) < 260]

    def raw(f):   # undo the detector padding (12% each side, 30% above, 18% below) to get the face itself
        w, h = (f[2] - f[0]) / 1.24, (f[3] - f[1]) / 1.48
        x0, y0 = f[0] + .12 * w, f[1] + .30 * h
        return x0, y0, x0 + w, y0 + h
    rz = [raw(f) for f in fz]
    cx = (min(r[0] for r in rz) + max(r[2] for r in rz)) / 2
    cy = (min(r[1] for r in rz) + max(r[3] for r in rz)) / 2
    R = max(math.hypot(px - cx, py - cy) for r in rz for px in (r[0], r[2]) for py in (r[1], r[3])) + 16
    if R > 430:
        ctx.fail(f'iris-card on {g["on"]!r}: the face moves too much for one iris; pick a steadier moment')
    bg = {'accent': 'var(--c-accent)', 'ink': 'var(--c-ink)'}.get(g.get('bg'), 'var(--c-accent2)')
    # title in the bigger band (above or below the circle)
    top_band = (240, cy - R - 40)
    bot_band = (cy + R + 40, 1470)
    band = top_band if top_band[1] - top_band[0] >= bot_band[1] - bot_band[0] else bot_band
    bh = band[1] - band[0]
    tc = g.get('timecode')
    tch = 60 if tc else 0
    ital = g.get('italic', '')
    n = len(lines) + (1 if ital else 0)
    fs = L.fit(ctx, 'iris-card lines', lines + ([ital] if ital else []), 820, 110, 40, 1, .56)
    fs = int(min(fs, (bh - tch - 30) / (n * 1.08)))
    if fs < 40:
        ctx.fail(f'iris-card on {g["on"]!r}: no room for the title beside the face; use fewer or shorter lines')
    block = tch + n * fs * 1.08 + 24
    ty = band[0] + (bh - block) / 2
    ctx._uid += 1
    wrap = f'iris{ctx._uid}'
    rows = ''.join(f'<div class="ln"><span class="l{k}">{ctx.esc(t)}</span></div>' for k, t in enumerate(lines))
    if ital:
        rows += f'<div class="ln it"><span class="l{len(lines)}">{ctx.esc(ital)}</span></div>'
    tcode = ''
    if tc:
        hh, mm, ss, ff = [int(x) for x in tc.split(':')]
        dig = lambda cls: f'<svg width="{DW}" height="{DH}" viewBox="0 0 {DW} {DH}"><g class="{cls}">' + ''.join(
            f'<text x="{DW / 2}" y="{DH * (k + .5)}" text-anchor="middle" dominant-baseline="central">{k}</text>' for k in range(10)) + '</g></svg>'
        tcode = (f'<div class="tc"><svg width="{DW * 5 + 4}" height="{DH}"><text x="0" y="{DH / 2}" dominant-baseline="central">{hh:02d}:{mm:02d}:</text></svg>'
                 f'{dig("s1")}{dig("s0")}<svg width="10" height="{DH}"><text x="0" y="{DH / 2}" dominant-baseline="central">:</text></svg>{dig("f1")}{dig("f0")}</div>')
    inner = (f'<div class="fx-iris-card" style="top:{ty:.0f}px;font-size:{fs}px">{tcode}{rows}<i class="ru"></i></div>'
             )
    ctx.clip(ctx.front, a, end, inner,
             f'position:absolute;inset:0;--r:1400px;background:radial-gradient(circle at {cx:.0f}px {cy:.0f}px,transparent var(--r),{bg} calc(var(--r) + 1.5px) calc(var(--r) + 12px),'
             f'color-mix(in srgb,var(--c-text) 55%,{bg}) calc(var(--r) + 13px) calc(var(--r) + 16px),{bg} calc(var(--r) + 17px));', wrap)
    q = ctx.q
    ctx.tw(f"tl.fromTo('.{wrap}',{{'--r':'1400px'}},{{'--r':'{R:.0f}px',duration:.5,ease:'power3.inOut',immediateRender:false}},{q(a)});")
    ctx.tw(f"gsap.set('.{wrap} .ln span',{{opacity:0}});")
    for k in range(n):
        ctx.tw(f"tl.fromTo('.{wrap} .l{k}',{{opacity:0,yPercent:70}},{{opacity:1,yPercent:0,duration:.3,ease:'power3.out',immediateRender:false}},{q(a + .45 + .18 * k)});")
    ctx.tw(f"tl.fromTo('.{wrap} .ru',{{scaleX:0}},{{scaleX:1,duration:.35,ease:'power2.out',immediateRender:false}},{q(a + .45 + .18 * n)});")
    if tc:
        hh, mm, ss, ff = [int(x) for x in tc.split(':')]
        N = int(round((end - a) * FPS))
        vals = []
        for k in range(N + 1):
            tot = ss * FPS + ff + k
            vals.append(((tot // FPS) % 60, tot % FPS))
        _wheel(ctx, f'.{wrap} .tc .s1', [v[0] // 10 for v in vals], a)
        _wheel(ctx, f'.{wrap} .tc .s0', [v[0] % 10 for v in vals], a)
        _wheel(ctx, f'.{wrap} .tc .f1', [v[1] // 10 for v in vals], a)
        _wheel(ctx, f'.{wrap} .tc .f0', [v[1] % 10 for v in vals], a)
        ctx.tw(f"gsap.set('.{wrap} .tc',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('.{wrap} .tc',{{opacity:0}},{{opacity:1,duration:.2,immediateRender:false}},{q(a + .35)});")
    ctx.tw(f"tl.to('.{wrap} .fx-iris-card',{{opacity:0,duration:.15}},{q(end - .45)});")
    ctx.tw(f"tl.to('.{wrap}',{{'--r':'1400px',duration:.42,ease:'power3.in'}},{q(end - .42)});")
    ctx.busy.append((a, end))
    ctx.lowbusy.append((a, end))
    ctx.topbusy.append((a, end))
    ctx.sfx(g.get('sfx'), a, .4)


def describe(g, beat):
    title = ' / '.join(g['lines'] if isinstance(g['lines'], list) else [g['lines']])
    return (f'On “{g["on"]}” the frame irises down to a circle around the face; "{title}" rolls up on the colour plate'
            f'{" under a ticking timecode" if g.get("timecode") else ""}, then the iris opens after {beat["hold"]:.1f} s. Captions pause.')
