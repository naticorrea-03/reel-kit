#!/usr/bin/env python3
"""Get the sound effects listed in assets/sfx/manifest.json into assets/sfx/<name>.mp3.

  python3 engine/fetch_sfx.py              download every sound that has a url; list the ones you must fetch by hand
  python3 engine/fetch_sfx.py --from DIR   copy <name>.mp3 files from a folder you already have (e.g. an older project)
  python3 engine/fetch_sfx.py --check      only report what is present and what is missing

Sounds are never committed (Pixabay license). After you drop a file in, trim any silence before the sound starts:
  ffmpeg -i in.mp3 -af silenceremove=start_periods=1:start_threshold=-45dB out.mp3
"""
import json, os, shutil, subprocess, sys, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(REPO, 'assets', 'sfx')
MAN = json.load(open(os.path.join(DIR, 'manifest.json')))


def lead_silence(path):
    """seconds of near-silence before the first sound (late files make every hit late)."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'silencedetect=noise=-45dB:d=0.05', '-f', 'null', '-'],
                       capture_output=True, text=True)
    lines = [l for l in r.stderr.splitlines() if 'silence_' in l]
    for k, line in enumerate(lines):
        if 'silence_start:' in line and float(line.split('silence_start:')[1].split()[0]) <= .01:
            end = next((l for l in lines[k + 1:] if 'silence_end:' in l), None)
            return float(end.split('silence_end:')[1].split('|')[0]) if end else 0.0
    return 0.0


def main(argv):
    src = argv[argv.index('--from') + 1] if '--from' in argv else None
    check = '--check' in argv
    missing = []
    for s in MAN['sounds']:
        dst = os.path.join(DIR, s['name'] + '.mp3')
        if os.path.exists(dst) and not src:
            continue
        if src and not check:
            cand = os.path.join(os.path.expanduser(src), s['name'] + '.mp3')
            if os.path.exists(cand):
                shutil.copy2(cand, dst)
                print(f'copied   {s["name"]}')
                continue
        if s.get('url') and not check:
            try:
                req = urllib.request.Request(s['url'], headers={'User-Agent': 'Mozilla/5.0 reel-kit'})
                with urllib.request.urlopen(req, timeout=30) as r, open(dst, 'wb') as fh:
                    fh.write(r.read())
                print(f'fetched  {s["name"]}')
                continue
            except Exception as e:
                print(f'failed   {s["name"]}: {e}')
        if not os.path.exists(dst):
            missing.append(s)
    for s in MAN['sounds']:
        dst = os.path.join(DIR, s['name'] + '.mp3')
        if os.path.exists(dst):
            lead = lead_silence(dst)
            if lead > .05:
                print(f'WARN {s["name"]}.mp3 starts with {lead:.2f} s of silence; trim it so hits land on time')
    if missing:
        print(f'\n{len(missing)} sound(s) to get by hand (free, Pixabay Content License):')
        for s in missing:
            q = urllib.request.quote(s['query'])
            print(f'  {s["name"]:16s} {s["use"]}\n  {"":16s} search: https://pixabay.com/sound-effects/search/{q}/  ->  save as {os.path.relpath(os.path.join(DIR, s["name"] + ".mp3"))}')
        print('\nThe build leaves a missing sound silent and says so. Nothing else breaks.')
    else:
        print(f'all {len(MAN["sounds"])} sounds present in {os.path.relpath(DIR)}')


if __name__ == '__main__':
    main(sys.argv[1:])
