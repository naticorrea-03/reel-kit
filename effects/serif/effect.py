"""Punch line in serif type under the speaker. Captions pause while it is up."""

META = {
    'id': 'serif', 'name': 'Serif line', 'category': 'text',
    'when': 'The one line of the clip worth reading twice: a small lead-in, then the big payoff.',
    'never': 'Never clear before its last word is said. Never two on screen. No sparkles.',
    'params': {'on': 'phrase where the big line lands', 'small': 'lead-in words (spoken just before)', 'big': 'the payoff words',
               'hold': 'seconds after the last word, default 1.4', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    # the line ends where its LAST word is said, not where `on` is (a line once cleared before its final word was spoken)
    r = ctx.find(g['big'], after=a - 3)
    if r:
        b = max(b, r[1])
    nxt = min((w['start'] for w in ctx.words if w['start'] > b + .05), default=ctx.DUR)
    e = min(ctx.DUR, b + g.get('hold', 1.4), max(b + .7, nxt + .1))   # clear before the next sentence so its caption shows
    if e < b + .5 and e < ctx.DUR - .05:
        ctx.fail(f'serif {g["big"]!r} clears {b + .5 - e:.2f} s before it can be read (last word ends {b:.2f}, gone {e:.2f})')
    s_w, b_w = g.get('small', '').split(), g['big'].split()
    wide = .64 if ctx.var('--serif-case') == 'uppercase' else .51   # heavy caps run wider than italic serif
    size = int(min(132, 860 / (len(g['big']) * wide)))
    inner = ('<div class="fx-serif"><div class="fx-serif-scrim"></div><div class="sv-s">' + ' '.join(f'<span class="sw">{ctx.esc(x)}</span>' for x in s_w) + '</div>'
             f'<div class="sv-b" style="font-size:{size}px">' + ' '.join(f'<span class="sw">{ctx.esc(x)}</span>' for x in b_w) + '</div></div>')
    s0 = max(0, a - .9)
    if s_w:
        r = ctx.find(g['small'], after=a - 3)
        if r:   # start on its own first word: never earlier (hides other captions), never later (the caption shows it first)
            s0 = max(0, r[0] - .05)
    est_h = int((54 * 1.3 if s_w else 0) + size * 1.1 + 30)
    _, _, top = ctx.place(880, est_h, s0, e, [(90, y) for y in range(1010, 1471 - est_h, 30)] or [(90, 1010)])
    lum, busy = ctx.bg_luma(s0, e, 90, top, 970, top + est_h)
    ctx.note(f"serif {g['big']!r} background brightness {lum:.2f}, busyness {busy:.2f}")
    if lum > .5 and busy < .08:   # plain bright wall: dark text, no scrim (a dark scrim there reads as a smudge)
        inner = inner.replace('<div class="fx-serif">', '<div class="fx-serif on-light">', 1)
    cid = ctx.clip(ctx.front, s0, e, inner, f'position:absolute;left:90px;right:110px;top:{top}px;')   # right edge 970 clears the button rail
    ctx.busy.append((s0, e))
    ctx.lowbusy.append((s0, e))
    ctx.sfx(g.get('sfx'), a - .04, .5)
    ctx.tw(f"gsap.set('#{cid} .sw',{{opacity:0}});")
    if s_w:
        ctx.tw(f"tl.fromTo('#{cid} .sv-s .sw',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.26,stagger:.07,ease:'power2.out',immediateRender:false}},{ctx.q(s0)});")
    ctx.tw(f"tl.fromTo('#{cid} .sv-b .sw',{{opacity:0,y:30,scale:.9}},{{opacity:1,y:0,scale:1,duration:.4,stagger:.1,ease:'power3.out',immediateRender:false}},{ctx.q(a - .05)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-16,duration:.18}},{ctx.q(e - .18)});")


def describe(g, beat):
    return (f'As the speaker says “{g.get("small", "")}” that line fades in low and the captions pause. On “{g["on"]}” "{g["big"]}" lands in the serif. '
            f'It clears on the next sentence, {beat["hold"]:.1f} s in all.')
