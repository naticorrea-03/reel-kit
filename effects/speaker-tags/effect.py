"""Speaker tags: a small label over each person in frame (a level, a role, a team); the tag of whoever is talking lights up."""
import importlib.util, os, sys

META = {
    'id': 'speaker-tags', 'name': 'Speaker tags', 'category': 'structure',
    'when': 'Two or three people in one shot, each standing for something (beginner, intermediate, expert; buyer and seller; host and guest).',
    'never': 'Never a label the viewer could not check against the people. Never more than 3 tags. Never covers a face.',
    'params': {'on': 'phrase where the tags appear', 'tags': '[{"text", "speaker"}] 1 to 3; speaker is the key in project.json speakers',
               'until': 'phrase where they leave (default the end of the clip)', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by an Instagram reel with three speakers labelled by level (Oct 2026)', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


FS, TH = 30, 50


def build(g, ctx):
    L = _lib()
    tags = g.get('tags') or []
    if not 1 <= len(tags) <= 3 or not all(isinstance(t, dict) and t.get('text') and t.get('speaker') for t in tags):
        ctx.fail(f'speaker-tags on {g["on"]!r} needs 1 to 3 tags, each with "text" and "speaker"')
    for t in tags:
        if t['speaker'] not in ctx.speakers:
            ctx.fail(f'speaker-tags: speaker {t["speaker"]!r} is not in project.json speakers ({", ".join(ctx.speakers)})')
    a = ctx.at(g['on'])[0]
    end = (ctx.at(g['until'], a)[0] - .05) if g.get('until') else ctx.DUR - .05
    # tags sorted left to right by each speaker's side, matched to the faces left to right
    order = sorted(range(len(tags)), key=lambda k: {'left': 0, 'center': 1, 'right': 2}.get((ctx.speakers[tags[k]['speaker']] or {}).get('side', 'left'), 1))
    widths = [int(len(t['text']) * FS * .68 + 44) for t in tags]
    # one layout per shot inside the window (faces move on every cut)
    cuts = sorted({a, end} | {s['frame'] / ctx.F for s in ctx.seg if a < s['frame'] / ctx.F < end})
    plans = []
    for s0, s1 in zip(cuts, cuts[1:]):
        if s1 - s0 < .2:
            continue
        fz = sorted(L.faces(ctx, s0 + .05, s1 - .05, n=4), key=lambda f: f[0])
        groups = []
        for f in fz:   # merge detections of the same face across samples
            if groups and abs((f[0] + f[2]) / 2 - (groups[-1][-1][0] + groups[-1][-1][2]) / 2) < 120:
                groups[-1].append(f)
            else:
                groups.append([f])
        faces = [[sorted(b[i] for b in grp)[len(grp) // 2] for i in range(4)] for grp in groups if len(grp) >= 2]
        allf = L.faces(ctx, s0 + .05, s1 - .05, n=4)
        pos = {}
        if len(faces) >= len(tags):
            pick = faces if len(faces) == len(tags) else sorted(faces, key=lambda f: -(f[2] - f[0]))[:len(tags)]
            pick = sorted(pick, key=lambda f: f[0])
            for rank, k in enumerate(order):
                pos[k] = pick[rank]
        elif faces:   # fewer faces than tags (a close shot): only the talker's tag, on the biggest face
            spk = ctx.speaker_at((s0 + s1) / 2)
            k = next((k for k, t in enumerate(tags) if t['speaker'] == spk), None)
            if k is not None:
                pos[k] = max(faces, key=lambda f: f[2] - f[0])
        lay = {}
        for k, f in pos.items():
            w = widths[k]
            x = max(L.SAFE[0], min(L.SAFE[2] - w, (f[0] + f[2]) / 2 - w / 2))
            near = [ff for ff in allf if ff[2] > x - L.MARGIN and ff[0] < x + w + L.MARGIN] or [f]
            y = min(ff[1] for ff in near) - L.MARGIN - 12 - TH
            if y < L.SAFE[1]:
                y = max(ff[3] for ff in near) + L.MARGIN + 12
            box = (x, y, x + w, y + TH)
            if L.face_share(box, allf) <= .002 and not L.unsafe(box):
                lay[k] = (int(x), int(y))
                L.reserve(ctx, box, s0, s1)
        plans.append((s0, s1, lay))
    if not any(p[2] for p in plans):
        ctx.fail(f'speaker-tags on {g["on"]!r}: no shot leaves room for a tag beside the faces')
    q = ctx.q
    for k, t in enumerate(tags):
        cid = ctx.clip(ctx.front, a, end, f'<div class="fx-speaker-tags"><span class="tg" style="font-size:{FS}px">{ctx.esc(t["text"])}</span></div>',
                       'position:absolute;left:0;top:0;')
        ctx.tw(f"gsap.set('#{cid}',{{opacity:0}});")
        shown = False
        for s0, s1, lay in plans:
            if k in lay:
                x, y = lay[k]
                ctx.tw(f"tl.fromTo('#{cid}',{{x:{x},y:{y}}},{{x:{x},y:{y},duration:.02,immediateRender:false}},{q(s0)});")
                ctx.tw(f"tl.fromTo('#{cid}',{{opacity:{1 if shown else 0},scale:{1 if shown else .8}}},{{opacity:1,scale:1,duration:{.04 if shown else .22},ease:'back.out(2)',immediateRender:false}},{q(s0)});")
                shown = True
            elif shown:
                ctx.tw(f"tl.fromTo('#{cid}',{{opacity:1}},{{opacity:0,duration:.04,immediateRender:false}},{q(s0)});")
                shown = False
        # light up while this speaker talks
        spk_cuts = [(s['frame'] / ctx.F, s['speaker']) for s in ctx.seg]
        prev = None
        for t0, sp in [(a, ctx.speaker_at(a))] + [(c, sp) for c, sp in spk_cuts if a < c < end]:
            on = sp == t['speaker']
            if on != prev:
                ctx.tw(f"tl.to('#{cid} .tg',{{className:'tg{' on' if on else ''}',duration:.01}},{q(t0)});")
                prev = on
    ctx.sfx(g.get('sfx'), a, .3)


def describe(g, beat):
    return f'From “{g["on"]}” tags ({", ".join(t["text"] for t in g["tags"])}) sit over each person; the talker\'s tag lights up. They hold {beat["hold"]:.1f} s.'
