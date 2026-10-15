#!/usr/bin/env python3
"""review/serve.py <project> [--port 8770] : the review page on this Mac, no claude.ai needed.

Serves review/review.html at http://127.0.0.1:<port>/ and keeps every decision and note in <project>/review/state.json,
the same shape the artifact db uses, so Claude reads feedback from that file. Load reels first with review/rows.py --local.
Only files inside <project> are served, and only to this machine.
"""
import argparse, json, os, re, threading, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ap = argparse.ArgumentParser(usage=__doc__)
ap.add_argument('project'); ap.add_argument('--port', type=int, default=8770)
a = ap.parse_args()
P = os.path.realpath(os.path.expanduser(a.project))
SP = os.path.join(P, 'review', 'state.json')
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'review.html')
LOCK = threading.Lock()
TYPES = {'.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webm': 'video/webm'}
if not os.path.exists(SP):
    raise SystemExit(f'no {SP}. Load reels first: python3 review/rows.py {P} --bucket <id> --local')


def load():
    return json.load(open(SP))


def save(st):
    tmp = SP + '.tmp'
    json.dump(st, open(tmp, 'w'), indent=1, ensure_ascii=False)
    os.replace(tmp, SP)


class H(BaseHTTPRequestHandler):
    def log_message(self, *x):
        pass

    def send(self, code, body, ctype='application/json'):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            return self.send(200, open(PAGE, 'rb').read(), 'text/html; charset=utf-8')
        if path == '/api/state':
            with LOCK:
                return self.send(200, json.dumps(load()))
        if path.startswith('/files/'):
            f = os.path.realpath(os.path.join(P, path[7:].replace('%20', ' ')))
            if not f.startswith(P + os.sep) or not os.path.isfile(f):
                return self.send(404, 'not found', 'text/plain')
            return self.file(f)
        self.send(404, 'not found', 'text/plain')

    def file(self, f):
        size = os.path.getsize(f); ctype = TYPES.get(os.path.splitext(f)[1].lower(), 'application/octet-stream')
        m = re.match(r'bytes=(\d*)-(\d*)', self.headers.get('Range', ''))
        start, end = 0, size - 1
        if m:   # range requests let the video seek
            start = int(m.group(1)) if m.group(1) else size - int(m.group(2))
            end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
            end = min(end, size - 1)
        self.send_response(206 if m else 200)
        self.send_header('Content-Type', ctype); self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if m:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with open(f, 'rb') as fh:
            fh.seek(start); left = end - start + 1
            try:
                while left > 0:
                    chunk = fh.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        except ValueError:
            return self.send(400, 'bad json', 'text/plain')
        with LOCK:
            st = load()
            if self.path == '/api/review' and body.get('id'):
                st.setdefault('reviews', {})[body.pop('id')] = body
            elif self.path == '/api/note' and body.get('clip') and str(body.get('text', '')).strip():
                st.setdefault('notes', []).append({**body, 'id': uuid.uuid4().hex[:12], 'at_ms': int(time.time() * 1000)})
            elif self.path == '/api/note/delete' and body.get('id'):
                st['notes'] = [n for n in st.get('notes', []) if n.get('id') != body['id']]
            else:
                return self.send(400, 'unknown request', 'text/plain')
            save(st)
            self.send(200, json.dumps(st))


print(f'review page: http://127.0.0.1:{a.port}/  (feedback saves to {os.path.relpath(SP)}; Ctrl+C stops it)')
ThreadingHTTPServer(('127.0.0.1', a.port), H).serve_forever()
