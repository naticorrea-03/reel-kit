"""Profile follow: a dark-mode social profile (avatar, verified mark, stats, bio, post grid). A finger taps Follow, then the comment sheet slides up and a keyword types in."""

META = {
    'id': 'profile-follow', 'name': 'Profile follow', 'category': 'social',
    'when': 'The call to action: "follow me and comment X". Shows the account, the tap, and the word to comment.',
    'never': 'Never stats or a verified mark the account does not have: both show only when params give them. Never someone else\'s account without their say.',
    'params': {'on': 'phrase that brings the profile in', 'name': 'display name (required)', 'handle': 'handle (required)',
               'verified': 'true to show the verified mark, default false', 'stats': '{"posts", "followers", "following"} real numbers, optional',
               'bio': 'one bio line, optional', 'avatar': 'avatar image file, optional (default the initial)',
               'posts': 'list of 3 image files for the grid, optional (default plain tiles)', 'tap_on': 'phrase where Follow is tapped, default 0.8 s in',
               'keyword': 'word typed into the comment sheet, optional (no sheet without it)', 'comment_on': 'phrase where the sheet opens, optional',
               'hold': 'seconds after the last beat, default 1.4'},
    'sfx': ['tap', 'typing', 'message-send'], 'source': 'ours', 'credit': 'inspired by tenfoldmarc', 'license': 'MIT',
}

# ---------- local helpers (proposed for fxlib: wrap, fit, window, spot, claim) ----------
GLYPH = .56   # average glyph width in em, on the wide side so an estimated box never comes up short


def _wrap(text, width, fs, k=GLYPH):
    """greedy word wrap estimate: the lines text breaks into at fs px inside width px."""
    lines, cur = [], ''
    for w in str(text).split():
        t = f'{cur} {w}'.strip()
        if cur and len(t) * fs * k > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def _fit(ctx, what, texts, width, fmax, fmin=30, max_lines=3, k=GLYPH):
    """one font size for every text (parallel items share a size), the largest that fits width in max_lines."""
    texts = [str(t) for t in texts if t]
    for fs in range(int(fmax), int(fmin) - 1, -2):
        if all(len(_wrap(t, width, fs, k)) <= max_lines and max(len(w) for w in t.split()) * fs * k <= width for t in texts):
            return fs
    ctx.fail(f'{what}: {max(texts, key=len)!r} does not fit {max_lines} line(s) at {fmin}px; shorten it')


def _lines(texts, width, fs, k=GLYPH):
    return max([len(_wrap(t, width, fs, k)) for t in texts if t] or [0])


def _window(ctx, g, hold, last=None):
    """(a, end): lands on its word, clears before the next graphic, the until phrase, or the end of the clip."""
    a = ctx.at(g['on'])[0]
    last = a if last is None else last
    end = min(ctx.DUR - .05, last + float(g.get('hold', hold)))
    if g.get('until'):
        end = min(end, ctx.at(g['until'], a)[0] - .05)
    later = [t for h in ctx.graphics if h is not g and h.get('on') for t in [ctx.at(h['on'])[0]] if t > a + .05]
    if later:
        end = min(end, min(later) - .15)
    if end - last < .7:
        ctx.fail(f'{g["type"]} on {g["on"]!r} gets {end - last:.2f} s after its last beat before the next graphic or the end; '
                 'move it or the graphic after it')
    return a, end


def _cap_top(ctx):
    return int(ctx._caption_cfg().get('top', 1250))


def _grid(w, h, xs=None, step=40):
    xs = xs or (90, (1080 - w) // 2, 950 - w)
    ys = list(range(250, 1471 - int(h), step)) + [1470 - int(h)]   # always try the lowest spot: under-chin bands are tight
    return [(int(x), int(y)) for y in ys for x in xs]


def _spot(ctx, what, w, h, t0, t1, cands, near=None, pause=False, quiet=False):
    """(x, y): the candidate that clears faces first, then the caption band, then hides the least of the speakers."""
    cap, best = _cap_top(ctx), None
    for x, y in cands:
        x, y = int(max(90, min(x, 950 - w))), int(max(250, min(y, 1470 - h)))
        face = ctx.face_hit(t0, t1, x, y, x + w, y + h)
        c = 10 * face + .3 * max(ctx.alpha_cover(t0 + (t1 - t0) * k / 3, x, y, x + w, y + h) for k in range(4))
        if not pause and y + h > cap - 16:
            c += .5
        if near:
            c += .3 * ((x + w / 2 - near[0]) ** 2 + (y + h / 2 - near[1]) ** 2) ** .5 / 1000
        if best is None or c < best[0] - .005:
            best = (c, x, y, face)
    if best is None:
        ctx.fail(f'{what}: a {w}x{h} box does not fit the safe zone (x 90-950, y 250-1470); make it smaller')
    if best[3] > .02 and not quiet:
        ctx.warn(f'{what} still covers {best[3]:.0%} of a face')
    return best[1], best[2]


def _fitspot(ctx, what, w, h, t0, t1, cands, near=None, pause=False, scales=(1.0, .86, .74)):
    """(x, y, scale): full size where a spot clears the faces, else the card shrinks (0.86, 0.74) until one does."""
    tries = []
    for sc in scales:
        ws, hs = int(w * sc), int(h * sc)
        x, y = _spot(ctx, what, ws, hs, t0, t1, cands(ws, hs), near, pause, quiet=True)
        face = ctx.face_hit(t0, t1, x, y, x + ws, y + hs)
        tries.append((face, -sc, x, y))
        if face <= .02:
            break
    face, sc, x, y = min(tries)
    if face > .02:
        ctx.warn(f'{what} still covers {face:.0%} of a face even at {min(scales):.0%} size; pick another moment')
    elif -sc < 1:
        ctx.note(f'{what} shrunk to {-sc:.0%} to clear a face')
    return x, y, -sc


def _zclip(ctx, sc, a, b, inner, style):
    """ctx.clip on the front layer, with the card zoomed when _fitspot had to shrink it."""
    return ctx.clip(ctx.front, a, b, inner if sc == 1 else f'<div class="rk-zoom" style="zoom:{sc}">{inner}</div>', style)


def _claim(ctx, x, y, w, h, t0, t1, pause):
    """captions pause when the effect carries its own text or reaches the caption band; name tags and eyebrow make room."""
    if pause or y + h > _cap_top(ctx) - 16:
        ctx.busy.append((t0, t1))
    if y + h > 1060:
        ctx.lowbusy.append((t0, t1))
    if y < 400:
        ctx.topbusy.append((t0, t1))


def _need(ctx, g, *keys):
    for k in keys:
        if g.get(k) in (None, '', []):
            ctx.fail(f'{g["type"]} on {g["on"]!r} needs "{k}"')


def _times(ctx, g, items, step):
    """one time per item: its own "on" phrase (in order, after the previous one) or an even step after the graphic's word."""
    a = ctx.at(g['on'])[0]
    out, after = [], a - .2
    for k, it in enumerate(items):
        t = ctx.at(it['on'], after)[0] if isinstance(it, dict) and it.get('on') else (out[-1] + step if out else a)
        out.append(max(t, a))
        after = t
    return out
# ---------- end of local helpers ----------

TICK = '<svg class="vf" viewBox="0 0 24 24"><path class="vb" d="M12 2l2.4 1.8 3-.2.9 2.9 2.5 1.7-1 2.8 1 2.8-2.5 1.7-.9 2.9-3-.2L12 22l-2.4-1.8-3 .2-.9-2.9-2.5-1.7 1-2.8-1-2.8 2.5-1.7.9-2.9 3 .2z"/><path class="vk" d="M8 12.3l2.6 2.6L16 9.5"/></svg>'


def build(g, ctx):
    _need(ctx, g, 'name', 'handle')
    a = ctx.at(g['on'])[0]
    t_tap = max(ctx.at(g['tap_on'], a)[0] if g.get('tap_on') else 0, a + .8)
    kw = str(g.get('keyword') or '')
    t_sheet = max(ctx.at(g['comment_on'], a)[0] if g.get('comment_on') else 0, t_tap + .55) if kw else None
    type_d = min(1.0, .09 * len(kw) + .15)
    t_post = t_sheet + .35 + type_d + .2 if kw else None
    a, end = _window(ctx, g, 1.4, last=(t_post if kw else t_tap + .3))
    W = 600
    stats = g.get('stats') or {}
    bio = g.get('bio', '')
    nfs = _fit(ctx, 'profile-follow name', [g['name']], W - 64 - (44 if g.get('verified') else 0), 38, 30, 1)
    bfs = _fit(ctx, 'profile-follow bio', [bio], W - 64, 30, 28, 2) if bio else 0
    blines = len(_wrap(bio, W - 64, bfs)) if bio else 0
    base = int(30 + 112 + 18 + nfs * 1.25 + 36 + (blines * bfs * 1.3 + 10 if bio else 0) + 18 + 68 + 30)
    face = ctx.speaker_face(a + .1)
    near = ((face[0] + face[2]) / 2, face[3] + 300) if face else None
    # the post grid goes first when room is short: a readable card beats a complete one
    pick = None
    for grid_on, scales in ((True, (1.0, .9)), (False, (1.0, .9, .8)), (True, (.8, .72)), (False, (.72,))):
        H = base + (18 + 130 if grid_on else 0)
        for sc_ in scales:
            x, y = _spot(ctx, 'profile-follow', int(W * sc_), int(H * sc_), a, end, _grid(int(W * sc_), int(H * sc_)), near, True, quiet=True)
            if ctx.face_hit(a, end, x, y, x + W * sc_, y + H * sc_) <= .02:
                pick = (grid_on, H, x, y, sc_)
                break
        if pick:
            break
    if not pick:
        ctx.warn('profile-follow: no spot clears the face even at 72%; pick another moment')
        pick = (False, base, x, y, .72)
    grid_on, H, x, y, sc = pick
    if sc < 1:
        ctx.note(f'profile-follow at {sc:.0%}' + ('' if grid_on else ', post grid left out for room'))
    by = int(30 + 112 + 18 + nfs * 1.25 + 36 + (blines * bfs * 1.3 + 10 if bio else 0) + 18 + 34)   # centre of the Follow button
    _claim(ctx, x, y, W * sc, H * sc, a, end, True)
    url = ctx.asset(g['avatar']) if g.get('avatar') else None
    av = f'<img class="av" src="{url}">' if url else f'<div class="av txt">{ctx.esc(g["name"][:1].upper())}</div>'
    st = ''.join(f'<div class="st"><b>{ctx.esc(stats[k])}</b><span>{k}</span></div>' for k in ('posts', 'followers', 'following') if stats.get(k))
    posts = (g.get('posts') or [])[:3]
    grid = ''.join(f'<img class="p" src="{ctx.asset(p)}">' if k < len(posts) else f'<div class="p q{k}"><i></i></div>' for k, p in enumerate(posts + [None] * (3 - len(posts))))
    sheet = ''
    if kw:
        letters = ''.join(f'<span class="tc">{ctx.esc(c)}</span>' for c in kw)
        sheet = (f'<div class="sheet"><div class="grab"></div><div class="row"><div class="me"></div>'
                 f'<div class="inp"><span class="ph">Add a comment...</span><span class="ty">{letters}</span><span class="cur"></span></div>'
                 f'<div class="post">Post</div></div></div>')
    html = (f'<div class="fx-profile-follow" style="width:{W}px;height:{H}px"><div class="top">{av}<div class="sts">{st}</div></div>'
            f'<div class="nm" style="font-size:{nfs}px">{ctx.esc(g["name"])}{TICK if g.get("verified") else ""}</div>'
            f'<div class="hd">{ctx.esc(g["handle"])}</div>'
            + (f'<div class="bio" style="font-size:{bfs}px">{ctx.esc(bio)}</div>' if bio else '') +
            f'<div class="btns"><div class="fb"><span class="b0">Follow</span><span class="b1">Following</span></div><div class="mb">Message</div></div>'
            + (f'<div class="grid">{grid}</div>' if grid_on else '') + f'{sheet}<div class="touch" style="left:150px;top:{by}px"></div></div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    S = f'#{cid}'
    ctx.tw(f"tl.fromTo('{S} .fx-profile-follow',{{opacity:0,y:50,scale:.94}},{{opacity:1,y:0,scale:1,duration:.38,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    for sel in ('.b1', '.touch', '.sheet', '.tc'):
        ctx.tw(f"gsap.set('{S} {sel}',{{opacity:0}});")
    # the finger: a soft dot lands on Follow, presses, lifts
    ctx.tw(f"tl.fromTo('{S} .touch',{{opacity:0,scale:1.6}},{{opacity:1,scale:1,duration:.18,ease:'power2.out',immediateRender:false}},{ctx.q(t_tap - .2)});")
    ctx.tw(f"tl.fromTo('{S} .fb',{{scale:1}},{{scale:.94,duration:.08,yoyo:true,repeat:1,ease:'power2.out',immediateRender:false}},{ctx.q(t_tap)});")
    ctx.tw(f"tl.to('{S} .b0',{{opacity:0,duration:.1}},{ctx.q(t_tap + .06)});")
    ctx.tw(f"tl.fromTo('{S} .b1',{{opacity:0}},{{opacity:1,duration:.1,immediateRender:false}},{ctx.q(t_tap + .08)});")
    ctx.tw(f"tl.fromTo('{S} .fb',{{'--done':0}},{{'--done':1,duration:.12,immediateRender:false}},{ctx.q(t_tap + .06)});")
    ctx.tw(f"tl.to('{S} .touch',{{opacity:0,scale:1.3,duration:.22}},{ctx.q(t_tap + .2)});")
    ctx.sfx('tap', t_tap, .45)
    if kw:
        t_type = t_sheet + .35
        ctx.tw(f"tl.fromTo('{S} .sheet',{{opacity:0,y:120}},{{opacity:1,y:0,duration:.34,ease:'power3.out',immediateRender:false}},{ctx.q(t_sheet)});")
        # what the sheet slides over steps back, so nothing reads through it
        ctx.tw(f"tl.to('{S} .bio, {S} .btns, {S} .grid',{{opacity:0,duration:.2}},{ctx.q(t_sheet + .08)});")
        ctx.tw(f"tl.to('{S} .ph',{{opacity:0,duration:.06}},{ctx.q(t_type)});")
        ctx.tw(f"gsap.set('{S} .tc',{{maxWidth:0}});")
        ctx.tw(f"tl.fromTo('{S} .tc',{{opacity:0,maxWidth:0}},{{opacity:1,maxWidth:80,duration:.02,stagger:{type_d / max(1, len(kw)):.3f},immediateRender:false}},{ctx.q(t_type)});")
        ctx.tw(f"tl.fromTo('{S} .post',{{'--on':0}},{{'--on':1,duration:.12,immediateRender:false}},{ctx.q(t_type + .05)});")
        ctx.tw(f"tl.fromTo('{S} .post',{{scale:1}},{{scale:.9,duration:.08,yoyo:true,repeat:1,immediateRender:false}},{ctx.q(t_post)});")
        ctx.sfx('typing', t_type, .32, type_d + .05)
        ctx.sfx('message-send', t_post, .4)
    ctx.tw(f"tl.to('{S}',{{opacity:0,y:-24,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")


def describe(g, beat):
    s = f'On “{g["on"]}” a dark profile for {g["name"]} ({g["handle"]}) slides in and a finger taps Follow'
    if g.get('keyword'):
        s += f', then the comment sheet opens and "{g["keyword"]}" types in and posts'
    return s + f'. It holds {beat["hold"]:.1f} s.'
