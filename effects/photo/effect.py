"""A polaroid photo that tilts in beside the speaker."""
import os

META = {
    'id': 'photo', 'name': 'Photo', 'category': 'media',
    'when': 'The speaker names a person, place or thing you have a real photo of.',
    'never': 'Never a photo of the speaker who is already on screen. Never over a face.',
    'params': {'on': 'phrase that triggers it', 'src': 'photo file (project-relative)', 'caption': 'handwritten caption under it',
               'w': 'width px, default 380 (shrinks to fit)', 'aspect': 'height/width, default 1.5', 'side': 'left or right',
               'hold': 'seconds, default 2.4', 'sfx': 'sound name, default camera-shutter'},
    'sfx': ['camera-shutter'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 2.4)
    names = [(s or {}).get('name') for s in ctx.speakers.values()]
    if g.get('caption') and g['caption'] in names:   # a photo of the speaker labelled with her own name while she is on camera with a name tag
        ctx.fail(f'photo {g["src"]!r} only shows a speaker who is already on screen; use something they name')
    url = ctx.asset(g['src'])
    for w in (g.get('w', 380), 300, 240, 200):
        hgt = w * g.get('aspect', 1.5) + 70
        cov, x, ty = ctx.place(w + 28, hgt, a, a + hold, [(x_, y_) for y_ in (260, 420, 600, 820) for x_ in (70, 1080 - w - 130)])
        if cov <= .05:
            break
    if cov > .05:
        ctx.warn(f'photo {g["src"]} hides {cov:.0%} of a speaker')
    if ty + hgt > 1230:
        ctx.busy.append((a - .08, a + hold))
    if ty < 400:
        ctx.topbusy.append((a - .08, a + hold))
    rot = 5 if x > 500 else -5
    cap = f'<div class="ph-cap">{ctx.esc(g["caption"])}</div>' if g.get('caption') else ''
    cid = ctx.clip(ctx.front, a - .08, a + hold, f'<div class="fx-photo"><img src="{url}" style="width:{w}px;display:block">{cap}</div>',
                   f'position:absolute;left:{x}px;top:{ty}px;')
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,scale:.5,y:80,rotation:{rot * 2.5}}},{{opacity:1,scale:1,y:0,rotation:{rot},duration:.45,ease:'back.out(1.5)',immediateRender:false}},{ctx.q(a - .08)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,scale:.8,y:-40,duration:.18,ease:'power2.in'}},{ctx.q(a + hold - .18)});")
    ctx.sfx(g.get('sfx', 'camera-shutter'), a - .05, .5)


def describe(g, beat):
    what = g.get('caption') or os.path.splitext(os.path.basename(g['src']))[0].replace('_', ' ').replace('-', ' ')
    return f'On “{g["on"]}” a photo ({what}) tilts in and holds {beat["hold"]:.1f} s.'
