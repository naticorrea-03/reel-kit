"""Phone notifications drop in from the top and stack, each on its spoken beat."""

META = {
    'id': 'notification-stack', 'name': 'Notification stack', 'category': 'ui',
    'when': 'The speaker describes an app, agent or person pinging them.',
    'never': 'Never more than three. Never a notification text nobody describes.',
    'params': {'on': 'phrase that triggers it', 'items': '[{"title", "text", "time", "on", "icon": glyph or file}]',
               'hold': 'seconds, default 3.0', 'sfx': 'sound name, default message-receive'},
    'sfx': ['message-receive'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    items = g['items']
    if len(items) > 3:
        ctx.fail('notification-stack shows at most three notifications')
    html, anim, last = '<div class="fx-notification-stack">', [], s0
    for k, it in enumerate(items):
        ic = it.get('icon', '')
        if ic.lower().endswith(('.png', '.svg', '.jpg', '.jpeg', '.webp')):
            ic = f'<img src="{ctx.asset(ic)}">'
        else:
            ic = ctx.esc(ic or it.get('title', ' ')[:1])
        html += (f'<div class="ios n{k}"><div class="ios-h"><span class="ios-ic">{ic}</span><b>{ctx.esc(it["title"])}</b>'
                 f'<span class="ios-t">{ctx.esc(it.get("time", "now"))}</span></div><div class="ios-b">{ctx.esc(it["text"])}</div></div>')
        t = s0 if k == 0 or not it.get('on') else ctx.at(it['on'], s0)[0] - .1
        last = max(last, t)
        anim.append(f"tl.fromTo('#ID .n{k}',{{opacity:0,y:-120}},{{opacity:1,y:0,duration:.4,ease:'back.out(1.4)',immediateRender:false}},{ctx.q(t)});")
        ctx.sfx(g.get('sfx', 'message-receive'), t, .55 if k == 0 else .5)
    html += '</div>'
    hold = max(hold, last + 1.6 - s0)
    ctx.ui_window(g, a, html, anim, hold, s0, 'front', height=170 * len(items))


def describe(g, beat):
    return f'On “{g["on"]}” notifications drop in and stack: ' + ' / '.join(f'{it["title"]}: "{it["text"]}"' for it in g['items']) + f'. It holds {beat["hold"]:.1f} s.'
