"""Word build: one spoken sentence builds word by word in the band above the head, and its key phrase gets a marker box."""
import importlib.util, os, re, sys

META = {
    'id': 'word-build', 'name': 'Word build', 'category': 'captions',
    'when': 'A sentence that carries the reel and has one key phrase ("Claude can now predict how viral your reel is gonna be before you even post it").',
    'never': 'Never more than three lines. Never a marker on a filler word: mark the phrase that is the point.',
    'params': {'on': 'first words of the sentence', 'until': 'last words of the sentence (required)', 'mark': 'phrase inside it to box (optional)',
               'bold': 'list of words to set bold (optional)', 'hold': 'seconds after the last word, default 0.8', 'sfx': 'optional sound name'},
    'sfx': [], 'source': 'ours', 'credit': 'Motion idea inspired by an Instagram reel on predicting virality (Oct 2026)', 'license': 'MIT',
}


def _lib():
    if 'igfx' not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', 'igfx.py')
        spec = importlib.util.spec_from_file_location('igfx', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules['igfx'] = mod
    return sys.modules['igfx']


def _n(s):
    return re.sub(r"[^a-z0-9']", '', s.lower())


def build(g, ctx):
    L = _lib()
    L.need(ctx, g, 'until')
    a0 = ctx.at(g['on'])[0]
    b0 = ctx.at(g['until'], a0)[1]
    words = [w for w in ctx.capwords if a0 - .05 <= w['start'] < b0 + .01 and ctx.disp(w['text'])]
    if not 2 <= len(words) <= 18:
        ctx.fail(f'word-build on {g["on"]!r}: {len(words)} words; keep it to one sentence of 2 to 18 words')
    a = a0 - .05
    end = min(ctx.DUR - .05, b0 + float(g.get('hold', .8)))
    later = [t for h in ctx.graphics if h is not g and h.get('on') and h.get('type') not in L.PINNED for t in [ctx.at(h['on'])[0]] if t > a + .05]
    if later:
        end = min(end, min(later) - .15)
    if end - b0 < .3:
        ctx.fail(f'word-build on {g["on"]!r}: the next graphic starts before the sentence lands; move it')
    text = [w['text'].strip() for w in words]
    shown = ' '.join(text)
    fs = L.fit(ctx, 'word-build', [shown], 840, 72, 40, 3, .55)
    lines = L.wrap(shown, 840, fs, .55)
    H = int(len(lines) * fs * 1.3 + 30)
    # the band above the head, else under the chin
    fz = L.faces(ctx, a, end)
    ftop = min([f[1] for f in fz] or [900])
    fbot = max([f[3] for f in fz] or [900])
    yt = max(250, int(min(330, ftop - L.MARGIN - 20 - H)))
    if ftop - L.MARGIN - 250 >= H and L.taken(ctx, (110, yt, 970, yt + H), a, end) <= .01:
        y = yt
    elif 1460 - fbot - L.MARGIN >= H:
        y = int(fbot + L.MARGIN + 20)
    else:
        ctx.fail(f'word-build on {g["on"]!r}: no band clear of the face for {len(lines)} line(s); shorten the sentence')
    ink, tone = L.wall_ink(ctx, a, end, (110, y, 970, y + H))
    mark = [_n(x) for x in str(g.get('mark', '')).replace('-', ' ').split()]
    bold = {_n(x) for x in g.get('bold', [])}
    mi = None
    tok = [_n(t) for t in text]
    if mark:
        for i in range(len(tok) - len(mark) + 1):
            if tok[i:i + len(mark)] == mark:
                mi = (i, i + len(mark))
                break
        if mi is None:
            ctx.fail(f'word-build mark {g["mark"]!r} is not inside the sentence')
    spans = []
    for i, t in enumerate(text):
        cls = 'w' + (' b' if tok[i] in bold or (mi and mi[0] <= i < mi[1]) else '')
        s = f'<span class="{cls} w{i}">{ctx.esc(t)}</span>'
        if mi and i == mi[0]:
            s = '<span class="mk"><i class="bx"></i><i class="tk t1"></i><i class="tk t2"></i><i class="tk t3"></i><i class="tk t4"></i>' + s
        if mi and i == mi[1] - 1:
            s += '</span>'
        spans.append(s)
    html = f'<div class="fx-word-build {tone}" style="font-size:{fs}px;color:{ink}">{"".join(spans)}</div>'
    cid = ctx.clip(ctx.front, a, end, html, f'position:absolute;left:110px;right:110px;top:{y}px;')
    q = ctx.q
    ctx.tw(f"gsap.set('#{cid} .w',{{opacity:0}});")
    for i, w in enumerate(words):
        t = max(a, w['start'] - .04)
        ctx.tw(f"tl.fromTo('#{cid} .w{i}',{{opacity:0,y:10,filter:'blur(8px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.22,ease:'power2.out',immediateRender:false}},{q(t)});")
    if mi:
        tm = max(a, words[mi[1] - 1]['start'])
        ctx.tw(f"gsap.set('#{cid} .bx',{{scaleX:0}});")
        ctx.tw(f"gsap.set('#{cid} .tk',{{opacity:0}});")
        ctx.tw(f"tl.fromTo('#{cid} .bx',{{scaleX:0}},{{scaleX:1,duration:.26,ease:'power3.out',immediateRender:false}},{q(tm)});")
        ctx.tw(f"tl.fromTo('#{cid} .tk',{{opacity:0,scale:.3}},{{opacity:1,scale:1,duration:.2,stagger:.04,ease:'back.out(3)',immediateRender:false}},{q(tm + .16)});")
    ctx.tw(f"tl.to('#{cid}',{{opacity:0,y:-14,filter:'blur(6px)',duration:.2,ease:'power2.in'}},{q(end - .2)});")
    ctx.busy.append((a, end))
    L.reserve(ctx, (110, y, 970, y + H), a, end)
    if y < 400:
        ctx.topbusy.append((a, end))
    if y + H > 1060:
        ctx.lowbusy.append((a, end))
    ctx.sfx(g.get('sfx'), a, .3)


def describe(g, beat):
    return (f'From “{g["on"]}” to “{g["until"]}” the sentence builds word by word above the head'
            f'{"; “" + g["mark"] + "” gets a marker box" if g.get("mark") else ""}. Captions pause; it holds {beat["hold"]:.1f} s.')
