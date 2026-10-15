"""Folder collect: website screenshots fan out in an arc, then drop one by one into a labeled folder that bumps as each lands.
Optionally the folder then slides over to an app icon, as if dragged into it."""
import importlib.util, os, sys

META = {
    'id': 'folder-collect', 'name': 'Folder collect', 'category': 'media',
    'when': 'The speaker gathers examples into one place ("I screenshot sites I love and drop them in one folder"), '
            'optionally then hands that folder to a tool ("then I give the folder to Claude").',
    'never': 'Never screenshots of sites the speaker does not mention or own the rights to show: use their own captures or plainly generic mocks. '
             'Never real app logos you have no rights to: pass your own icon file or use the letter tile. Never covers a face.',
    'params': {'on': 'phrase where the screenshots fan in', 'shots': '3 to 5 image files (project-relative), website screenshots',
               'folder': 'folder label, e.g. "design-taste/" (required)', 'drop_on': 'phrase where they drop into the folder (default 1.1 s after on)',
               'app': 'optional {"name", "on", "icon"?}: the folder slides over to this app icon on its phrase; icon is an image file, else a letter tile',
               'hold': 'seconds after the last beat, default 1.0', 'host': '"auto" (default): "split" when the room above the face is under 40% of the frame, else "float" above the head; or force "split", "bubble" or "float"',
               'plate': 'host plate, "light" or "dark" (split defaults light, bubble dark)', 'sfx': 'optional sound per drop'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by a creator reel on Instagram (Oct 2026)', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


FLOAT = dict(W=860, H=390, TW=290, TH=182, FW=250, FH=180, LAB=40, LIFT=56, ARC=46, AP=150)
BIG = dict(W=820, H=610, TW=390, TH=244, FW=340, FH=244, LAB=50, LIFT=72, ARC=40, AP=180)   # inside a split or bubble host


def build(g, ctx):
    L = _lib()
    HS = L.hosts()
    L.need(ctx, g, 'shots', 'folder')
    shots = g['shots']
    if not 3 <= len(shots) <= 5:
        ctx.fail(f'folder-collect on {g["on"]!r} needs 3 to 5 shots')
    a0 = ctx.at(g['on'])[0]
    kind = HS.pick(L, ctx, g, a0, a0 + 2, fit=(FLOAT['W'], FLOAT['H'], (1.0, .86, .74)))
    c0 = a0 + (HS.T[kind][0] if kind else 0)          # the graphic lands once the host has opened
    td = max(ctx.at(g['drop_on'], a0)[0] if g.get('drop_on') else c0 + 1.1, c0 + .75)
    n = len(shots)
    tdrops = [td + k * .16 for k in range(n)]
    app = g.get('app')
    ta = None
    if app:
        if not app.get('name'):
            ctx.fail('folder-collect: "app" needs a "name"')
        ta = max(ctx.at(app['on'], td)[0] if app.get('on') else tdrops[-1] + .7, tdrops[-1] + .45)
    last = (ta + .55) if ta else tdrops[-1] + .3
    a, end = L.window(ctx, g, 1.0 + (HS.T[kind][1] if kind else 0), last=last)
    D = BIG if kind else FLOAT
    W, H, TW, TH, FW, FH = D['W'], D['H'], D['TW'], D['TH'], D['FW'], D['FH']
    if kind:
        h = HS.open(L, ctx, g, kind, a, end, 'folder-collect')
        if h['end'] < last + .2:
            ctx.fail(f'folder-collect on {g["on"]!r}: a shot cut lands before the last drop; start it earlier in the shot')
        x, y, sc = HS.place(L, ctx, h, W, H, 'folder-collect')
        ga, ge, gout = h['c0'], h['c1'], h['c1'] - .22
    else:
        x, y, sc = L.above_head(ctx, 'folder-collect', W, H, a, end)
        L.claim(ctx, x, y, W * sc, H * sc, a, end)
        ga, ge, gout = a, end, end - .22

    fx, fy = (W - FW) / 2, H - FH - D['LIFT']    # folder spot; the label sits under it
    span = W - TW
    pos = []
    thumbs = ''
    for k, s in enumerate(shots):
        url = ctx.asset(s)
        u = k / (n - 1)
        tx, ty, rot = span * u, 8 + D['ARC'] * (2 * u - 1) ** 2, -13 + 26 * u      # arc: the middle card sits highest
        pos.append((u, tx, ty, rot))
        thumbs += (f'<div class="th t{k}" style="left:{tx:.0f}px;top:{ty:.0f}px;width:{TW}px;height:{TH}px;z-index:{3 + k};'
                   f'background-image:url({url})"></div>')
    icon = ''
    AP = D['AP']
    ax, ay = W - AP - 70, fy + (FH - AP) / 2
    if app:
        face = f'<img src="{ctx.asset(app["icon"])}">' if app.get('icon') else f'<span class="lt">{ctx.esc(app["name"][:1].upper())}</span>'
        icon = (f'<div class="app" style="left:{ax:.0f}px;top:{ay:.0f}px;width:{AP}px;height:{AP}px">{face}</div>'
                f'<div class="appn" style="left:{ax + AP / 2 - 115:.0f}px;top:{ay + AP + 12:.0f}px;font-size:{D["LAB"]}px">{ctx.esc(app["name"])}</div>')
    fold = f'left:{fx:.0f}px;top:{fy:.0f}px;width:{FW}px;height:{FH}px'
    name = ctx.esc(g['folder'])
    if kind:   # big folder: the name is printed on its front, so it travels with the folder
        fs = int(min(D['LAB'], (FW - 40) / (.62 * max(6, len(g['folder'])))))
        front, lab = f'<div class="fd front" style="{fold}"><span class="flab" style="font-size:{fs}px">{name}</span></div>', ''
    else:
        front = f'<div class="fd front" style="{fold}"></div>'
        lab = f'<div class="lab" style="left:{fx + FW / 2 - 260:.0f}px;width:520px;top:{fy + FH + 12:.0f}px;font-size:{D["LAB"]}px">{name}</div>'
    LB = '' if kind else f', {{S}} .lab'
    html = (f'<div class="fx-folder-collect" style="width:{W}px;height:{H}px">'
            f'<div class="fd back" style="{fold}"></div>{thumbs}{front}{lab}{icon}</div>')
    cid = L.zclip(ctx, ctx.front, sc, ga, ge, html, f'position:absolute;left:{x}px;top:{y}px;')
    S, q = f'#{cid}', ctx.q
    LB = LB.replace('{S}', S)
    FD = f'{S} .fd'
    ctx.tw(f"tl.fromTo('{FD}{LB}',{{opacity:0,scale:.6,y:30}},{{opacity:1,scale:1,y:0,duration:.4,ease:'back.out(1.8)',immediateRender:false}},{q(ga)});")
    for k, (u, tx, ty, rot) in enumerate(pos):
        ctx.tw(f"tl.fromTo('{S} .t{k}',{{opacity:0,x:{(u - .5) * 160:.0f},y:{60 + 40 * abs(u - .5):.0f},rotation:0,scale:.7}},"
               f"{{opacity:1,x:0,y:0,rotation:{rot:.1f},scale:1,duration:.42,ease:'back.out(1.5)',immediateRender:false}},{q(ga + .1 + .09 * k)});")
    # drop: each card flies to the folder mouth, shrinks and slips behind the front panel
    for k, t in enumerate(tdrops):
        u, tx, ty, rot = pos[k]
        dx = fx + FW / 2 - TW / 2 - tx
        dy = fy + 40 - TH / 2 - ty
        ctx.tw(f"tl.to('{S} .t{k}',{{x:{dx:.0f},y:{dy - 50:.0f},rotation:{(u - .5) * 10:.0f},scale:.5,duration:.24,ease:'power2.out'}},{q(t)});")
        ctx.tw(f"tl.to('{S} .t{k}',{{y:{dy + 60:.0f},scale:.42,duration:.18,ease:'power2.in'}},{q(t + .24)});")
        ctx.tw(f"tl.set('{S} .t{k}',{{opacity:0}},{q(t + .42)});")
        ctx.tw(f"tl.fromTo('{FD}',{{scaleY:1,scaleX:1}},{{scaleY:.92,scaleX:1.05,duration:.08,ease:'power1.out',yoyo:true,repeat:1,immediateRender:false}},{q(t + .38)});")
        ctx.sfx(g.get('sfx'), t + .38, .35)
    if app:
        c0 = fx + FW / 2
        ctx.tw(f"gsap.set('{S} .app, {S} .appn',{{opacity:0}});")
        ctx.tw(f"tl.to('{FD}{LB}',{{x:{W * .26 - c0:.0f},duration:.32,ease:'power2.inOut'}},{q(ta - .32)});")
        ctx.tw(f"tl.fromTo('{S} .app',{{opacity:0,scale:.5}},{{opacity:1,scale:1,duration:.35,ease:'back.out(2)',immediateRender:false}},{q(ta - .3)});")
        ctx.tw(f"tl.fromTo('{S} .appn',{{opacity:0}},{{opacity:1,duration:.2,immediateRender:false}},{q(ta - .2)});")
        if not kind:
            ctx.tw(f"tl.to('{S} .lab',{{opacity:0,duration:.12}},{q(ta)});")
        ctx.tw(f"tl.to('{FD}',{{x:{ax + AP / 2 - c0:.0f},y:{ay + AP / 2 - (fy + FH / 2) - 40:.0f},scale:.3,duration:.38,ease:'power3.in'}},{q(ta)});")
        ctx.tw(f"tl.to('{FD}',{{opacity:0,duration:.08}},{q(ta + .32)});")
        ctx.tw(f"tl.fromTo('{S} .app',{{scale:1}},{{scale:1.12,duration:.1,yoyo:true,repeat:1,ease:'power1.out',immediateRender:false}},{q(ta + .38)});")
    ctx.tw(f"tl.to('{S} .fx-folder-collect',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(gout)});")


def describe(g, beat):
    tail = f', then the folder slides into the {g["app"]["name"]} icon' if g.get('app') else ''
    return (f'On “{g["on"]}” {len(g["shots"])} screenshots fan in, then drop one by one into a folder labeled “{g["folder"]}”{tail}. '
            f'It holds {beat["hold"]:.1f} s.')
