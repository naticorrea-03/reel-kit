"""A card with a title and a row of chips that land one by one (boards, clients, places)."""

META = {
    'id': 'list-card', 'name': 'List card', 'category': 'ui',
    'when': 'The speaker refers to a set of names you can list: boards, clients, cities.',
    'never': 'Never a list that is not sourced. Put the source line on the card.',
    'params': {'on': 'phrase that triggers it', 'title': 'card title', 'items': 'chip texts', 'source': 'small source line',
               'hold': 'seconds, default 3.0', 'until': 'close before this phrase'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 3.0)
    s0 = a - .1
    items = g['items']
    html = (f'<div class="fx-list-card rk-win"><div class="win-h">{ctx.esc(g.get("title", ""))}</div><div class="brd-row">'
            + ''.join(f'<span class="brd-i">{ctx.esc(x)}</span>' for x in items) + '</div>'
            + (f'<div class="win-src">{ctx.esc(g["source"])}</div>' if g.get('source') else '') + '</div>')
    anim = ["gsap.set('#ID .brd-i',{opacity:0});"]
    for k in range(len(items)):   # chips land silently
        anim.append(f"tl.fromTo(document.querySelectorAll('#ID .brd-i')[{k}],{{opacity:0,x:-40}},{{opacity:1,x:0,duration:.25,ease:'power3.out',immediateRender:false}},{ctx.q(s0 + .3 + k * .22)});")
    rows = max(1, -(-sum(len(x) * 18 + 52 for x in items) // 848))
    ctx.ui_window(g, a, html, anim, hold, s0, 'card', height=120 + 70 * rows + (40 if g.get('source') else 0))


def describe(g, beat):
    return f'On “{g["on"]}” a card titled "{g.get("title", "")}" lists ' + ', '.join(g['items']) + f' one by one. It holds {beat["hold"]:.1f} s.'
