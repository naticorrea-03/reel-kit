"""Logo card that drops in when a company or product is named."""
import os

META = {
    'id': 'logo', 'name': 'Logo', 'category': 'media',
    'when': 'A company, product or brand is named out loud.',
    'never': 'Never a logo nobody says. Never on top of the hook card. Never over a face.',
    'params': {'on': 'the spoken name', 'src': 'logo file (project-relative)', 'fallback_text': 'wordmark text if there is no file',
               'side': 'left or right, default right', 'hold': 'seconds, default 1.8', 'bg': 'card color for this logo (data, not style)',
               'top': 'fixed y if auto placement picks a bad spot', 'fs': 'fallback wordmark size, default 52', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    hold = g.get('hold', 1.8)
    if a < ctx.hook_end + .1:   # a logo once landed on top of the hook card: wait for the hook to clear
        hold, a = hold - (ctx.hook_end + .1 - a), ctx.hook_end + .1
    side = g.get('side', 'right')
    url = ctx.asset(g.get('src'), required=False) if g.get('src') and g.get('src') != 'none' else None
    if not url and not g.get('fallback_text'):
        ctx.fail(f'logo on {g["on"]!r}: file {g.get("src")!r} not found and no fallback_text')
    fs = g.get('fs', 52)
    if url:
        body = f'<img src="{url}" style="width:280px;height:auto;max-height:120px;object-fit:contain;display:block">'
        lw = 344
    else:
        body = f'<div class="lg-word" style="font-size:{fs}px;letter-spacing:{6 * fs / 52:.0f}px">{ctx.esc(g["fallback_text"])}</div>'
        lw = (70 + 40 * len(g['fallback_text'])) * fs / 52
    lh = 190
    xs = (640, 380, 90) if side == 'right' else (90, 380, 640)
    cands = [(min(x, 990 - lw), y) for y in (260, 400, 560, 720, 860, 960) for x in xs]
    cov, x, ly = ctx.place(lw, lh, a - .08, a + hold, cands)
    if g.get('top'):   # a fixed spot chosen on the beat sheet
        ly, x, cov = g['top'], min(x, 990 - lw), 0
    if cov > .02:
        ctx.warn(f'logo {g.get("src") or g.get("fallback_text")} still covers {cov:.0%} of a speaker')
    if ly < 400:
        ctx.topbusy.append((a - .08, a + hold))
    bg = f'background:{g["bg"]};' if g.get('bg') else ''
    cid = ctx.clip(ctx.front, a - .08, a + hold, f'<div class="fx-logo" style="{bg}">{body}</div>', f'position:absolute;left:{x:.0f}px;top:{ly}px;')
    rot = 6 if side == 'right' else -6
    ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,scale:.4,y:60,rotation:{rot * 2}}},{{opacity:1,scale:1,y:0,rotation:{rot},duration:.42,ease:'back.out(1.6)',immediateRender:false}},{ctx.q(a - .08)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,scale:.7,y:-40,rotation:{rot * 2},duration:.18,ease:'power2.in'}},{ctx.q(a + hold - .18)});")
    ctx.sfx(g.get('sfx'), a - .05, .5)


def describe(g, beat):
    name = g.get('fallback_text') or os.path.splitext(os.path.basename(g.get('src', '')))[0].replace('-', ' ')
    return f'On “{g["on"]}” the {name} logo card drops in and holds {beat["hold"]:.1f} s.'
