"""Handwritten note with an arrow drawn to the speaker's face."""
import math, re

META = {
    'id': 'note', 'name': 'Handwritten note', 'category': 'annotation',
    'when': 'Adds a fact the speaker does not say (a number, a name, a date).',
    'never': 'Never echo words spoken within 2 s. Never point at nothing: the arrow lands on the speaker.',
    'params': {'on': 'phrase that triggers it', 'text': 'note text (must add information)', 'side': 'left or right, default right',
               'sfx': 'optional sound name, literal to the note (e.g. alarm-clock for a time)'},
    'sfx': [], 'source': 'ours', 'credit': '', 'license': 'MIT',
}

BLOCKERS = {'behind', 'highlight-paper', 'photo', 'logo', 'screenshot'}


def build(g, ctx):
    a, b = ctx.at(g['on'])
    side = g.get('side', 'right')
    text = g['text']
    # a note that only repeats the spoken words adds nothing: refuse to build it
    nw = re.findall(r'[a-z0-9]+', text.lower())
    said = {w for x in ctx.words if a - 2 <= x['start'] <= b + 1 for w in re.findall(r'[a-z0-9]+', x['text'].lower())}
    if nw and all(w in said for w in nw):
        ctx.fail(f'note {text!r} only repeats what is said; cut it or make it add info')
    nwid = max(260, len(text) * 36)
    later = [ctx.at(h['on'])[0] for h in ctx.graphics if h is not g and h.get('on')
             and (h.get('type') in BLOCKERS or ctx.meta(h.get('type', '')).get('category') == 'ui') and ctx.at(h['on'])[0] > a]
    b = min(b, min(later, default=ctx.DUR) - 1.75)
    end = min(ctx.DUR, b + 1.6)
    if end - a < .8:
        ctx.fail(f'note {text!r} gets {end - a:.2f} s before the next graphic; move it or the graphic after it')
    xs = (620, 960 - nwid, 340, 80) if side == 'right' else (80, 340, 960 - nwid)
    cov, x, ny = ctx.place(nwid, 220, a, end, [(min(x_, 960 - nwid), y_) for y_ in (260, 300, 420, 560, 720) for x_ in xs])
    if cov > .05:
        ctx.warn(f'note {text!r} hides {cov:.0%}')
    if ny < 400:
        ctx.topbusy.append((a, end))
    # the arrow lands just outside whoever is talking, drawn in canvas coordinates (a fixed squiggle once pointed at the wall)
    # aim at where the face sits across the whole hold, not one instant (a speaker who leans moved the target 136 px)
    boxes = [f for f in (ctx.speaker_face(a + .2 + (end - a - .4) * k / 4) for k in range(5)) if f]
    if not boxes:
        ctx.fail(f'note {text!r} has no face to point at')
    fx0, fy0, fx1, fy1 = [sorted(b[i] for b in boxes)[len(boxes) // 2] for i in range(4)]
    nh = 110
    sx = min(max(x + 30, (fx0 + fx1) / 2), x + nwid - 30)
    sy = ny + nh
    cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    if sy < fy0:                  # note above the head: land over the crown
        tx, ty = cx, fy0 - 28
    elif sx < fx0:
        tx, ty = fx0 - 28, cy - (fy1 - fy0) * .15
    else:
        tx, ty = fx1 + 28, cy - (fy1 - fy0) * .15
    dx, dy = tx - sx, ty - sy
    L = max(1, math.hypot(dx, dy))
    qx, qy = (sx + tx) / 2 - dy / L * L * .18, (sy + ty) / 2 + dx / L * L * .18
    ang = math.atan2(ty - qy, tx - qx)
    hd = [(tx - 30 * math.cos(ang + d), ty - 30 * math.sin(ang + d)) for d in (.5, -.5)]
    dl = int(L * 1.3) + 40
    arrow = (f'<svg class="arr" width="1080" height="1920" viewBox="0 0 1080 1920" style="position:absolute;left:{-x}px;top:{-ny}px;overflow:visible">'
             f'<path style="stroke-dasharray:{dl};stroke-dashoffset:{dl}" d="M{sx:.0f} {sy:.0f} Q {qx:.0f} {qy:.0f} {tx:.0f} {ty:.0f}" />'
             f'<path style="stroke-dasharray:80;stroke-dashoffset:80" d="M{hd[0][0]:.0f} {hd[0][1]:.0f} L {tx:.0f} {ty:.0f} L {hd[1][0]:.0f} {hd[1][1]:.0f}" /></svg>'
             f'<div class="arr-tip" style="position:absolute;left:{tx - x - 2:.0f}px;top:{ty - ny - 2:.0f}px;width:4px;height:4px"></div>')
    cid = ctx.clip(ctx.front, a, end, f'<div class="fx-note"><div class="note">{ctx.esc(text)}</div>{arrow}</div>',
                   f'position:absolute;left:{x}px;top:{ny}px;width:{nwid}px;')
    ctx.tw(f"tl.fromTo('#{cid} .note',{{opacity:0,rotation:-8,scale:.8}},{{opacity:1,rotation:-4,scale:1,duration:.3,ease:'back.out(2)',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.to('#{cid} .arr path',{{strokeDashoffset:0,duration:.45,stagger:.3,ease:'power2.out'}},{ctx.q(a + .15)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.18}},{ctx.q(end - .18)});")
    ctx.sfx(g.get('sfx'), a, .35)


def describe(g, beat):
    return f'On “{g["on"]}” a handwritten note "{g["text"]}" appears and its arrow draws to the speaker. It holds {beat["hold"]:.1f} s.'
