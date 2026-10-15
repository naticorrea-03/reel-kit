"""A chat window types out a prompt, then placeholder answer lines draw in."""

META = {
    'id': 'chat-prompt', 'name': 'Chat prompt', 'category': 'ui',
    'when': 'The speaker describes asking an AI or app something. Show the exact ask.',
    'never': 'Never placeholder bars alone (a blank card). Never a prompt the speaker did not describe.',
    'params': {'on': 'phrase that triggers it', 'text': 'the prompt that types out', 'app': 'window title, default "Assistant"',
               'icon': 'app icon file (project-relative), optional', 'lines': 'answer bars after the prompt, default 3',
               'type_time': 'seconds to type, default 1.1', 'hold': 'seconds, default 3.0', 'until': 'close before this phrase',
               'sfx': 'sound name, default typing'},
    'sfx': ['typing'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    msg = g['text']
    tt = g.get('type_time', 1.1)
    bars = int(g.get('lines', 3))
    widths = [88, 72, 80, 64, 84][:bars]
    html = (f'<div class="fx-chat-prompt rk-win">{ctx.app_header(g)}<div class="rk-bub me">{ctx.typed(msg)}</div>'
            f'<div class="sk">' + ''.join(f'<i style="width:{w}%"></i>' for w in widths) + '</div></div>')
    anim = [f"tl.fromTo('#ID .tc',{{opacity:0}},{{opacity:1,duration:.01,stagger:{tt / max(1, len(msg.replace(' ', ''))):.4f},immediateRender:false}},{ctx.q(s0 + .08)});"]
    if bars:
        anim.append(f"tl.fromTo('#ID .sk i',{{scaleX:0}},{{scaleX:1,duration:.35,stagger:.12,ease:'power2.out',immediateRender:false}},{ctx.q(s0 + tt + .4)});")
    ctx.sfx(g.get('sfx', 'typing'), s0 + .08, .38, tt + .02)
    nlines = max(1, -(-len(msg) // 36))
    ctx.ui_window(g, a, html, anim, hold, s0, 'wall', height=150 + 47 * nlines + 34 * bars)


def describe(g, beat):
    return f'On “{g["on"]}” a {g.get("app", "chat")} window types the prompt "{g["text"]}". It holds {beat["hold"]:.1f} s.'
