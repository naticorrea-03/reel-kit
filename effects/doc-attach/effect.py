"""A file attaches to a chat window and the ask types out under it."""

META = {
    'id': 'doc-attach', 'name': 'Document + prompt', 'category': 'ui',
    'when': 'The speaker hands a document to an AI: a PDF, a deck, a contract.',
    'never': 'Never placeholder bars alone. The file name and the ask come from what was said.',
    'params': {'on': 'phrase that triggers it', 'file': 'file name shown', 'kind': 'badge text, default PDF', 'meta': 'small detail (pages, size)',
               'text': 'the prompt that types out', 'lines': 'answer bars, default 4', 'type_time': 'seconds to type, default 1.05',
               'hold': 'seconds, default 3.0', 'sfx': 'sound name, default typing'},
    'sfx': ['typing'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    msg, tt, bars = g['text'], g.get('type_time', 1.05), int(g.get('lines', 4))
    widths = [90, 76, 84, 60, 80][:bars]
    meta = f' <small>{ctx.esc(g["meta"])}</small>' if g.get('meta') else ''
    html = (f'<div class="fx-doc-attach rk-win"><div class="win-h"><span class="badge">{ctx.esc(g.get("kind", "PDF"))}</span> {ctx.esc(g["file"])}{meta}</div>'
            f'<div class="rk-bub me">{ctx.typed(msg)}</div><div class="sk">' + ''.join(f'<i style="width:{w}%"></i>' for w in widths) + '</div></div>')
    anim = [f"tl.fromTo('#ID .tc',{{opacity:0}},{{opacity:1,duration:.01,stagger:{tt / max(1, len(msg.replace(' ', ''))):.4f},immediateRender:false}},{ctx.q(s0 + .1)});"]
    if bars:
        anim.append(f"tl.fromTo('#ID .sk i',{{scaleX:0}},{{scaleX:1,duration:.3,stagger:.1,ease:'power2.out',immediateRender:false}},{ctx.q(s0 + tt + .15)});")
    ctx.sfx(g.get('sfx', 'typing'), s0 + .1, .38, tt + .02)
    nlines = max(1, -(-len(msg) // 36))
    ctx.ui_window(g, a, html, anim, hold, s0, 'wall', height=150 + 47 * nlines + 34 * bars)


def describe(g, beat):
    return f'On “{g["on"]}” {g["file"]} attaches to a chat and the prompt "{g["text"]}" types out. It holds {beat["hold"]:.1f} s.'
