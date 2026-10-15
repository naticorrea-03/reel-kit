"""Word trio: three (or so) words land one per beat as the speaker says them. Captions pause."""

META = {
    'id': 'words3', 'name': 'Word trio', 'category': 'text',
    'when': 'The speaker lists two to four parallel things in one breath.',
    'never': 'Never for a list that is not said out loud in order. Each word waits for its own beat.',
    'params': {'on': 'phrase near the first item', 'items': '[[shown word, spoken phrase], ...]', 'hold': 'seconds after the last item, default 1.5'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    items = g['items']
    times = [ctx.at(ph, a - .2)[0] for _, ph in items]
    if any(t1 < t0 for t0, t1 in zip(times, times[1:])):
        ctx.fail(f'words3 items are not said in order: {[ph for _, ph in items]}')
    e = min(ctx.DUR, times[-1] + g.get('hold', 1.5))
    fs = int(min(118, 860 / (len(' '.join(t for t, _ in items)) * .52)))
    inner = (f'<div class="fx-words3"><div class="fx-words3-scrim"></div><div class="w3" style="font-size:{fs}px">'
             + ''.join(f'<span class="w3w">{ctx.esc(t)}</span>' for t, _ in items) + '</div></div>')
    est_h = int(fs * 1.15 + 30)
    _, _, top = ctx.place(880, est_h, times[0] - .05, e, [(90, y) for y in range(1060, 1471 - est_h, 30)] or [(90, 1060)])
    lum, busy = ctx.bg_luma(times[0], e, 90, top, 970, top + est_h)
    if lum > .5 and busy < .08:   # plain bright wall: dark words, no scrim
        inner = inner.replace('<div class="fx-words3">', '<div class="fx-words3 on-light">', 1)
    cid = ctx.clip(ctx.front, times[0] - .05, e, inner, f'position:absolute;left:90px;right:110px;top:{top}px;')
    ctx.busy.append((times[0] - .05, e))
    ctx.lowbusy.append((times[0] - .05, e))
    ctx.tw(f"gsap.set('#{cid} .w3w',{{opacity:0}});")   # each word waits for its beat
    for k, t in enumerate(times):
        ctx.tw(f"tl.fromTo('#{cid} .w3w:nth-child({k + 1})',{{opacity:0,scale:1.4,filter:'blur(12px)'}},{{opacity:1,scale:1,filter:'blur(0px)',duration:.22,ease:'power3.out',immediateRender:false}},{ctx.q(t - .04)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.18}},{ctx.q(e - .18)});")


def describe(g, beat):
    return 'Words land one per beat: ' + ', '.join(f'"{w}" on “{ph}”' for w, ph in g['items']) + '.'
