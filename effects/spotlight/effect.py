"""Spotlight: the room falls dark around the speaker for one line, the light follows their face, then the room comes back."""

META = {
    'id': 'spotlight', 'name': 'Spotlight', 'category': 'structure',
    'when': 'One line that has to land: a confession, a rule, the payoff. The room goes dark around the speaker while they say it.',
    'never': 'Never more than once or twice a reel. Never on a line with a card or window on screen (it darkens them too).',
    'params': {'on': 'phrase where the light drops', 'until': 'phrase where it comes back, optional (default end of the on phrase + hold)',
               'hold': 'seconds after the on phrase ends, default 1.2', 'dark': 'how dark the room gets, 0.5 to 0.95, default 0.82',
               'sfx': 'optional sound name, literal only (none by default)'},
    'sfx': [], 'source': 'ours', 'credit': 'inspired by tenfoldmarc', 'license': 'MIT',
}

def build(g, ctx):
    a, b = ctx.at(g['on'])
    end = b + float(g.get('hold', 1.2))
    if g.get('until'):
        end = ctx.at(g['until'], a)[0] + .1
    later = [t for h in ctx.graphics if h is not g and h.get('on') for t in [ctx.at(h['on'])[0]] if t > a + .05]
    end = min(end, ctx.DUR - .05, *(t - .1 for t in later))
    if end - a < 1.0:
        ctx.fail(f'spotlight on {g["on"]!r} gets {end - a:.2f} s before the next graphic or the end; it needs 1 s to read')
    dark = max(.5, min(.95, float(g.get('dark', .82))))
    # the light follows the face: one key every 0.25 s
    n_ = max(2, int((end - a) / .25) + 1)
    keys = []
    for k in range(n_):
        t = a + (end - a) * k / (n_ - 1)
        f = ctx.speaker_face(t)
        if f:
            keys.append((t, f))
    if not keys:
        ctx.fail(f'spotlight on {g["on"]!r}: no face found to light')
    fw = sorted(f[2] - f[0] for _, f in keys)[len(keys) // 2]
    fh = sorted(f[3] - f[1] for _, f in keys)[len(keys) // 2]
    S = 2800   # the pool of light is a big soft gradient moved with x/y, so it never has an edge on screen
    rx, ry = int(max(260, fw * 1.25)), int(max(330, fh * 1.45))

    def pos(f):   # light centred a little below the eyes, so head and shoulders sit in it
        return (f[0] + f[2]) / 2 - S / 2, (f[1] + f[3]) / 2 + fh * .18 - S / 2

    x0, y0 = pos(keys[0][1])
    html = (f'<div class="fx-spotlight"><div class="scrim" style="width:{S}px;height:{S}px;'
            f'--rx:{rx}px;--ry:{ry}px;--dark:{dark * 100:.0f}%"></div></div>')
    cid = ctx.clip(ctx.front, a, end, html, 'position:absolute;left:0;top:0;width:1080px;height:1920px;')
    ctx.tw(f"gsap.set('#{cid} .scrim',{{x:{x0:.0f},y:{y0:.0f}}});")
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0}},{{opacity:1,duration:.45,ease:'power2.out',immediateRender:false}},{ctx.q(a)});")
    for (t1, f1), (t2, f2) in zip(keys, keys[1:]):
        (xa, ya), (xb, yb) = pos(f1), pos(f2)
        if abs(xb - xa) + abs(yb - ya) > 4:
            ctx.tw(f"tl.fromTo('#{cid} .scrim',{{x:{xa:.0f},y:{ya:.0f}}},{{x:{xb:.0f},y:{yb:.0f},duration:{t2 - t1:.3f},ease:'sine.inOut',immediateRender:false}},{ctx.q(t1)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.5,ease:'power2.inOut'}},{ctx.q(end - .5)});")
    ctx.sfx(g.get('sfx'), a, .35)


def describe(g, beat):
    return (f'On “{g["on"]}” the room fades to dark around the speaker and a soft pool of light follows their face. '
            f'The room comes back after {beat["hold"]:.1f} s.')
