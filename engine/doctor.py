#!/usr/bin/env python3
"""doctor.py : check everything reel-kit needs, and compile the face detector.

Checks ffmpeg/ffprobe (with libvpx-vp9), node >= 22, python3 >= 3.9 with Pillow and numpy, faster-whisper,
the macOS Vision face detector (compiles engine/audit/faces from faces.swift), hyperframes and its headless Chrome,
and the sound effects. Exit 1 if anything required is missing.
"""
import os, platform, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HF_VERSION = os.environ.get('HF_VERSION', '0.8.61')
bad = []


def ok(name, good, fix='', required=True):
    print(f'  {"ok  " if good else ("MISS" if required else "warn")}  {name}' + ('' if good else f'   -> {fix}'))
    if not good and required:
        bad.append(name)


def run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, '', str(e))


print('reel-kit doctor')
ff = shutil.which('ffmpeg')
ok('ffmpeg', bool(ff), 'brew install ffmpeg')
ok('ffprobe', bool(shutil.which('ffprobe')), 'brew install ffmpeg')
if ff:
    ok('ffmpeg has libvpx-vp9 (alpha cutouts)', 'libvpx-vp9' in run(['ffmpeg', '-hide_banner', '-encoders']).stdout, 'brew reinstall ffmpeg')
node = shutil.which('node')
nv = run(['node', '-v']).stdout.strip().lstrip('v') if node else ''
ok(f'node >= 22 (have {nv or "none"})', bool(nv) and int(nv.split('.')[0]) >= 22, 'install Node 22+ (nvm install 22)')
ok(f'python >= 3.9 (have {platform.python_version()})', sys.version_info >= (3, 9), 'install a newer python3')
for mod, pip in (('PIL', 'pillow'), ('numpy', 'numpy')):
    try:
        __import__(mod)
        ok(f'python {pip}', True)
    except ImportError:
        ok(f'python {pip}', False, f'python3 -m pip install {pip}')
try:
    __import__('faster_whisper')
    ok('faster-whisper (engine/transcribe.py)', True)
except ImportError:
    ok('faster-whisper (engine/transcribe.py)', False, 'python3 -m pip install faster-whisper', required=False)

if platform.system() == 'Darwin':
    try:
        from fxlib import ensure_faces
        ensure_faces()
        ok('face detector (engine/audit/faces, macOS Vision)', True)
    except SystemExit as e:
        ok('face detector (engine/audit/faces, macOS Vision)', False, str(e))
else:
    ok('face detector', False, 'needs macOS: graphics placement and the face audit use Apple Vision. Run reel-kit on a Mac.')

if node:
    r = run(['npx', '--yes', f'hyperframes@{HF_VERSION}', 'browser', 'path'], timeout=600)
    chrome = (r.stdout.strip().splitlines() or [''])[-1]
    ok(f'hyperframes@{HF_VERSION} headless Chrome', r.returncode == 0 and os.path.exists(chrome),
       f'npx --yes hyperframes@{HF_VERSION} browser ensure')

r = run([sys.executable, os.path.join(REPO, 'engine', 'fetch_sfx.py'), '--check'])
ok('sound effects in assets/sfx', 'all ' in r.stdout, 'python3 engine/fetch_sfx.py (missing sounds stay silent)', required=False)
print()
if bad:
    print(f'{len(bad)} required item(s) missing: ' + ', '.join(bad))
    sys.exit(1)
print('ready')
