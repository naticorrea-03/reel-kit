#!/usr/bin/env python3
"""Build one reel composition: python3 engine/build.py <project_dir> <slug> [--safe] [--look id]

Reads <project>/project.json, <project>/clips.json, the user's profile (~/.reel-kit/profile.json or project.json
"profile"), and a look (looks/<id>.json). Writes <project>/clips/<slug>/index.html (HyperFrames) and plan.json.

Layers, bottom to top: graded base video | WALL (words and cards behind the heads) | speaker cutout (same grade) |
grade overlays | FRONT (cards, notes, logos) | TOP (captions, name tags) | eyebrow.
Every timed element is a .clip wrapper with data-start/data-duration; GSAP animates only the inner .in node.
Graphics are effects: effects/<type>/effect.py builds them, effects/<type>/style.css styles them.
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fxlib import Context, F, REPO, EFFECTS, load_effect, ffprobe_duration  # noqa: E402

GSAP = 'https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js'


def load_json(path, what):
    try:
        return json.load(open(path))
    except FileNotFoundError:
        sys.exit(f'ERROR: {what} not found: {path}')
    except json.JSONDecodeError as e:
        sys.exit(f'ERROR: {what} is not valid JSON ({path}): {e}')


def main(argv):
    argv = list(argv)
    look_arg = None
    if '--look' in argv:
        i = argv.index('--look')
        if i + 1 >= len(argv):
            sys.exit('ERROR: --look needs a look id: ' + ', '.join(sorted(f[:-5] for f in os.listdir(os.path.join(REPO, 'looks')) if f.endswith('.json'))))
        look_arg = argv[i + 1]
        del argv[i:i + 2]
    safe = '--safe' in argv
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 2:
        sys.exit(__doc__)
    project_dir, slug = os.path.abspath(os.path.expanduser(args[0])), args[1]

    project = load_json(os.path.join(project_dir, 'project.json'), 'project.json')
    clips = load_json(os.path.join(project_dir, project.get('clips', 'clips.json')), 'clips.json')['clips']
    clip = next((c for c in clips if c['slug'] == slug), None)
    if clip is None:
        sys.exit(f'ERROR: no clip {slug!r} in clips.json (have: {", ".join(c["slug"] for c in clips)})')
    prof_path = os.path.expanduser(project.get('profile') or os.environ.get('REELKIT_PROFILE') or '~/.reel-kit/profile.json')
    if not os.path.isabs(prof_path):
        prof_path = os.path.join(project_dir, prof_path)
    profile = load_json(prof_path, 'profile') if os.path.exists(prof_path) else {}
    look_id = look_arg or clip.get('look') or project.get('look') or profile.get('look') or 'editorial'
    look = load_json(os.path.join(REPO, 'looks', f'{look_id}.json'), f'look {look_id!r}')

    ctx = Context(project_dir, slug, clip, look, profile, project, safe)
    build_hook(ctx, clip)
    used = build_graphics(ctx, clip)
    guard_parallel(ctx)
    cues = build_captions(ctx)
    build_lower_thirds(ctx)
    eyebrow_html = build_eyebrow(ctx)
    build_punches(ctx)
    audio, sfx_len = build_audio(ctx)
    css = page_css(ctx, used)
    page = page_html(ctx, css, audio, eyebrow_html)
    write_plan(ctx, sfx_len)
    with open(os.path.join(ctx.D, 'index.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(page)
    hf = os.path.join(ctx.D, 'hyperframes.json')
    if not os.path.exists(hf):
        json.dump({'$schema': 'https://hyperframes.heygen.com/schema/hyperframes.json',
                   'paths': {'blocks': 'compositions', 'components': 'compositions/components', 'assets': 'assets'},
                   'media': {'autoProxy': True}}, open(hf, 'w'), indent=2)
    print(f'{slug}: index.html {ctx.DUR:.2f}s, look {look_id}, {cues} caption cues ({len(ctx.busy)} busy windows), '
          f'{len(ctx.seg)} shots, {len(audio)} sfx, cutout={ctx.has_cut}')


# ---------------- HOOK (first ~2.1 s) ----------------
def build_hook(ctx, clip):
    hook = clip.get('hook')
    if not hook:
        return
    small, big = hook[0], hook[1]
    sub = hook[2] if len(hook) > 2 else ''   # optional third line: a tracked-caps subtitle (masthead)
    first_g = min([ctx.at(g['on'])[0] for g in clip.get('graphics', []) if g.get('on')] + [ctx.DUR])
    hook_end = max(1.2, min(2.2, first_g - .12))
    ctx.hook_end = hook_end
    style = ctx.look.get('hook', {}).get('style', 'stack')
    if style in HOOK_STYLES and HOOK_STYLES[style](ctx, small, big, sub, hook_end):
        return
    lines, cur = [], []
    for w in big.split():
        if cur and len(' '.join(cur + [w])) > 9:
            lines.append(cur)
            cur = []
        cur.append(w)
    lines.append(cur)
    longest = max(len(' '.join(l)) for l in lines)
    hs = int(min(230, 940 / (max(longest, 4) * .74)))
    big_html = '<br>'.join(ctx.esc(' '.join(l)) for l in lines)
    hh = 100 + len(lines) * hs * .9
    # below the chins first (it reads as a cover line), anywhere clear of the face otherwise
    htop = next((y for y in range(960, int(1470 - hh) + 1, 20) if ctx.face_hit(0, hook_end, 140, y, 940, y + hh) <= .02), None)
    if htop is None:   # no room under the chin (a low, centred face): the band above the head
        htop = next((y for y in range(240, 960, 20) if ctx.face_hit(0, hook_end, 140, y, 940, y + hh) <= .02), 960)
    if ctx.face_hit(0, hook_end, 140, htop, 940, htop + hh) > .02:
        ctx.warn('hook still touches a face')
    hk = ctx.look.get('hook', {})
    ctx.beat('hook', text=f'{small} {big}', g={'small': small, 'big': big})
    hid = ctx.clip(ctx.front, 0, hook_end, f'<div class="hk-s {hk.get("small", "")}">{ctx.esc(small)}</div>'
                   f'<div class="hk-b {"serif" if hk.get("big") == "serif" else ""}" style="font-size:{hs}px">{big_html}</div>',
                   f'position:absolute;left:0;right:0;top:{htop}px;')
    ctx.busy.append((0, hook_end))
    ctx.lowbusy.append((0, hook_end))
    ctx.tw(f"tl.fromTo('#{hid} .hk-s',{{opacity:0,y:30}},{{opacity:1,y:0,duration:.35,ease:'power3.out',immediateRender:false}},0);")
    ctx.tw(f"tl.fromTo('#{hid} .hk-b',{{opacity:0,scale:1.35,filter:'blur(18px)'}},{{opacity:1,scale:1,filter:'blur(0px)',duration:.4,ease:'power3.out',immediateRender:false}},0.18);")
    ctx.tw(f"tl.to('#{hid}',{{opacity:0,y:-30,filter:'blur(10px)',duration:.22,ease:'power2.in'}},{ctx.q(hook_end - .22)});")
    # the hook lands in silence: sounds only for literal nouns


# ---------------- hook variants (look json "hook": {"style": ...}) ----------------
# Each returns True when it placed the hook, False to fall back to the default stacked hook.
def _hook_top(ctx, h, hook_end, x0=120, x1=960):
    """first y from the top band down where an h-tall box clears every face; None when there is none."""
    h += 40   # rendered type runs taller than its estimate (descenders, the script line), so keep a margin over the hair
    return next((y for y in range(250, int(1470 - h) + 1, 10) if ctx.face_hit(0, hook_end, x0, y, x1, y + h) <= .005), None)


def _hook_light(ctx, hook_end, x0, y0, x1, y1):
    """True on a plain bright wall, where light type reads as a smudge: the hook switches to ink."""
    lum, busy = ctx.bg_luma(0, hook_end, x0, y0, x1, y1)
    ctx.note(f'hook background brightness {lum:.2f}, busyness {busy:.2f}')
    return lum > .55 and busy < .12


def _hook_lines(text, per):
    lines, cur = [], []
    for w in text.split():
        if cur and len(' '.join(cur + [w])) > per:
            lines.append(cur)
            cur = []
        cur.append(w)
    lines.append(cur)
    return [' '.join(l) for l in lines]


def _hook_balanced(text, per):
    """the fewest lines of at most ~per characters, broken where the lines come out most even."""
    words = text.split()
    n = max(1, -(-len(text) // per))
    best = None
    def splits(ws, k):
        if k == 1:
            yield [' '.join(ws)]
            return
        for i in range(1, len(ws) - k + 2):
            for rest in splits(ws[i:], k - 1):
                yield [' '.join(ws[:i])] + rest
    for k in range(n, len(words) + 1):
        for cand in splits(words, k):
            score = max(len(l) for l in cand)
            if best is None or score < best[0]:
                best = (score, cand)
        if best and best[0] <= per:
            break
    return best[1] if best else [text]


def hook_cover(ctx, small, big, sub, hook_end):
    """golden-hour: a sentence-case editorial serif title in the top band, a handwritten line under it."""
    best = None   # the biggest title that fits the band above the head, on one, two or three lines
    for per in (40, 24, 17, 12):
        lines = _hook_balanced(big, per)
        ts = int(min(104, 880 / (max(max(len(l) for l in lines), 6) * .47)))
        while ts >= 64:
            hh = int(len(lines) * ts * 1.0 + (66 if small else 0) + 10)
            top = _hook_top(ctx, hh, hook_end)
            if top is not None and top < 700:
                if best is None or ts > best[0]:
                    best = (ts, lines, hh, top)
                break
            ts -= 6
    if best is None:
        return False
    ts, lines, hh, top = best
    light = _hook_light(ctx, hook_end, 120, top, 960, top + hh)
    ctx.beat('hook', text=f'{big} {small}', g={'small': small, 'big': big})
    inner = (f'<div class="hk-cover{" on-light" if light else ""}"><div class="hk-ct" style="font-size:{ts}px">'
             + '<br>'.join(ctx.esc(l) for l in lines) + '</div>'
             + (f'<div class="hk-cs">{ctx.esc(small)}</div>' if small else '') + '</div>')
    hid = ctx.clip(ctx.front, 0, hook_end, inner, f'position:absolute;left:0;right:0;top:{top}px;')
    ctx.busy.append((0, hook_end))
    ctx.topbusy.append((0, hook_end))
    ctx.tw(f"tl.fromTo('#{hid} .hk-ct',{{opacity:0,y:18,filter:'blur(10px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.55,ease:'power2.out',immediateRender:false}},0);")
    if small:
        # the handwritten line writes itself on left to right, about 18 characters a second
        ctx.tw(f"gsap.set('#{hid} .hk-cs',{{clipPath:'inset(-20% 100% -20% 0)'}});")
        ctx.tw(f"tl.fromTo('#{hid} .hk-cs',{{clipPath:'inset(-20% 100% -20% 0)'}},{{clipPath:'inset(-20% 0% -20% 0)',duration:{min(1.4, max(.5, len(small) / 18)):.2f},ease:'none',immediateRender:false}},0.3);")
    ctx.tw(f"tl.to('#{hid}',{{opacity:0,filter:'blur(8px)',duration:.3,ease:'power1.in'}},{ctx.q(hook_end - .3)});")
    return True


def hook_mixed(ctx, small, big, sub, hook_end):
    """native: heavy sans caps line, then an italic serif accent line, in the top band like a feed cover."""
    a_lines = _hook_balanced(small, 18)
    b_lines = _hook_balanced(big, 16)
    sa0 = min(128, 940 / (max(max(len(l) for l in a_lines), 5) * .64))
    sb0 = min(min(150, 940 / (max(max(len(l) for l in b_lines), 5) * .50)), sa0 * 1.25)   # the accent line never dwarfs the caps
    for k in (1, .92, .84, .76, .68, .6):   # shrink together until the pair fits the band above the head
        sa, sb = int(sa0 * k), int(sb0 * k)
        hh = int(len(a_lines) * sa * .95 + len(b_lines) * sb * 1.0 + 20)
        top = _hook_top(ctx, hh, hook_end, 90, 990)
        if top is not None and top < 700:
            break
    else:
        return False
    light = _hook_light(ctx, hook_end, 90, top, 990, top + int(len(a_lines) * sa))
    ctx.beat('hook', text=f'{small} {big}', g={'small': small, 'big': big})
    inner = (f'<div class="hk-mix{" on-light" if light else ""}"><div class="hk-ma" style="font-size:{sa}px">'
             + '<br>'.join(ctx.esc(l) for l in a_lines) + f'</div><div class="hk-mb" style="font-size:{sb}px">'
             + '<br>'.join(ctx.esc(l) for l in b_lines) + '</div></div>')
    hid = ctx.clip(ctx.front, 0, hook_end, inner, f'position:absolute;left:0;right:0;top:{top}px;')
    ctx.busy.append((0, hook_end))
    ctx.topbusy.append((0, hook_end))
    ctx.tw(f"tl.fromTo('#{hid} .hk-ma',{{opacity:0,scale:.82,y:10}},{{opacity:1,scale:1,y:0,duration:.22,ease:'back.out(2.2)',immediateRender:false}},0);")
    ctx.tw(f"tl.fromTo('#{hid} .hk-mb',{{opacity:0,y:26}},{{opacity:1,y:0,duration:.3,ease:'power3.out',immediateRender:false}},0.2);")
    ctx.tw(f"tl.to('#{hid}',{{opacity:0,y:-20,duration:.18,ease:'power2.in'}},{ctx.q(hook_end - .18)});")
    return True


def hook_masthead(ctx, small, big, sub, hook_end):
    """masthead: a giant condensed serif title tucked behind the head (bottom edge under the hair), a title-case
    serif line and an optional tracked-caps kicker above it, or under the chin when the head leaves no headroom.
    Without a cutout, or with no room for the title at 150 px, it falls back to the default hook."""
    if not ctx.has_cut:
        return False
    ts_ = [hook_end * k / 5 for k in range(6)]
    tops = [ctx.head_top(t) for t in ts_]
    if any(t is None for t in tops):
        return False
    ht = min(tops)
    lines = _hook_lines(big.upper() if ctx.var('--hook-case') == 'uppercase' else big, 10)
    wf = .54   # condensed serif caps: average advance per character, in em (measured, with margin)
    size = int(min(400, 920 / (max(max(len(l) for l in lines), 4) * wf)))
    while size >= 150:
        tw = max(len(l) for l in lines) * wf * size
        x0, x1 = 540 - tw / 2, 540 + tw / 2
        th = len(lines) * .86 * size
        best = None
        for dy in range(int(.42 * size), -int(.6 * size), -8):   # deepest tuck whose title stays readable
            bot = ht + dy
            cov = max(ctx.alpha_cover(t, x0, bot - th, x1, bot) for t in ts_)
            if cov <= .035:   # the audit fails a wall word over 8% hidden; the estimate runs a little wide, so keep margin
                best = bot
                break
        if best is not None and best - th >= 250:
            break
        size -= 12
    else:
        return False
    tt = int(best - th)
    ss = int(max(50, min(92, size * .32))) if small else 0
    ks = 30 if sub else 0
    above = (int(ss * 1.15) if small else 0) + (int(ks * 2.0) if sub else 0)
    lower = None
    if above and tt - above < 250:   # no headroom for the cover lines: they go under the chin, like a magazine cover line
        lh = above + 20
        lower = next((y for y in range(960, int(1470 - lh) + 1, 10) if ctx.face_hit(0, hook_end, 140, y, 940, y + lh) <= .005), None)
        if lower is None:
            return False
    light = _hook_light(ctx, hook_end, x0, tt, x1, best)
    on = ' on-light' if light else ''
    lon = on if lower is None else (' on-light' if _hook_light(ctx, hook_end, 140, lower, 940, lower + above) else '')
    ctx.beat('hook', text=' '.join(x for x in (sub, small, big) if x), g={'small': small, 'big': big})
    ctx.busy.append((0, hook_end))
    ctx.topbusy.append((0, hook_end))
    ctx.lowbusy.append((0, hook_end))
    tid = ctx.clip(ctx.wall, 0, hook_end, f'<div class="hk-mh{on}"><div class="hk-mt" style="font-size:{size}px">'
                   + '<br>'.join(ctx.esc(l) for l in lines) + '</div></div>', f'position:absolute;left:0;right:0;top:{tt}px;', 'wallz')
    if lower is None:   # kicker on top, then the serif line, then the title
        ky, sy = tt - above, tt - int(ss * 1.15)
        if small:
            sid = ctx.clip(ctx.front, 0, hook_end, f'<div class="hk-mh{on}"><div class="hk-ms" style="font-size:{ss}px">{ctx.esc(small)}</div></div>',
                           f'position:absolute;left:0;right:0;top:{sy}px;')
            ctx.tw(f"tl.fromTo('#{sid}',{{opacity:0,y:20,filter:'blur(8px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.45,ease:'expo.out',immediateRender:false}},0.05);")
            ctx.tw(f"tl.to('#{sid}',{{opacity:0,duration:.22}},{ctx.q(hook_end - .22)});")
        if sub:
            kid = ctx.clip(ctx.front, 0, hook_end, f'<div class="hk-mh{on}"><div class="hk-mk">{ctx.esc(sub)}</div></div>',
                           f'position:absolute;left:0;right:0;top:{ky}px;')
            ctx.tw(f"tl.fromTo('#{kid}',{{opacity:0,scaleX:1.4,filter:'blur(6px)'}},{{opacity:1,scaleX:1,filter:'blur(0px)',duration:.5,ease:'expo.out',immediateRender:false}},0.3);")
            ctx.tw(f"tl.to('#{kid}',{{opacity:0,duration:.22}},{ctx.q(hook_end - .22)});")
    else:   # under the chin the cover lines sit on a plate (the caption plate colours), so they read on any shirt
        ss = min(ss, 60)
        inner = ((f'<div class="hk-ms" style="font-size:{ss}px">{ctx.esc(small)}</div>' if small else '')
                 + (f'<div class="hk-mk">{ctx.esc(sub)}</div>' if sub else ''))
        lid = ctx.clip(ctx.front, 0, hook_end, f'<div class="hk-mh hk-low">{inner}</div>', f'position:absolute;left:0;right:0;top:{lower}px;')
        ctx.tw(f"tl.fromTo('#{lid}',{{opacity:0,y:24,filter:'blur(8px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.45,ease:'expo.out',immediateRender:false}},0.25);")
        if sub:
            ctx.tw(f"tl.fromTo('#{lid} .hk-mk',{{scaleX:1.4,opacity:0}},{{scaleX:1,opacity:1,duration:.5,ease:'expo.out',immediateRender:false}},0.4);")
        ctx.tw(f"tl.to('#{lid}',{{opacity:0,duration:.22}},{ctx.q(hook_end - .22)});")
    # the title wipes up out of its own baseline (a mask edge rising), letters lifting into place behind the head
    ctx.tw(f"gsap.set('#{tid} .hk-mt',{{clipPath:'inset(100% -5% -10% -5%)'}});")
    ctx.tw(f"tl.fromTo('#{tid} .hk-mt',{{clipPath:'inset(100% -5% -10% -5%)',filter:'blur(6px)'}},{{clipPath:'inset(0% -5% -10% -5%)',filter:'blur(0px)',duration:.55,ease:'expo.out',immediateRender:false}},0.1);")
    ctx.tw(f"tl.to('#{tid}',{{opacity:0,filter:'blur(10px)',duration:.25,ease:'power1.in'}},{ctx.q(hook_end - .25)});")
    return True


HOOK_STYLES = {'cover': hook_cover, 'mixed': hook_mixed, 'masthead': hook_masthead}


# ---------------- GRAPHICS (one effect module per type) ----------------
def default_text(g):
    return g.get('text') or ' '.join(g.get('words', [])) or g.get('big') or g.get('caption') or g.get('title') or g.get('src') or ''


def build_graphics(ctx, clip):
    used, mods = [], {}
    for g in clip.get('graphics', []):
        T = g.get('type')
        if T not in mods:
            mods[T] = load_effect(T) if T else None
        mod = mods[T]
        if mod is None or not hasattr(mod, 'build'):   # a graphic nothing draws would silently never show
            have = sorted(d for d in os.listdir(EFFECTS) if os.path.exists(os.path.join(EFFECTS, d, 'effect.py')))
            ctx.fail(f'graphic type {T!r} on {g.get("on")!r} has no effect (effects/{T}/effect.py); known: {", ".join(have)}')
        if not g.get('on'):
            ctx.fail(f'graphic {T!r} has no "on" phrase')
        ctx.at(g['on'])
        ctx.beat(T, text=default_text(g), g=g)
        mod.build(g, ctx)
        if T not in used:
            used.append(T)
    ctx.beat_close()
    ctx._mods = mods
    return used


def guard_parallel(ctx):
    for _k, st in ctx.parallel.items():
        if len(st) > 1 and len({(n_, s_) for _, n_, s_ in st}) > 1:
            ctx.fail('parallel behind words render differently: ' + ', '.join(f'{w!r} {n_} line(s) at {s_}px' for w, n_, s_ in st))


# ---------------- CAPTIONS (paused inside busy windows) ----------------
def build_captions(ctx):
    cfg = ctx._caption_cfg()
    if cfg.get('style') == 'none':
        return 0
    style, size, top = cfg.get('style', 'pill'), int(cfg.get('size', 58)), int(cfg.get('top', 1250))
    left, fill = cfg.get('align') == 'left', bool(cfg.get('fill'))
    cues = ctx.caption_chunks(ctx.capwords)
    for ci, c in enumerate(cues):
        a = c[0]['start']
        b = cues[ci + 1][0]['start'] if ci + 1 < len(cues) and cues[ci + 1][0]['start'] - c[-1]['end'] < .5 else c[-1]['end'] + .25
        inside = [x1 for x0, x1 in ctx.busy if x0 - .05 <= a < x1]
        if inside:   # a cue that starts under a serif/hook still shows once it clears, if enough is left to read
            if b - max(inside) < .3:
                continue
            a = max(inside) + .02
        b = min(b, ctx.DUR)
        for x0, x1 in ctx.busy:
            if a < x0 < b:
                b = x0
        spans = ''.join(f'<span class="w" id="c{ci}w{k}">{ctx.esc(ctx.disp(w["text"]))}</span>' for k, w in enumerate(c))
        ctop = top   # a low face (centred selfie) pushes this cue down, never off the safe zone
        ch = int(size * 1.35)
        if style == 'box':   # a white box grows a line for every ~760 px of text, plus its padding
            ch = int((1 + int(len(' '.join(ctx.disp(w['text']) for w in c)) * size * .5 / 760)) * size * 1.22 + size * .5)
        fx0, fx1 = (70, 400) if left else (160, 920)
        while ctop + ch < 1470 and ctx.face_hit(a, b, fx0, ctop, fx1, ctop + ch) > .01:
            ctop += 10
        if ctx.face_hit(a, b, fx0, ctop, fx1, ctop + ch) > .01:
            ctop = top
        pos = 'left:70px;width:330px;' if left else 'left:60px;right:60px;'
        light = ''
        if cfg.get('adaptive'):   # light type on a plain bright wall reads as a smudge: those cues switch to ink
            lum, busy = ctx.bg_luma(a, b, fx0, ctop, fx1, ctop + ch)
            light = ' on-light' if lum > .55 and busy < .12 else ''
        cid = ctx.clip(ctx.top, a, b, f'<div class="cap{light}">{spans}</div>',
                       f'position:absolute;{pos}top:{ctop}px;font-size:{size}px;')
        ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:14,scale:.96}},{{opacity:1,y:0,scale:1,duration:.16,ease:'power3.out',immediateRender:false}},{ctx.q(a)});")
        for k, w in enumerate(c):
            ctx.tw(f"tl.set('#c{ci}w{k}',{{className:'w on'}},{ctx.q(max(a, w['start'] - .03))});")
            if k + 1 < len(c) and not fill:   # fill: spoken words stay lit, the rest of the cue waits dimmed
                ctx.tw(f"tl.set('#c{ci}w{k}',{{className:'w'}},{ctx.q(max(a, c[k + 1]['start'] - .03))});")
    return len(cues)


# ---------------- name tags (first close shot per speaker, after the hook) ----------------
def build_lower_thirds(ctx):
    seen = set()
    for s in ctx.seg:
        t0 = s['frame'] / F
        if s['speaker'] in seen or s.get('face', s['zoom'] * .054) < .097 or t0 < 2.0:
            continue
        sp = ctx.speakers.get(s['speaker'])
        if not sp or not sp.get('name'):
            seen.add(s['speaker'])
            continue
        seen.add(s['speaker'])
        name, role, side = sp['name'], sp.get('role', ''), sp.get('side', 'left')
        e = min(t0 + 3.2, ctx.DUR - .2)
        if any(x0 < e and t0 < x1 for x0, x1 in ctx.lowbusy):
            continue
        pos = 'left:60px;' if side == 'left' else 'right:110px;text-align:right;'   # right edge 970 clears the button rail
        ctx.beat('lt', text=f'{name}, {role}' if role else name, g={'side': side, 'name': name})
        cid = ctx.clip(ctx.top, t0 + .15, e, f'<div class="lt {side}"><div class="ltn">{ctx.esc(name)}</div>'
                       + (f'<div class="ltr">{ctx.esc(role)}</div>' if role else '') + '</div>', f'position:absolute;top:1090px;{pos}')
        ctx.tw(f"tl.fromTo('#{cid}',{{opacity:0,x:{-30 if side == 'left' else 30}}},{{opacity:1,x:0,duration:.35,ease:'power3.out',immediateRender:false}},{ctx.q(t0 + .15)});")
        ctx.tw(f"tl.to('#{cid}',{{opacity:0,duration:.25}},{ctx.q(e - .25)});")
    ctx.beat_close()


# ---------------- eyebrow (hides while the top band is used) ----------------
def build_eyebrow(ctx):
    brand = ctx.profile.get('brand', {})
    text = ctx.clipspec.get('eyebrow', ctx.project.get('eyebrow', brand.get('eyebrow')))
    logo = ctx.project.get('eyebrow_logo') or brand.get('logo')
    if not text and not logo:
        return ''
    img = ''
    if logo:
        url = ctx.asset(logo, required=False)
        if url:
            img = f'<img src="{url}">'
        else:
            ctx.warn(f'eyebrow logo not found: {logo}')
    merged = []
    for x0, x1 in sorted(ctx.topbusy):
        if merged and x0 <= merged[-1][1] + .3:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    for x0, x1 in merged:
        ctx.tw(f"tl.to('#eyebrow',{{opacity:0,duration:.15}},{ctx.q(max(0, x0 - .15))});")
        ctx.tw(f"tl.to('#eyebrow',{{opacity:1,duration:.2}},{ctx.q(x1 + .05)});")
    return f'<div id="eyebrow">{img}<span>{ctx.esc(text or "")}</span></div>'


# ---------------- shot punches ----------------
def build_punches(ctx):
    kind, amt = ctx.look.get('punch', 'scale'), float(ctx.look.get('cut_punch', 1.05))
    if kind == 'none':
        return
    if kind == 'push':   # slow push-in across every shot
        for s in ctx.seg:
            t = s['frame'] / F
            ctx.tw(f"tl.fromTo('#stage',{{scale:1}},{{scale:{amt},duration:{s['frames'] / F:.3f},ease:'none',immediateRender:false}},{t:.3f});")
        return
    for s in ctx.seg[1:]:
        t = s['frame'] / F - .002
        ctx.tw(f"tl.fromTo('#stage',{{scale:{amt}}},{{scale:1,duration:.28,ease:'power2.out',immediateRender:false}},{t:.3f});")


# ---------------- audio lanes ----------------
def build_audio(ctx):
    sfx_dir = os.path.join(REPO, 'assets', 'sfx')
    sfx_len = {}
    if os.path.isdir(sfx_dir):
        for f in os.listdir(sfx_dir):
            if f.endswith('.mp3'):
                try:
                    sfx_len[f[:-4]] = ffprobe_duration(os.path.join(sfx_dir, f), stream=False)
                except ValueError:
                    pass
    if not ctx.profile.get('sfx', True) or ctx.project.get('sfx') is False:
        ctx.sfxs = []
    missing = sorted({e[0] for e in ctx.sfxs if e[0] not in sfx_len})
    if missing:
        ctx.warn(f'sound(s) not downloaded, left silent: {", ".join(missing)} (run python3 engine/fetch_sfx.py)')
    audio, lanes = [], []
    for k, (name, t, vol, *cap) in enumerate(sorted([e for e in ctx.sfxs if e[0] in sfx_len], key=lambda x: x[1])):
        t = max(0, t)
        d = min(sfx_len[name], ctx.DUR - t, *cap)
        if d <= .05:
            continue
        lane = next((i for i, e in enumerate(lanes) if e <= t), None)
        if lane is None:
            lanes.append(0)
            lane = len(lanes) - 1
        lanes[lane] = t + d
        dst = os.path.join(ctx.D, 'assets', 'sfx', f'{name}.mp3')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src = os.path.join(sfx_dir, f'{name}.mp3')
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            import shutil
            shutil.copy2(src, dst)
        audio.append(f'<audio id="sfx{k}" src="assets/sfx/{name}.mp3" data-start="{t:.3f}" data-duration="{d:.3f}" '
                     f'data-track-index="{70 + lane}" data-volume="{vol:.3f}"></audio>')
    return audio, sfx_len


# ---------------- CSS ----------------
BRAND_COLORS = {'text': '--c-text', 'accent': '--c-accent', 'accent2': '--c-accent2', 'ink': '--c-ink', 'card': '--c-card'}
BRAND_FONTS = {'display': '--f-display', 'serif': '--f-serif', 'body': '--f-body', 'script': '--f-script', 'mono': '--f-mono'}


def css_vars(ctx):
    v = dict(ctx.look.get('vars', {}))
    brand = ctx.profile.get('brand', {})
    for k, var in BRAND_COLORS.items():
        if brand.get('colors', {}).get(k):
            v[var] = brand['colors'][k]
    for k, var in BRAND_FONTS.items():
        if brand.get('fonts', {}).get(k):
            v[var] = "'" + brand['fonts'][k].strip("'\"") + "'"
    v.update(brand.get('vars', {}))
    v.update(ctx.project.get('vars', {}))
    return ':root{' + ';'.join(f'{k}:{val}' for k, val in v.items()) + '}'


def font_faces(ctx):
    man = json.load(open(os.path.join(REPO, 'assets', 'fonts', 'fonts.json')))['fonts']
    extra = ctx.profile.get('brand', {}).get('font_files', [])
    out = []
    for f in man + extra:
        src = f['file'] if os.path.isabs(os.path.expanduser(f['file'])) else os.path.join(REPO, 'assets', 'fonts', f['file'])
        src = os.path.expanduser(src)
        if not os.path.exists(src):
            ctx.warn(f'font file missing: {src}')
            continue
        dst = os.path.join(ctx.D, 'assets', 'fonts', os.path.basename(src))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            import shutil
            shutil.copy2(src, dst)
        out.append(f"@font-face{{font-family:'{f['family']}';src:url('assets/fonts/{os.path.basename(src)}') format('woff2');"
                   f"font-weight:{f.get('weight', '400')};font-style:{f.get('style', 'normal')};"
                   + (f"font-stretch:{f['stretch']};" if f.get('stretch') else '') + "font-display:block}")
    return '\n'.join(out)


def page_css(ctx, used):
    ov = ctx.look.get('overlays', {})
    vig = float(ov.get('vignette', 0) or 0)
    parts = [font_faces(ctx), css_vars(ctx), open(os.path.join(REPO, 'engine', 'core.css')).read(),
             f".g{{filter:{ctx.look.get('grade', 'none')}}}",
             f"#vig{{background:radial-gradient(120% 70% at 50% 42%,transparent 55%,color-mix(in srgb,var(--c-shadow) {vig * 100:.0f}%,transparent) 100%)}}"]
    tint = ov.get('tint')
    if tint:   # a colour wash over the footage: {"color", "opacity", "blend"}
        parts.append(f"#tint{{background:{tint.get('color', '#000')};opacity:{float(tint.get('opacity', .1))};mix-blend-mode:{tint.get('blend', 'soft-light')}}}")
    g = ov.get('grad')
    if isinstance(g, (int, float)) and not isinstance(g, bool):   # a number sets how dark the bottom of the frame gets
        parts.append(f"#grad{{background:linear-gradient(180deg,color-mix(in srgb,var(--c-shadow) {g * 44:.0f}%,transparent) 0%,transparent 18%,"
                     f"transparent 54%,color-mix(in srgb,var(--c-shadow) {g * 100:.0f}%,transparent) 100%)}}")
    for T in used:
        p = os.path.join(EFFECTS, T, 'style.css')
        if os.path.exists(p):
            parts.append(f'/* effects/{T} */\n' + open(p).read())
    if ctx.look.get('css'):   # look-level restyling of effects, applied last
        css = ctx.look['css']
        parts.append('/* look */\n' + ('\n'.join(css) if isinstance(css, list) else css))
    # captions read the look's style as a class on the .cap node
    return '\n'.join(parts)


SAFE_GUIDE = ('<div style="position:absolute;inset:0;z-index:99;pointer-events:none">'
              '<div style="position:absolute;left:0;right:0;top:0;height:220px;background:rgba(255,0,0,.28)"></div>'
              '<div style="position:absolute;left:0;right:0;bottom:0;height:450px;background:rgba(255,0,0,.28)"></div>'
              '<div style="position:absolute;right:0;top:1155px;width:100px;bottom:450px;background:rgba(255,0,0,.28)"></div></div>')


def page_html(ctx, css, audio, eyebrow_html):
    nl = '\n'
    D = ctx.DUR
    ov = ctx.look.get('overlays', {})
    fx = (('<div id="warm" class="fx"></div>' if ov.get('warm') else '') + ('<div id="tint" class="fx"></div>' if ov.get('tint') else '')
          + ('<div id="vig" class="fx"></div>' if ov.get('vignette') else '')
          + ('<div id="grad" class="fx"></div>' if ov.get('grad') else ''))
    cfg = ctx._caption_cfg()
    style = cfg.get('style', 'pill')
    if cfg.get('font') in ('serif', 'script', 'title'):   # body and display are the styles' own fonts
        style += f' f-{cfg["font"]}'
    if cfg.get('align') == 'left':
        style += ' left'
    top = [x.replace('<div class="cap">', f'<div class="cap {style}">').replace('<div class="cap on-light">', f'<div class="cap {style} on-light">')
           for x in ctx.top]
    cut_html = (f'<div id="cutwrap"><video id="cut" class="full g" src="assets/subject.webm" muted playsinline data-start="0" data-media-start="0" '
                f'data-duration="{D:.3f}" data-track-index="1"></video></div>') if ctx.has_cut else ''
    return f'''<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<style>{css}</style>
<script src="{GSAP}"></script>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{D:.3f}" data-width="1080" data-height="1920">
  <audio id="bga" src="assets/aroll.mp4" data-start="0" data-media-start="0" data-duration="{D:.3f}" data-track-index="2" data-volume="1"></audio>
{nl.join(audio)}
  <div id="stage">
    <video id="bgv" class="full g" src="assets/aroll.mp4" muted playsinline data-start="0" data-media-start="0" data-duration="{D:.3f}" data-track-index="0"></video>
{nl.join(ctx.wall)}
{cut_html}
  </div>
  {fx}
{nl.join(ctx.front)}
{nl.join(top)}
  {eyebrow_html}
{SAFE_GUIDE if ctx.safe else ''}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{nl.join(x for x in ctx.tws if x)}
tl.set({{}}, {{}}, {D:.3f});
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
</script>
</body>
</html>
'''


# ---------------- storyboard plan (plain English, tied to the spoken words; readable before any render) ----------------
CORE_NAMES = {'hook': 'Hook card', 'lt': 'Name tag'}


def shot_name(ctx, t):
    who = ctx.speaker_name(ctx.speaker_at(t)).split()[0]
    f = ctx.face_scale_at(t)
    return f'Close on {who}' if f >= .097 else (f'Medium on {who}' if f >= .07 else 'Wide shot')


def plan_text(ctx, p):
    g, k, t0, t1 = p['g'], p['kind'], p['t0'], p['t1']
    hold = t1 - t0
    if k == 'hook':
        return f'A cover card holds the first {hold:.1f} s: "{g["small"]}" small, then "{g["big"]}" big. It clears before the first graphic.'
    if k == 'lt':
        return f'The name tag for {g["name"]} slides in on the {g["side"]} and holds {hold:.1f} s on the first close shot.'
    mod = getattr(ctx, '_mods', {}).get(k)
    if mod is not None and hasattr(mod, 'describe'):
        try:
            return mod.describe(g, {**p, 'hold': hold})
        except (KeyError, TypeError, IndexError):
            pass
    name = (getattr(mod, 'META', {}) or {}).get('name', k) if mod else k
    return f'On “{g.get("on", "")}” a {name.lower()} shows for {hold:.1f} s.'


def write_plan(ctx, sfx_len):
    out = []
    for i, p in enumerate(sorted(ctx.plan, key=lambda x: x['t0'])):
        snd = [x for x in p['sounds'] if x in sfx_len]
        mod = getattr(ctx, '_mods', {}).get(p['kind'])
        kind_name = CORE_NAMES.get(p['kind']) or ((getattr(mod, 'META', {}) or {}).get('name') if mod else None) or p['kind']
        out.append({'id': f'b{i + 1:02d}', 't0': p['t0'], 't1': p['t1'], 'kind': p['kind'], 'kindName': kind_name,
                    'shot': shot_name(ctx, p['t0'] + .1), 'text': p['text'], 'said': ctx.said(p['t0'], p['t1']), 'plan': plan_text(ctx, p),
                    'sounds': [f'{x} x{snd.count(x)}' if snd.count(x) > 1 else x for x in dict.fromkeys(snd)]})
    json.dump({'slug': ctx.slug, 'dur': round(ctx.DUR, 2), 'look': ctx.look.get('id'), 'beats': out},
              open(os.path.join(ctx.D, 'plan.json'), 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main(sys.argv[1:])
