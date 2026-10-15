"""Orbit carousel: 5 to 8 phone-sized reel tiles spin around the speaker's head, passing BEHIND the head on the far side
and IN FRONT of the chest on the near side.

Each tile exists twice: a wall copy (under the speaker cutout) and a front copy (over it). The front copy shows on the
near half of the ring and the wall copy on the far half; they swap at the ring's left and right extremes, where both sit
beside the face in the same spot, so the swap is invisible. Every pose is computed per frame and baked into GSAP keyframes,
so the frame-stepping renderer is deterministic.

Geometry (tied to the face box, followed frame by frame, never across a cut): the far arc runs at the eye line, so far
tiles cross directly behind the face and the cutout hides them; the near arc runs just under the chin, so near tiles sweep
across the chest and arms; the ring is as wide as the frame allows, so side tiles pass beside the face at face height. A
close-up does not shrink or flatten the ring. Front copies never cover a face: a near tile passing under the chin eases
into the band between the padded chin and the bottom of the safe zone. Captions pause while the ring spins.

Audit: wall copies carry no text and are marked data-pass-behind (an image tile passing behind the head is the effect,
exception approved 10/14); both copies share one data-fx-group, so they are not judged as overlapping each other.
"""
import importlib.util, math, os, sys

META = {
    'id': 'orbit-carousel', 'name': 'Orbit carousel', 'category': 'carousel',
    'when': 'The speaker names a set of things (reels, results, places, offers) and the set itself is the point: '
            '5 to 8 phone tiles orbit the head while the line lands.',
    'never': 'Never tiles the speaker does not name or imply. Never fewer than 5 tiles (it reads as a broken ring). '
             'Never on a line where the face turns away (nothing to orbit).',
    'params': {'on': 'phrase that starts the spin',
               'videos': 'list of 5 to 8 mp4 clips (9:16, muted) that play inside the phone tiles; the strongest look',
               'tiles': '[{"title", "src"?, "video"?, "sub"?, "kicker"?}] 5 to 8; video or src fill the phone, else a word tile is drawn. '
                        'With "videos", titles here are optional and pair by index',
               'hold': 'seconds on screen, default 3.6', 'speed': 'cruise spin in degrees per second, default 105',
               'size': 'tile size multiplier, default 1 (video/image tiles: 1.42 face heights; word tiles: 320 px)',
               'width': 'ring width multiplier for video/image tiles, default 1 (2.45 face widths, at most 1.05 x the frame half-width)',
               'labels': 'true to print titles on the near (front) image or video tiles; far tiles never carry text',
               'until': 'optional phrase to clear before', 'sfx': 'optional sound name for the spin-up (e.g. swipe)'},
    'sfx': ['swipe'], 'source': 'ours', 'credit': 'Idea inspired by Marc (tenfold) orbit; code is ours.', 'license': 'MIT',
}


def _lib():
    if 'rk3d' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'rk3d.py')
        spec = importlib.util.spec_from_file_location('rk3d', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['rk3d'] = mod
    return sys.modules['rk3d']


S_BACK = .6      # tile scale at the far side of the ring (word-tile mode)
# measured on the reference orbit against its raw face box (see the effect report): tile heights in face heights,
# arc heights in face heights from the face top, radius in face widths
MARC = {'near_h': 1.42, 'far_scale': .65, 'far_y': .5, 'radius_y': .72, 'radius_w': 2.45}
RING_W = 1.05   # horizontal radius on a close-up, in frame half-widths: 6+ tiles on screen (Nati's call 10/14)
E_IN, E_OUT = .8, .55
AR = 9 / 16      # phone-sized vertical reel tiles
TURN = 25        # degrees a tile turns toward the side it travels (narrows it beside the face, reads as 3D)


def _tiles(ctx, g, L):
    vids = g.get('videos') or []
    tiles = [dict(t) for t in (g.get('tiles') or [])]
    if vids:
        if tiles and len(tiles) != len(vids):
            ctx.fail(f'orbit-carousel on {g["on"]!r}: "tiles" and "videos" pair by index; give the same number of each')
        tiles = [dict(tiles[k] if tiles else {}, video=v) for k, v in enumerate(vids)]
        for k, t in enumerate(tiles):
            t.setdefault('title', os.path.splitext(os.path.basename(t['video']))[0])
    if not 5 <= len(tiles) <= 8:
        ctx.fail(f'orbit-carousel on {g["on"]!r} needs 5 to 8 tiles (or videos)')
    for t in tiles:
        if not (t.get('title') or t.get('src') or t.get('video')):
            ctx.fail(f'orbit-carousel on {g["on"]!r}: every tile needs a video, an image or a title')
        if not t.get('video') and not t.get('src') and not t.get('title'):
            ctx.fail(f'orbit-carousel on {g["on"]!r}: a word tile needs a "title"')
    return tiles


def build(g, ctx):
    L = _lib()
    tiles = _tiles(ctx, g, L)
    n = len(tiles)
    a, end = L.window(ctx, g, 3.6, min_after=1.8)
    if not ctx.has_cut:
        ctx.fail(f'orbit-carousel on {g["on"]!r} needs the speaker cutout (assets/subject.webm) to pass tiles behind the head')
    track = L.face_track(ctx, a, end)
    if track is None:
        ctx.fail(f'orbit-carousel on {g["on"]!r}: no face found between {a:.2f} and {end:.2f} s; nothing to orbit')
    T = L.frames(a, end)
    speed = float(g.get('speed', 105))
    boxes0 = [track(t) for t in T]
    fh = sorted(b[3] - b[1] for b in boxes0)[len(T) // 2]
    faces = [L.all_faces(ctx, t) for t in T]

    def theta_at(t):
        """total ring rotation in degrees: spins up fast on the way in, cruises, accelerates out."""
        u = t - a
        th = speed * u + 240 * L.out_cubic(u / E_IN)
        if t > end - E_OUT:
            th += 220 * L.in_cubic((t - (end - E_OUT)) / E_OUT)
        return th

    def k_at(t):
        """ring scale: grows out of the head, shrinks back into it on the way out."""
        if t < a + E_IN:
            return max(0.0, L.out_cubic((t - a) / (E_IN * .85)))
        if t > end - E_OUT:
            return max(0.0, 1 - L.in_cubic((t - (end - E_OUT)) / E_OUT))
        return 1.0

    # Two modes. Image or video tiles with no words (the reference look): sized by the FACE, on a ring wider than the frame,
    # free to run off its edges (audit exception for image-only orbit tiles, approved 10/14). Tiles that carry words: every
    # safe-zone rule still applies, so the ring stays inside it.
    show_lb = [not (t.get('src') or t.get('video')) or bool(g.get('labels')) for t in tiles]
    free = not any(show_lb)
    user = float(g.get('size', 1.0))
    # the raw face (the detector's box before the engine's hair and chin padding), the unit Marc's orbit is measured in
    rfh = fh / 1.48
    rfw = sorted(b[2] - b[0] for b in boxes0)[len(T) // 2] / 1.24
    if free:
        # proportions measured on the reference orbit (tenfold, 6.5 to 11 s) against its face box: near tiles 1.42 face
        # heights tall, far tiles 0.65 of that, far arc through the face centre, near arc 1.0 face height under the chin,
        # horizontal radius 2.45 face widths (wider than the frame on a close-up: side tiles run off its edges)
        H0 = MARC['near_h'] * rfh * user
        W0 = H0 * AR
        # Marc's 2.45 face widths puts half the ring off frame on a close-up; cap it near the frame width so 6+ tiles show
        R = min(MARC['radius_w'] * rfw, RING_W * 540) * float(g.get('width', 1.0))
    else:
        H0 = 320 * user
        W0 = H0 * AR
        R = (L.SAFE[2] - L.SAFE[0]) / 2 - W0 * .52 - 8   # as wide as the safe zone allows; the centre slides toward the frame centre
        NEAR = H0 * .52 + 34
    FAR = .45 * fh                                       # eye line: the far arc crosses directly behind the face
    sback = MARC['far_scale'] if free else S_BACK

    drop = 0.0   # extra px the near arc is lowered when a face pass would run too long

    def pose_row(fi):
        fb, t = boxes0[fi], T[fi]
        if free:   # Marc's bands, on this frame's raw face
            rh = (fb[3] - fb[1]) / 1.48
            rtop = fb[1] + .3 * rh
            y_far = rtop + MARC['far_y'] * rh                     # far arc through the face centre: behind the head
            y_near = y_far + 2 * MARC['radius_y'] * rh + drop     # near arc: tiles sweep across the chin and neck
        else:
            y_far, y_near = fb[1] + FAR, fb[3] + NEAR
        cx, cy, ry = (fb[0] + fb[2]) / 2, (y_far + y_near) / 2, (y_near - y_far) / 2
        if not free:
            span = R + W0 * .52 + 6
            cx = min(max(cx, L.SAFE[0] + span), L.SAFE[2] - span)
        k, th = k_at(t), theta_at(t)
        row = []
        for i in range(n):
            ang = math.radians(th + i * 360 / n)
            c, sn = math.cos(ang), math.sin(ang)
            s = L.lerp(sback, 1.0, (1 + c) / 2) * k
            x, y = cx + R * k * sn, cy + ry * k * c
            turn = math.radians(abs(sn) * TURN)
            w = W0 * s * (math.cos(turn) + .06) + 4                       # turned tiles are narrower on screen
            h = H0 * s * (1 + .5 * W0 * s * math.sin(turn) / 700) + 4     # and their near edge grows a little
            row.append({'x': x, 'y': y, 's': s, 'c': c, 'sin': sn, 'box': [x - w / 2, y - h / 2, x + w / 2, y + h / 2]})
        # a near tile passing under the chin eases into the band between the padded chin and the bottom of the safe zone,
        # shrinking only as much as that band needs: it never touches the face and never leaves the frame
        top, bot = fb[3] + 22, (L.SAFE[3] - 2 if not free else 1920 + H0)   # free tiles keep full size and may dip off the bottom
        for p in row:
            if free or p['c'] <= 0 or p['s'] < .05:   # free tiles sweep across the chin (quick passes, checked below)
                continue
            x0, y0, x1, y1 = p['box']
            ov = L.clamp((min(x1, fb[2] + 20) - max(x0, fb[0] - 20)) / max(1, (x1 - x0) * .25))
            if ov <= 0 or bot - top < 100:
                continue
            h = y1 - y0
            h2 = min(h, bot - top)
            y2 = min(max(p['y'], top + h2 / 2), bot - h2 / 2)
            f = L.lerp(1, h2 / h, ov)
            p['s'] *= f
            p['y'] = L.lerp(p['y'], y2, ov)
            w, h = (x1 - x0) * f, h * f
            p['box'] = [p['x'] - w / 2, p['y'] - h / 2, p['x'] + w / 2, p['y'] + h / 2]
        # anything still past the top or bottom of the safe zone moves the whole frame's ring back in
        vis = [p['box'] for p in row if p['s'] > .05]
        if vis and not free:
            over = max(b[3] for b in vis) - (L.SAFE[3] - 1)
            under = (L.SAFE[1] + 1) - min(b[1] for b in vis)
            sh = -over if over > 0 else (under if under > 0 else 0)
            for p in row:
                p['y'] += sh
                p['box'][1] += sh
                p['box'][3] += sh
        return row

    def passes(P):
        """face passes as the audit counts them: any front tile over a face (it sums a tile's card and video, so 2x the
        share, over 3%); returns (longest pass, shortest gap between passes) in seconds."""
        on = [any(p['c'] >= 0 and p['s'] > .05 and 2 * L.box_face_share(p['box'], faces[fi], margin=6) > .03 for p in row)
              for fi, row in enumerate(P)]
        runs, cur = [], None
        for fi, v in enumerate(on):
            if v and cur is None:
                cur = fi
            if not v and cur is not None:
                runs.append((cur, fi - 1))
                cur = None
        if cur is not None:
            runs.append((cur, len(on) - 1))
        longest = max([(b - a_ + 1) * L.DT for a_, b in runs] or [0])
        gap = min([(runs[k + 1][0] - runs[k][1] - 1) * L.DT for k in range(len(runs) - 1)] or [9])
        return longest, gap, len(runs)

    P = [pose_row(fi) for fi in range(len(T))]
    if free:   # a near tile may sweep across the face, but each pass under 0.35 s and never back to back (audit: 0.4 s per run)
        for _ in range(40):
            longest, gap, nruns = passes(P)
            if longest < .35 and gap >= .35:
                break
            drop += 8
            P = [pose_row(fi) for fi in range(len(T))]
        else:
            ctx.fail(f'orbit-carousel on {g["on"]!r}: near tiles would linger on the face; lower "size" or raise "speed"')
        if nruns:
            ctx.note(f'orbit-carousel: {nruns} quick face passes, longest {longest:.2f} s (near arc lowered {drop:.0f} px)')
    unsafe = 0 if free else sum(1 for row in P for p in row if p['s'] > .05 and L.unsafe(p['box']))
    if unsafe:
        ctx.fail(f'orbit-carousel on {g["on"]!r}: {unsafe} tile-frames leave the safe zone; use a smaller "size"')
    # front copy on the near half unless it would touch a face (then it passes behind it on the wall layer)
    front_on = [[p['c'] >= 0 and (free or L.box_face_share(p['box'], faces[fi]) <= .004) for p in row] for fi, row in enumerate(P)]
    for i in range(n):   # no single-frame flips between layers
        for fi in range(1, len(T) - 1):
            if front_on[fi - 1][i] == front_on[fi + 1][i] != front_on[fi][i]:
                front_on[fi][i] = front_on[fi - 1][i]
    touch = sum(1 for fi, row in enumerate(P) for i, p in enumerate(row) if p['c'] >= 0 and not front_on[fi][i] and p['s'] > .2)
    if touch:
        ctx.note(f'orbit-carousel: {touch} near tile-frames would touch a face; those pass behind it on the wall layer')
    ctx.note(f'orbit-carousel ring {2 * R:.0f} px wide, tiles {W0:.0f}x{H0:.0f} (face {rfw:.0f}x{rfh:.0f}), '
             + ('reference proportions' if free else f'safe-zone ring, near arc {NEAR:.0f} px under the chin'))
    fade = [min(1.0, (end - t) / .18) for t in T]

    # ---- markup: one clip per layer; wall copies carry no text ----
    shown = [t for t, on in zip(tiles, show_lb) if on]
    tfs, sfs = L.tile_fonts(ctx, 'orbit-carousel', shown, W0, H0, tmax=46, smin=28) if shown else (34, 28)

    def media(t, k):
        if t.get('video'):
            url = ctx.asset(t['video'])
            try:
                dur = L_ffprobe(ctx.asset_path(url))
            except Exception:
                dur = 4.0
            out, s0 = '', a
            while s0 < end - .05:   # loop: back-to-back copies, each later one on top (HyperFrames media has no loop)
                d = min(dur - .05, end - s0)
                out += (f'<video class="im" src="{url}" muted playsinline data-start="{s0:.3f}" data-media-start="0" '
                        f'data-duration="{d:.3f}" data-track-index="{90 + k}"></video>')
                s0 += d
            return out
        if t.get('src'):
            return f'<img class="im" src="{ctx.asset(t["src"])}">'
        return None

    def tile_inner(k, t, with_text):
        m = media(t, k)
        title, sub = ctx.esc(t.get('title', '')), ctx.esc(t.get('sub', ''))
        if m is not None:
            lb = f'<div class="lb"><div class="lt" style="font-size:{tfs}px">{title}</div></div>' if with_text and show_lb[k] else ''
            return m + lb
        if not with_text:   # a word tile's far copy: the same phone drawn as an image, soft bars where the words sit
            return (f'<div class="tg v{k % 4}"><svg class="im far" viewBox="0 0 90 160" preserveAspectRatio="none">'
                    '<rect x="10" y="14" width="22" height="7" rx="3.5"/><rect x="10" y="112" width="62" height="11" rx="5.5"/>'
                    '<rect x="10" y="130" width="44" height="11" rx="5.5"/></svg></div>')
        kick = ctx.esc(t.get('kicker') or f'{k + 1:02d}')
        return (f'<div class="tg v{k % 4}"><div class="kk" style="font-size:{sfs}px">{kick}</div>'
                f'<div class="tt" style="font-size:{tfs}px">{title}</div>'
                + (f'<div class="sb" style="font-size:{sfs}px">{sub}</div>' if sub else '') + '</div>')

    grp = f'orbit-{ctx.slug}-{L.group_cls(ctx)}'

    def ring(with_text):
        cards = ''.join(f'<div class="tl t{i}"{"" if with_text else " data-pass-behind=\"1\""} '
                        f'style="width:{W0:.0f}px;height:{H0:.0f}px;left:{-W0 / 2:.0f}px;top:{-H0 / 2:.0f}px">'
                        f'<div class="cd">{tile_inner(i, t, with_text)}<div class="vl"></div></div></div>' for i, t in enumerate(tiles))
        return f'<div class="fx-orbit-carousel" data-fx-group="{grp}">{cards}</div>'
    full = 'position:absolute;left:0;top:0;width:1080px;height:1920px;'
    wid = ctx.clip(ctx.wall, a, end, ring(False), full, 'wallz')
    fid = ctx.clip(ctx.front, a, end, ring(True), full)

    for i in range(n):
        motion, turn, veil, label, op_w, op_f = [], [], [], [], [], []
        for fi, row in enumerate(P):
            p = row[i]
            motion.append({'x': round(p['x'], 1), 'y': round(p['y'], 1), 'scale': round(p['s'], 4), 'zIndex': int(100 + 50 * p['c'])})
            turn.append({'rotationY': round(-p['sin'] * TURN, 2), **({'transformPerspective': 700} if fi == 0 else {})})
            veil.append({'opacity': round(.28 * (1 - p['c']) / 2, 3)})   # far tiles a touch darker: depth, not transparency
            label.append({'opacity': round(L.clamp((p['s'] * tfs - 25) / 3), 3)})
            on_f = front_on[fi][i]
            op_f.append({'opacity': round(fade[fi] if on_f else 0, 3)})
            op_w.append({'opacity': round(0 if on_f else fade[fi], 3)})
        L.emit_track(ctx, f'#{wid} .t{i}, #{fid} .t{i}', a, motion)
        L.emit_track(ctx, f'#{wid} .t{i} .cd, #{fid} .t{i} .cd', a, turn)
        L.emit_track(ctx, f'#{wid} .t{i} .vl, #{fid} .t{i} .vl', a, veil)
        if show_lb[i]:
            L.emit_track(ctx, f'#{fid} .t{i} ' + ('.lb' if (tiles[i].get('src') or tiles[i].get('video')) else '.tg > *'), a, label)
        L.emit_track(ctx, f'#{fid} .t{i}', a, op_f)
        L.emit_track(ctx, f'#{wid} .t{i}', a, op_w)

    top = min(p['box'][1] for row in P for p in row if p['s'] > .3)
    bottom = max(p['box'][3] for row in P for p in row if p['s'] > .3)
    L.claim(ctx, top, bottom, a, end, pause=True)   # captions pause while the ring spins (near tiles cross the caption band)
    ctx.sfx(g.get('sfx'), a, .3)


def L_ffprobe(path):
    import subprocess
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def describe(g, beat):
    n = len(g.get('videos') or g.get('tiles') or [])
    kind = 'reel clips' if g.get('videos') else 'tiles'
    names = ', '.join(f'"{t.get("title", "")}"' for t in (g.get('tiles') or []) if t.get('title'))
    return (f'On “{g["on"]}” {n} phone-sized {kind} spin up out of the head and orbit it: behind the head on the far side, '
            f'across the chest on the near side' + (f' ({names})' if names else '') + f'. Captions pause; it spins out after {beat["hold"]:.1f} s.')
