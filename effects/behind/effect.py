"""Big words behind the speaker's head (the cutout sits in front of them)."""

META = {
    'id': 'behind', 'name': 'Big words', 'category': 'text',
    'when': 'Lands the payoff word or two of a line, huge, behind the head.',
    'never': 'Never as gap filler on a non-payoff word. Never on a wide shot. Parallel lines get one shared size (max_size).',
    'params': {'on': 'phrase that triggers it', 'words': 'list of words to show', 'hold': 'seconds, default 1.3',
               'max_size': 'px cap; give every line of a parallel set the same value', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 1.3)
    words = g['words']
    if ctx.has_cut and ctx.face_scale_at(a) < .075:
        ctx.fail(f'behind {words} cannot be placed (wide shot, heads cover the band); move or cut it, a silent skip hides a graphic you asked for')
    longest = max(len(w) for w in words)
    size = int(min(250, 940 / (max(longest, 4) * .62)))
    ht = ctx.head_top(a + .15) or 520

    def layout(size):
        per = max(1, int(940 / (size * .6)))
        lines, cur = [], []
        for w in words:
            if cur and len(' '.join(cur + [w])) > per:
                lines.append(cur)
                cur = []
            cur.append(w)
        lines.append(cur)
        topy = int(max(240, ht + .15 * size - .72 * size - (len(lines) - 1) * .86 * size))
        return lines, topy

    def worst_word(size, lines, topy):
        # every word judged on its own: one hidden word makes the line unreadable
        worst = 0.0
        for li, ln in enumerate(lines):
            x = 540 - len(' '.join(ln)) * .6 * size / 2
            y0, y1 = topy + li * .86 * size + .12 * size, topy + (li + 1) * .86 * size
            for w in ln:
                ww = len(w) * .6 * size
                worst = max(worst, max(ctx.alpha_cover(a + k * hold / 3, x, y0, x + ww, y1) for k in (0, 1, 2)))
                x += ww + .6 * size
        return worst

    best = None
    while size >= 110:
        lines, topy = layout(size)
        if max(len(' '.join(l)) for l in lines) * .6 * size <= 950:
            cov = worst_word(size, lines, topy)
            if best is None or cov < best[0]:
                best = (cov, size, lines, topy)
            if cov <= .03:
                break
        size -= 10
    if best is None:
        ctx.fail(f'behind {words} is too long to fit the frame at any size; use fewer words')
    cov, size, lines, topy = best
    layer = ctx.wall
    if cov > .03:
        # the keyword still has to land: put it in front, in the clear band above the faces
        ftop = min([f[1] for k in range(5) for f in ctx.faces_at(a + hold * k / 4)] or [700])
        size = int(min(g.get('max_size', 220), 940 / (max(longest, 4) * .62)))   # max_size keeps parallel words one size
        while size >= 90:
            lines, _ = layout(size)
            hgt = len(lines) * .86 * size + .1 * size
            if 250 + hgt <= ftop - 20 and max(len(' '.join(l)) for l in lines) * .6 * size <= 900:
                break
            size -= 10
        if size < 90:
            ctx.fail(f'behind {words} cannot be placed (no clear band above the faces); move or cut it, a silent skip hides a graphic you asked for')
        topy, layer = 250, ctx.front
        ctx.note(f'behind {words} moved in front, above the faces ({cov:.0%} would hide behind heads)')
    inner = '<br>'.join(' '.join(f'<span class="bw" style="display:inline-block">{ctx.esc(w)}</span>' for w in ln) for ln in lines)
    if g.get('max_size'):
        ctx.parallel.setdefault(g['max_size'], []).append((' '.join(words), len(lines), size))
    ctx.topbusy.append((a - .05, a + hold))
    cid = ctx.clip(layer, a - .05, a + hold, f'<div class="fx-behind" style="font-size:{size}px">{inner}</div>',
                   f'position:absolute;left:0;right:0;top:{topy}px;', 'wallz' if layer is ctx.wall else '')
    step = min(.18, hold / max(2, len(words)) / 2)
    ctx.tw(f"gsap.set('#{cid} .bw',{{opacity:0}});")
    for k in range(len(words)):
        ctx.tw(f"tl.fromTo(document.querySelectorAll('#{cid} .bw')[{k}],{{opacity:0,scale:1.25,filter:'blur(16px)'}},"
               f"{{opacity:1,scale:1,filter:'blur(0px)',duration:.22,ease:'power3.out',immediateRender:false}},{ctx.q(a - .05 + k * step)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,filter:'blur(8px)',duration:.14}},{ctx.q(a + hold - .14)});")
    ctx.sfx(g.get('sfx'), a - .05, .5)


def describe(g, beat):
    where = 'behind the head' if beat['onwall'] else 'above the head'
    return f'On “{g["on"]}” the words "{" ".join(g["words"])}" land word by word in big type {where}, then blur out after {beat["hold"]:.1f} s.'
