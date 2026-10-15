"""Sphere carousel (carousel-orbit): Cards ride a spinning 3D Fibonacci sphere behind the head, billboarded to camera, sized by distance, in fast-slow-fast swings.

Port of the HyperFrames registry block carousel-orbit-1 (Copyright HeyGen, Apache License 2.0), re-laid out for 9:16. The rig math
lives in effects/_lib/carousel_rig.py (ported to Python and baked into per-frame GSAP keyframes); the layout, tiles,
dimming and labels live in effects/_lib/carousel_port.py. See CREDITS.md.
"""
import importlib.util, os, sys

META = {
    'id': 'carousel-orbit', 'name': 'Sphere carousel', 'category': 'carousel',
    'when': 'A set of many things (work samples, clients, posts) where the volume is the point: 8 to 16 tiles swirl behind the head.',
    'never': 'Never tiles the speaker does not name or imply (no stock filler). Never on a line where the face turns away.',
    'params': {'on': 'phrase that brings the carousel in', 'tiles': '[{"title", "src"?, "sub"?, "kicker"?}] 6 to 16; src is an image, else a word tile is drawn',
               'hold': 'seconds on screen, default 3.4', 'speed': 'motion speed multiplier, default 1 (the registry timing)',
               'size': 'layout scale multiplier, default 1', 'place': 'around or above the head; default picks the one where the speakers hide the least', 'until': 'optional phrase to clear before', 'sfx': 'optional sound name (e.g. swipe)'},
    'sfx': ['swipe'], 'source': 'hyperframes-registry:carousel-orbit-1', 'credit': 'HeyGen (HyperFrames registry carousel-orbit-1), adapted to 9:16 and our effect contract',
    'license': 'Apache-2.0',
}


def _load(name):
    if name not in sys.modules:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_lib', name + '.py')
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules[name] = mod
    return sys.modules[name]


def build(g, ctx):
    _load('carousel_port').run(g, ctx, 'orbit', _load('rk3d'), _load('carousel_rig'), 6, 16)


def describe(g, beat):
    names = ', '.join(f'"{t.get("title", "")}"' for t in g['tiles'])
    return f'On “{g["on"]}” {len(g["tiles"])} cards swirl on a spinning sphere behind the head: {names}. It holds {beat["hold"]:.1f} s.'
