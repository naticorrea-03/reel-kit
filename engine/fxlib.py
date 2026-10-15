"""fxlib: the Context object every effect receives.

One Context per built clip. It holds the cut timeline (words, shots), the layers the page is
assembled from, the GSAP lines, the sound cues, and the placement helpers that read the speaker
cutout and the face boxes. Effects never touch files or paths directly; they go through ctx.

Coordinates are always the 1080x1920 canvas. Times are seconds on the cut timeline.
"""
import importlib.util, json, math, os, platform, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(REPO, 'engine')
EFFECTS = os.path.join(REPO, 'effects')
FACEBIN = os.path.join(ENGINE, 'audit', 'faces')
F = 30

# safe zone on 1080x1920 (Instagram / TikTok UI): text inside x 90-950, y 240-1470, no right rail below 1155
SAFE = {'x0': 90, 'x1': 950, 'y0': 240, 'y1': 1470, 'rail_x': 950, 'rail_y': 1155}

WEAK_END = {'i', "i'm", "i've", "i'll", 'the', 'a', 'an', 'to', 'and', 'of', 'my', 'we', "we're", 'it', 'is', 'that', 'for',
            'in', 'on', 'with', 'but', 'so', 'or', 'your', 'our', 'this'}
DEFAULT_FIXES = {'ai': 'AI', 'llm': 'LLM', 'chatgpt': 'ChatGPT', 'csuite': 'C-suite', 'linkedin': 'LinkedIn',
                 'claude': 'Claude', 'gemini': 'Gemini', 'ceo': 'CEO', 'ok': 'OK'}
DEFAULT_PAIRS = [('a', 'm', 'a.m.'), ('p', 'm', 'p.m.'), ('chat', 'gpt', 'ChatGPT'), ('new', 'york', 'New York')]


def n(s):
    return re.sub(r"[^a-z0-9']", '', s.lower())


def toks(s):
    return [n(x) for x in s.replace('-', ' ').split() if n(x)]


def ffprobe_duration(path, stream=True):
    args = ['ffprobe', '-v', 'error']
    args += (['-select_streams', 'v:0', '-show_entries', 'stream=duration'] if stream else ['-show_entries', 'format=duration'])
    out = subprocess.run(args + ['-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip().split(',')[0].split('\n')[0]
    return float(out)


def image_size(path):
    """(width, height) of a raster image or an SVG with a viewBox."""
    if path.lower().endswith('.svg'):
        head = open(path, 'rb').read(4000).decode('utf8', 'ignore')
        m = re.search(r'viewBox="\s*[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)[ ,]+([\d.]+)', head)
        if m:
            return float(m.group(1)), float(m.group(2))
        m = re.search(r'width="([\d.]+)[^"]*"\s+height="([\d.]+)', head)
        return (float(m.group(1)), float(m.group(2))) if m else (1200.0, 1600.0)
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def ensure_faces():
    """path to the compiled macOS Vision face detector; compiles faces.swift on first use. Fails loudly off macOS."""
    if os.path.exists(FACEBIN):
        return FACEBIN
    if platform.system() != 'Darwin':
        sys.exit('ERROR: face detection needs macOS (Vision framework via engine/audit/faces.swift). '
                 'reel-kit will not place graphics or audit faces without it. Run on a Mac.')
    if not shutil.which('swiftc'):
        sys.exit('ERROR: swiftc not found. Install the Xcode command line tools (xcode-select --install), then run python3 engine/doctor.py')
    src = os.path.join(ENGINE, 'audit', 'faces.swift')
    r = subprocess.run(['swiftc', '-O', src, '-o', FACEBIN], capture_output=True, text=True)
    if r.returncode or not os.path.exists(FACEBIN):
        sys.exit(f'ERROR: could not compile {src}:\n{r.stderr}')
    return FACEBIN


def load_effect(eid):
    """import effects/<eid>/effect.py; None when the folder does not exist."""
    path = os.path.join(EFFECTS, eid, 'effect.py')
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(f'rk_effect_{eid.replace("-", "_")}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if getattr(mod, 'META', {}).get('id') != eid:
        sys.exit(f'ERROR: effects/{eid}/effect.py META id is {getattr(mod, "META", {}).get("id")!r}, expected {eid!r}')
    return mod


class Context:
    def __init__(self, project_dir, slug, clip, look, profile, project, safe=False):
        self.project_dir = os.path.abspath(project_dir)
        self.slug, self.clipspec, self.look, self.profile, self.project = slug, clip, look, profile, project
        self.safe = safe
        self.D = os.path.join(self.project_dir, 'clips', slug)
        self.work = os.path.join(self.D, '.work')
        os.makedirs(self.work, exist_ok=True)
        need = [os.path.join(self.D, 'cut.words.json'), os.path.join(self.D, 'segments.json'), os.path.join(self.D, 'assets', 'aroll.mp4')]
        for p in need:
            if not os.path.exists(p):
                self.fail(f'missing {os.path.relpath(p, self.project_dir)} (run engine/cut.py first)')
        W = json.load(open(need[0]))
        self.words = W['words'] if isinstance(W, dict) else W
        self.seg = json.load(open(need[1]))
        self.DUR = ffprobe_duration(need[2])
        self.has_cut = os.path.exists(os.path.join(self.D, 'assets', 'subject.webm'))
        self.F = F
        self.speakers = project.get('speakers', {})
        self.graphics = clip.get('graphics', [])
        # layers, bottom to top: wall (behind the cutout), front (over the speakers), top (captions, name tags)
        self.wall, self.front, self.top = [], [], []
        self.tws, self.sfxs = [], []
        self.busy, self.topbusy, self.lowbusy = [], [], []
        self.parallel = {}
        self.plan, self._beat = [], None
        self._uid = 0
        self.hook_end = 0.0
        self._alpha, self._head, self._faces = {}, {}, {}
        self._meta = {}
        self.capwords = self._caption_words()

    # ---------- messages ----------
    def fail(self, msg):
        sys.exit(f'ERROR {self.slug}: {msg}')

    def warn(self, msg):
        print(f'WARN {self.slug}: {msg}')

    def note(self, msg):
        print(f'NOTE {self.slug}: {msg}')

    def var(self, name):
        """a CSS var as the page will see it (profile brand and project vars override the look)."""
        v = dict(self.look.get('vars', {}))
        v.update(self.profile.get('brand', {}).get('vars', {}))
        v.update(self.project.get('vars', {}))
        return str(v.get(name, '')).strip()

    # ---------- text ----------
    @staticmethod
    def q(t):
        return f'{round(max(0, t) * F) / F:.3f}'

    @staticmethod
    def esc(s):
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    def typed(self, msg):
        """letter spans grouped by word, so typed text wraps by word (never letter spans with &nbsp;)."""
        return ' '.join('<span class="tw">' + ''.join(f'<span class="tc">{self.esc(c)}</span>' for c in w) + '</span>' for w in msg.split())

    # ---------- timeline ----------
    def find(self, phrase, after=0.0):
        """(start, end) of phrase on the cut timeline (first match at/after `after`), or None."""
        seq = toks(phrase)
        if not seq:
            return None
        flat = [(t, i) for i, w in enumerate(self.words) for t in toks(w['text'])]
        for p in range(len(flat) - len(seq) + 1):
            if self.words[flat[p][1]]['start'] < after:
                continue
            if [x[0] for x in flat[p:p + len(seq)]] == seq:
                return self.words[flat[p][1]]['start'], self.words[flat[p + len(seq) - 1][1]]['end']
        return None

    def at(self, phrase, after=0.0):
        r = self.find(phrase, after)
        if r is None:
            self.fail(f'phrase not on cut timeline: {phrase!r}' + (f' (after {after:.2f} s)' if after else ''))
        return r

    def said(self, t0, t1):
        return ' '.join(w['text'] for w in self.words if t0 - .05 <= w['start'] < t1)

    def face_scale_at(self, t):
        """face height as a share of the frame for the shot at t: 0.13 is a close-up, under 0.075 is a wide shot.
        Old cuts without a measured "face" fall back to zoom x 0.054 (the framing the zoom numbers were tuned on)."""
        f = None
        for s in self.seg:
            if s['frame'] / F <= t + 1e-3:
                f = s.get('face', s['zoom'] * .054)
        return f if f is not None else self.seg[0].get('face', self.seg[0]['zoom'] * .054)

    def zoom_at(self, t):
        z = self.seg[0]['zoom']
        for s in self.seg:
            if s['frame'] / F <= t + 1e-3:
                z = s['zoom']
        return z

    def speaker_at(self, t):
        return next((s['speaker'] for s in reversed(self.seg) if s['frame'] / F <= t + 1e-3), self.seg[0]['speaker'])

    def speaker_name(self, key):
        return (self.speakers.get(key) or {}).get('name') or key

    def graphic_start(self, g):
        return self.at(g['on'])[0]

    def meta(self, eid):
        if eid not in self._meta:
            mod = load_effect(eid)
            self._meta[eid] = getattr(mod, 'META', {}) if mod else {}
        return self._meta[eid]

    # ---------- the speaker cutout and faces ----------
    def alpha_frame(self, t):
        """subject alpha at time t as 270x480 gray bytes (1 px = 4 px of the canvas)."""
        key = round(t, 2)
        if key not in self._alpha:
            raw = os.path.join(self.work, 'alpha.gray')
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-c:v', 'libvpx-vp9', '-ss', f'{max(0, t):.2f}', '-i',
                            os.path.join(self.D, 'assets', 'subject.webm'), '-frames:v', '1', '-vf', 'alphaextract,scale=270:480',
                            '-pix_fmt', 'gray', '-f', 'rawvideo', raw], check=True)
            data = open(raw, 'rb').read()
            if len(data) < 270 * 480:   # past the end of the cutout: treat as empty
                data = bytes(270 * 480)
            self._alpha[key] = data
        return self._alpha[key]

    def alpha_cover(self, t, x0, y0, x1, y1):
        """fraction of the box hidden by the speakers at time t (0 without a cutout)."""
        if not self.has_cut:
            return 0.0
        raw = self.alpha_frame(t)
        xs, ys = range(max(0, int(x0 / 4)), min(270, int(x1 / 4))), range(max(0, int(y0 / 4)), min(480, int(y1 / 4)))
        tot = len(xs) * len(ys)
        return sum(1 for y in ys for x in xs if raw[y * 270 + x] > 128) / tot if tot else 0.0

    def bg_luma(self, t0, t1, x0, y0, x1, y1):
        """(mean brightness, standard deviation), both 0-1, of the background behind a box over [t0, t1], speaker pixels left out.
        The layout audit cannot judge contrast: light text on a bright wall passed it and read as a smudge."""
        tot, cnt, sq = 0.0, 0, 0.0
        for k in range(3):
            t = max(0, min(t0 + (t1 - t0) * k / 2, self.DUR - .05))
            key = ('luma', round(t, 1))
            if key not in self._alpha:
                raw = os.path.join(self.work, 'luma.gray')
                subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{t:.2f}', '-i', os.path.join(self.D, 'assets', 'aroll.mp4'),
                                '-frames:v', '1', '-vf', 'scale=270:480,format=gray', '-f', 'rawvideo', raw], check=True)
                self._alpha[key] = open(raw, 'rb').read()
            lum = self._alpha[key]
            al = self.alpha_frame(t) if self.has_cut else None
            for y in range(max(0, int(y0 / 4)), min(480, int(y1 / 4))):
                for x in range(max(0, int(x0 / 4)), min(270, int(x1 / 4))):
                    if al is not None and al[y * 270 + x] > 128:
                        continue
                    v = lum[y * 270 + x]
                    tot += v
                    sq += v * v
                    cnt += 1
        if not cnt:
            return 0.0, 0.0
        m = tot / cnt
        return m / 255, max(0.0, sq / cnt - m * m) ** .5 / 255   # (brightness, busyness): a plain wall has busyness under ~0.06

    def faces_at(self, t):
        """padded face boxes at time t from the a-roll frame (same detector and padding as audit/analyze.py)."""
        key = round(max(0, min(t, self.DUR - .05)), 1)
        if key not in self._faces:
            png = os.path.join(self.work, 'face.png')
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{key:.2f}', '-i', os.path.join(self.D, 'assets', 'aroll.mp4'),
                            '-frames:v', '1', '-vf', 'scale=540:960', png], check=True)
            raw = json.loads(subprocess.run([ensure_faces(), png], capture_output=True, check=True).stdout).get(png, [])
            self._faces[key] = [[(x - .12 * w) * 2, (y - .30 * h) * 2, (x + w * 1.12) * 2, (y + h * 1.18) * 2] for x, y, w, h in raw]
        return self._faces[key]

    def face_hit(self, t0, t1, x0, y0, x1, y1):
        """worst share of any face covered by the box over [t0, t1] (sampled every 0.2 s)."""
        worst, k_n = 0.0, max(2, int((t1 - t0) / .2) + 1)
        for k in range(k_n):
            for fx0, fy0, fx1, fy1 in self.faces_at(t0 + (t1 - t0) * k / (k_n - 1)):
                ix, iy = max(0, min(x1, fx1) - max(x0, fx0)), max(0, min(y1, fy1) - max(y0, fy0))
                worst = max(worst, ix * iy / max(1, (fx1 - fx0) * (fy1 - fy0)))
        return worst

    def place(self, w, h, t0, t1, cands, scan=True):
        """(cost, x, y): the candidate whose w x h box hides the least of the speakers over [t0, t1]; faces count 10x.

        The listed candidates are tried first, in order. When none of them is clear and scan is on, every y in the safe
        zone is tried too, because candidates tuned on one framing (heads high in a wide shot) land on the face in another
        (a centred selfie)."""
        def cost(x, y):
            return max(self.alpha_cover(t0 + (t1 - t0) * k / 3, x, y, x + w, y + h) for k in (0, 1, 2, 3)) + 10 * self.face_hit(t0, t1, x, y, x + w, y + h)
        best = None
        for x, y in cands:
            c = cost(x, y)
            if best is None or c < best[0] - .01:
                best = (c, x, y)
        # scan only when the best listed spot touches a FACE: covering a body is fine for a front card, a face never is
        if scan and best and self.face_hit(t0, t1, best[1], best[2], best[1] + w, best[2] + h) > .005:
            x = best[1]
            for y in range(SAFE['y0'], int(SAFE['y1'] - h - 40) + 1, 30):
                c = cost(x, y)
                if c < best[0] - .01:
                    best = (c, x, y)
        return best

    def head_top(self, t):
        """topmost subject pixel (canvas y) at time t inside the centre band; None without a cutout."""
        if not self.has_cut:
            return None
        key = round(t, 2)
        if key not in self._head:
            raw = self.alpha_frame(t)
            top = None
            for y in range(480):
                row = raw[y * 270:(y + 1) * 270]
                if sum(1 for x in range(50, 220) if row[x] > 128) >= 6:
                    top = y * 4
                    break
            self._head[key] = top
        return self._head[key]

    def speaker_face(self, t):
        """face box of whoever is talking at t, using the speaker's side from project.json."""
        fz = sorted(self.faces_at(t), key=lambda f: f[0])
        if not fz:
            return None
        side = (self.speakers.get(self.speaker_at(t)) or {}).get('side', 'left')
        return fz[0] if side == 'left' else fz[-1]

    # ---------- page assembly ----------
    def clip(self, layer, a, b, inner, style='', cls=''):
        """timed wrapper (HyperFrames needs class="clip" windows). Returns the id of the inner node GSAP animates."""
        # duration from frame-rounded ends, so back-to-back captions never share a frame
        self._uid += 1
        cid = f'e{self._uid}'
        if self._beat is not None and '<div class="cap">' not in inner:
            self._beat['clips'].append((a, b))
            self._beat.setdefault('wall', []).append(layer is self.wall)
        dur = max(.1, (round(max(0, b) * F) - round(max(0, a) * F)) / F - .01)
        layer.append(f'<div class="clip {cls}" data-start="{self.q(a)}" data-duration="{dur:.3f}" data-track-index="{20 + self._uid % 40}" style="{style}">'
                     f'<div id="{cid}" class="in">{inner}</div></div>')
        return cid

    def tw(self, line):
        self.tws.append(line)

    def sfx(self, name, t, vol=.5, cap=None):
        """queue a sound (name from assets/sfx/manifest.json). name None or '' or 'none' is silence."""
        if not name or name == 'none':
            return
        self.sfxs.append((name, t, vol) + ((cap,) if cap else ()))

    def asset(self, path, required=True):
        """copy a project file (or effect demo file) into the clip folder; returns its relative url, or None."""
        if not path:
            return None
        cands = [os.path.expanduser(path)] if os.path.isabs(os.path.expanduser(path)) else \
            [os.path.join(self.project_dir, path), os.path.join(self.project_dir, 'assets', path)] + \
            [os.path.join(EFFECTS, e, 'demo', path) for e in ([self._beat['kind']] if self._beat else [])]
        src = next((c for c in cands if os.path.isfile(c)), None)
        if not src:
            if required:
                self.fail(f'asset not found: {path!r} (looked in the project folder and project/assets)')
            return None
        rel = re.sub(r'[^A-Za-z0-9._-]+', '_', os.path.relpath(src, self.project_dir) if src.startswith(self.project_dir) else os.path.basename(src)).lstrip('._')
        dst = os.path.join(self.D, 'assets', 'fx', rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src) or os.path.getsize(dst) != os.path.getsize(src):
            shutil.copy2(src, dst)
        return f'assets/fx/{rel}'

    def asset_path(self, url):
        return os.path.join(self.D, url)

    def image_size(self, url):
        return image_size(self.asset_path(url))

    # ---------- storyboard plan ----------
    def beat(self, kind, text='', g=None):
        """open a storyboard beat; every clip() until the next beat belongs to it."""
        self.beat_close()
        self._beat = {'kind': kind, 'clips': [], 'sfx0': len(self.sfxs), 'g': g or {}, 'text': text}

    def beat_text(self, text):
        if self._beat is not None:
            self._beat['text'] = text

    def beat_close(self):
        c, self._beat = self._beat, None
        if not c or not c['clips']:
            return
        t0, t1 = min(x[0] for x in c['clips']), min(self.DUR, max(x[1] for x in c['clips']))
        self.plan.append({'onwall': any(c.get('wall', [])), 'kind': c['kind'], 't0': round(max(0, t0), 2), 't1': round(t1, 2),
                          'g': c.get('g', {}), 'text': c.get('text', ''), 'sounds': [x[0] for x in self.sfxs[c['sfx0']:]]})

    # ---------- shared window helpers for ui effects ----------
    def app_header(self, g, default='Assistant', title=None, small=None):
        """window title row: app icon (file from g['icon'], else the app's initial) and name."""
        app = g.get('app', default)
        url = self.asset(g['icon']) if g.get('icon') else None
        ic = f'<img src="{url}" class="ic">' if url else f'<span class="ic txt">{self.esc(app[:1].upper())}</span>'
        sm = f' <small>{self.esc(small)}</small>' if small else ''
        return f'<div class="win-h">{ic} {self.esc(title or app)}{sm}</div>'


    def ui_window(self, g, a, html, anim, hold, s0=None, layer_pref='wall', height=400, topy=330, extra_css='', cls_hint=''):
        """place, time and animate a UI window.

        anim: GSAP lines using '#ID' for the window id. layer_pref: 'wall' (behind the heads when they leave room,
        else moved in front under the faces), 'front', or 'card' (a short card that prefers the band above the heads).
        """
        s0 = a - .1 if s0 is None else s0
        if 'class="sk"' in html and 'class="bub' not in html and 'rk-bub' not in html:   # two windows of grey bars read as blank cards
            self.fail(f'{g["type"]} on {g["on"]!r} shows only placeholder bars; give it a real line of text')
        if g.get('until'):   # close before a later line so its caption shows
            hold = min(hold, self.at(g['until'], s0)[0] - .05 - s0)
        layer = self.wall if (layer_pref == 'wall' and self.has_cut) else self.front
        zoom_css = extra_css
        first = [float(m.group(1)) for x in anim if '#ID ' in x for m in [re.search(r',([\d.]+)\);?$', x)] if m]
        if first and min(first) > s0 + .9:   # no empty window: open 0.45 s before the first message lands
            ns = min(first) - .45
            hold -= ns - s0
            s0 = ns
        if layer_pref == 'wall' and self.has_cut and height:
            cov = max(self.alpha_cover(s0 + hold * k / 8, 90, topy, 990, topy + height) for k in range(9))
            if cov > .06:
                # heads would hide the content: bring it to the front, clear of the faces, captions pause
                # shrink only as far as it takes to find a spot clear of the face (+50: windows render taller than their estimate)
                for zf in ([.82, .7, .6] if height > 360 else [1.0, .82, .7]):
                    hh = int(height * zf) + 50
                    _, _, topy = self.place(900, hh, s0, s0 + hold, [(90, int(1250 - height * zf))])
                    if self.face_hit(s0, s0 + hold, 90, topy, 990, topy + hh) <= .005:
                        break
                if zf < 1:
                    html = f'<div style="zoom:{zf};width:900px">{html}</div>'
                    zoom_css = f'left:{90 + 900 * (1 - zf) / 2:.0f}px;width:{900 * zf:.0f}px;'
                self.note(f'{g["type"]} moved to front under the faces, y {topy} (was {cov:.0%} behind heads)')
                layer_pref, layer = 'front', self.front
                self.busy.append((s0, s0 + hold))
                self.lowbusy.append((s0, s0 + hold))
        if layer_pref == 'card':
            topy = 300
            cov = max(self.alpha_cover(s0 + hold * k / 8, 90, 300, 990, 300 + height) for k in range(9))
            layer = self.wall if self.has_cut else self.front
            if cov > .03:   # closer zooms: heads hide the card, so bring it in front where it clears faces
                _, _, topy = self.place(900, height, s0, s0 + hold, [(90, y) for y in (240, 860, 940, 1010)])
                self.note(f'{g["type"]} card moved in front at y {topy} (was {cov:.0%} behind heads)')
                layer = self.front
                if topy > 800:
                    self.busy.append((s0, s0 + hold))
                    self.lowbusy.append((s0, s0 + hold))
        if topy < 400:
            self.topbusy.append((s0, s0 + hold))
        win_w = 860 if topy + height > SAFE['rail_y'] else 900   # right edge 950 clears the like/comment rail
        cid = self.clip(layer, s0, s0 + hold, html, f'position:absolute;left:90px;top:{topy}px;width:{win_w}px;{zoom_css}',
                        'wallz' if layer is self.wall else '')
        self.tw(f"tl.fromTo('#{cid}',{{opacity:0,y:-60,scale:.94}},{{opacity:1,y:0,scale:1,duration:.4,ease:'power3.out',immediateRender:false}},{self.q(s0)});")
        for x in anim:
            m = re.match(r"tl\.fromTo\('(#ID [^']+)',\{opacity:0", x)
            if m:
                self.tw(f"gsap.set('{m.group(1).replace('#ID', '#' + cid)}',{{opacity:0}});")
        for x in anim:
            self.tw(x.replace('#ID', f'#{cid}'))
        self.tw(f"tl.to('#{cid}',{{opacity:0,y:-30,duration:.2,ease:'power2.in'}},{self.q(s0 + hold - .2)});")
        return cid, s0, hold, topy

    # ---------- captions ----------
    def _caption_cfg(self):
        c = dict(self.look.get('captions', {}))
        c.update(self.profile.get('captions', {}))
        return c

    def _caption_words(self):
        fixes = dict(DEFAULT_FIXES)
        fixes.update({n(k): v for k, v in (self.project.get('caption_fixes') or {}).items()})
        pairs = DEFAULT_PAIRS + [tuple(p) for p in (self.project.get('caption_pairs') or [])]
        self._fixes, self._pair_out = fixes, {p[2] for p in pairs}
        cw = [dict(w) for w in self.words]
        for k in range(len(cw) - 1):
            if cw[k + 1]['text'].startswith('-') and cw[k]['text']:   # "C -suite" -> "C-suite"
                cw[k]['text'] = cw[k]['text'].rstrip('.,') + cw[k + 1]['text']
                cw[k]['end'] = cw[k + 1]['end']
                cw[k + 1]['text'] = ''
                continue
            a, b = n(cw[k]['text']), n(cw[k + 1]['text'])
            for x, y, out in pairs:
                if a == n(x) and b == n(y):
                    tail = cw[k + 1]['text'][-1] if cw[k + 1]['text'][-1:] in '.,!?' else ''
                    cw[k]['text'] = out + (tail if not out.endswith(tail) else '')
                    cw[k]['end'] = cw[k + 1]['end']
                    cw[k + 1]['text'] = ''
                    break   # a pair listed twice (defaults + project) used to merge again into an empty word and crash
        return cw

    def disp(self, t):
        """caption display form of one word: fixes first, then the look's case."""
        if not t:
            return ''
        core = t.strip().strip('.,!?;:"').strip()
        if not core:
            return ''
        k = n(core)
        case = self._caption_cfg().get('case', 'lower')
        if core in self._pair_out or core + '.' in self._pair_out:
            out = core if core in self._pair_out else core + '.'
        elif k in self._fixes:
            out = self._fixes[k]
        elif case == 'lower':
            out = core.lower()
        else:
            out = core
        return out.upper() if case == 'upper' else out

    def caption_chunks(self, words):
        cfg = self._caption_cfg()
        per, maxc = int(cfg.get('words_per_cue', 3)), int(cfg.get('max_chars', 16))
        spk_cuts = [s['frame'] / F for k, s in enumerate(self.seg) if k and s['speaker'] != self.seg[k - 1]['speaker']]
        out, cur = [], []
        for i, w in enumerate(words):
            if not self.disp(w['text']):
                continue
            cur.append(w)
            nxt = next((x for x in words[i + 1:] if self.disp(x['text'])), None)
            L = len(' '.join(self.disp(x['text']) for x in cur))
            hard = w['text'][-1:] in '.!?' or nxt is None or nxt['start'] - w['end'] > .28 or any(w['start'] < c <= nxt['start'] + .02 for c in spk_cuts)
            if hard or len(cur) >= per or (nxt and L + len(self.disp(nxt['text'])) > maxc) or (w['text'][-1:] == ',' and len(cur) >= 2):
                if not hard and len(cur) > 1 and self.disp(w['text']).lower().strip(',') in WEAK_END:
                    carry = cur.pop()    # never end a caption on the word that opens the next phrase
                    out.append(cur)
                    cur = [carry]
                else:
                    out.append(cur)
                    cur = []
        if cur:
            out.append(cur)
        merged, most = [], int(cfg.get('max_words', per + 1))
        for c in out:   # a cue on screen under 0.2 s is a flash: fold it into the next one
            if merged and c[0]['start'] - merged[-1][0]['start'] < .2 and len(merged[-1]) + len(c) <= most:
                merged[-1] = merged[-1] + c
            else:
                merged.append(c)
        return merged
