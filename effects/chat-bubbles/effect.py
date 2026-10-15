"""A chat window where messages arrive one by one, each on its spoken beat."""

META = {
    'id': 'chat-bubbles', 'name': 'Chat bubbles', 'category': 'ui',
    'when': 'The speaker quotes a back-and-forth with an assistant or a person.',
    'never': 'Never invented replies. Each message lands on the words that describe it.',
    'params': {'on': 'phrase that triggers it', 'app': 'window title', 'icon': 'app icon file, optional',
               'messages': '[{"from": "ai"|"me", "text", "lead": "bold opening words (ai only)", "on": "phrase it lands on", "small": true}]',
               'hold': 'seconds, default 3.0', 'until': 'close before this phrase'},
    'sfx': ['message-receive', 'message-send'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    msgs = g['messages']
    body, anim, last = '', [], s0
    for k, m in enumerate(msgs):
        who = 'ai' if m.get('from', 'ai') == 'ai' else 'me'
        lead = f'<b>{ctx.esc(m["lead"])}</b> ' if m.get('lead') else ''
        body += f'<div class="rk-bub {who} m{k}{" sm" if m.get("small") else ""}">{lead}{ctx.esc(m["text"])}</div>'
        t = ctx.at(m['on'], s0 - 1)[0] - .05 if m.get('on') else (s0 + .2 + .6 * k)
        last = max(last, t)
        anim.append(f"tl.fromTo('#ID .m{k}',{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,ease:'power3.out',immediateRender:false}},{ctx.q(t)});")
        ctx.sfx(m.get('sfx', 'message-receive' if who == 'ai' else 'message-send'), t, .5 if who == 'ai' else .45)
    hold = max(hold, last + 1.2 - s0)
    html = f'<div class="fx-chat-bubbles rk-win">{ctx.app_header(g)}{body}</div>'
    ctx.ui_window(g, a, html, anim, hold, s0, 'wall', height=110 + 100 * len(msgs))


def describe(g, beat):
    return f'On “{g["on"]}” a {g.get("app", "chat")} window opens and the messages arrive one by one: ' + ' / '.join(
        f'"{(m.get("lead", "") + " " + m["text"]).strip()}"' for m in g['messages']) + f'. It holds {beat["hold"]:.1f} s.'
