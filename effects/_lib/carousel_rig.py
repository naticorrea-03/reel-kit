"""carousel_rig: the HyperFrames registry carousel rigs (carousel-orbit-1, carousel-circle-1, carousel-vision-1,
carousel-path-1), ported to Python and re-laid out for a 1080x1920 talking-head reel.

Adapted from the HyperFrames registry (https://github.com/heygen-com/hyperframes), Copyright HeyGen, Apache License 2.0.
Changes from the original: the browser-side CarouselRig (aeCurve, chainedDrive, buildProgress, orbitRig, pathRig) is
reimplemented in Python and evaluated once per video frame at build time; the poses are baked into GSAP keyframes instead
of a per-frame onUpdate render; the 3840x2160 landscape layouts are re-laid out around the speaker's head on the wall layer
(behind the speaker cutout) of a 9:16 frame; cards are reel-kit tiles (images or word tiles from params) instead of 24
fixed image slots; wall cards dim while the speaker covers them, and labels show only on cards big and clear enough to read.
"""
import math

DEG = 180 / math.pi


# ---------------- After Effects style keyframe curves (port of aeCurve / chainedDrive) ----------------
def ae_curve(keys):
    segs = []
    for a, b in zip(keys, keys[1:]):
        T = b['time'] - a['time']
        linear = not a.get('easeOut') or not b.get('easeIn') or str(a.get('flags', '')).startswith('0101')
        if linear:
            P1 = (a['time'] + T / 3, a['value'] + (b['value'] - a['value']) / 3)
            P2 = (a['time'] + 2 * T / 3, a['value'] + 2 * (b['value'] - a['value']) / 3)
        else:
            lo, li = a['easeOut']['influence'] * T, b['easeIn']['influence'] * T
            P1 = (a['time'] + lo, a['value'] + a['easeOut']['speed'] * lo)
            P2 = (b['time'] - li, b['value'] - b['easeIn']['speed'] * li)
        segs.append((a['time'], b['time'], (a['time'], a['value']), P1, P2, (b['time'], b['value'])))

    def bez(p0, p1, p2, p3, s):
        m = 1 - s
        return m * m * m * p0 + 3 * m * m * s * p1 + 3 * m * s * s * p2 + s * s * s * p3

    def at(t):
        if t <= segs[0][0]:
            return keys[0]['value']
        sg = next((g for g in segs if t <= g[1]), segs[-1])
        if t >= sg[1]:
            return sg[5][1]
        P0, P1, P2, P3 = sg[2], sg[3], sg[4], sg[5]
        s = (t - sg[0]) / (sg[1] - sg[0])
        for _ in range(8):   # Newton on the time axis
            x = bez(P0[0], P1[0], P2[0], P3[0], s) - t
            m = 1 - s
            dx = 3 * m * m * (P1[0] - P0[0]) + 6 * m * s * (P2[0] - P1[0]) + 3 * s * s * (P3[0] - P2[0])
            if abs(dx) < 1e-9:
                break
            s = min(1, max(0, s - x / dx))
        return bez(P0[1], P1[1], P2[1], P3[1], s)
    return at, keys[-1]['time'] - keys[0]['time'], keys[-1]['value'] - keys[0]['value']


def chained(keys, cumulative):
    """the registry's chainedDrive: the keyed swing repeats; cumulative drives keep adding, others ping-pong."""
    at, T, delta = ae_curve(keys)
    t0 = keys[0]['time']

    def f(t):
        if T <= 0:
            return keys[0]['value']
        k = math.floor(t / T)
        r = t - k * T
        if not cumulative:
            return at(t0 + r) if k % 2 == 0 else at(t0 + (T - r))
        return at(t0 + r) + k * delta
    return f


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(t):
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def ae_linear(v, a, b, c, d):
    return c if a == b else lerp(c, d, clamp01((v - a) / (b - a)))


def ae_ease(v, a, b, c, d):
    t = clamp01((v - a) / (b - a))
    e = 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2
    return lerp(c, d, e)


# ---------------- paths (port of buildPath) ----------------
def build_path(vertices, closed, samples=64):
    n = len(vertices)
    seg_count = n if closed else n - 1
    pts = []
    for s in range(seg_count):
        a, b = vertices[s], vertices[(s + 1) % n]
        p0, p3 = a['p'], b['p']
        p1 = (a['p'][0] + a['out'][0], a['p'][1] + a['out'][1])
        p2 = (b['p'][0] + b['in'][0], b['p'][1] + b['in'][1])
        last = samples if s == seg_count - 1 else samples - 1
        for k in range(last + 1):
            t = k / samples
            mt = 1 - t
            pts.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                        mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = cum[-1]

    def locate(pct):
        pct = pct % 1 if closed else clamp01(pct)
        target = pct * total
        lo, hi = 0, len(cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cum[mid] <= target:
                lo = mid
            else:
                hi = mid
        seg = cum[hi] - cum[lo] or 1
        return lo, hi, (target - cum[lo]) / seg

    def point(pct):
        i, j, f = locate(pct)
        return lerp(pts[i][0], pts[j][0], f), lerp(pts[i][1], pts[j][1], f)

    def tangent(pct):
        i, j, _ = locate(pct)
        dx, dy = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
        l = math.hypot(dx, dy) or 1
        return dx / l, dy / l
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {'point': point, 'tangent': tangent, 'closed': closed, 'bbox': (min(xs), min(ys), max(xs), max(ys))}


# ---------------- the four registry presets (style 1 of each family), values copied from the registry DATA ----------------
SWING = [{'time': 0, 'value': 0, 'flags': '02020000', 'easeIn': {'speed': 0, 'influence': .333333}, 'easeOut': {'speed': 238.51658, 'influence': .124734}},
         {'time': 1.51667, 'value': 75.5, 'flags': '02020000', 'easeIn': {'speed': 563.152726, 'influence': .063927}, 'easeOut': {'speed': 0, 'influence': .333333}}]
PRESETS = {
    'orbit': {'radius': 863, 'offset': 60.1, 'rotationX': 0, 'rotationZ': 26, 'perspectiveBoost': 84.9, 'scaleMin': -15.4, 'scaleMax': 11,
              'cam': 5669.2913,
              'keys': {'Rotation Y': [{'time': 0, 'value': 813, 'flags': '02020000', 'easeIn': {'speed': 0, 'influence': .166667}, 'easeOut': {'speed': 840.336559, 'influence': .124734}},
                                      {'time': 1.51667, 'value': 1079, 'flags': '02020000', 'easeIn': {'speed': 1984.087751, 'influence': .063927}, 'easeOut': {'speed': 0, 'influence': .166667}}]}},
    'circle': {'speed': 40, 'globalScale': 57, 'scaleDepth': 160, 'scaleMin': -47, 'depthAngle': 37, 'moveCarousel': 42.55, 'rotationFollow': 0,
               'path': {'vertices': [{'p': (2228.028, 354.208), 'in': (-357.877, 0), 'out': (357.877, 0)},
                                     {'p': (2876.028, 1002.208), 'in': (0, -357.877), 'out': (0, 357.877)},
                                     {'p': (2228.028, 1650.208), 'in': (357.877, 0), 'out': (-357.877, 0)},
                                     {'p': (1580.028, 1002.208), 'in': (0, 357.877), 'out': (0, -357.877)}], 'closed': True},
               'keys': {'Move Carousel': SWING}},
    'vision': {'speed': 20, 'globalScale': 100, 'scaleDepth': 130, 'scaleMin': -45.8, 'depthAngle': 0, 'moveCarousel': 19.74, 'rotationFollow': 0,
               'xSlider': -106, 'ySlider': 0, 'yAngle3d': -70, 'parent': {'position': (1920, 1299, 0), 'anchor': (1920, 1080, 0)}, 'cam': 5669.2913,
               'path': {'vertices': [{'p': (1920, 230.6), 'in': (-463.087, 0), 'out': (463.087, 0)},
                                     {'p': (2758.5, 1101.45), 'in': (0, -480.953), 'out': (0, 480.953)},
                                     {'p': (1920, 1972.3), 'in': (463.087, 0), 'out': (-463.087, 0)},
                                     {'p': (1081.5, 1101.45), 'in': (0, 480.953), 'out': (0, -480.953)}], 'closed': True},
               'keys': {'Move Carousel': SWING}},
    'path': {'speed': -5, 'globalScale': 46.3, 'scaleDepth': 133, 'scaleMin': -27.5, 'depthAngle': 853, 'moveCarousel': -111.94, 'rotationFollow': 0,
             'path': {'vertices': [{'p': (1711, 1852.2), 'in': (0, 0), 'out': (0, 0)},
                                   {'p': (1296.781, 828.793), 'in': (-599.805, 681.095), 'out': (233.9, -265.6)},
                                   {'p': (2385.699, 479.619), 'in': (-522.577, -80.694), 'out': (1061.206, 163.867)},
                                   {'p': (2848.5, 1653.3), 'in': (0, 0), 'out': (0, 0)}], 'closed': False},
             'keys': {'Move Carousel': [{'time': 0, 'value': -93.099998, 'flags': '02020000', 'easeIn': {'speed': 0, 'influence': .333333}, 'easeOut': {'speed': 349.272605, 'influence': .073989}},
                                        {'time': 1.53333, 'value': -42.899998, 'flags': '02020000', 'easeIn': {'speed': 131.14541, 'influence': .203595}, 'easeOut': {'speed': 0, 'influence': .333333}}],
                      'Rotation Follow': [{'time': 0, 'value': 61, 'flags': '01010000', 'easeIn': {'speed': 0, 'influence': 0}, 'easeOut': {'speed': 0, 'influence': 0}},
                                          {'time': 1.53333, 'value': 37, 'flags': '01010000', 'easeIn': {'speed': 0, 'influence': 0}, 'easeOut': {'speed': 0, 'influence': 0}}]}},
}
COMP_W, COMP_H = 3840, 2160   # the registry's working space


def rig(family, n, speed_scale=1.0):
    """returns pose(t) -> list of n dicts {x, y (registry px, centred on 0,0), z, scale (share of the fit box), rotZ, rotY, rotX, alpha, depth}."""
    P = PRESETS[family]
    drives = {k: chained(v, k in ('Move Carousel', 'Rotation X', 'Rotation Y', 'Rotation Z') and abs(v[-1]['value'] - v[0]['value']) > 1e-6)
              for k, v in P.get('keys', {}).items()}
    cx, cy = COMP_W / 2, COMP_H / 2
    if family == 'orbit':
        r, cam = P['radius'], P['cam']
        ga = math.pi * (3 - math.sqrt(5))

        def pose(t):
            ry = drives['Rotation Y'](t * speed_scale) / DEG
            rx, rz = P['rotationX'] / DEG, P['rotationZ'] / DEG
            out = []
            for k in range(n):
                i = ((k + 1 - .5 + P['offset']) % n + n) % n
                inc = math.acos(max(-1, min(1, 1 - 2 * (i / n))))
                azi = ga * i
                p = [math.sin(inc) * math.cos(azi) * r, math.cos(inc) * r, math.sin(inc) * math.sin(azi) * r]
                p = [p[0], p[1] * math.cos(rx) - p[2] * math.sin(rx), p[1] * math.sin(rx) + p[2] * math.cos(rx)]
                p = [p[0] * math.cos(ry) + p[2] * math.sin(ry), p[1], -p[0] * math.sin(ry) + p[2] * math.cos(ry)]
                p = [p[0] * math.cos(rz) - p[1] * math.sin(rz), p[0] * math.sin(rz) + p[1] * math.cos(rz), p[2]]
                jit = 1 + ((k + 1) % 2) * .01
                x, y, z = p[0] * jit, p[1] * jit, p[2] * jit
                d = math.hypot(x, y, z + cam)
                tt = clamp01(ae_linear(d, cam - r, cam + r, 0, 1))
                s = ae_linear(tt, 0, 1, P['scaleMax'], P['scaleMin'])
                fs = ae_linear(P['perspectiveBoost'], 0, 100, 100, s)
                yaw = math.atan2(-x, -(-cam - z)) * DEG
                pitch = -math.atan2(-y, math.hypot(x, -cam - z)) * DEG
                out.append({'x': x, 'y': y, 'z': z, 'scale': fs / 100, 'rotZ': 0, 'rotY': yaw, 'rotX': pitch, 'alpha': 1, 'depth': 1 - tt})
            return out
        return pose
    path = build_path(P['path']['vertices'], P['path']['closed'])
    bx = path['bbox']
    pcx, pcy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2   # centerPath: the registry recentres the path on the comp

    def pose(t):
        tt = t * speed_scale
        move = drives['Move Carousel'](tt) if 'Move Carousel' in drives else P['moveCarousel']
        follow = drives['Rotation Follow'](tt) if 'Rotation Follow' in drives else P.get('rotationFollow', 0)
        u = P['speed'] / 1000 * tt
        dang = P.get('depthAngle', 0) / DEG
        max_d = math.hypot(cx, cy)
        out = []
        for idx in range(n):
            pct = (u + idx / n + move / 100) % 1
            px, py = path['point'](pct)
            px, py = px - pcx, py - pcy
            proj = px * math.sin(dang) + py * math.cos(dang)
            norm = (proj / max_d + 1) / 2
            ds = ae_linear(norm, 0, 1, P['scaleMin'], 100)
            mixed = ae_linear(P['scaleDepth'] / 100, 0, 1, 100, ds)
            scale = mixed * P['globalScale'] / 100 / 100
            tg = path['tangent'](pct)
            rotz = math.atan2(tg[1], tg[0]) * DEG * follow / 100
            x, y, z, ry_, rx_ = px, py, 0.0, 0.0, 0.0
            if P.get('parent'):
                rx, ry = P['xSlider'] / DEG, P['ySlider'] / DEG
                an, pos = P['parent']['anchor'], P['parent']['position']
                l = [px + pcx - an[0], py + pcy - an[1], 0]
                l = [l[0] * math.cos(ry) + l[2] * math.sin(ry), l[1], -l[0] * math.sin(ry) + l[2] * math.cos(ry)]
                l = [l[0], l[1] * math.cos(rx) - l[2] * math.sin(rx), l[1] * math.sin(rx) + l[2] * math.cos(rx)]
                x, y, z = pos[0] + l[0] - cx, pos[1] + l[1] - cy, pos[2] + l[2]
                cam = P['cam']
                vx, vy, vz = -x, -y, -cam - z
                ry_ = math.atan2(vx, -vz) * DEG
                rx_ = -math.atan2(vy, math.hypot(vx, vz)) * DEG
            if P.get('yAngle3d'):
                r_ = ae_ease(abs(x), 0, COMP_W * (700 / 1920), 0, P['yAngle3d'])
                ry_ += -r_ if x < 0 else r_
            alpha = 1.0
            if not path['closed']:
                e = min(pct, 1 - pct) / .06
                alpha = e if e < 1 else 1.0
            out.append({'x': x, 'y': y, 'z': z, 'scale': scale, 'rotZ': rotz, 'rotY': ry_, 'rotX': rx_, 'alpha': alpha, 'depth': norm})
        return out
    return pose


def bounds(family, n, dur=6.0):
    """registry-space extent of the card centres over a run (used to fit the layout to the head)."""
    pose = rig(family, n)
    xs, ys, ss = [], [], []
    for k in range(int(dur * 10)):
        for p in pose(k / 10):
            xs.append(p['x'])
            ys.append(p['y'])
            ss.append(p['scale'])
    return min(xs), min(ys), max(xs), max(ys), max(ss)
