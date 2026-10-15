"""igfx: shared helpers for the object effects added in October 2026 (stamp, calendar-flip, flip-clock, odometer, slot-number,
letter-drop, ticket-dispenser, signup-sheet, app-tray, receipt-print, keycap-rain, contact-sheet, iris-card, film-strip,
word-build, score-pins, retention-drop, script-write, icon-split, chapter-title, speaker-tags).

Not an effect itself (no effect.py), so build.py and the guide skip this folder. Effects load it with _lib() (see any of
the effects above). Nothing here touches files or paths except through ctx.

Placement rules every helper keeps: text and key UI inside x 90-950, y 240-1470; nothing in the right rail (x > 950 below
y 1155); never on a face. Faces are grown by MARGIN px before any test, because the layout audit re-detects faces on the
graded frame and lands up to ~20 px off.
"""
import math, re

SAFE = (90, 240, 950, 1470)
RAIL = (950, 1155)
MARGIN = 18
GLYPH = .56


# ---------------- timing ----------------
PINNED = {'chapter-title', 'speaker-tags', 'film-strip', 'progress-dots'}   # long-running layers other graphics share the screen with


def window(ctx, g, hold, last=None, min_after=.7):
    """(a, end): lands on its phrase, clears before the next graphic, the until phrase, or the end of the clip.
    Pinned layers (a title, speaker tags, the film look) do not end a window."""
    a = ctx.at(g['on'])[0]
    last = a if last is None else last
    end = min(ctx.DUR - .05, last + float(g.get('hold', hold)))
    if g.get('until'):
        end = min(end, ctx.at(g['until'], a)[0] - .05)
    later = [t for h in ctx.graphics if h is not g and h.get('on') and h.get('type') not in PINNED for t in [ctx.at(h['on'])[0]] if t > a + .05]
    if later:
        end = min(end, min(later) - .15)
    if end - last < min_after:
        ctx.fail(f'{g["type"]} on {g["on"]!r} gets {end - last:.2f} s after its last beat before the next graphic or the end; '
                 'move it or the graphic after it')
    return a, end


def times(ctx, g, items, step, key='on'):
    """one time per item: its own "on" phrase (in order, each after the previous one) or an even step after the graphic's word."""
    a = ctx.at(g['on'])[0]
    out, after = [], a - .2
    for it in items:
        if isinstance(it, dict) and it.get(key):
            t = ctx.at(it[key], after)[0]
        else:
            t = out[-1] + step if out else a
        out.append(max(t, a))
        after = t
    return out


def need(ctx, g, *keys):
    for k in keys:
        if g.get(k) in (None, '', []):
            ctx.fail(f'{g["type"]} on {g["on"]!r} needs "{k}"')


def echo_guard(ctx, g, text, a, b, what):
    """refuse text that only repeats what is said within 2 s: an effect must add information."""
    nw = re.findall(r'[a-z0-9]+', str(text).lower())
    said = {w for x in ctx.words if a - 2 <= x['start'] <= b + 2 for w in re.findall(r'[a-z0-9]+', x['text'].lower())}
    return bool(nw) and all(w in said for w in nw)


# ---------------- text fitting ----------------
def wrap(text, width, fs, k=GLYPH):
    lines, cur = [], ''
    for w in str(text).split():
        t = f'{cur} {w}'.strip()
        if cur and len(t) * fs * k > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def fit(ctx, what, texts, width, fmax, fmin=30, max_lines=3, k=GLYPH):
    """one font size for every text (parallel items share a size), the largest that fits width in max_lines."""
    texts = [str(t) for t in texts if t]
    if not texts:
        return int(fmax)
    for fs in range(int(fmax), int(fmin) - 1, -2):
        if all(len(wrap(t, width, fs, k)) <= max_lines and max(len(w) for w in t.split()) * fs * k <= width for t in texts):
            return fs
    ctx.fail(f'{what}: {max(texts, key=len)!r} does not fit {max_lines} line(s) at {fmin}px; shorten it')


# ---------------- faces ----------------
def faces(ctx, t0, t1, n=6):
    out = []
    for k in range(n):
        out += ctx.faces_at(min(ctx.DUR - .06, t0 + (t1 - t0) * k / max(1, n - 1)))
    return out


def face_share(box, fz, margin=MARGIN):
    worst = 0.0
    for fx0, fy0, fx1, fy1 in fz:
        fx0, fy0, fx1, fy1 = fx0 - margin, fy0 - margin, fx1 + margin, fy1 + margin
        ix, iy = max(0, min(box[2], fx1) - max(box[0], fx0)), max(0, min(box[3], fy1) - max(box[1], fy0))
        worst = max(worst, ix * iy / max(1, (fx1 - fx0) * (fy1 - fy0)))
    return worst


def speaker_box(ctx, t0, t1, n=5):
    """median padded face box of whoever talks across [t0, t1], or None."""
    bs = [f for f in (ctx.speaker_face(min(ctx.DUR - .06, t0 + (t1 - t0) * k / max(1, n - 1))) for k in range(n)) if f]
    if not bs:
        return None
    return [sorted(b[i] for b in bs)[len(bs) // 2] for i in range(4)]


def unsafe(box):
    x0, y0, x1, y1 = box
    return x0 < SAFE[0] - .5 or x1 > SAFE[2] + .5 or y0 < SAFE[1] - .5 or y1 > SAFE[3] + .5 or (x1 > RAIL[0] and y1 > RAIL[1])


# ---------------- boxes other new effects already hold ----------------
def reserve(ctx, box, t0, t1):
    """record a box this effect occupies, so later effects from this family place around it."""
    if not hasattr(ctx, '_igboxes'):
        ctx._igboxes = []
    ctx._igboxes.append((t0, t1, tuple(box)))


def taken(ctx, box, t0, t1, pad=16):
    """worst share of box covered by a box another effect reserved over an overlapping time."""
    worst = 0.0
    for a, b, r in getattr(ctx, '_igboxes', []):
        if a < t1 and t0 < b:
            ix = max(0, min(box[2], r[2] + pad) - max(box[0], r[0] - pad))
            iy = max(0, min(box[3], r[3] + pad) - max(box[1], r[1] - pad))
            worst = max(worst, ix * iy / max(1, (box[2] - box[0]) * (box[3] - box[1])))
    return worst


# ---------------- placement ----------------
def grid(w, h, xs=None, step=30):
    xs = xs or (90, (1080 - w) // 2, 950 - w)
    ys = list(range(SAFE[1], SAFE[3] + 1 - int(h), step)) + [SAFE[3] - int(h)]
    return [(int(x), int(y)) for y in ys for x in xs]


def spot(ctx, w, h, t0, t1, cands, near=None, pause=False, fz=None):
    """(cost, x, y, face): the candidate that clears faces first, then the caption band, then hides the least of the speakers."""
    cap = int(ctx._caption_cfg().get('top', 1250))
    fz = faces(ctx, t0, t1) if fz is None else fz
    best = None
    for x, y in cands:
        x, y = int(max(SAFE[0], min(x, SAFE[2] - w))), int(max(SAFE[1], min(y, SAFE[3] - h)))
        if x + w > RAIL[0] and y + h > RAIL[1]:
            x = int(RAIL[0] - w)
            if x < SAFE[0]:
                continue
        face = face_share((x, y, x + w, y + h), fz)
        busy = taken(ctx, (x, y, x + w, y + h), t0, t1)
        c = (50 if face > .005 else 0) + 10 * face + (20 if busy > .01 else 0) + .3 * max(ctx.alpha_cover(t0 + (t1 - t0) * k / 3, x, y, x + w, y + h) for k in range(4))
        if not pause and y + h > cap - 16:
            c += .5
        if near:
            c += .3 * math.hypot(x + w / 2 - near[0], y + h / 2 - near[1]) / 1000
        if best is None or c < best[0] - .005:
            best = (c, x, y, face)
    return best


def fitspot(ctx, what, w, h, t0, t1, cands=None, near=None, pause=False, scales=(1.0, .86, .74, .64)):
    """(x, y, scale): full size where a spot clears the faces, else the card shrinks until one does. Fails rather than cover a face."""
    fz = faces(ctx, t0, t1)
    tries = []
    for sc in scales:
        ws, hs = int(w * sc), int(h * sc)
        b = spot(ctx, ws, hs, t0, t1, (cands or grid)(ws, hs), near, pause, fz)
        if b is None:
            continue
        busy = taken(ctx, (b[1], b[2], b[1] + ws, b[2] + hs), t0, t1)
        tries.append((b[3] + busy, -sc, b[1], b[2]))
        if b[3] <= .005 and busy <= .01:
            break
    if not tries:
        ctx.fail(f'{what}: a {w}x{h} box does not fit the safe zone; make it smaller')
    face, sc, x, y = min(tries)
    if face > .005:
        ctx.fail(f'{what} would cover {face:.0%} of a face (or another graphic) even at {-sc:.0%} size; pick another moment')
    if -sc < 1:
        ctx.note(f'{what} shrunk to {-sc:.0%} to clear a face')
    return x, y, -sc


def above_head(ctx, what, w, h, t0, t1, gap=12, scales=(1.0, .86, .74), fallback=True):
    """(x, y, scale): an object that sits on top of the speaker's head (a calendar, a ticket, a clipboard), centred over the
    face. Shrinks to fit the band above the head; falls back to the clearest spot anywhere when the band is too thin."""
    fb = speaker_box(ctx, t0, t1)
    fz = faces(ctx, t0, t1)
    if fb:
        cx = (fb[0] + fb[2]) / 2
        ftop = min(f[1] for f in fz) if fz else fb[1]
        for sc in scales:
            ws, hs = w * sc, h * sc
            y = ftop - MARGIN - gap - hs
            x = max(SAFE[0], min(SAFE[2] - ws, cx - ws / 2))
            if y < SAFE[1]:
                continue
            box = (x, y, x + ws, y + hs)
            if face_share(box, fz) <= .002 and not unsafe(box) and taken(ctx, box, t0, t1) <= .01:
                return int(x), int(y), sc
    if not fallback:
        return None
    ctx.note(f'{what}: no room above the head, placed in the clearest spot instead')
    return fitspot(ctx, what, w, h, t0, t1, near=((fb[0] + fb[2]) / 2, fb[1]) if fb else None)


def drop_from(y, h, sc, cap=260):
    """how far above its spot an object starts its drop: from the top of the frame when it sits high, never more than cap
    (a long fall from the top would cross the captions and faces when the object sits low)."""
    return int(min(y / sc + h + 40, cap / sc))


def zclip(ctx, layer, sc, a, b, inner, style, cls=''):
    """ctx.clip with the content zoomed when placement had to shrink it."""
    return ctx.clip(layer, a, b, inner if sc == 1 else f'<div class="rk-zoom" style="zoom:{sc:.3f}">{inner}</div>', style, cls)


def claim(ctx, x, y, w, h, t0, t1, pause=False):
    """captions pause when the effect carries its own text or reaches the caption band; name tags and eyebrow make room."""
    cap = int(ctx._caption_cfg().get('top', 1250))
    reserve(ctx, (x, y, x + w, y + h), t0, t1)
    if pause or y + h > cap - 16:
        ctx.busy.append((t0, t1))
    if y + h > 1060:
        ctx.lowbusy.append((t0, t1))
    if y < 400:
        ctx.topbusy.append((t0, t1))


# ---------------- big words on the wall (behind the head) ----------------
def wall_band(ctx, what, text, t0, t1, fmax, fmin, k=.62, lh=.9):
    """(layer, size, top): one line of big type behind the head, sized so no letter hides behind a speaker (the audit fails
    any line more than 8% hidden). Moves in front, above the faces, when the heads cover every band."""
    n = max(4, len(text))
    fz = faces(ctx, t0, t1)
    ftop = min([f[1] for f in fz] or [800])
    ht = ctx.head_top(t0 + .1) if ctx.has_cut else None
    for size in range(int(min(fmax, 900 / (n * k))), int(fmin) - 1, -6):
        w = n * k * size
        x0 = 540 - w / 2
        h = size * lh
        for top in range(SAFE[1] + 6, int(min(ftop, SAFE[3]) - h * .6), 10):
            box = (x0, top + size * .14, x0 + w, top + h)
            cov = max(ctx.alpha_cover(t0 + (t1 - t0) * j / 3, *box) for j in range(4)) if ctx.has_cut else 0
            if cov <= .025 and face_share(box, fz, 0) <= .002 and taken(ctx, box, t0, t1) <= .01:
                return (ctx.wall if ctx.has_cut else ctx.front), size, top
    # in front, in the band above the faces, else any band clear of them (under the chin in a tight close-up)
    for size in range(int(min(fmax, 900 / (n * k))), int(fmin) - 1, -6):
        h = size * lh
        w = n * k * size
        for top in [SAFE[1] + 6] + list(range(SAFE[1] + 6, int(SAFE[3] - h), 10)):
            box = (540 - w / 2, top, 540 + w / 2, top + h)
            if face_share(box, fz) <= .002 and taken(ctx, box, t0, t1) <= .01:
                ctx.note(f'{what} moved in front, clear of the faces (y {top})')
                return ctx.front, size, top
    ctx.fail(f'{what}: no band clear of the faces for {text!r}; shorten it or pick another moment')


# ---------------- small svg pieces ----------------
def icon_svg(name, size=40, stroke='currentColor'):
    """a few plain line icons drawn here (no third-party icon sets)."""
    p = {
        'comment': '<path d="M6 8h28a3 3 0 0 1 3 3v15a3 3 0 0 1-3 3H17l-8 6v-6H6a3 3 0 0 1-3-3V11a3 3 0 0 1 3-3z"/>',
        'heart': '<path d="M20 34s-13-7.6-13-17a7 7 0 0 1 13-3.6A7 7 0 0 1 33 17c0 9.4-13 17-13 17z"/>',
        'eye': '<path d="M3 20s6-11 17-11 17 11 17 11-6 11-17 11S3 20 3 20z"/><circle cx="20" cy="20" r="5"/>',
        'share': '<path d="M5 20 35 6 26 34l-6-11z"/><path d="M20 23 35 6"/>',
        'cross': '<path d="M9 9l22 22M31 9 9 31"/>',
        'check': '<path d="M7 21l9 9L33 10"/>',
        'clock': '<circle cx="20" cy="20" r="15"/><path d="M20 11v9l6 4"/>',
    }.get(name, '')
    return (f'<svg viewBox="0 0 40 40" width="{size}" height="{size}" fill="none" stroke="{stroke}" stroke-width="3.4" '
            f'stroke-linecap="round" stroke-linejoin="round">{p}</svg>')


def wall_ink(ctx, t0, t1, box):
    """text colour for words on the wall: dark ink on a plain bright wall, the look's light text everywhere else
    (light text on a bright wall passed the audit and read as a smudge)."""
    if ctx.has_cut and max(ctx.alpha_cover(t0 + (t1 - t0) * k / 2, *box) for k in range(3)) > .1:
        return 'var(--c-text)', 'light'   # the words sit over the speaker (a front fallback): light type with its shadow
    lum, busy = ctx.bg_luma(t0, t1, *box)
    return ('var(--c-ink)', 'dark') if lum > .5 and busy < .14 else ('var(--c-text)', 'light')


# ---------------- full-frame hosts (split screen, face bubble) ----------------
def hosts():
    """the hosts module (_lib/hosts.py): split and bubble layouts other effects can run inside."""
    import importlib.util, os, sys
    if 'rkhosts' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hosts.py')
        spec = importlib.util.spec_from_file_location('rkhosts', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['rkhosts'] = mod
    return sys.modules['rkhosts']
