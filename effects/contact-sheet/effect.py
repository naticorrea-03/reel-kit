"""Contact sheet: a film contact sheet of the reel's own raw frames drops in, and the bad takes get circled and crossed out in red."""
import importlib.util, os, subprocess, sys

META = {
    'id': 'contact-sheet', 'name': 'Contact sheet markup', 'category': 'annotation',
    'when': 'The speaker talks about raw footage, takes or the cut: "I drop in the raw footage", "the bad takes", "it finds the dead air".',
    'never': 'Never marks with no meaning: each circle or cross has a label or a spoken reason. Never covers a face.',
    'params': {'on': 'phrase that drops the sheet in', 'frames': 'number of frames, 8 or 12 (default 12), pulled evenly from this clip\'s own footage',
               'images': 'optional list of image files to use instead of the clip\'s own frames',
               'marks': '[{"frame": index, "mark": "circle" or "cross", "label"?: short red note, "on"?: phrase}] up to 4',
               'title': 'small footer line, default "Raw takes"', 'hold': 'seconds after the last mark, default 1.2',
               'sfx': 'sound per mark, default marker-circle ("none" for silence)'},
    'sfx': ['marker-circle'], 'source': 'ours', 'credit': 'Motion idea inspired by @justyn.ai on Instagram', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


FW, FH = 118, 150   # one frame on the sheet
COLS = 6


def _frames(ctx, n):
    """n stills spread across this clip's own a-roll, cropped to the frame shape; returns asset urls."""
    out = []
    for k in range(n):
        t = ctx.DUR * (k + .5) / n
        rel = f'assets/fx/contact-{k:02d}-{int(t * 100)}.jpg'
        dst = ctx.asset_path(rel)
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{t:.2f}', '-i', os.path.join(ctx.D, 'assets', 'aroll.mp4'), '-frames:v', '1',
                            '-vf', f'crop=iw:iw*{FH / FW:.4f}:0:(ih-iw*{FH / FW:.4f})*0.35,scale={FW * 2}:{FH * 2}', '-q:v', '4', dst], check=True)
        out.append(rel)
    return out


def build(g, ctx):
    L = _lib()
    n = int(g.get('frames', 12))
    if g.get('images'):
        urls = [ctx.asset(p) for p in g['images']][:12]
        n = len(urls)
    else:
        if n not in (8, 12):
            ctx.fail(f'contact-sheet on {g["on"]!r}: frames must be 8 or 12')
        urls = _frames(ctx, n)
    cols = min(COLS, (n + 1) // 2)
    marks = (g.get('marks') or [])[:4]
    for m in marks:
        if not 0 <= int(m.get('frame', -1)) < n or m.get('mark') not in ('circle', 'cross'):
            ctx.fail(f'contact-sheet mark {m!r}: needs "frame" 0-{n - 1} and "mark" circle or cross')
    a0 = ctx.at(g['on'])[0]
    mt = L.times(ctx, g, marks, .45)
    mt = [max(t, a0 + .9 + .35 * k) for k, t in enumerate(mt)]
    for k in range(1, len(mt)):
        mt[k] = max(mt[k], mt[k - 1] + .3)
    a, end = L.window(ctx, g, 1.2, last=(mt[-1] + .4) if mt else a0 + .9)
    rows = (n + cols - 1) // cols
    W = cols * (FW + 12) + 2 * 40
    strip_h = FH + 2 * 26
    H = 56 + rows * strip_h + (rows - 1) * 18 + 64
    x, y, sc = L.above_head(ctx, 'contact-sheet', W, H, a, end)
    L.claim(ctx, x, y, W * sc, H * sc, a, end)
    cells = ''
    for r in range(rows):
        fr = ''
        for c in range(cols):
            k = r * cols + c
            if k < n:
                fr += f'<div class="fr f{k}"><img src="{urls[k]}"></div>'
        cells += f'<div class="st" style="top:{56 + r * (strip_h + 18)}px">{fr}</div>'
    svg, labels = '', ''
    for i, m in enumerate(marks):
        k = int(m['frame'])
        r, c = divmod(k, cols)
        cx = 40 + c * (FW + 12) + 6 + FW / 2
        cy = 56 + r * (strip_h + 18) + 26 + FH / 2
        if m['mark'] == 'circle':
            rx, ry = FW * .62, FH * .6
            path = (f'M{cx + rx:.0f} {cy:.0f} C{cx + rx:.0f} {cy - ry * 1.3:.0f} {cx - rx * 1.25:.0f} {cy - ry * 1.15:.0f} {cx - rx:.0f} {cy + 4:.0f} '
                    f'C{cx - rx * .9:.0f} {cy + ry * 1.25:.0f} {cx + rx * 1.2:.0f} {cy + ry * 1.1:.0f} {cx + rx * .96:.0f} {cy - ry * .2:.0f}')
            svg += f'<path class="m{i}" d="{path}" style="stroke-dasharray:900;stroke-dashoffset:900"/>'
        else:
            d = FW * .42
            svg += (f'<path class="m{i}" d="M{cx - d:.0f} {cy - d * 1.2:.0f} L{cx + d:.0f} {cy + d * 1.2:.0f}" style="stroke-dasharray:300;stroke-dashoffset:300"/>'
                    f'<path class="m{i}" d="M{cx + d:.0f} {cy - d * 1.2:.0f} L{cx - d:.0f} {cy + d * 1.2:.0f}" style="stroke-dasharray:300;stroke-dashoffset:300"/>')
        if m.get('label'):
            ly = 4 if r == 0 else H - 56
            labels += f'<div class="lb l{i}" style="left:{cx - 120:.0f}px;top:{ly}px">{ctx.esc(m["label"])}</div>'
    title = g.get('title', 'Raw takes')
    html = (f'<div class="fx-contact-sheet" style="width:{W}px;height:{H}px">{cells}'
            f'<svg class="mk" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{svg}</svg>{labels}'
            + ('' if any(int(m['frame']) >= cols and m.get('label') for m in marks) else f'<div class="ft"><span>{ctx.esc(title)}</span><span>{n} frames</span></div>')
            + '</div>')
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"tl.fromTo('#{cid} .fx-contact-sheet',{{opacity:0,y:-60,rotation:-2}},{{opacity:1,y:0,rotation:0,duration:.4,ease:'power3.out',immediateRender:false}},{q(a)});")
    ctx.tw(f"gsap.set('#{cid} .fr img',{{opacity:0}});")
    ctx.tw(f"tl.to('#{cid} .fr img',{{opacity:1,duration:.12,stagger:{.35 / n:.3f}}},{q(a + .3)});")
    for i, m in enumerate(marks):
        t = mt[i]
        ctx.tw(f"tl.to('#{cid} path.m{i}',{{strokeDashoffset:0,duration:{.32 if m['mark'] == 'circle' else .14},stagger:.12,ease:'power2.out'}},{q(t)});")
        if m['mark'] == 'cross':
            ctx.tw(f"tl.to('#{cid} .f{int(m['frame'])} img',{{filter:'grayscale(1) brightness(.75)',duration:.2}},{q(t)});")
        if m.get('label'):
            ctx.tw(f"gsap.set('#{cid} .l{i}',{{'--p':'-12%'}});")
            ctx.tw(f"tl.fromTo('#{cid} .l{i}',{{'--p':'-12%'}},{{'--p':'118%',duration:.4,ease:'none',immediateRender:false}},{q(t + .1)});")
        ctx.sfx(g.get('sfx', 'marker-circle'), t, .3)
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{q(end - .22)});")


def describe(g, beat):
    ms = ', '.join(f'frame {m["frame"]} {"circled" if m["mark"] == "circle" else "crossed out"}' + (f' ("{m["label"]}")' if m.get('label') else '') for m in g.get('marks', []))
    return f'On “{g["on"]}” a contact sheet of the clip\'s own frames drops in; {ms or "no marks"}. It holds {beat["hold"]:.1f} s.'
