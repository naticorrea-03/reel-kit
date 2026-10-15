"""Comment-for-the-link CTA: an "Add a comment" bar types the keyword and posts it, then a DM pops in, "Sent you the link", with a link chip."""

META = {
    'id': 'comment-dm', 'name': 'Comment for the link', 'category': 'social',
    'when': 'The end call to action: "comment X and I will send you the link".',
    'never': 'Never a keyword the speaker does not say. Never a link label that promises something the post does not give.',
    'params': {'on': 'phrase that brings the bar in', 'keyword': 'the word to comment (required)', 'link': 'link chip label (required)',
               'message': 'DM text, default "Sent you the link"', 'you': 'small label before the comment, default "you"',
               'avatar': 'image for the sender of the DM, optional (default the first letter of name)', 'name': 'sender name for the initial, optional',
               'send_on': 'phrase where the comment posts, optional', 'dm_on': 'phrase where the DM arrives, optional', 'hold': 'seconds after the DM, default 1.6'},
    'sfx': ['typing', 'message-send', 'message-receive'], 'source': 'ours', 'credit': 'inspired by tenfoldmarc', 'license': 'MIT',
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

LINK = '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>'
HEART = '<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>'
SEND = '<svg viewBox="0 0 24 24"><path d="M12 19V6M6 11l6-6 6 6"/></svg>'


def build(g, ctx):
    _need(ctx, g, 'keyword', 'link')
    a = ctx.at(g['on'])[0]
    kw, link = str(g['keyword']), str(g['link'])
    t_type = a + .4
    type_d = min(1.0, .09 * len(kw) + .15)
    t_send = max(ctx.at(g['send_on'], a)[0] if g.get('send_on') else 0, t_type + type_d + .25)
    t_dm = max(ctx.at(g['dm_on'], a)[0] if g.get('dm_on') else 0, t_send + .55)
    a, end = _window(ctx, g, 1.6, last=t_dm)
    W, H = 760, 360
    face = ctx.speaker_face(a + .1)
    near = ((face[0] + face[2]) / 2, face[3] + 200) if face else (540, 1200)
    x, y, sc = _fitspot(ctx, 'comment-dm', W, H, a, end, lambda W, H: _grid(W, H, xs=((1080 - W) // 2, 90, 950 - W)), near, True,
                        scales=(1.0, .86, .74))
    _claim(ctx, x, y, W * sc, H * sc, a, end, True)
    url = ctx.asset(g['avatar']) if g.get('avatar') else None
    av = f'<img class="av2" src="{url}">' if url else f'<div class="av2 txt">{ctx.esc((g.get("name") or "A")[:1].upper())}</div>'
    letters = ''.join(f'<span class="tc">{ctx.esc(c)}</span>' for c in kw)
    html = (f'<div class="fx-comment-dm" style="width:{W}px;height:{H}px">'
            f'<div class="bar"><div class="av"></div><div class="in"><span class="ph">Add a comment...</span>'
            f'<span class="ty">{letters}</span><span class="cur"></span></div><div class="go">{SEND}</div></div>'
            f'<div class="cm"><div class="av"></div><div class="bub"><span class="you">{ctx.esc(g.get("you", "you"))}</span>'
            f'<span class="kw">{ctx.esc(kw)}</span><span class="ht">{HEART}</span></div></div>'
            f'<div class="wire"></div>'
            f'<div class="dm">{av}<div class="dbub"><div class="msg">{ctx.esc(g.get("message", "Sent you the link"))}</div>'
            f'<div class="lk">{LINK}<span>{ctx.esc(link)}</span></div></div></div></div>')
    cid = _zclip(ctx, sc, a, end, html, f'position:absolute;left:{x}px;top:{y}px;')
    S = f'#{cid}'
    for sel in ('.tc', '.cm', '.dm', '.wire', '.ht'):
        ctx.tw(f"gsap.set('{S} {sel}',{{opacity:0}});")
    ctx.tw(f"tl.fromTo('{S} .bar',{{opacity:0,y:40}},{{opacity:1,y:0,duration:.32,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    ctx.tw(f"tl.to('{S} .ph',{{opacity:0,duration:.06}},{ctx.q(t_type)});")
    # letters take no room until typed, so the cursor sits right after the last one
    ctx.tw(f"gsap.set('{S} .tc',{{maxWidth:0}});")
    ctx.tw(f"tl.fromTo('{S} .tc',{{opacity:0,maxWidth:0}},{{opacity:1,maxWidth:80,duration:.02,stagger:{type_d / max(1, len(kw)):.3f},immediateRender:false}},{ctx.q(t_type)});")
    ctx.tw(f"tl.fromTo('{S} .go',{{scale:1}},{{scale:.86,duration:.08,yoyo:true,repeat:1,ease:'power2.out',immediateRender:false}},{ctx.q(t_send - .12)});")
    # the bar becomes the posted comment: it lifts away and the comment settles in its place
    ctx.tw(f"tl.to('{S} .bar',{{opacity:0,y:-16,duration:.18,ease:'power2.in'}},{ctx.q(t_send)});")
    ctx.tw(f"tl.fromTo('{S} .cm',{{opacity:0,y:24,scale:.96}},{{opacity:1,y:0,scale:1,duration:.3,ease:'back.out(1.6)',immediateRender:false}},{ctx.q(t_send + .08)});")
    ctx.tw(f"tl.fromTo('{S} .ht',{{opacity:0,scale:0}},{{opacity:1,scale:1,duration:.28,ease:'back.out(3)',immediateRender:false}},{ctx.q(t_send + .3)});")
    ctx.tw(f"tl.fromTo('{S} .wire',{{opacity:0,scaleY:0}},{{opacity:1,scaleY:1,duration:.22,ease:'power2.out',immediateRender:false}},{ctx.q(t_dm - .18)});")
    ctx.tw(f"tl.fromTo('{S} .dm',{{opacity:0,x:-30,scale:.94}},{{opacity:1,x:0,scale:1,duration:.34,ease:'back.out(1.5)',immediateRender:false}},{ctx.q(t_dm)});")
    ctx.tw(f"tl.fromTo('{S} .lk',{{scale:.8}},{{scale:1,duration:.3,ease:'back.out(2.4)',immediateRender:false}},{ctx.q(t_dm + .18)});")
    ctx.tw(f"tl.to('{S}',{{opacity:0,y:-20,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")
    ctx.sfx('typing', t_type, .32, type_d + .05)
    ctx.sfx('message-send', t_send, .4)
    ctx.sfx('message-receive', t_dm, .4)


def describe(g, beat):
    return (f'On “{g["on"]}” an "Add a comment" bar types "{g["keyword"]}" and posts it, then a DM arrives, '
            f'"{g.get("message", "Sent you the link")}", with a "{g["link"]}" link chip. It holds {beat["hold"]:.1f} s.')
