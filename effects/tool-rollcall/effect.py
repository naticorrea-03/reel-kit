"""Tool roll call: a logo pill on top swaps to each tool as the speaker names it, with that tool's site in a browser frame
underneath. Each swap lands on its word."""
import importlib.util, os, sys

META = {
    'id': 'tool-rollcall', 'name': 'Tool roll call', 'category': 'ui',
    'when': 'The speaker runs through 2 to 5 tools or sites by name ("I use A, B, and C"). Each one shows on its own name.',
    'never': 'Never a tool the speaker does not name. Never real logos or site captures you have no rights to show: pass your own '
             'captures and icon files, or use the letter tiles. Never covers a face.',
    'params': {'on': 'phrase where the first tool shows', 'tools': '[{"name", "on", "src", "logo"?, "url"?}] 2 to 5; src is a screenshot of the site, '
               'logo an optional icon file (else a letter tile), url the text in the address bar (default the name)',
               'hold': 'seconds after the last tool, default 1.2', 'captions': '"pause" or "keep", default keep', 'host': '"auto" (default): "split" when the room above the face is under 40% of the frame, else "float" above the head; or force "split", "bubble" or "float"',
               'plate': 'host plate, "light" or "dark" (split defaults light, bubble dark)', 'sfx': 'optional sound per swap'},
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


W, PILL, GAPY, BAR, IMG = 860, 84, 16, 66, 260
PILLB = 116
TINTS = ['var(--c-accent)', 'var(--c-accent2)', 'var(--c-ink)', 'color-mix(in srgb,var(--c-accent) 50%,var(--c-accent2))', 'var(--c-muted)']


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'tools')
    tools = g['tools']
    if not 2 <= len(tools) <= 5 or not all(isinstance(t, dict) and t.get('name') and t.get('src') for t in tools):
        ctx.fail(f'tool-rollcall on {g["on"]!r} needs 2 to 5 tools, each with "name" and "src"')
    ts = L.times(ctx, g, tools, .9)
    for k in range(1, len(ts)):
        ts[k] = max(ts[k], ts[k - 1] + .45)
    HS = L.hosts()
    kind = HS.pick(L, ctx, g, ts[0], ts[-1] + 1, fit=(W, PILL + GAPY + BAR + IMG, (1.0, .86, .74, .66)))
    a, end = L.window(ctx, g, 1.2 + (HS.T[kind][1] if kind else 0), last=ts[-1])
    pause = g.get('captions', 'keep') == 'pause'
    if kind:
        h = HS.open(L, ctx, g, kind, a, end, 'tool-rollcall')
        if h['end'] < ts[-1] + .6:
            ctx.fail(f'tool-rollcall on {g["on"]!r}: a shot cut lands before the last tool has shown; start it earlier in the shot')
        x0, y0, x1, y1 = h['region']
        Wd, pill = x1 - x0, PILLB                                 # browser frame near full width, a big logo pill
        img = (y1 - y0) - pill - GAPY - BAR
        H = pill + GAPY + BAR + img
        x, y, sc = HS.place(L, ctx, h, Wd, H, 'tool-rollcall')
        ts = [max(t, h['c0']) for t in ts]
        for k in range(1, len(ts)):
            ts[k] = max(ts[k], ts[k - 1] + .45)
        ga, ge, gout = h['c0'], h['c1'], h['c1'] - .22
    else:
        Wd, pill, img = W, PILL, IMG
        H = pill + GAPY + BAR + img
        x, y, sc = L.above_head(ctx, 'tool-rollcall', W, H, a, end, scales=(1.0, .86, .74, .66))
        L.claim(ctx, x, y, W * sc, H * sc, a, end, pause)
        ga, ge, gout = a, end, end - .22
    pills = shots = urls = ''
    for k, t in enumerate(tools):
        logo = (f'<img src="{ctx.asset(t["logo"])}">' if t.get('logo')
                else f'<span class="lt" style="background:{TINTS[k % len(TINTS)]}">{ctx.esc(t["name"][:1].upper())}</span>')
        pills += f'<div class="pl p{k}"><span class="lg">{logo}</span><span class="nm">{ctx.esc(t["name"])}</span></div>'
        shots += f'<div class="sh s{k}" style="background-image:url({ctx.asset(t["src"])})"></div>'
        urls += f'<span class="u u{k}">{ctx.esc(t.get("url") or t["name"].lower().replace(" ", "") + ".com")}</span>'
    html = (f'<div class="fx-tool-rollcall{" big" if kind else ""}" style="width:{Wd}px;height:{H}px"><div class="pills">{pills}</div>'
            f'<div class="win" style="top:{pill + GAPY}px"><div class="bar"><span class="dots"><i></i><i></i><i></i></span><span class="addr">{urls}</span></div>'
            f'<div class="vp" style="height:{img}px">{shots}</div></div></div>')
    cid = L.zclip(ctx, ctx.front, sc, ga, ge, html, f'position:absolute;left:{x}px;top:{y}px;')
    S, q = f'#{cid}', ctx.q
    ctx.tw(f"gsap.set('{S} .win',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('{S} .win',{{opacity:0,y:50,scale:.95}},{{opacity:1,y:0,scale:1,duration:.4,ease:'back.out(1.5)',immediateRender:false}},{q(max(ga, ts[0] - .1))});")
    for k in range(len(tools)):
        ctx.tw(f"gsap.set('{S} .p{k}, {S} .s{k}, {S} .u{k}',{{opacity:0}});")
    for k, t in enumerate(ts):
        # the old pill, address and site are fully gone before the new ones arrive, so two sites never share a frame
        if k:
            ctx.tw(f"tl.to('{S} .p{k - 1}',{{opacity:0,y:-24,duration:.14,ease:'power2.in'}},{q(t - .2)});")
            ctx.tw(f"tl.to('{S} .u{k - 1}',{{opacity:0,duration:.12}},{q(t - .2)});")
            ctx.tw(f"tl.to('{S} .s{k - 1}',{{xPercent:-12,opacity:0,duration:.16,ease:'power2.in'}},{q(t - .2)});")
        ctx.tw(f"tl.fromTo('{S} .p{k}',{{opacity:0,y:30,scale:.8}},{{opacity:1,y:0,scale:1,duration:.3,ease:'back.out(2)',immediateRender:false}},{q(t)});")
        ctx.tw(f"tl.fromTo('{S} .u{k}',{{opacity:0}},{{opacity:1,duration:.15,immediateRender:false}},{q(t + .02)});")
        ctx.tw(f"tl.fromTo('{S} .s{k}',{{opacity:0,xPercent:{12 if k else 0},scale:{1 if k else 1.04}}},{{opacity:1,xPercent:0,scale:1,duration:.3,ease:'power3.out',immediateRender:false}},{q(t)});")
        if k:
            ctx.sfx(g.get('sfx'), t, .35)
    ctx.tw(f"tl.to('{S} .fx-tool-rollcall',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(gout)});")


def describe(g, beat):
    names = ', '.join(t['name'] for t in g['tools'])
    return f'From “{g["on"]}” a browser window swaps through {names}, each with its logo pill landing on its name. It holds {beat["hold"]:.1f} s.'
