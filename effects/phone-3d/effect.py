"""3D phone with UI breakouts: a CSS-built phone spins in with overshoot, then UI rows lift out of its screen and float.

The phone (rounded bezel, dynamic island, side buttons) is built from divs and turned in CSS 3D. Its screen shows an app
(name, title, rows) or a screen image. Each row with an "on" phrase breaks out of the screen on its word: the row in the
screen empties to a placeholder while a full-size card flies out past the phone's edge and floats there.
The whole group (phone plus breakouts) is placed clear of every face and shrinks until it fits.
"""
import importlib.util, os, sys

META = {
    'id': 'phone-3d', 'name': '3D phone with breakouts', 'category': 'ui',
    'when': 'The speaker talks about an app, a feed, an inbox, a result on a phone; the rows that pop out are the things she names.',
    'never': 'Never an app the speaker does not mention or imply. Never rows that only repeat the caption. Never covers a face.',
    'params': {'on': 'phrase that brings the phone in', 'app': 'app name in the status row', 'title': 'screen title',
               'rows': '[{"title", "sub"?, "on"?}] 3 to 5 rows; rows with "on" break out of the screen on that word (1 to 3)',
               'src': 'optional screen image (9:19.5); the breakout rows then fly out of the screen centre',
               'side': 'left or right: which way breakouts fly, default away from the face', 'hold': 'seconds after the last breakout, default 1.4',
               'sfx': 'optional sound per breakout (e.g. message-receive for a notification)'},
    'sfx': ['message-receive'], 'source': 'ours', 'credit': 'Motion grammar inspired by 3D phone reels with UI breakouts.', 'license': 'MIT',
}

PW, PH = 330, 680            # phone at scale 1
POPW, OVER = 330, 70         # breakout card width, and how far it still overlaps the phone edge
ROW_Y0, ROW_H = 238, 104     # first row top inside the phone, row pitch


def _lib():
    if 'rk3d' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'rk3d.py')
        spec = importlib.util.spec_from_file_location('rk3d', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['rk3d'] = mod
    return sys.modules['rk3d']


def build(g, ctx):
    L = _lib()
    rows = g.get('rows') or []
    if not 3 <= len(rows) <= 5 or not all(isinstance(r, dict) and r.get('title') for r in rows):
        ctx.fail(f'phone-3d on {g["on"]!r} needs 3 to 5 rows, each with "title"')
    pops = [i for i, r in enumerate(rows) if r.get('on')]
    if not 1 <= len(pops) <= 3:
        ctx.fail(f'phone-3d on {g["on"]!r}: give 1 to 3 rows an "on" phrase (those break out of the screen on their word)')
    ptimes = L.item_times(ctx, g, [rows[i] for i in pops], 1.0)
    a0 = L.fq(ctx.at(g['on'])[0])
    ptimes = [max(t, a0 + .75) for t in ptimes]   # the phone lands first
    for k in range(1, len(ptimes)):
        if ptimes[k] - ptimes[k - 1] < .45:
            ctx.fail(f'phone-3d on {g["on"]!r}: breakout {k + 1} lands {ptimes[k] - ptimes[k - 1]:.2f} s after the one before; give each 0.45 s or more')
    a, end = L.window(ctx, g, 1.4, last=ptimes[-1], min_after=.9)
    pfs = 30
    for r in rows:
        for txt, fs, w in ((r["title"], 28, 196), (r.get("sub", ""), 28, 208)):   # 188 px of row; the width estimate runs ~7% wide for bold titles, more for body subs
            if txt and len(L.wrap(txt, w, fs)) > 1:
                ctx.fail(f'phone-3d row {txt!r} is too long for one line in the phone; keep row text under ~12 characters (188 px)')
    cfs = L.fit(ctx, 'phone-3d breakout titles', [rows[i]['title'] for i in pops], POPW - 104, 40, 30, 2)

    # ---- placement: phone plus breakouts, clear of every face, as big as fits ----
    track = L.face_track(ctx, a, end)
    fcx = (track(a + (end - a) / 2)[0] + track(a + (end - a) / 2)[2]) / 2 if track else 540
    sides = [g['side']] if g.get('side') in ('left', 'right', 'up') else ['right', 'left', 'up']
    CH = 150   # breakout card height at scale 1 (2-line title worst case)
    def group(sc, side, x, y):
        """(phone x, phone y, group box, part boxes) for a group whose top-left is x, y. Parts are checked one by one:
        a single bounding box wasted the free space beside a big face."""
        pw, ph, ext = PW * sc, PH * sc, (POPW - OVER) * sc
        m = 6
        if side == 'up':   # breakouts stack above the phone (narrow bands beside a big face)
            up = len(pops) * (CH + 18) * sc - OVER * sc
            px, py_ = x + max(0, (POPW - PW) * sc / 2), y + up
            parts = [[px - m, py_ - m, px + pw + m, py_ + ph * 1.04]] + \
                    [[x - m, y + k * (CH + 18) * sc - m, x + POPW * sc + m, y + (k * (CH + 18) + CH) * sc + m] for k in range(len(pops))]
        else:
            px, py_ = (x if side == 'right' else x + ext), y
            cx = px + (PW - OVER) * sc if side == 'right' else px - (POPW - OVER) * sc
            parts = [[px - m, py_ - ph * .04, px + pw + m, py_ + ph * 1.04]] + \
                    [[cx - m, py_ + (ROW_Y0 + i * ROW_H - 18 - 10) * sc, cx + POPW * sc + m, py_ + (ROW_Y0 + i * ROW_H - 18 + CH + 10) * sc] for i in pops]
        box = [min(b[0] for b in parts), min(b[1] for b in parts), max(b[2] for b in parts), max(b[3] for b in parts)]
        return px, py_, box, parts
    best = None
    for sc in (1.0, .9, .8, .7, .62, .55, .5):
        for side in sides:
            for y in range(L.SAFE[1] + 34, L.SAFE[3], 16):   # breakouts bob and grow in z: keep 34 px under the top line
                for x in range(L.SAFE[0] + 6, L.SAFE[2], 16):
                    px, py_, box, parts = group(sc, side, x, y)
                    if L.unsafe(box):
                        continue
                    hit = max(L.box_face_share(b, L.all_faces(ctx, t)) for b in parts for t in (a, (a + end) / 2, end - .05))
                    if hit > .002:
                        continue
                    cost = abs((box[0] + box[2]) / 2 - 540) / 1000 + (0 if side != 'up' else .1) + \
                        (.2 if side != 'up' and (side == 'right') != (px + PW * sc / 2 > fcx) else 0)
                    if best is None or cost < best[0]:
                        best = (cost, sc, side, x, y)
        if best:
            break
    if not best:
        ctx.fail(f'phone-3d on {g["on"]!r}: no spot clears the faces even at half size; use a wider shot')
    _, sc, side, gx0, gy0 = best
    px, py, gbox, gparts = group(sc, side, gx0, gy0)
    if sc < 1:
        ctx.note(f'phone-3d placed at {sc:.0%} size to clear the faces (breakouts {side})')
    pw, ph, ext = PW * sc, PH * sc, (POPW - OVER) * sc
    if max(ctx.face_hit(a, end, *b) for b in gparts) > .005:
        ctx.warn(f'phone-3d on {g["on"]!r} touches a face mid-hold')

    # ---- markup (built at scale 1, zoomed) ----
    app = ctx.esc(g.get('app', 'App'))
    if g.get('src'):
        screen = f'<img class="shot" src="{ctx.asset(g["src"])}">'
    else:
        rws = ''.join(f'<div class="row r{i}"><i class="ic"></i><div class="rt"><div class="t1">{ctx.esc(r["title"])}</div>'
                      + (f'<div class="t2">{ctx.esc(r["sub"])}</div>' if r.get('sub') else '') + '</div><b class="ph"></b></div>'
                      for i, r in enumerate(rows))
        screen = (f'<div class="app"><div class="st"><span>9:41</span><span class="an">{app}</span></div>'
                  f'<div class="h1">{ctx.esc(g.get("title", ""))}</div>{rws}</div>')
    phone = (f'<div class="ph3" style="left:{(px - gx0) / sc:.0f}px;top:{(py - gy0) / sc:.0f}px"><div class="bz"><div class="sc">{screen}</div>'
             f'<div class="isl"></div></div><i class="bt b1"></i><i class="bt b2"></i><i class="bt b3"></i></div>')
    cards = ''
    for k, i in enumerate(pops):
        r = rows[i]
        ry = (ROW_Y0 + i * ROW_H if not g.get('src') else PH * .4 + k * 30) + (py - gy0) / sc
        if side == 'up':
            cx, cy_ = 0, (len(pops) - 1 - k) * (CH + 18)
        else:
            cx, cy_ = (px - gx0) / sc + (PW - OVER if side == 'right' else OVER - POPW), ry - 18
        cards += (f'<div class="bo k{k}" style="left:{cx:.0f}px;top:{cy_:.0f}px;width:{POPW}px" data-ry="{ry:.0f}"><i class="ic"></i>'
                  f'<div class="rt"><div class="t1" style="font-size:{cfs}px">{ctx.esc(r["title"])}</div>'
                  + (f'<div class="t2">{ctx.esc(r["sub"])}</div>' if r.get('sub') else '') + '</div></div>')
        r['_from'] = (0, ry - 18 - cy_) if side == 'up' else None
    html = f'<div class="fx-phone-3d" style="width:{(gbox[2] - gbox[0] - 24) / sc:.0f}px;height:{(gbox[3] - gy0) / sc:.0f}px;zoom:{sc:.3f}">{phone}{cards}</div>'
    cid = ctx.clip(ctx.front, a, end, html, f'position:absolute;left:{gx0:.0f}px;top:{gy0:.0f}px;')
    turn = -1 if side == 'right' else 1 if side == 'left' else (-1 if px + PW * sc / 2 > fcx else 1)   # the screen turns toward the breakouts, or away from the face
    ph_ = f'#{cid} .ph3'
    ctx.tw(f"gsap.set('{ph_}',{{transformPerspective:1400,transformOrigin:'50% 55%'}});")
    ctx.tw(f"tl.fromTo('{ph_}',{{opacity:0,rotationY:{-75 * turn},rotationX:22,rotationZ:{-8 * turn},scale:.55,y:220}},"
           f"{{opacity:1,rotationY:{14 * turn},rotationX:7,rotationZ:{-2 * turn},scale:1,y:0,duration:.85,ease:'back.out(1.6)',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.fromTo('{ph_}',{{rotationY:{14 * turn},rotationX:7}},{{rotationY:{8 * turn},rotationX:3,duration:{max(.3, end - a - 1.2):.2f},ease:'sine.inOut',immediateRender:false}},{ctx.q(a + .85)});")
    for k, (i, t) in enumerate(zip(pops, ptimes)):
        sel = f'#{cid} .bo.k{k}'
        dx = (-(PW - OVER) * .55) if side == 'right' else ((PW - OVER) * .55) if side == 'left' else 0
        dy = rows[i]['_from'][1] if side == 'up' else 0
        ctx.tw(f"gsap.set('{sel}',{{opacity:0,transformPerspective:1000}});")
        if not g.get('src'):   # the row lifts out: its slot in the screen empties
            ctx.tw(f"tl.fromTo('#{cid} .r{i} .rt, #{cid} .r{i} .ic',{{opacity:1}},{{opacity:0,duration:.12,immediateRender:false}},{ctx.q(t)});")
            ctx.tw(f"tl.fromTo('#{cid} .r{i} .ph',{{opacity:0}},{{opacity:1,duration:.2,immediateRender:false}},{ctx.q(t + .05)});")
        ctx.tw(f"tl.fromTo('{sel}',{{opacity:0,x:{dx:.0f},y:{dy:.0f},scale:.72,rotationY:{-30 * turn},z:-60}},"
               f"{{opacity:1,x:0,y:0,scale:1,rotationY:{-6 * turn},z:80,duration:.6,ease:'back.out(1.8)',immediateRender:false}},{ctx.q(t)});")
        bob = end - (t + .6) - .25
        if bob > .5:   # float: a slow bob, two half cycles at most per second
            reps = max(1, int(bob / .9))
            ctx.tw(f"tl.fromTo('{sel}',{{y:0}},{{y:{-10 if k % 2 else 10},duration:{bob / reps:.3f},repeat:{reps - 1},yoyo:true,ease:'sine.inOut',immediateRender:false}},{ctx.q(t + .6)});")
        ctx.sfx(g.get('sfx'), t, .3)
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:40,duration:.25,ease:'power2.in'}},{ctx.q(end - .25)});")
    L.claim(ctx, gbox[1], gbox[3], a, end)


def describe(g, beat):
    names = ', '.join(f'"{g["rows"][i]["title"]}"' for i, r in enumerate(g['rows']) if r.get('on'))
    return f'On “{g["on"]}” a 3D phone spins in showing {g.get("app", "an app")}; {names} break out of the screen on their words. It holds {beat["hold"]:.1f} s.'
