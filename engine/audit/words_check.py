#!/usr/bin/env python3
"""words_check.py <project_dir> <slug> [video] : re-transcribe the rendered reel and diff it against the cut's word list.
Catches words clipped or dropped by the cut, render or master. Exit 1 if under 95% match (95% or better is normal).
Uses `npx hyperframes transcribe` (local whisper small.en, free)."""
import difflib, json, os, re, subprocess, sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
P, s = os.path.abspath(os.path.expanduser(sys.argv[1])), sys.argv[2]
vid = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.join(P, 'renders', s + '.mp4')
O = os.path.join(P, 'audits', s, 'qa_words')
os.makedirs(O, exist_ok=True)
tj = os.path.join(O, 'transcript.json')
if os.path.exists(tj):
    os.remove(tj)   # a stale transcript must never pass as fresh
tok = lambda x: re.sub(r"[^a-z0-9' ]", ' ', x.lower().replace('$', '')).split()
r = subprocess.run(['npx', '-y', f'hyperframes@{os.environ.get("HF_VERSION", "0.8.61")}', 'transcribe', vid, '-d', O, '--json', '--model', 'small.en'],
                   capture_output=True, text=True)
if not os.path.exists(tj):
    sys.exit(f'# {s} words: transcription failed\n{r.stderr[-800:]}')
W = json.load(open(os.path.join(P, 'clips', s, 'cut.words.json')))
W = W['words'] if isinstance(W, dict) else W
H = json.load(open(tj))
H = H.get('words', H) if isinstance(H, dict) else H
exp = [t for w in W for t in tok(w['text'])]
heard = [t for w in H for t in tok(w['text'])]
sm = difflib.SequenceMatcher(None, exp, heard, autojunk=False)
miss = [' '.join(exp[a:b]) for op, a, b, _, _ in sm.get_opcodes() if op in ('delete', 'replace')]
ratio = sm.ratio()
print(f'# {s} words: {ratio:.0%} match' + (f'; check: {miss[:8]}' if miss else ''))
sys.exit(0 if ratio >= .95 else 1)
