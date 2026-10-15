"""A screenshot card (article, post, page) that drops in and slowly scrolls."""
import os

META = {
    'id': 'screenshot', 'name': 'Screenshot', 'category': 'media',
    'when': 'The speaker cites something you can show: an article, a post, a page.',
    'never': 'Never a screenshot whose title is hidden behind a head. Never unreadable small text.',
    'params': {'on': 'phrase that triggers it', 'src': 'image file (project-relative)', 'crop': '[x, y, w, h] in image pixels, default the whole image',
               'caption': 'short pill under the card', 'wall': 'true to sit behind the heads', 'hold': 'seconds, default 3.0', 'sfx': 'optional sound name'},
    'sfx': ['page-flip'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    url = ctx.asset(g['src'])
    W, H = ctx.image_size(url)
    x0, y0, cw, ch = g.get('crop') or [0, 0, W, min(H, W * .6)]
    img = (f'<div class="shot-img" style="background-image:url({url});background-size:{W * 900 / cw:.0f}px auto;'
           f'background-position:-{x0 * 900 / cw:.0f}px -{y0 * 900 / cw:.0f}px;height:{900 * ch / cw:.0f}px"></div>')
    cap = f'<div class="cap-pill">{ctx.esc(g["caption"])}</div>' if g.get('caption') else ''
    layer = ctx.wall if g.get('wall') and ctx.has_cut else ctx.front
    h_est = int(900 * ch / cw + (70 if cap else 0) + 20)
    _, _, top = ctx.place(900, h_est, a - .1, a + hold, [(90, 250)])
    if ctx.face_hit(a - .1, a + hold, 90, top, 990, top + h_est) > .005:   # no clear spot at full width: shrink it into the band above the head
        for wd in (760, 640, 540):
            h2 = int(h_est * wd / 900)
            _, _, top = ctx.place(wd, h2, a - .1, a + hold, [((1080 - wd) // 2, 250)])
            if ctx.face_hit(a - .1, a + hold, (1080 - wd) // 2, top, (1080 + wd) // 2, top + h2) <= .005:
                img = f'<div style="zoom:{wd / 900:.3f}">{img}</div>'
                break
    if top < 400:
        ctx.topbusy.append((a - .1, a + hold))
    elif top > 800:
        ctx.busy.append((a - .1, a + hold))
    cid = ctx.clip(layer, a - .1, a + hold, f'<div class="fx-screenshot"><div class="shot">{img}</div>{cap}</div>',
                   f'position:absolute;left:90px;top:{top}px;width:900px;', 'wallz' if layer is ctx.wall else '')
    scroll = min(60, max(0, (H - y0 - ch) * 900 / cw))   # never scroll past the bottom of the image
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:-80,rotation:-4,scale:.92}},{{opacity:1,y:0,rotation:-2,scale:1,duration:.5,ease:'power3.out',immediateRender:false}},{ctx.q(a - .1)});")
    if scroll > 4:
        ctx.tw(f"tl.to('#{cid} .shot-img',{{backgroundPositionY:'-={scroll:.0f}',duration:{hold - .6:.2f},ease:'none'}},{ctx.q(a + .4)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-40,duration:.2,ease:'power2.in'}},{ctx.q(a + hold - .2)});")
    ctx.sfx(g.get('sfx'), a - .1, .5)


def describe(g, beat):
    cap = f', captioned "{g["caption"]}"' if g.get('caption') else ''
    return f'On “{g["on"]}” a screenshot of {os.path.splitext(os.path.basename(g["src"]))[0].replace("-", " ")} drops in at the top{cap}, and holds {beat["hold"]:.1f} s.'
