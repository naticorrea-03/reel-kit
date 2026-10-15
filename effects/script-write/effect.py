"""Script write: short handwritten lines write themselves on, left to right, each with an optional drawn cross or check."""
import importlib.util, os, sys

META = {
    'id': 'script-write', 'name': 'Handwritten lines', 'category': 'annotation',
    'when': 'A quick pro and con or a before and after in a few words ("no robotic voice, keeps my tone"), or a handwritten subtitle under the hook.',
    'never': 'Never more than 3 lines. Never a line that only repeats the caption word for word: a cross or check adds the verdict, or the line adds the detail.',
    'params': {'on': 'phrase where the first line writes', 'lines': '[{"text", "tick"?: "cross" or "check", "on"?}] 1 to 3',
               'size': 'font size in px, default fits the band (max 64)', 'hold': 'seconds after the last line, default 1.6',
               'sfx': 'sound while writing, default pen-scribble ("none" for silence)'},
    'sfx': ['pen-scribble'], 'source': 'ours', 'credit': 'Motion idea inspired by Instagram creator reels (handwritten write-on subtitles), Oct 2026', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


CPS = 24   # handwriting speed, characters per second
TICK = {'cross': '<path d="M8 8 L32 32"/><path d="M32 8 L8 32"/>', 'check': '<path d="M6 21 L16 31 L34 8"/>'}


def build(g, ctx):
    L = _lib()
    lines = [x if isinstance(x, dict) else {'text': x} for x in (g.get('lines') or [])]
    if not 1 <= len(lines) <= 3 or not all(x.get('text') for x in lines):
        ctx.fail(f'script-write on {g["on"]!r} needs 1 to 3 lines with "text"')
    for x in lines:
        if x.get('tick') not in (None, 'cross', 'check'):
            ctx.fail(f'script-write tick must be "cross" or "check", got {x["tick"]!r}')
    a0 = ctx.at(g['on'])[0]
    ts = L.times(ctx, g, lines, 0, key='on')
    for k in range(1, len(ts)):
        ts[k] = max(ts[k], ts[k - 1] + len(lines[k - 1]['text']) / CPS + .1)
    done = ts[-1] + len(lines[-1]['text']) / CPS
    for x in lines:   # a line that adds nothing: every word said right around it, and no verdict
        if not x.get('tick') and L.echo_guard(ctx, g, x['text'], a0, done, 'script-write'):
            ctx.fail(f'script-write line {x["text"]!r} only repeats what is said; add a cross or check, or make it add a detail')
    a, end = L.window(ctx, g, 1.6, last=done)
    anyt = any(x.get('tick') for x in lines)
    tw = 0
    fs = int(g.get('size') or L.fit(ctx, 'script-write', [x['text'] for x in lines], 820 - (70 if anyt else 0), 64, 40, 1, .44))
    tw = int(fs * .9) if anyt else 0
    H = int(len(lines) * fs * 1.25 + 10)
    Wt = int(max(len(x['text']) for x in lines) * fs * .44 + (tw + 16 if anyt else 0) + 20)
    fz = L.faces(ctx, a, end)
    cands = [(int(540 - Wt / 2), yy) for yy in range(250, 1471 - H, 20)]
    x, y, sc = L.fitspot(ctx, 'script-write', Wt, H, a, end, cands=lambda w, h: [(int(540 - w / 2), yy) for yy in range(250, 1471 - int(h), 20)],
                         near=(540, 300))
    L.claim(ctx, x, y, Wt * sc, H * sc, a, end)
    ink, tone = L.wall_ink(ctx, a, end, (x, y, x + Wt * sc, y + H * sc))
    rows = ''
    for k, ln in enumerate(lines):
        tk = (f'<svg class="tk {ln["tick"]}" viewBox="0 0 40 40" width="{tw}" height="{tw}">{TICK[ln["tick"]]}</svg>' if ln.get('tick')
              else (f'<i class="sp" style="width:{tw}px"></i>' if anyt else ''))
        rows += f'<div class="rw r{k}">{tk}<span class="tx">{ctx.esc(ln["text"])}</span></div>'
    html = f'<div class="fx-script-write {tone}" style="font-size:{fs}px;color:{ink};width:{Wt}px">{rows}</div>'
    cid = L.zclip(ctx, ctx.front, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    q = ctx.q
    for k, ln in enumerate(lines):
        d = len(ln['text']) / CPS
        ctx.tw(f"gsap.set('#{cid} .r{k} .tx',{{'--p':'-8%'}});")
        ctx.tw(f"tl.fromTo('#{cid} .r{k} .tx',{{'--p':'-8%'}},{{'--p':'118%',duration:{d:.2f},ease:'none',immediateRender:false}},{q(ts[k])});")
        if ln.get('tick'):
            ctx.tw(f"gsap.set('#{cid} .r{k} .tk path',{{strokeDasharray:60,strokeDashoffset:60}});")
            ctx.tw(f"tl.to('#{cid} .r{k} .tk path',{{strokeDashoffset:0,duration:.16,stagger:.1,ease:'power2.out'}},{q(max(a, ts[k] - .2))});")
        ctx.sfx(g.get('sfx', 'pen-scribble'), ts[k], .25, cap=d)
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.25}},{q(end - .25)});")


def describe(g, beat):
    ls = ' / '.join((('✗ ' if x.get('tick') == 'cross' else '✓ ' if x.get('tick') == 'check' else '') + x['text']) if isinstance(x, dict) else x for x in g['lines'])
    return f'On “{g["on"]}” handwritten lines write themselves on: {ls}. They hold {beat["hold"]:.1f} s.'
