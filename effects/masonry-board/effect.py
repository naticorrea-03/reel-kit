"""Masonry board: a moodboard of images in staggered columns drops in and drifts upward, each column at its own speed,
with a small source pill pinned on top. Captions keep running underneath."""
import importlib.util, os, sys

META = {
    'id': 'masonry-board', 'name': 'Masonry moodboard', 'category': 'media',
    'when': 'The speaker talks about collecting inspiration or references ("I save everything to one board").',
    'never': 'Never other people\'s images presented as the speaker\'s own work: use their saved references with credit, or plainly generic art. '
             'Never a platform logo you have no rights to: the pill is plain text. Never covers a face.',
    'params': {'on': 'phrase where the board drops in', 'images': '6 or more image files (project-relative); they repeat to fill the columns',
               'source': 'text on the pill, e.g. "My saved board" (required)', 'cols': '2 or 3 columns, default 3',
               'hold': 'seconds on screen, default 2.6', 'host': '"auto" (default): "split" when the room above the face is under 40% of the frame, else "float" above the head; or force "split", "bubble" or "float"',
               'plate': 'host plate, "light" or "dark" (split defaults light, bubble dark)', 'sfx': 'optional sound name'},
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


BW, BH, PAD, GAP = 860, 420, 16, 14
RATIOS = [1.25, .7, 1.0, 1.45, .62, .9, 1.15, .78]     # fallback tile height / width when an image size cannot be read


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'images', 'source')
    imgs = g['images']
    if len(imgs) < 6:
        ctx.fail(f'masonry-board on {g["on"]!r} needs 6 or more images')
    HS = L.hosts()
    a0 = ctx.at(g['on'])[0]
    kind = HS.pick(L, ctx, g, a0, a0 + 2, fit=(BW, BH, (1.0, .86, .74)))
    a, end = L.window(ctx, g, 2.6 + (HS.T[kind][1] if kind else 0))
    W, H = BW, BH
    if kind:
        h = HS.open(L, ctx, g, kind, a, end, 'masonry-board')
        x0, y0, x1, y1 = h['region']
        W, H = x1 - x0, y1 - y0                                  # the board fills the host's page: tall, near full width
        x, y, sc = HS.place(L, ctx, h, W, H, 'masonry-board')
        ga, ge, gout = h['c0'], h['c1'], h['c1'] - .22
    else:
        x, y, sc = L.above_head(ctx, 'masonry-board', W, H, a, end, scales=(1.0, .86, .74))
        L.claim(ctx, x, y, W * sc, H * sc, a, end)
        ga, ge, gout = a, end, end - .22
    nc = 3 if int(g.get('cols', 3)) >= 3 else 2
    cw = (W - 2 * PAD - (nc - 1) * GAP) / nc
    urls = [ctx.asset(p) for p in imgs]
    asp = []
    for k_, u in enumerate(urls):   # each tile keeps its image's own shape, so nothing stretches or letterboxes
        try:
            iw, ih = ctx.image_size(u)
            asp.append(min(1.6, max(.55, ih / iw)))
        except Exception:
            asp.append(RATIOS[k_ % len(RATIOS)])
    cols, k = [], 0
    T = ge - ga
    drift = [70 + 40 * T, 110 + 55 * T, 85 + 45 * T][:nc]        # px each column travels, middle one fastest
    ch = H - 84 - PAD                                            # column window under the pill
    pos0, pos1 = [], []
    for c in range(nc):
        # one div per column painted with stacked background layers: the box never leaves the card while the images scroll
        lay, hgt = [], -30 * c                                   # columns start offset so the board reads as masonry
        while hgt < ch + drift[c] + 40:
            th = cw * asp[k % len(urls)]
            lay.append((urls[k % len(urls)], hgt, th))
            hgt += th + GAP
            k += 1
        imgs_ = ','.join(f'url({u})' for u, _, _ in lay)
        size = ','.join(f'{cw:.0f}px {th:.0f}px' for _, _, th in lay)
        pos0.append(','.join(f'0px {t:.0f}px' for _, t, _ in lay))
        pos1.append(','.join(f'0px {t - drift[c]:.0f}px' for _, t, _ in lay))
        cols.append(f'<div class="col c{c}" style="left:{PAD + c * (cw + GAP):.0f}px;width:{cw:.0f}px;height:{ch}px;'
                    f'background-image:{imgs_};background-size:{size};background-position:{pos0[-1]}"></div>')
    html = (f'<div class="fx-masonry-board" style="width:{W}px;height:{H}px"><div class="vp">{"".join(cols)}</div>'
            f'<div class="pill">{ctx.esc(g["source"])}</div></div>')
    cid = L.zclip(ctx, ctx.front, sc, ga, ge, html, f'position:absolute;left:{x}px;top:{y}px;')
    S, q = f'#{cid}', ctx.q
    ctx.tw(f"tl.fromTo('{S} .fx-masonry-board',{{opacity:0,y:-60,rotation:-2,scale:.94}},{{opacity:1,y:0,rotation:0,scale:1,duration:.45,ease:'power3.out',immediateRender:false}},{q(ga)});")
    ctx.tw(f"tl.fromTo('{S} .col',{{opacity:0,y:24}},{{opacity:1,y:0,duration:.3,stagger:.06,ease:'power3.out',immediateRender:false}},{q(ga + .1)});")
    ctx.tw(f"tl.fromTo('{S} .pill',{{opacity:0,y:-14}},{{opacity:1,y:0,duration:.25,ease:'power2.out',immediateRender:false}},{q(ga + .3)});")
    for c in range(nc):
        ctx.tw(f"tl.fromTo('{S} .c{c}',{{backgroundPosition:'{pos0[c]}'}},{{backgroundPosition:'{pos1[c]}',duration:{T:.3f},ease:'none',immediateRender:false}},{q(ga)});")
    ctx.sfx(g.get('sfx'), ga, .4)
    ctx.tw(f"tl.to('{S} .fx-masonry-board',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(gout)});")


def describe(g, beat):
    return f'On “{g["on"]}” a moodboard of {len(g["images"])} images drops in and drifts upward under a “{g["source"]}” pill. It holds {beat["hold"]:.1f} s.'
