"""Two app windows slide in side by side with the same ask, for a comparison."""

META = {
    'id': 'side-by-side', 'name': 'Side by side', 'category': 'ui',
    'when': 'The speaker compares two tools on the same task.',
    'never': 'Never two windows of grey bars: each shows the real ask.',
    'params': {'on': 'phrase that triggers it', 'left': '{"app", "icon", "text"}', 'right': '{"app", "icon", "text"}', 'vs': 'middle word, default "vs"',
               'hold': 'seconds, default 3.0', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    wins = []
    for side, bars in (('left', (90, 70, 82)), ('right', (84, 92, 66))):
        w = g[side]
        if not w.get('text'):
            ctx.fail(f'side-by-side {side} window has no text (a window of grey bars reads as a blank card)')
        wins.append(f'<div class="rk-win mini">{ctx.app_header(w)}<div class="rk-bub me sbq">{ctx.esc(w["text"])}</div>'
                    f'<div class="sk">' + ''.join(f'<i style="width:{x}%"></i>' for x in bars) + '</div></div>')
    html = f'<div class="fx-side-by-side">{wins[0]}<div class="vs">{ctx.esc(g.get("vs", "vs"))}</div>{wins[1]}</div>'
    anim = ["gsap.set('#ID .rk-win',{opacity:0});",
            f"tl.fromTo(document.querySelectorAll('#ID .rk-win')[0],{{opacity:0,x:-200}},{{opacity:1,x:0,duration:.35,ease:'power3.out',immediateRender:false}},{ctx.q(s0)});",
            f"tl.fromTo(document.querySelectorAll('#ID .rk-win')[1],{{opacity:0,x:200}},{{opacity:1,x:0,duration:.35,ease:'power3.out',immediateRender:false}},{ctx.q(s0 + .12)});",
            f"tl.fromTo('#ID .sk i',{{scaleX:0}},{{scaleX:1,duration:.3,stagger:.08,ease:'power2.out',immediateRender:false}},{ctx.q(s0 + .5)});",
            f"tl.fromTo('#ID .sbq',{{opacity:0,y:10}},{{opacity:1,y:0,duration:.25,stagger:.1,ease:'power2.out',immediateRender:false}},{ctx.q(s0 + .3)});"]
    ctx.sfx(g.get('sfx'), s0, .45)
    ctx.ui_window(g, a, html, anim, hold, s0, 'wall', height=290)


def describe(g, beat):
    return (f'On “{g["on"]}” {g["left"].get("app", "one app")} and {g["right"].get("app", "another")} slide in side by side with the same ask. '
            f'It holds {beat["hold"]:.1f} s.')
