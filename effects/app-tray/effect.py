"""App tray: a row of app icons in edit mode; each one is deleted as the speaker names it, and what is left is the point."""
import importlib.util, os, sys

META = {
    'id': 'app-tray', 'name': 'App tray delete', 'category': 'ui',
    'when': 'The speaker lists tools they no longer need ("no CapCut, no Edits app, nothing"). Each icon goes on its own name; the end word lands the payoff.',
    'never': 'Never icons the speaker does not name. Never real logos you do not have rights to: pass your own icon files or use the letter tiles. Never covers a face.',
    'params': {'on': 'phrase that brings the tray in', 'title': 'small tray header, default "Edit mode"',
               'apps': '[{"name", "on", "icon"?, "keep"?}] 2 to 5; each is deleted on its "on" phrase unless "keep" is true; icon is an image file, else a letter tile',
               'end': 'italic word that replaces the tray contents at the end, e.g. "nothing." (optional)', 'end_on': 'phrase for the end word',
               'hold': 'seconds after the last beat, default 1.2', 'sfx': 'optional sound per delete'},
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


IC, GAP, PAD = 128, 38, 36
TINTS = ['var(--c-accent2)', 'var(--c-accent)', 'var(--c-ink)', 'color-mix(in srgb,var(--c-accent) 50%,var(--c-accent2))', 'var(--c-muted)']


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'apps')
    apps = g['apps']
    if not 2 <= len(apps) <= 5 or not all(isinstance(x, dict) and x.get('name') for x in apps):
        ctx.fail(f'app-tray on {g["on"]!r} needs 2 to 5 apps, each with "name"')
    a0 = ctx.at(g['on'])[0]
    dels, after = [], a0 + .2
    for x in apps:
        if x.get('keep'):
            dels.append(None)
            continue
        t = ctx.at(x['on'], after)[0] if x.get('on') else (max([d for d in dels if d] or [a0 + .2]) + .55)
        t = max(t, a0 + .55, max([d for d in dels if d] or [0]) + .4)
        dels.append(t)
        after = t
    te = None
    if g.get('end'):
        te = max(ctx.at(g['end_on'], a0)[0] if g.get('end_on') else max([d for d in dels if d] or [a0]) + .5,
                 max([d for d in dels if d] or [a0]) + .35)
    last = max([d for d in dels if d] + [te or 0, a0 + .6])
    a, end = L.window(ctx, g, 1.2, last=last)
    n = len(apps)
    W = 2 * PAD + n * IC + (n - 1) * GAP
    W = max(W, 560)
    H = 66 + IC + 56 + 30
    x, y, sc = L.above_head(ctx, 'app-tray', W, H, a, end)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    title = g.get('title', 'Edit mode')
    keep_n = sum(1 for d in dels if d is None)
    counts = [n]
    for d in sorted(d for d in dels if d):
        counts.append(counts[-1] - 1)
    cnt = ''.join(f'<span class="c c{k}">{c} app{"s" if c != 1 else ""}</span>' for k, c in enumerate(counts))
    x0 = (W - (n * IC + (n - 1) * GAP)) / 2
    icons = ''
    for k, ap in enumerate(apps):
        url = ctx.asset(ap['icon']) if ap.get('icon') else None
        face = f'<img src="{url}">' if url else f'<span class="lt">{ctx.esc(ap["name"][:1].upper())}</span>'
        bg = '' if url else f'background:{TINTS[k % len(TINTS)]};'
        icons += (f'<div class="ap a{k}" style="left:{x0 + k * (IC + GAP):.0f}px"><div class="ic" style="{bg}">{face}</div>'
                  + ('' if ap.get('keep') else '<b class="mn"></b>') + f'<div class="nm">{ctx.esc(ap["name"])}</div></div>')
    endw = f'<div class="ew">{ctx.esc(g["end"])}</div>' if g.get('end') else ''
    html = (f'<div class="fx-app-tray" style="width:{W}px;height:{H}px"><div class="hd"><span>{ctx.esc(title)}</span><span class="cs">{cnt}</span></div>'
            f'<div class="row">{icons}</div>{endw}</div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .fx-app-tray',{{opacity:0,y:-50,scale:.94}},{{opacity:1,y:0,scale:1,duration:.4,ease:'back.out(1.6)',immediateRender:false}},{q(a)});")
    for k in range(1, len(counts)):
        ctx.tw(f"gsap.set('#{cid} .c{k}',{{opacity:0}});")
    # edit-mode jiggle while the icons wait
    for k, ap in enumerate(apps):
        if ap.get('keep'):
            continue
        r = 2.4 if k % 2 else -2.4
        ctx.tw(f"tl.fromTo('#{cid} .a{k} .ic',{{rotation:{-r}}},{{rotation:{r},duration:.13,yoyo:true,repeat:{int((end - a) / .13)},ease:'sine.inOut',immediateRender:false}},{q(a + .3)});")
    order = sorted((d, k) for k, d in enumerate(dels) if d)
    shift = [0] * n
    for ci, (d, k) in enumerate(order):
        ctx.tw(f"tl.to('#{cid} .a{k}',{{scale:0,opacity:0,duration:.2,ease:'back.in(2)'}},{q(d)});")
        for j in range(k + 1, n):
            if dels[j] is None or dels[j] > d:
                shift[j] -= IC + GAP
                ctx.tw(f"tl.to('#{cid} .a{j}',{{x:{shift[j]},duration:.3,ease:'power3.out'}},{q(d + .14)});")
        ctx.tw(f"tl.fromTo('#{cid} .c{ci}',{{opacity:1}},{{opacity:0,duration:.01,immediateRender:false}},{q(d + .1)});")
        ctx.tw(f"tl.fromTo('#{cid} .c{ci + 1}',{{opacity:0}},{{opacity:1,duration:.01,immediateRender:false}},{q(d + .1)});")
        ctx.sfx(g.get('sfx'), d, .35)
    if te:
        ctx.tw(f"gsap.set('#{cid} .ew',{{opacity:0}});")
        for k, ap in enumerate(apps):
            if dels[k] is None or dels[k] > te:
                ctx.tw(f"tl.to('#{cid} .a{k}',{{y:260,rotation:{(-1) ** k * 24},opacity:0,duration:.4,ease:'power2.in'}},{q(te - .05 + .05 * k)});")
        ctx.tw(f"tl.to('#{cid} .cs',{{opacity:0,duration:.15}},{q(te)});")
        ctx.tw(f"tl.fromTo('#{cid} .ew',{{opacity:0,y:20,filter:'blur(8px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.35,ease:'power3.out',immediateRender:false}},{q(te + .2)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(end - .22)});")


def describe(g, beat):
    gone = ', '.join(x['name'] for x in g['apps'] if not x.get('keep'))
    return (f'On “{g["on"]}” a tray of app icons drops in, jiggling in edit mode; {gone} get deleted one by one as each is named'
            f'{", then “" + g["end"] + "” takes their place" if g.get("end") else ""}. It holds {beat["hold"]:.1f} s.')
