"""An agent's chat: messages land one by one on their words, optional chips cross off on theirs."""

META = {
    'id': 'agent-chat', 'name': 'Agent chat', 'category': 'ui',
    'when': 'The speaker describes talking to a named AI agent or teammate: what they asked, what it answered.',
    'never': 'Never messages that were not described. Each lands on its own spoken phrase.',
    'params': {'on': 'phrase that triggers it', 'name': 'agent name', 'role': 'small label after the name', 'initial': 'avatar letter (default the first letter)',
               'tone': 'accent or accent2 (avatar color)', 'messages': '[{"from": "me"|"ai", "text", "on"}]',
               'chips': '[{"text", "on"}] crossed-off chips under the last message', 'mark': 'chip mark, default the multiplication sign',
               'hold': 'seconds, default 3.0', 'sfx_message': 'sound per message, default message-send for me, none for ai',
               'sfx_chip': 'sound per chip, default message-send'},
    'sfx': ['message-send'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    msgs, chips = g.get('messages', []), g.get('chips', [])
    if not msgs:
        ctx.fail('agent-chat needs at least one message')
    tone = 'accent2' if g.get('tone', 'accent2') == 'accent2' else 'accent'
    head = (f'<div class="win-h"><span class="av {tone}">{ctx.esc(g.get("initial", g["name"][:1]))}</span> {ctx.esc(g["name"])}'
            + (f' <small>{ctx.esc(g["role"])}</small>' if g.get('role') else '') + '</div>')
    body, anim, after, last_end = '', [], s0 - .5, s0
    for k, m in enumerate(msgs):
        who = 'ai' if m.get('from') == 'ai' else 'me'
        body += f'<div class="rk-bub {who} m{k}">{ctx.esc(m["text"])}</div>'
        t0, t1 = ctx.at(m['on'], after) if m.get('on') else (s0 + .2 + .5 * k, s0 + .6 + .5 * k)
        after, last_end = t0, max(last_end, t1)
        anim.append(f"tl.fromTo('#ID .m{k}',{{opacity:0,y:18}},{{opacity:1,y:0,duration:.22,ease:'power3.out',immediateRender:false}},{ctx.q(t0 - .05)});")
        ctx.sfx(m.get('sfx', g.get('sfx_message', 'message-send' if who == 'me' else None)), t0 - .05, .6 if who == 'me' else .45)
    if chips:
        mark = ctx.esc(g.get('mark', '✕'))
        body += '<div class="ck">' + ''.join(f'<span class="cki c{k}"><i>{mark}</i>{ctx.esc(c["text"])}</span>' for k, c in enumerate(chips)) + '</div>'
        for k, c in enumerate(chips):
            t0, t1 = ctx.at(c.get('on', c['text']), after)
            after, last_end = t0, max(last_end, t1)
            anim.append(f"tl.fromTo('#ID .c{k}',{{opacity:0,scale:.6}},{{opacity:1,scale:1,duration:.22,ease:'back.out(2)',immediateRender:false}},{ctx.q(t0 - .03)});")
            ctx.sfx(c.get('sfx', g.get('sfx_chip', 'message-send')), t0 - .03, .6)
    hold = max(hold, last_end + (1.2 if chips else .6) - s0)
    html = f'<div class="fx-agent-chat rk-win">{head}{body}</div>'
    ctx.ui_window(g, a, html, anim, hold, s0, 'wall', height=110 + 92 * len(msgs) + (80 if chips else 0))


def describe(g, beat):
    parts = ' / '.join(f'"{m["text"]}"' for m in g.get('messages', []))
    chips = (', then crosses out ' + ', '.join(c['text'] for c in g['chips'])) if g.get('chips') else ''
    return f'On “{g["on"]}” the chat with {g["name"]} fills one message at a time: {parts}{chips}. It holds {beat["hold"]:.1f} s.'
