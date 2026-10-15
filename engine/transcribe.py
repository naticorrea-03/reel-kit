#!/usr/bin/env python3
"""transcribe.py <project_dir> [--model medium] [--force] : word-level transcript of project.json "source".

Writes <project>/transcript/words.json as {"model", "source", "words": [{"text", "start", "end"}]}, cached: it reruns only
when the source file, its size or the model changes (or with --force). Uses faster-whisper locally (free, no API).
Whisper mishears names. Proofread names into project.json "caption_fixes" after reading the transcript.
"""
import json, os, sys


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    P = os.path.abspath(os.path.expanduser(args[0]))
    model = argv[argv.index('--model') + 1] if '--model' in argv else os.environ.get('REELKIT_WHISPER', 'medium')
    proj = json.load(open(os.path.join(P, 'project.json')))
    src = os.path.expanduser(proj['source'])
    if not os.path.isabs(src):
        src = os.path.join(P, src)
    if not os.path.exists(src):
        sys.exit(f'ERROR: source video not found: {src}')
    out_dir = os.path.join(P, 'transcript')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'words.json')
    key = {'source': os.path.abspath(src), 'size': os.path.getsize(src), 'mtime': int(os.path.getmtime(src)), 'model': model}
    if os.path.exists(out) and '--force' not in argv:
        old = json.load(open(out))
        if old.get('key') == key:
            print(f'transcript cached: {os.path.relpath(out, P)} ({len(old["words"])} words, {model})')
            return
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit('ERROR: faster-whisper is not installed. python3 -m pip install faster-whisper')
    print(f'transcribing {os.path.basename(src)} with faster-whisper {model} (local, this can take a while)...')
    wm = WhisperModel(model, device='auto', compute_type='auto')
    segs, info = wm.transcribe(src, word_timestamps=True, vad_filter=False, language=proj.get('language'))
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append({'text': t, 'start': round(w.start, 3), 'end': round(w.end, 3)})
        print(f'  {s.end:7.1f}s  {s.text.strip()[:70]}', flush=True)
    json.dump({'key': key, 'model': model, 'language': info.language, 'words': words}, open(out, 'w'), indent=1)
    with open(os.path.join(out_dir, 'transcript.txt'), 'w') as fh:   # readable copy with times, for picking the hot takes
        line, t0 = [], None
        for w in words:
            t0 = w['start'] if t0 is None else t0
            line.append(w['text'])
            if w['text'][-1:] in '.?!':
                fh.write(f'[{t0:7.2f}] {" ".join(line)}\n')
                line, t0 = [], None
        if line:
            fh.write(f'[{t0:7.2f}] {" ".join(line)}\n')
    print(f'wrote {os.path.relpath(out, P)} ({len(words)} words) and transcript/transcript.txt')


if __name__ == '__main__':
    main(sys.argv[1:])
