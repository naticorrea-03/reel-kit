#!/usr/bin/env python3
"""preview.py <effect_id> [demo_clip_dir] [--look id] [--start s] : render one effect alone over demo footage.

Writes effects/<id>/preview.mp4 (540x960, about 4.5 s) and effects/<id>/poster.jpg.
The demo clip folder (argument or env REELKIT_DEMO) is any built clip: it needs assets/aroll.mp4 and, for effects that
sit behind heads, assets/subject.webm. effects/<id>/demo.json gives {"said": "...", "graphic": {...}}: the words are
spread evenly over the preview so the graphic's "on" phrase lands where it would in a real reel.
"""
import json, os, shutil, subprocess, sys, tempfile

E = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(E)
DUR = 4.5


def main(argv):
    argv = list(argv)
    look = 'editorial'
    start = float(os.environ.get('REELKIT_DEMO_START', 0))
    for flag in ('--look', '--start'):
        if flag in argv:
            i = argv.index(flag)
            val = argv[i + 1]
            del argv[i:i + 2]
            if flag == '--look':
                look = val
            else:
                start = float(val)
    if not argv:
        sys.exit(__doc__)
    eid = argv[0]
    demo_clip = os.path.expanduser(argv[1] if len(argv) > 1 else os.environ.get('REELKIT_DEMO', ''))
    fxdir = os.path.join(REPO, 'effects', eid)
    if not os.path.exists(os.path.join(fxdir, 'demo.json')):
        sys.exit(f'ERROR: effects/{eid}/demo.json not found')
    if not demo_clip or not os.path.exists(os.path.join(demo_clip, 'assets', 'aroll.mp4')):
        sys.exit('ERROR: pass a demo clip folder (with assets/aroll.mp4) or set REELKIT_DEMO')
    demo = json.load(open(os.path.join(fxdir, 'demo.json')))
    tmp = tempfile.mkdtemp(prefix=f'rk-preview-{eid}-')
    C = os.path.join(tmp, 'clips', 'preview')
    os.makedirs(os.path.join(C, 'assets'))
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', f'{start:.2f}', '-t', f'{DUR}', '-i',
                    os.path.join(demo_clip, 'assets', 'aroll.mp4'), '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                    '-r', '30', '-c:a', 'aac', '-af', 'volume=0.6', os.path.join(C, 'assets', 'aroll.mp4')], check=True)
    sub = os.path.join(demo_clip, 'assets', 'subject.webm')
    if os.path.exists(sub):
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-c:v', 'libvpx-vp9', '-ss', f'{start:.2f}', '-t', f'{DUR}', '-i', sub,
                        '-vf', 'format=yuva420p', '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-b:v', '0', '-crf', '30', '-row-mt', '1',
                        '-auto-alt-ref', '0', os.path.join(C, 'assets', 'subject.webm')], check=True)
    words = demo['said'].split()
    span, t, out = 3.4, .35, []
    total = sum(len(w) + 2 for w in words)
    for w in words:   # spread the words over the preview, longer words take longer
        d = span * (len(w) + 2) / total
        out.append({'text': w, 'start': round(t, 3), 'end': round(t + d * .85, 3), 'speaker': 'A'})
        t += d
    json.dump({'words': out}, open(os.path.join(C, 'cut.words.json'), 'w'))
    shot = {'zoom': 2.2, 'face': .12}
    seg_src = os.path.join(demo_clip, 'segments.json')
    if os.path.exists(seg_src):
        shots = json.load(open(seg_src))
        shot = next((s for s in reversed(shots) if s['frame'] / 30 <= start + 1e-3), shots[0])
    json.dump([{'frame': 0, 'frames': int(DUR * 30), 'zoom': shot['zoom'], 'face': shot.get('face', shot['zoom'] * .054), 'speaker': 'A', 'src': 0}],
              open(os.path.join(C, 'segments.json'), 'w'))
    json.dump({'speakers': {'A': {'name': '', 'side': 'left'}}, 'profile': os.path.join(tmp, 'none.json')}, open(os.path.join(tmp, 'project.json'), 'w'))
    json.dump({'clips': [{'slug': 'preview', 'graphics': [demo['graphic']]}]}, open(os.path.join(tmp, 'clips.json'), 'w'))
    r = subprocess.run([sys.executable, os.path.join(E, 'build.py'), tmp, 'preview', '--look', look], capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        sys.exit(f'{eid}: preview build failed\n{r.stderr.strip()}')
    # every preview passes the same layout audit as a real reel: a preview that hides a face or clips text never ships
    a = subprocess.run(['bash', os.path.join(E, 'audit', 'audit.sh'), tmp, 'preview'], capture_output=True, text=True)
    rep = os.path.join(tmp, 'audits', 'preview', 'report.md')
    report = open(rep).read() if os.path.exists(rep) else (a.stdout + a.stderr)[-1500:]
    head = report.splitlines()[0] if report else 'no report'
    print(head.replace('preview', eid, 1))
    if ' 0 error(s)' not in head and os.environ.get('FORCE') != '1':
        sys.exit(f'{eid}: preview fails the layout audit (FORCE=1 renders anyway)\n{report}')
    raw = os.path.join(tmp, 'raw.mp4')
    r = subprocess.run(['npx', '--yes', f'hyperframes@{os.environ.get("HF_VERSION", "0.8.61")}', 'render', '.', '-o', raw, '--fps', '30'],
                       cwd=C, capture_output=True, text=True)
    if r.returncode or not os.path.exists(raw):
        sys.exit(f'{eid}: preview render failed\n{(r.stderr or r.stdout)[-1500:]}')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', raw, '-vf', 'scale=540:960', '-c:v', 'libx264', '-crf', '23',
                    '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
                    os.path.join(fxdir, 'preview.mp4')], check=True)
    plan = json.load(open(os.path.join(C, 'plan.json')))['beats']
    b = next((x for x in plan if x['kind'] == eid), plan[0] if plan else {'t0': 1, 't1': 3})
    tp = (b['t0'] + b['t1']) / 2
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', f'{tp:.2f}', '-i', raw, '-frames:v', '1', '-vf', 'scale=540:960',
                    '-q:v', '3', os.path.join(fxdir, 'poster.jpg')], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'{eid}: effects/{eid}/preview.mp4 + poster.jpg (poster at {tp:.2f} s)')


if __name__ == '__main__':
    main(sys.argv[1:])
