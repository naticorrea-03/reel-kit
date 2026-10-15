"""Stat chips: numbers count up and labels pop in, one per spoken beat, in a 2-up grid above the heads."""

META = {
    'id': 'stats', 'name': 'Stat chips', 'category': 'data',
    'when': 'The speaker says numbers or a short list of hard facts.',
    'never': 'Never a number nobody says. Clears before the next graphic lands.',
    'params': {'on': 'phrase of the first item (defaults to items[0].on)',
               'items': '[{"on", "to", "prefix", "suffix", "label", "sfx"} for a counter, or {"on", "text", "sfx"} for a chip]',
               'hold': 'seconds after the last item, default 1.6'},
    'sfx': ['cash-register', 'coin', 'clock-tick'], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def item_text(it):
    return f"{it.get('prefix', '')}{it['to']}{it.get('suffix', '')} {it.get('label', '')}".strip() if 'to' in it else it['text']


def build(g, ctx):
    items = g.get('items') or []
    if not items:
        ctx.fail(f'stats on {g["on"]!r} has no items')
    ctx.beat_text(' · '.join(item_text(it) for it in items))
    times, after = [], ctx.at(g['on'])[0] - .2
    for it in items:
        t = ctx.at(it.get('on', g['on']), after)[0]
        times.append(t)
        after = t
    end = min(ctx.DUR, times[-1] + g.get('hold', 1.6))
    later = [ctx.at(h['on'])[0] for h in ctx.graphics if h is not g and h.get('on') and ctx.at(h['on'])[0] > times[-1]]
    if later:
        end = min(end, min(later) - .2)            # clear the stack before the next graphic lands
    tiles = ''
    for k, it in enumerate(items):
        if 'to' in it:
            tiles += (f'<div class="stat"><span class="num" data-k="{k}">{ctx.esc(it.get("prefix", ""))}0{ctx.esc(it.get("suffix", ""))}</span>'
                      f'<span class="lab">{ctx.esc(it.get("label", ""))}</span></div>')
        else:
            tiles += f'<div class="stat chip"><span class="lab">{ctx.esc(it["text"])}</span></div>'
    sw, sh = 900, 16 + 128 * ((len(items) + 1) // 2)
    cov, sx, sy = ctx.place(sw, sh, times[0], end, [(90, y) for y in (250, 280, 320)])
    if cov > .02:
        ctx.warn(f'stat tiles cover {cov:.0%} of a speaker')
    cid = ctx.clip(ctx.front, times[0] - .05, end, f'<div class="fx-stats">{tiles}</div>', f'position:absolute;left:{sx}px;top:{sy}px;')
    ctx.topbusy.append((times[0] - .05, end))
    for k, (it, t) in enumerate(zip(items, times)):
        ctx.tw(f"gsap.set('#{cid} .stat:nth-child({k + 1})',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .stat:nth-child({k + 1})',{{opacity:0,x:-50,scale:.85}},{{opacity:1,x:0,scale:1,duration:.3,ease:'back.out(1.8)',immediateRender:false}},{ctx.q(t - .05)});")
        ctx.sfx(it.get('sfx', 'cash-register' if it.get('prefix') == '$' else None), t - .05, .45)
        if 'to' in it:
            pre, suf = it.get('prefix', '').replace("'", "\\'"), it.get('suffix', '').replace("'", "\\'")
            ctx.tw(f"(function(){{const o={{v:0}};tl.to(o,{{v:{float(it['to'])},duration:.6,ease:'power2.out',onUpdate:function(){{"
                   f"const el=document.querySelector('#{cid} .num[data-k=\"{k}\"]');if(el)el.textContent='{pre}'+Math.round(o.v)+'{suf}';}},immediateRender:false}},{ctx.q(t)});}})();")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,x:-40,duration:.25}},{ctx.q(end - .25)});")


def describe(g, beat):
    return f'On “{g["on"]}” stat chips count up one at a time across the top: {beat["text"]}. They clear before the next graphic.'
