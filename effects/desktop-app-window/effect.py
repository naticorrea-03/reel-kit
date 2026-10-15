"""Desktop app window: a generic chat app where files drop into the input with a count badge, a slash command types with its menu,
and the reply works through a checklist and hands back a file card. Sits on the wall behind the speaker when the wall has room."""

META = {
    'id': 'desktop-app-window', 'name': 'Desktop app window', 'category': 'ui',
    'when': 'The speaker describes the whole workflow in one breath: "drop the clips in, type the command, it sends back the edit".',
    'never': 'Never branded as a real product (no real app names, logos or colours). Never steps the speaker does not describe.',
    'params': {'on': 'phrase that opens the window', 'app': 'neutral app name in the title bar, default "Studio"',
               'files': 'list of file names or a number, default 5 clips', 'command': 'slash command typed (required), e.g. "/edit-reel"',
               'menu': 'two other commands for the menu, optional', 'steps': '2 to 4 reply steps that tick off (required)',
               'output': 'file name of the result (required)', 'status': 'line under the file name, default "ready"',
               'drop_on': 'phrase where the files drop, optional', 'type_on': 'phrase where typing starts, optional', 'reply_on': 'phrase where the reply starts, optional',
               'hold': 'seconds after the file card, default 1.2', 'captions': '"pause" or "keep" when the window comes to the front, default pause'},
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

FILE = '<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z M14 3v4h4"/></svg>'
PLAY = '<svg viewBox="0 0 24 24"><path d="M9 7l8 5-8 5z"/></svg>'
SPARK = '<svg viewBox="0 0 24 24"><path d="M5 12h14M12 5v14"/></svg>'
W, H = 900, 540


def _chk(ctx, text):
    return (f'<div class="sp"><div class="bx"><svg viewBox="0 0 24 24"><path d="M6 12.5l4 4L18 8.5"/></svg></div>'
            f'<span>{ctx.esc(text)}</span></div>')


def build(g, ctx):
    _need(ctx, g, 'command', 'steps', 'output')
    steps = [str(s) for s in g['steps']]
    if not 2 <= len(steps) <= 4:
        ctx.fail(f'desktop-app-window on {g["on"]!r} needs 2 to 4 steps')
    files = g.get('files', 5)
    files = [f'clip-{k + 1:02d}.mov' for k in range(int(files))] if isinstance(files, (int, float)) else [str(f) for f in files]
    nf = len(files)
    cmd = str(g['command'])
    cmd = cmd if cmd.startswith('/') else '/' + cmd
    menu = [cmd] + [m if str(m).startswith('/') else '/' + str(m) for m in (g.get('menu') or ['/summarize', '/translate'])][:2]
    a = ctx.at(g['on'])[0]
    t_drop = max(a + .15, ctx.at(g['drop_on'], a)[0] if g.get('drop_on') else 0)
    t_type = max(t_drop + .2 + .08 * min(nf, 5), ctx.at(g['type_on'], a)[0] if g.get('type_on') else 0)
    type_d = min(1.0, .06 * len(cmd) + .12)
    t_send = t_type + type_d + .25
    t_reply = max(t_send + .35, ctx.at(g['reply_on'], a)[0] if g.get('reply_on') else 0)
    t_steps = [t_reply + .3 + .24 * k for k in range(len(steps))]
    t_file = t_steps[-1] + .32
    a, end = _window(ctx, g, 1.2, last=t_file)
    pause = g.get('captions', 'pause') != 'keep'

    # where: on the wall behind the speaker when the text area clears every head, else in front clear of the faces
    layer, pick = None, None
    if ctx.has_cut:
        for sc in (1.0, .9, .8, .72):
            w_, h_ = int(W * sc), int(H * sc)
            for y in range(250, 1200 - h_, 20):
                for x in sorted({90, (1080 - w_) // 2, 950 - w_}):
                    if max(ctx.alpha_cover(a + (end - a) * k / 5, x, y, x + w_, y + h_ - int(40 * sc)) for k in range(6)) <= .02:
                        pick = (x, y, sc)
                        break
                if pick:
                    break
            if pick:
                layer = 'wall'
                break
    if not pick:
        face = ctx.speaker_face(a + .1)
        near = ((face[0] + face[2]) / 2, face[3] + 300) if face else None
        for sc in (.9, .8, .72, .64, .58):
            x, y = _spot(ctx, 'desktop-app-window', int(W * sc), int(H * sc), a, end, _grid(int(W * sc), int(H * sc)), near, pause, quiet=True)
            if ctx.face_hit(a, end, x, y, x + W * sc, y + H * sc) <= .02:
                pick = (x, y, sc)
                break
        if not pick:
            ctx.warn('desktop-app-window still touches a face at 58%; pick a moment with a smaller face')
            pick = (x, y, .58)
        layer = 'front'
        _claim(ctx, pick[0], pick[1], W * pick[2], H * pick[2], a, end, pause)
    elif pick[1] < 400:
        ctx.topbusy.append((a, end))
    x, y, sc = pick
    ctx.note(f'desktop-app-window on the {layer} at {sc:.0%}')

    chips = ''.join(f'<div class="fc f{k}" style="left:{k * 46}px;z-index:{10 - k}">{PLAY}</div>' for k in range(min(nf, 5)))
    letters = ''.join(f'<span class="tc">{ctx.esc(c)}</span>' for c in cmd)
    mitems = ''.join(f'<div class="mi m{k}"><b>{ctx.esc(m)}</b></div>' for k, m in enumerate(menu))
    html = (f'<div class="fx-desktop-app-window" style="width:{W}px;height:{H}px">'
            f'<div class="tb"><span class="dots"><i></i><i></i><i></i></span><span class="app">{ctx.esc(g.get("app", "Studio"))}</span></div>'
            f'<div class="msgs"><div class="ub"><span class="nf">{nf} files</span><span class="uc">{ctx.esc(cmd)}</span></div>'
            f'<div class="rp"><div class="pill">{SPARK}<span>Running {ctx.esc(cmd)}</span></div>'
            + ''.join(f'<div class="s{k}">{_chk(ctx, s)}</div>' for k, s in enumerate(steps)) +
            f'<div class="card"><div class="ic">{FILE}</div><div><div class="fn">{ctx.esc(g["output"])}</div>'
            f'<div class="fs">{ctx.esc(g.get("status", "ready"))}</div></div></div></div></div>'
            f'<div class="menu">{mitems}</div>'
            f'<div class="comp"><div class="chips" style="width:{46 * (min(nf, 5) - 1) + 64}px">{chips}<span class="badge">{nf}</span></div>'
            f'<div class="ty"><span class="ph">Message {ctx.esc(g.get("app", "Studio"))}</span>{letters}<span class="cur"></span></div><div class="send">{SPARK}</div></div></div>')
    lay = ctx.wall if layer == 'wall' else ctx.front
    inner = html if sc == 1 else f'<div class="rk-zoom" style="zoom:{sc}">{html}</div>'
    cid = ctx.clip(lay, a, end, inner, f'position:absolute;left:{x}px;top:{y}px;', 'wallz' if layer == 'wall' else '')
    S = f'#{cid}'
    for sel in ('.fc', '.badge', '.tc', '.menu', '.ub', '.pill', '.sp', '.card'):
        ctx.tw(f"gsap.set('{S} {sel}',{{opacity:0}});")
    ctx.tw(f"gsap.set('{S} .tc',{{maxWidth:0}});")
    ctx.tw(f"tl.fromTo('{S} .fx-desktop-app-window',{{opacity:0,y:-50,scale:.95}},{{opacity:1,y:0,scale:1,duration:.4,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
    # 1. files drop into the input, the count badge pops
    ctx.tw(f"tl.fromTo('{S} .fc',{{opacity:0,y:-160,rotation:-12,scale:1.2}},{{opacity:1,y:0,rotation:0,scale:1,duration:.32,stagger:.08,ease:'back.out(1.6)',immediateRender:false}},{ctx.q(t_drop)});")
    t_badge = t_drop + .08 * (min(nf, 5) - 1) + .28
    ctx.tw(f"tl.fromTo('{S} .badge',{{opacity:0,scale:0}},{{opacity:1,scale:1,duration:.24,ease:'back.out(3)',immediateRender:false}},{ctx.q(t_badge)});")
    # 2. the slash command types; its menu opens on the slash
    ctx.tw(f"tl.to('{S} .ph',{{opacity:0,duration:.08}},{ctx.q(t_type - .08)});")
    ctx.tw(f"tl.fromTo('{S} .tc',{{opacity:0,maxWidth:0}},{{opacity:1,maxWidth:60,duration:.02,stagger:{type_d / len(cmd):.3f},immediateRender:false}},{ctx.q(t_type)});")
    ctx.tw(f"tl.fromTo('{S} .menu',{{opacity:0,y:20}},{{opacity:1,y:0,duration:.2,ease:'power3.out',immediateRender:false}},{ctx.q(t_type + .05)});")
    ctx.tw(f"tl.fromTo('{S} .mi.m0',{{'--hl':0}},{{'--hl':1,duration:.15,immediateRender:false}},{ctx.q(t_type + type_d * .5)});")
    # 3. send: menu and composer clear, the user message lands
    ctx.tw(f"tl.to('{S} .menu',{{opacity:0,duration:.12}},{ctx.q(t_send - .05)});")
    ctx.tw(f"tl.to('{S} .fc, {S} .badge, {S} .tc',{{opacity:0,duration:.14}},{ctx.q(t_send)});")
    ctx.tw(f"tl.fromTo('{S} .ub',{{opacity:0,y:30,scale:.95}},{{opacity:1,y:0,scale:1,duration:.3,ease:'back.out(1.5)',immediateRender:false}},{ctx.q(t_send + .05)});")
    # 4. the reply works through the steps and hands back a file
    ctx.tw(f"tl.fromTo('{S} .pill',{{opacity:0,x:-20}},{{opacity:1,x:0,duration:.25,ease:'power3.out',immediateRender:false}},{ctx.q(t_reply)});")
    for k, t in enumerate(t_steps):
        ctx.tw(f"tl.fromTo('{S} .s{k} .sp',{{opacity:0,y:12}},{{opacity:1,y:0,duration:.2,ease:'power3.out',immediateRender:false}},{ctx.q(t - .12)});")
        ctx.tw(f"tl.fromTo('{S} .s{k} .bx',{{'--on':0}},{{'--on':1,duration:.14,immediateRender:false}},{ctx.q(t + .1)});")
        ctx.tw(f"tl.fromTo('{S} .s{k} path',{{strokeDashoffset:24}},{{strokeDashoffset:0,duration:.22,ease:'power2.out',immediateRender:false}},{ctx.q(t + .12)});")
    ctx.tw(f"tl.fromTo('{S} .card',{{opacity:0,y:24,scale:.94}},{{opacity:1,y:0,scale:1,duration:.32,ease:'back.out(1.6)',immediateRender:false}},{ctx.q(t_file)});")
    ctx.tw(f"tl.to('{S}',{{opacity:0,y:-30,duration:.22,ease:'power2.in'}},{ctx.q(end - .22)});")
    ctx.sfx('typing', t_type, .3, type_d + .05)
    ctx.sfx('message-send', t_send, .38)
    ctx.sfx('message-receive', t_file, .38)


def describe(g, beat):
    files = g.get('files', 5)
    nf = files if isinstance(files, (int, float)) else len(files)
    return (f'On “{g["on"]}” a {g.get("app", "Studio")} desktop window opens: {int(nf)} files drop into the input, '
            f'"{g["command"]}" types with its menu, and the reply ticks off {len(g["steps"])} steps and hands back {g["output"]}. '
            f'It holds {beat["hold"]:.1f} s.')
