"""A left-to-right pipeline: each node pops in on its word and the link to it draws."""

META = {
    'id': 'pipeline', 'name': 'Pipeline', 'category': 'ui',
    'when': 'The speaker walks through a workflow: this tool, then that one, then the result.',
    'never': 'Never more than five nodes. Every node lands on its own spoken word.',
    'params': {'on': 'phrase that triggers it', 'nodes': '[{"label", "on", "icon": file, "glyph": text}]', 'hold': 'seconds, default 3.0',
               'sfx': 'sound per node, default message-send'},
    'sfx': ['message-send'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    nodes = g['nodes']
    if not 2 <= len(nodes) <= 5:
        ctx.fail(f'pipeline needs 2 to 5 nodes, got {len(nodes)}')
    parts = []
    for k, nd in enumerate(nodes):
        if nd.get('icon'):
            icon = f'<img src="{ctx.asset(nd["icon"])}" class="nic">'
        else:
            icon = f'<span class="nic txt">{ctx.esc(nd.get("glyph", nd["label"][:1].upper()))}</span>'
        if k:
            parts.append('<div class="link"><i></i></div>')
        parts.append(f'<div class="node">{icon}<span>{ctx.esc(nd["label"])}</span></div>')
    html = '<div class="fx-pipeline">' + ''.join(parts) + '</div>'
    anim, after, seq = [], s0 - .5, []
    for k, nd in enumerate(nodes):
        t = ctx.at(nd.get('on', nd['label']), after)[0]
        after = t
        seq.append(t - (.1 if k == 0 else 0))
    anim.append("gsap.set('#ID .node',{opacity:0});gsap.set('#ID .link i',{scaleX:0});")
    for k, t in enumerate(seq):
        anim.append(f"tl.fromTo(document.querySelectorAll('#ID .node')[{k}],{{opacity:0,scale:.5}},{{opacity:1,scale:1,duration:.28,ease:'back.out(2)',immediateRender:false}},{ctx.q(t)});")
        if k:
            anim.append(f"tl.fromTo(document.querySelectorAll('#ID .link i')[{k - 1}],{{scaleX:0}},{{scaleX:1,duration:.25,ease:'power2.out',immediateRender:false}},{ctx.q(t - .2)});")
        ctx.sfx(g.get('sfx', 'message-send'), t, .5)
    hold = max(hold, seq[-1] + 1.4 - s0)
    ctx.ui_window(g, a, html, anim, hold, s0, 'wall', height=320)


def describe(g, beat):
    return f'On “{g["on"]}” a pipeline builds left to right: ' + ', '.join(n['label'] for n in g['nodes']) + f'. It holds {beat["hold"]:.1f} s.'
