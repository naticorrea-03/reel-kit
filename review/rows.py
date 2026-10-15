#!/usr/bin/env python3
"""review/rows.py <project> --bucket <id> [options] : loads rendered reels into the review page.

Reads, per clip: renders/phone/<slug>.mp4 (else renders/<slug>.mp4), audits/<slug>/report.json (layout audit),
audits/<slug>/beats.json (storyboard with frame strips, else clips/<slug>/plan.json), and when present
audits/<slug>/watch.json ({"source": "...", "flags": [{cat, t, text, verdict, why}]}) and audits/<slug>/ears.json
([{t, said, alt}] words the transcripts disagree on).

Two targets:
  --local                 merge into <project>/review/state.json for review/serve.py (keeps every review and note)
  --out DIR               write one JSON file per db document (DIR/<collection>/<id>.json) for an artifact db batch.
                          Pass --urls urls.json ({"slug": "asset url"}) and --strips strips.json
                          ({"slug/b01": "asset url"}) after uploading. --uploads prints what to upload first.
Options: --bucket-name "Name"  --batch <id> (default: project folder name)  --label "Batch label"  --slugs a,b
"""
import argparse, datetime, json, os, re, subprocess, sys

ap = argparse.ArgumentParser(usage=__doc__)
ap.add_argument('project'); ap.add_argument('--bucket', required=True); ap.add_argument('--bucket-name')
ap.add_argument('--batch'); ap.add_argument('--label'); ap.add_argument('--slugs')
ap.add_argument('--local', action='store_true'); ap.add_argument('--out'); ap.add_argument('--uploads', action='store_true')
ap.add_argument('--urls'); ap.add_argument('--strips')
ap.add_argument('--profile', default='~/.reel-kit/profile.json')
a = ap.parse_args()
P = os.path.abspath(os.path.expanduser(a.project))
J = lambda p, d=None: json.load(open(p)) if p and os.path.exists(p) else d
urls, strips = J(a.urls, {}), J(a.strips, {})
batch = a.batch or re.sub(r'[^a-z0-9-]+', '-', os.path.basename(P).lower()).strip('-')
label = a.label or f'{os.path.basename(P)} · {datetime.date.today():%b %-d}'
clips_spec = {c['slug']: c for c in (J(os.path.join(P, 'clips.json'), {}) or {}).get('clips', [])}


def video_of(s):
    for rel in (f'renders/phone/{s}.mp4', f'renders/{s}.mp4'):
        if os.path.exists(os.path.join(P, rel)):
            return rel
    return None


slugs = a.slugs.split(',') if a.slugs else [s for s in clips_spec if video_of(s)]
if not slugs:
    sys.exit('no rendered clips found (renders/phone/<slug>.mp4 or renders/<slug>.mp4)')


def dur(rel):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', os.path.join(P, rel)],
                       capture_output=True, text=True)
    return round(float(r.stdout.strip() or 0), 2)


def title(s):
    c = clips_spec.get(s, {})
    if c.get('title'):
        return c['title']
    hook = c.get('hook')
    return ' '.join(hook).capitalize() if isinstance(hook, list) and hook else s.replace('-', ' ').capitalize()


def audit(s):
    r = J(os.path.join(P, 'audits', s, 'report.json'), {}) or {}
    items = [{'sev': i.get('sev', 'error'), 'rule': i.get('rule', ''), 't': i.get('t0', 0), 'text': i.get('msg', ''), 'why': ''}
             for i in r.get('issues', [])]
    return {'errors': sum(i['sev'] == 'error' for i in items), 'warnings': sum(i['sev'] != 'error' for i in items), 'items': items}


def watch(s, vid):
    p = os.path.join(P, 'audits', s, 'watch.json')
    if not os.path.exists(p) or os.path.getmtime(p) < os.path.getmtime(os.path.join(P, vid)):
        return {'flags': []}   # the watcher never saw this render
    return J(p)


def beats(s, local):
    keep = ('id', 't0', 't1', 'kind', 'kindName', 'shot', 'text', 'said', 'plan', 'sounds')
    bj = J(os.path.join(P, 'audits', s, 'beats.json'))
    src = (bj or J(os.path.join(P, 'clips', s, 'plan.json'), {}) or {}).get('beats', [])
    out = []
    for b in src:
        row = {k: b.get(k) for k in keep}
        st = b.get('strip')
        row['strip'] = ('files/' + st) if (local and st) else strips.get(f"{s}/{b['id']}", '')
        out.append(row)
    return out


def rows(local):
    out = []
    for i, s in enumerate(slugs):
        vid = video_of(s)
        if not vid:
            sys.exit(f'{s}: no render')
        out.append({'id': f'{batch}--{s}', 'bucket': a.bucket, 'batch': batch, 'batchLabel': label, 'slug': s, 'title': title(s),
                    'order': i, 'dur': dur(vid), 'video': ('files/' + vid) if local else urls.get(s, ''),
                    'audit': audit(s), 'watch': watch(s, vid), 'beats': beats(s, local),
                    'ears': J(os.path.join(P, 'audits', s, 'ears.json'), [])})
    return out


def brand():
    pr = J(os.path.expanduser(a.profile), {}) or {}
    b = pr.get('brand', {})
    name = pr.get('name', '')
    mark = ''.join(w[0] for w in name.split()[:2]).upper() or 'RK'
    return {k: v for k, v in {'mark': mark, 'accent': b.get('colors', {}).get('accent'),
                              'display': b.get('fonts', {}).get('serif') or b.get('fonts', {}).get('display'),
                              'body': b.get('fonts', {}).get('body')}.items() if v}


if a.uploads:
    up = {'videos': {s: os.path.join(P, video_of(s)) for s in slugs}, 'strips': {}}
    for s in slugs:
        for b in (J(os.path.join(P, 'audits', s, 'beats.json'), {}) or {}).get('beats', []):
            if b.get('strip'):
                up['strips'][f"{s}/{b['id']}"] = os.path.join(P, b['strip'])
    print(json.dumps(up, indent=1))
elif a.local:
    sp = os.path.join(P, 'review', 'state.json')
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    st = J(sp, {}) or {}
    st.setdefault('reviews', {}); st.setdefault('notes', [])
    st['brand'] = {**brand(), **st.get('brand_override', {})}
    bk = st.setdefault('buckets', [])
    if not any(b['id'] == a.bucket for b in bk):
        bk.append({'id': a.bucket, 'name': a.bucket_name or a.bucket.replace('-', ' ').title(), 'order': len(bk)})
    new = rows(True)
    ids = {r['id'] for r in new}
    st['clips'] = [c for c in st.get('clips', []) if c['id'] not in ids] + new
    json.dump(st, open(sp, 'w'), indent=1, ensure_ascii=False)
    print(f'loaded {len(new)} clips into {os.path.relpath(sp, P)}. Run: python3 review/serve.py {P}')
elif a.out:
    O = os.path.abspath(a.out)
    for col in ('clips', 'buckets', 'settings'):
        os.makedirs(os.path.join(O, col), exist_ok=True)
    for r in rows(False):
        json.dump({k: v for k, v in r.items() if k != 'id'}, open(os.path.join(O, 'clips', r['id'] + '.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump({'name': a.bucket_name or a.bucket.replace('-', ' ').title(), 'order': 0},
              open(os.path.join(O, 'buckets', a.bucket + '.json'), 'w'), indent=1)
    json.dump(brand(), open(os.path.join(O, 'settings', 'brand.json'), 'w'), indent=1)
    print(json.dumps(sorted(os.path.relpath(os.path.join(d, f), O) for d, _, fs in os.walk(O) for f in fs), indent=1))
else:
    sys.exit('pick a target: --local, --out DIR, or --uploads')
