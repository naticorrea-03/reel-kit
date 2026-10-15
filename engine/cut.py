#!/usr/bin/env python3
"""Script-level cut straight from the source: python3 engine/cut.py <project_dir> <slug> [--words path]

clips.json gives each clip a "segments" list: the speaker's exact sentences, in the order you want them, each with
"at" (seconds in the source, roughly where it is said) and "spk" (a speaker key from project.json).

1. Each segment's text is aligned to the word transcript (engine/transcribe.py) near its "at" hint.
2. Edges snap to the quietest 10 ms inside the gap to the neighbouring word (never into a kept or dropped word).
3. Fillers (um, uh) inside a segment are cut out.
4. Shots: every segment gets a different zoom than the one before (hides the jump cut), from the profile's zoom
   cycle. Segments over 3.2 s split at their biggest internal pause into two shots.
5. Video parts render from the source (HDR sources are tone-mapped to SDR), cropped to 9:16 around the speaker's head,
   1080x1920, exact frame counts; audio per segment gets 12 ms fades; both concatenate frame-exact into
   clips/<slug>/assets/aroll.mp4.
Writes cut.words.json (cut timeline), segments.json (shots: frame, frames, zoom, speaker, src), cut.txt (the script).
"""
import concurrent.futures as cf
import difflib, json, os, platform, re, struct, subprocess, sys, wave

F = 30
FILLERS = {'um', 'uh', 'umm', 'uhm', 'erm', 'hmm'}
DEFAULT_ZOOMS = [2.4, 1.9, 2.2, 1.8]   # no full-body look: 1.5-1.6 still showed boots, so 1.8 is the floor


def norm(s):
    s = s.lower().replace('-', ' ').replace('.', ' ')
    s = re.sub(r"[^a-z0-9' ]", ' ', s)
    return s.split()


# Face height as a share of the 1080x1920 frame, per shot in the cycle. Measured on the interview reels a reviewer
# approved (2026-10-14): close 0.13, medium 0.10. Zooms come from these targets, so a wide two-shot and a waist-up
# selfie both land at the same framing. A fixed zoom list was tuned on one wide source and filled the frame with a
# face on a selfie source, so every graphic collided with it.
FACE_TARGETS = [0.13, 0.10, 0.12, 0.098]
FACE_AT_1 = {}   # speaker -> face height share at zoom 1, filled by framing()
REFERENCE_FACE_AT_1 = 0.054   # reference framing the zoom-number defaults were tuned on


def framing(src, SW, SH, BW, BH, segments, speakers, HEADS, explicit, slug, OUT_DIR):
    """zoom cycle per speaker. Explicit zooms (clip, project, or profile) win; otherwise measured from the face."""
    if explicit:
        return {k: list(explicit) for k in speakers}
    fbin = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audit', 'faces')
    zmax = max(1.0, BW / 900)          # never upscale more than 1.2x
    if not os.path.exists(fbin):
        print(f'WARN {slug}: no face detector (run engine/doctor.py), using the default zoom cycle {DEFAULT_ZOOMS}')
        return {k: list(DEFAULT_ZOOMS) for k in speakers}
    os.makedirs(OUT_DIR, exist_ok=True)
    sc = 540 / SW
    cycles = {}
    for spk in speakers:
        times = [x['at'] + .6 for x in segments if x['spk'] == spk][:4]
        hs, centers = [], []
        for i, t in enumerate(times):
            png = os.path.join(OUT_DIR, f'_face{i}.png')
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{t:.2f}', '-i', src, '-frames:v', '1', '-vf', 'scale=540:-2', png], check=True)
            boxes = json.loads(subprocess.run([fbin, png], capture_output=True, text=True, check=True).stdout or '{}').get(png, [])
            os.remove(png)
            if not boxes:
                continue
            hx = HEADS.get(spk, (.5, .42))[0]
            x, y, w, h = min(boxes, key=lambda b: abs((b[0] + b[2] / 2) / sc / SW - hx))
            hs.append(h / sc / BH)
            centers.append(((x + w / 2) / sc / SW, (y + h / 2) / sc / SH))
        if not hs:
            print(f'WARN {slug}: no face found for speaker {spk}, using the default zoom cycle')
            cycles[spk] = list(DEFAULT_ZOOMS)
            continue
        fh = sorted(hs)[len(hs) // 2]
        if 'head' not in speakers[spk]:
            cx, cy = sorted(centers)[len(centers) // 2]
            HEADS[spk] = (cx, cy)
        z = [round(min(zmax, max(1.0, t / fh)), 2) for t in FACE_TARGETS]
        if max(z) - min(z) < .15:      # the source is already close: keep a visible zoom change on every cut
            z = [round(min(zmax, 1.18), 2), 1.0, round(min(zmax, 1.1), 2), 1.0]
        cycles[spk] = z
        FACE_AT_1[spk] = fh
        print(f'framing {slug} {spk}: face is {fh:.3f} of the frame at zoom 1, zoom cycle {z}')
    return cycles


def probe(src):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,color_transfer,color_primaries:stream_side_data=rotation', '-of', 'json', src],
                       capture_output=True, text=True, check=True)
    st = json.loads(r.stdout)['streams'][0]
    w, h = st['width'], st['height']
    rot = next((abs(int(d.get('rotation', 0))) for d in st.get('side_data_list', []) if 'rotation' in d), 0)
    if rot in (90, 270):
        w, h = h, w
    hdr = st.get('color_transfer') in ('arib-std-b67', 'smpte2084') or st.get('color_primaries') == 'bt2020'
    return w, h, hdr


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 2:
        sys.exit(__doc__)
    P, slug = os.path.abspath(os.path.expanduser(args[0])), args[1]
    proj = json.load(open(os.path.join(P, 'project.json')))
    src = os.path.expanduser(proj['source'])
    SRC = src if os.path.isabs(src) else os.path.join(P, src)
    if not os.path.exists(SRC):
        sys.exit(f'ERROR: source video not found: {SRC}')
    wpath = argv[argv.index('--words') + 1] if '--words' in argv else os.path.join(P, 'transcript', 'words.json')
    if not os.path.exists(wpath):
        sys.exit(f'ERROR: no transcript at {wpath}. Run: python3 engine/transcribe.py {P}')
    W = json.load(open(wpath))
    W = W['words'] if isinstance(W, dict) else W
    clips = json.load(open(os.path.join(P, proj.get('clips', 'clips.json'))))['clips']
    CL = next((c for c in clips if c['slug'] == slug), None)
    if CL is None or not CL.get('segments'):
        sys.exit(f'ERROR: clip {slug!r} not in clips.json or has no "segments"')
    prof_path = os.path.expanduser(proj.get('profile') or '~/.reel-kit/profile.json')
    prof_path = prof_path if os.path.isabs(prof_path) else os.path.join(P, prof_path)
    profile = json.load(open(prof_path)) if os.path.exists(prof_path) else {}
    EXPLICIT = CL.get('zooms') or proj.get('zooms') or profile.get('zooms')
    speakers = proj.get('speakers', {})
    for s in CL['segments']:
        if s['spk'] not in speakers:
            sys.exit(f'ERROR: segment speaker {s["spk"]!r} is not in project.json speakers ({", ".join(speakers)})')
    HEADS = {k: tuple(v.get('head', (0.5, 0.42))) for k, v in speakers.items()}
    SW, SH, HDR = probe(SRC)
    BW, BH = (SW, SW * 16 / 9) if SW / SH <= 9 / 16 else (SH * 9 / 16, SH)   # the largest 9:16 box in the source is zoom 1
    CYCLES = framing(SRC, SW, SH, BW, BH, CL['segments'], speakers, HEADS, EXPLICIT, slug, OUT_DIR=os.path.join(P, 'clips', slug))
    OUT = os.path.join(P, 'clips', slug)
    os.makedirs(os.path.join(OUT, 'assets'), exist_ok=True)
    PARTS = os.path.join(OUT, 'parts')
    os.makedirs(PARTS, exist_ok=True)
    for f in os.listdir(PARTS):   # parts from an older cut must never be concatenated into this one
        os.remove(os.path.join(PARTS, f))

    # ---------- audio envelope of the source (cached per project) ----------
    tdir = os.path.join(P, 'transcript')
    os.makedirs(tdir, exist_ok=True)
    ENV = os.path.join(tdir, 'env10ms.json')
    key = [os.path.abspath(SRC), os.path.getsize(SRC)]
    env = json.load(open(ENV)) if os.path.exists(ENV) else None
    if not env or env.get('key') != key:
        wav = os.path.join(tdir, 'src16k.wav')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', SRC, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
        with wave.open(wav) as wf:
            nfr = wf.getnframes()
            raw = wf.readframes(nfr)
        samples = struct.unpack(f'<{nfr}h', raw)
        hop = 160
        env = {'key': key, 'env': [int((sum(x * x for x in samples[k:k + hop]) / hop) ** .5) for k in range(0, nfr - hop, hop)]}
        json.dump(env, open(ENV, 'w'))
        os.remove(wav)
    ENVV = env['env']

    def quietest(a, b):
        """time of the quietest 10 ms frame in [a, b] (prefers the middle on ties)."""
        if b <= a:
            return a
        i0, i1 = max(0, int(a * 100)), min(len(ENVV) - 1, int(b * 100))
        if i1 <= i0:
            return a
        mid = (i0 + i1) / 2
        return min(range(i0, i1 + 1), key=lambda i: (ENVV[i], abs(i - mid))) / 100

    # ---------- align each segment ----------
    def align(seg):
        tok = norm(seg['text'])
        n = len(tok)
        best = None
        for i, w in enumerate(W):
            if abs(w['start'] - seg['at']) > 3.0:
                continue
            for m in (n - 2, n - 1, n, n + 1, n + 2):
                if m < 1 or i + m > len(W):
                    continue
                cand = []
                for x in W[i:i + m]:
                    cand += norm(x['text'])
                r = difflib.SequenceMatcher(None, tok, cand).ratio()
                score = r - abs(w['start'] - seg['at']) * .02
                if best is None or score > best[0]:
                    best = (score, i, i + m - 1, r)
        if not best or best[3] < .6:
            sys.exit(f'ERROR {slug}: cannot align {seg["text"]!r} near {seg["at"]} (best ratio {best[3] if best else 0:.2f}); check the "at" time and the exact words')
        return best[1], best[2], best[3]

    segs = []
    for s in CL['segments']:
        i, j, r = align(s)
        run = []
        for k in range(i, j + 1):   # split out fillers inside the run
            if norm(W[k]['text']) and norm(W[k]['text'])[0] in FILLERS:
                if run:
                    segs.append({'i': run[0], 'j': run[-1], 'spk': s['spk'], 'ratio': r})
                    run = []
            else:
                run.append(k)
        if run:
            segs.append({'i': run[0], 'j': run[-1], 'spk': s['spk'], 'ratio': r})

    for s in segs:
        i, j = s['i'], s['j']
        prev_end = W[i - 1]['end'] if i > 0 else 0
        next_start = W[j + 1]['start'] if j + 1 < len(W) else W[j]['end'] + 1
        a, b = W[i]['start'], W[j]['end']
        lo = max(prev_end, a - .25)
        s['in'] = quietest(lo, a + .02) if a - lo > .03 else max(lo, a - .02)
        hi = min(next_start, b + .30)
        s['out'] = quietest(b - .02, hi) if hi - b > .03 else min(hi, b + .02)
        s['in'] = max(prev_end - .01, s['in'] - .02)
        s['out'] = min(next_start + .01, s['out'] + .03)

    merged = []   # segments that are back-to-back in the source play as one
    for s in segs:
        if merged and merged[-1]['j'] + 1 == s['i'] and s['in'] - merged[-1]['out'] < .12 and merged[-1]['spk'] == s['spk']:
            merged[-1]['j'] = s['j']
            merged[-1]['out'] = s['out']
        else:
            merged.append(dict(s))
    segs = merged

    t = 0
    for s in segs:   # frame grid
        s['frames'] = max(6, round((s['out'] - s['in']) * F))
        s['frame'] = t
        t += s['frames']
    TOTAL = t

    # ---------- shots ----------
    shots, zi, prev_z = [], 0, None
    for s in segs:
        pieces = [(s['frame'], s['frames'])]
        if s['frames'] > 3.2 * F:   # split at the biggest internal pause
            gaps = [(W[k + 1]['start'] - W[k]['end'], W[k]['end']) for k in range(s['i'], s['j'])]
            gaps = [g for g in gaps if 1.2 < g[1] - s['in'] < (s['out'] - s['in']) - 1.2]
            if gaps:
                g = max(gaps)
                cut = s['frame'] + round((g[1] + min(g[0], .1) / 2 - s['in']) * F)
                pieces = [(s['frame'], cut - s['frame']), (cut, s['frame'] + s['frames'] - cut)]
        for fr, nfr in pieces:
            ZC = CYCLES[s['spk']]
            z = ZC[zi % len(ZC)]
            zi += 1
            if z == prev_z:
                z = ZC[zi % len(ZC)]
                zi += 1
            prev_z = z
            shots.append({'frame': fr, 'frames': nfr, 'zoom': z, 'speaker': s['spk'], 'src': s['in'] + (fr - s['frame']) / F,
                          'face': round(z * FACE_AT_1.get(s['spk'], REFERENCE_FACE_AT_1), 3)})

    ZMAX_USED = max(max(c) for c in CYCLES.values())
    worst = BW / ZMAX_USED
    if worst < 1080 * .8:
        print(f'WARN {slug}: zoom {ZMAX_USED} crops to {worst:.0f} px wide and upscales {1080 / worst:.2f}x; expect softness')
    VF0 = ('format=yuv420p10le,colorspace=all=bt709:iall=bt2020:itrc=bt2020-10:format=yuv420p,eq=saturation=1.12:contrast=1.04'
           if HDR else 'format=yuv420p')   # brew ffmpeg has no zscale/libplacebo; colorspace works for SDR mezzanines

    def crop(z, spk):
        hx, hy = HEADS.get(spk, (0.5, 0.42))
        cw, ch = BW / z, BH / z
        cy = hy + (0.035 if z >= 1.8 else 0.06 if z >= 1.3 else 0.08)
        cx = min(max(hx, cw / SW / 2), 1 - cw / SW / 2)
        cy = min(max(cy, ch / SH / 2), 1 - ch / SH / 2)
        w, h = round(cw / 2) * 2, round(ch / 2) * 2
        return f'crop={w}:{h}:{round(cx * SW - w / 2)}:{round(cy * SH - h / 2)}'

    hw = ['-hwaccel', 'videotoolbox'] if platform.system() == 'Darwin' else []

    def vpart(k):
        s = shots[k]
        p = os.path.join(PARTS, f'v{k:03d}.mp4')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y'] + hw + ['-ss', f"{s['src']:.4f}", '-i', SRC, '-an', '-vf',
                        f"fps={F},{VF0},{crop(s['zoom'], s['speaker'])},scale=1080:1920:flags=lanczos,setsar=1",
                        '-frames:v', str(s['frames']), '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                        '-g', '30', '-keyint_min', '30', '-r', str(F), p], check=True)
        return p

    def apart(k):
        s = segs[k]
        d = s['frames'] / F
        p = os.path.join(PARTS, f'a{k:03d}.wav')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', f"{s['in']:.4f}", '-t', f'{d:.4f}', '-i', SRC,
                        '-vn', '-ac', '1', '-ar', '48000', '-af', f'afade=t=in:d=0.012,afade=t=out:st={d - .012:.4f}:d=0.012,apad',
                        '-t', f'{d:.4f}', '-c:a', 'pcm_s16le', p], check=True)
        return p

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        vparts = list(ex.map(vpart, range(len(shots))))
        aparts = list(ex.map(apart, range(len(segs))))
    for name, parts in (('v.txt', vparts), ('a.txt', aparts)):
        with open(os.path.join(PARTS, name), 'w') as fh:
            fh.write(''.join(f"file '{p}'\n" for p in parts))
    aroll = os.path.join(OUT, 'assets', 'aroll.mp4')
    for f in ('subject.webm', '.tailpad', 'aroll_nopad.mp4', 'subject_nopad.webm'):   # a new cut invalidates the old cutout and pad
        if os.path.exists(os.path.join(OUT, 'assets', f)):
            os.remove(os.path.join(OUT, 'assets', f))
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(PARTS, 'v.txt'),
                    '-f', 'concat', '-safe', '0', '-i', os.path.join(PARTS, 'a.txt'), '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', aroll], check=True)

    # ---------- words on the cut timeline ----------
    cw = []
    for s in segs:
        for k in range(s['i'], s['j'] + 1):
            w = W[k]
            if norm(w['text']) and norm(w['text'])[0] in FILLERS:
                continue
            st = s['frame'] / F + max(0.0, w['start'] - s['in'])
            en = s['frame'] / F + min(s['frames'] / F, w['end'] - s['in'])
            cw.append({'text': w['text'].strip(), 'start': round(st, 3), 'end': round(max(en, st + .05), 3), 'speaker': s['spk']})
    json.dump({'text': ' '.join(w['text'] for w in cw), 'words': cw}, open(os.path.join(OUT, 'cut.words.json'), 'w'), indent=1)
    json.dump(shots, open(os.path.join(OUT, 'segments.json'), 'w'), indent=1)
    json.dump(segs, open(os.path.join(OUT, 'source_segments.json'), 'w'), indent=1)
    with open(os.path.join(OUT, 'cut.txt'), 'w') as fh:
        for s in segs:
            fh.write(f"[{s['frame'] / F:6.2f}] {s['spk']} {' '.join(W[k]['text'] for k in range(s['i'], s['j'] + 1))}   "
                     f"(src {s['in']:.2f}-{s['out']:.2f}, match {s['ratio']:.2f})\n")
    dur = sorted(x['frames'] / F for x in shots)
    print(f'{slug}: {len(segs)} segments, {len(shots)} shots, {TOTAL / F:.2f}s, median shot {dur[len(dur) // 2]:.2f}s'
          f'{", HDR tone-mapped" if HDR else ""}. Next: engine/cutout.sh {os.path.relpath(OUT)} && engine/tailpad.sh {os.path.relpath(OUT)}')


if __name__ == '__main__':
    main(sys.argv[1:])
