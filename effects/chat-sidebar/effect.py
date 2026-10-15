"""An app window with a sidebar list: one item highlights on its word, then a prompt types in the main pane."""

META = {
    'id': 'chat-sidebar', 'name': 'Chat sidebar', 'category': 'ui',
    'when': 'The speaker describes organizing work into projects or folders in an app, then asking inside one.',
    'never': 'Never a highlight on an item nobody names.',
    'params': {'on': 'phrase that triggers it', 'title': 'sidebar heading, default "Projects"', 'items': 'sidebar entries',
               'active': 'the entry that highlights', 'active_on': 'phrase where it highlights (default: the active text)',
               'prompt': 'text that types in the main pane', 'prompt_on': 'phrase where typing starts', 'app': 'app name', 'icon': 'icon file, optional',
               'hold': 'seconds, default 3.0', 'sfx': 'sound name, default typing'},
    'sfx': ['typing'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    active = g['active']
    if active not in g['items']:
        ctx.fail(f'chat-sidebar active {active!r} is not one of its items')
    items = ''.join(f'<div class="sb-i{" sb-on" if x == active else ""}"><i class="hl"></i><span>{ctx.esc(x)}</span></div>' for x in g['items'])
    prompt = g.get('prompt', '')
    main = ctx.app_header(g, title=active)
    if prompt:
        main += f'<div class="rk-bub me">{ctx.typed(prompt)}</div>'
    html = (f'<div class="fx-chat-sidebar rk-win"><div class="sb"><div class="sb-h">{ctx.esc(g.get("title", "Projects"))}</div>{items}</div>'
            f'<div class="main">{main}</div></div>')
    ta = ctx.at(g.get('active_on', active), s0 - .5)[0]
    anim = [f"tl.fromTo('#ID .sb-on .hl',{{opacity:0}},{{opacity:1,duration:.25,immediateRender:false}},{ctx.q(ta)});",
            f"tl.set('#ID .sb-on',{{className:'sb-i sb-on lit'}},{ctx.q(ta + .05)});"]
    if prompt:
        tp = ctx.at(g['prompt_on'], s0 - .5)[0] if g.get('prompt_on') else ta + .5
        anim.append(f"tl.fromTo('#ID .tc',{{opacity:0}},{{opacity:1,duration:.01,stagger:{1.3 / max(1, len(prompt)):.4f},immediateRender:false}},{ctx.q(tp)});")
        hold = max(hold, tp + 1.9 - s0)
        ctx.sfx(g.get('sfx', 'typing'), tp, .38, 1.1)
    ctx.ui_window(g, a, html, anim, hold, s0, 'wall', height=max(430, 130 + 66 * len(g['items'])))


def describe(g, beat):
    p = f', then types "{g["prompt"]}"' if g.get('prompt') else ''
    return f'On “{g["on"]}” a {g.get("title", "Projects")} sidebar highlights {g["active"]}{p}. It holds {beat["hold"]:.1f} s.'
