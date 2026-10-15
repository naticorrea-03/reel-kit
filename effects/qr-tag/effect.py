"""A hang tag swings in and its QR code pops."""
import random

META = {
    'id': 'qr-tag', 'name': 'QR hang tag', 'category': 'media',
    'when': 'The speaker mentions QR codes, tags, or scanning something in a store.',
    'never': 'Never a real-looking code that points somewhere: the pattern is decorative.',
    'params': {'on': 'phrase that triggers it', 'brand': 'small caps text on the tag, default "hang tag"', 'label': 'handwritten line, default "scan me"',
               'seed': 'pattern seed, default 7', 'hold': 'seconds, default 3.0', 'sfx': 'sound name, default scanner-beep'},
    'sfx': ['scanner-beep'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def qr_cells(seed):
    rnd = random.Random(seed)
    finder = lambda x, y, ox, oy: (x - ox in (0, 6) or y - oy in (0, 6) or (2 <= x - ox <= 4 and 2 <= y - oy <= 4))
    out = []
    for y in range(21):
        for x in range(21):
            if x < 7 and y < 7:
                on = finder(x, y, 0, 0)
            elif x >= 14 and y < 7:
                on = finder(x, y, 14, 0)
            elif x < 7 and y >= 14:
                on = finder(x, y, 0, 14)
            elif (x < 8 and y < 8) or (x > 12 and y < 8) or (x < 8 and y > 12):
                on = False
            else:
                on = rnd.random() < .5
            if on:
                out.append(f'<i style="left:{x * 14}px;top:{y * 14}px"></i>')
    return ''.join(out)


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    for zf in (1.0, .8, .65, .5):
        tw_, th_ = 420 * zf, 560 * zf
        cov, qx, topy = ctx.place(tw_, th_, s0, s0 + hold, [(x, y) for y in (260, 420, 600, 760) for x in (100, 540 - tw_ / 2, 980 - tw_)])
        if cov <= .04:
            break
    if cov > .04:
        ctx.warn(f'qr tag hides {cov:.0%}')
    html = (f'<div class="fx-qr-tag"><div class="tag" style="zoom:{zf};margin:0"><div class="tag-hole"></div><div class="tag-brand">{ctx.esc(g.get("brand", "hang tag"))}</div>'
            f'<div class="qr">{qr_cells(g.get("seed", 7))}</div><div class="tag-s">{ctx.esc(g.get("label", "scan me"))}</div></div></div>')
    anim = [f"tl.fromTo('#ID .tag',{{rotation:-14,transformOrigin:'50% 0%'}},{{rotation:6,duration:.9,ease:'elastic.out(1,.4)',immediateRender:false}},{ctx.q(s0)});",
            f"tl.fromTo('#ID .qr',{{opacity:0,scale:.6}},{{opacity:1,scale:1,duration:.3,ease:'back.out(2)',immediateRender:false}},{ctx.q(s0 + .35)});"]
    ctx.sfx(g.get('sfx', 'scanner-beep'), s0 + .35, .45)
    ctx.ui_window(g, a, html, anim, hold, s0, 'front', height=0, topy=topy, extra_css=f'left:{qx:.0f}px;width:{420 * zf + 20:.0f}px;')


def describe(g, beat):
    return f'On “{g["on"]}” a hang tag swings in and its QR code pops. It holds {beat["hold"]:.1f} s.'
