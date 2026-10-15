"""A study or document: its header drops in at the top, then the cited line appears below with a highlighter pass."""
import os

META = {
    'id': 'highlight-paper', 'name': 'Study screenshot', 'category': 'annotation',
    'when': 'The speaker cites a study, report or document and one line of it is the proof.',
    'never': 'Never a header so small the title cannot be read (it is dropped instead). Never a line hidden behind a head.',
    'params': {'on': 'phrase that triggers it', 'src': 'tall capture of the page (project-relative)',
               'header': '[[y, h], ...] bands of the image stacked as the header card (image px)',
               'line': '{"y", "h", "marks": [[x0, y0, x1, y1], ...]} the cited band and highlight boxes inside it (image px)',
               'caption': 'pill above the cited line, e.g. the source', 'hold': 'seconds, default 3.6', 'sfx': 'sound name, default page-flip'},
    'sfx': ['page-flip'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.6)
    src = ctx.asset(g['src'])
    IW, IH = ctx.image_size(src)
    bands = g.get('header') or [[0, min(IH, IW * .3)]]
    hsum = sum(h for _, h in bands)
    line = g['line']

    # a head behind any one text line makes it unreadable: judge 20 px line bands, not the whole card
    def worst(Wd, top):
        h = hsum * Wd / IW + 16   # + the card frame padding
        return max(ctx.alpha_cover(a - .1 + (hold - .1) * k / 12, (1080 - Wd) / 2, y, (1080 + Wd) / 2, min(top + h, y + 20))
                   for k in range(13) for y in range(top, int(top + h), 20))
    fit = next(((w, t) for w in range(900, 540, -20) for t in (330, 290, 250) if worst(w, t) <= .02), None)
    layer = ctx.wall if ctx.has_cut else ctx.front
    if fit:
        Wd, ptop = fit
    else:   # closer zooms leave no room behind the head: go in front, as wide as clears every face
        layer = ctx.front
        Wd, ptop = next(((w, 240) for w in range(900, 400, -20)
                         if ctx.face_hit(a - .1, a + hold, (1080 - w) / 2 - 6, 240, (1080 + w) / 2 + 6, 240 + hsum * w / IW + 22) <= .005), (420, 240))
        ctx.note(f'paper header moved in front at {Wd} px (no clear spot behind the head)')
    skip_hdr = Wd < 760   # a narrow header shrinks the title past reading; the cited-line card names the source anyway
    if not skip_hdr:   # the cited-line card must also fit somewhere clear of faces with the header up; if not, the header gives way
        _ch = int(line['h'] * 980 / IW + (70 if g.get('caption') else 0) + 30)
        _hb = ptop + hsum * Wd / IW + 36
        _t2 = a + .9
        if not any(ctx.face_hit(_t2, a + hold, 44, y, 1036, y + _ch) <= .005
                   for y in range(240, 1156 - _ch, 30) if y >= _hb or y + _ch <= ptop - 16):
            skip_hdr = True
            ctx.note('paper header dropped: with it up, the cited-line card has no spot clear of the faces')
    if skip_hdr and Wd < 760:
        ctx.note(f'paper header dropped (only {Wd} px fits); the cited-line card carries the source')
    sc = Wd / IW
    crop = lambda y0, h: f'<div style="width:{Wd}px;height:{h * sc:.0f}px;background:url({src}) no-repeat 0 -{y0 * sc:.0f}px/{Wd}px auto"></div>'
    if not skip_hdr:
        hdr = f'<div class="fx-highlight-paper"><div class="shot" style="width:{Wd + 12}px">{"".join(crop(y, h) for y, h in bands)}</div></div>'
        cid = ctx.clip(layer, a - .1, a + hold, hdr, f'position:absolute;left:{(1080 - Wd - 12) // 2}px;top:{ptop}px;', 'wallz' if layer is ctx.wall else '')
        ctx.topbusy.append((a - .1, a + hold))
        ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:-90,rotation:-3}},{{opacity:1,y:0,rotation:-1.5,duration:.5,ease:'power3.out',immediateRender:false}},{ctx.q(a - .1)});")
        ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-40,duration:.2,ease:'power2.in'}},{ctx.q(a + hold - .2)});")
    fw = 980
    fs = fw / IW
    hl = ''.join(f'<i class="paper-hl" style="left:{x0 * fs:.0f}px;top:{y0 * fs:.0f}px;width:{(x1 - x0) * fs:.0f}px;height:{(y1 - y0) * fs:.0f}px"></i>'
                 for x0, y0, x1, y1 in line.get('marks', []))
    cap = f'<div class="cap-pill">{ctx.esc(g["caption"])}</div>' if g.get('caption') else ''
    card = (f'<div class="fx-highlight-paper">{cap}<div class="shot find" style="width:{fw + 12}px;position:relative">'
            f'<div style="width:{fw}px;height:{line["h"] * fs:.0f}px;background:url({src}) no-repeat 0 -{line["y"] * fs:.0f}px/{fw}px auto"></div>{hl}</div></div>')
    t2 = a + (.05 if skip_hdr else .9)
    card_h = int(line['h'] * fs + (70 if cap else 0) + 30)
    cx = (1080 - fw - 12) // 2
    ys = [y for y in [880] + list(range(240, 1471 - card_h, 30)) if y + card_h <= 1155]   # full width: stay above the button rail
    if not skip_hdr:   # never on top of its own header
        hdr_h = sum(h for _, h in bands) * sc + 20
        ys = [y for y in ys if y >= ptop + hdr_h + 16 or y + card_h <= ptop - 16]
    _, _, ctop = ctx.place(fw + 12, card_h, t2, a + hold, [(cx, y) for y in ys] or [(cx, 880)], scan=False)
    cid2 = ctx.clip(ctx.front, t2, a + hold, card, f'position:absolute;left:{(1080 - fw - 12) // 2}px;top:{ctop}px;')
    ctx.busy.append((t2, a + hold))
    ctx.lowbusy.append((t2, a + hold))
    ctx.tw(f"tl.fromTo('#{cid2}',{{opacity:0,y:60,scale:.92}},{{opacity:1,y:0,scale:1,duration:.4,ease:'back.out(1.4)',immediateRender:false}},{ctx.q(t2)});")
    ctx.tw(f"gsap.set('#{cid2} .paper-hl',{{scaleX:0}});")
    ctx.tw(f"tl.fromTo('#{cid2} .paper-hl',{{scaleX:0}},{{scaleX:1,duration:.35,stagger:.3,ease:'power2.inOut',immediateRender:false}},{ctx.q(t2 + .45)});")
    ctx.tw(f"tl.to('#{cid2}',{{opacity:0,y:30,duration:.2,ease:'power2.in'}},{ctx.q(a + hold - .2)});")
    snd = g.get('sfx', 'page-flip')
    ctx.sfx(snd, a - .1, .55)
    ctx.sfx(snd, t2, .45)


def describe(g, beat):
    cap = f', captioned "{g["caption"]}"' if g.get('caption') else ''
    return f'On “{g["on"]}” the study header drops in at the top, then the cited line slides up with a highlighter pass{cap}. It holds {beat["hold"]:.1f} s.'
