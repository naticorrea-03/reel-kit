#!/usr/bin/env python3
"""guide/build.py [--pdf] : builds the Reel Kit guide from the repo itself.

Reads effects/*/effect.py META (without importing), looks/*.json, gallery/registry.json, and the previews in
effects/<id>/preview.mp4 + poster.jpg. Writes:
  guide/index.html  the repo copy; effect previews load straight from ../effects/<id>/ so a clone needs no copies
  guide/site.html   the published copy (gitignored); effect previews copied to guide/media/fx-* (also gitignored),
                    because a published page only sees files next to it
  with --pdf also guide/reel-kit-guide.pdf (posters instead of videos) through headless Chrome.
"""
import ast, re, html, json, os, shutil, subprocess, sys

G = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(G)
MEDIA = os.path.join(G, 'media')
os.makedirs(MEDIA, exist_ok=True)
E = html.escape
CAT_ORDER = ['text', 'captions', 'annotation', 'ui', 'social', 'popup', 'carousel', 'media', 'data', 'structure', 'transition']
CAT_NAME = {'text': 'Text', 'captions': 'Captions', 'annotation': 'Annotation', 'ui': 'App windows', 'social': 'Social',
            'popup': 'Popups', 'carousel': 'Carousels', 'media': 'Media', 'data': 'Data', 'structure': 'Structure',
            'transition': 'Transitions'}


def meta_of(path):
    tree = ast.parse(open(path).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'META' for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def effects():
    out = []
    root = os.path.join(REPO, 'effects')
    for eid in sorted(os.listdir(root)):
        p = os.path.join(root, eid, 'effect.py')
        if not os.path.exists(p):
            continue
        m = meta_of(p) or {}
        m.setdefault('id', eid)
        for kind, ext in (('preview', 'mp4'), ('poster', 'jpg')):
            src = os.path.join(root, eid, f'{kind}.{ext}')
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(MEDIA, f'fx-{eid}.{ext}'))
                m['_' + kind] = f'media/fx-{eid}.{ext}'
        out.append(m)
    out.sort(key=lambda m: (CAT_ORDER.index(m.get('category')) if m.get('category') in CAT_ORDER else 99, m.get('name', '')))
    return out


def looks():
    out = []
    for lid in ('editorial', 'punch', 'minimal', 'golden-hour', 'masthead', 'native'):
        p = os.path.join(REPO, 'looks', f'{lid}.json')
        if os.path.exists(p):
            L = json.load(open(p))
            L['_video'] = f'media/look-{lid}-phone.mp4' if os.path.exists(os.path.join(MEDIA, f'look-{lid}-phone.mp4')) else None
            L['_poster'] = f'media/look-{lid}.jpg' if os.path.exists(os.path.join(MEDIA, f'look-{lid}.jpg')) else None
            out.append(L)
    return out


LOOK_FACTS = {
    'editorial': ('Interviews, founders, anything that should feel premium and calm.',
                  'Italic serif punch lines, word-pill captions, cream cards, warm grade.'),
    'punch': ('Hot takes, numbers, energy. Feeds where the hook has one second.',
              'Huge heavy words behind the head, two-word caption stacks, hard cut punches, high contrast.'),
    'minimal': ('Documentary, teaching, expert explainers. Lets the person carry it.',
                'Small clean captions, lower-thirds, thin-rule cards, neutral grade, slow push-ins.'),
    'golden-hour': ('Lifestyle, creators, digital products. Warm rooms and soft light.',
                    'Serif cover title with a handwritten line, tiny serif word captions, butter italic punch lines, orbiting tiles, honey grade.'),
    'masthead': ('Founders and opinion pieces that should read like a magazine cover.',
                 'Giant condensed serif title behind the head, tracked caps kicker, serif captions on a forest plate, muted olive grade.'),
    'native': ('Tutorials, tools, quick tips. Looks like it was made in the app.',
               'White box captions that fill in as spoken, heavy caps hook with an orange italic accent, stickers and tags, true-to-life grade.'),
}

STEPS = [
    ('Install', 'Clone the repo and run the installer. It links five skills into Claude Code and checks ffmpeg, Node, Python and the face detector.',
     'git clone https://github.com/naticorrea-03/reel-kit ~/reel-kit\ncd ~/reel-kit && ./install.sh'),
    ('Set up your brand', 'One interview, once. Your colors, fonts, logo, look, caption style and the things you never want to see. Saved to ~/.reel-kit/profile.json.',
     '/reel-setup'),
    ('Make reels', 'Point it at a long video. It reads the whole transcript, picks the hot takes, writes each clip as a script, plans one graphic per beat, cuts, renders and masters.',
     '/reel-edit ~/Downloads/interview.mov'),
    ('Check before you watch', 'Layout audit on every sixth of a second, words check, loudness, and beat sheets Claude reads itself. Errors block the render.',
     '/reel-qa'),
    ('Review and give notes', 'Your reels land on a review page in your brand. Approve or redo each one, pin a note to the exact second, or comment on one storyboard beat. Claude reads every note before the next round. It can be a private claude.ai page you share with a client, or a page on your Mac.',
     '/reel-review'),
    ('Browse effects', 'Ask for what you need in plain words. "Add a popup when she says follow me." It picks from the library below.',
     '/reel-effects'),
]

RULES = [
    ('Hot takes, not topics.', 'A clip is one sharp claim and the line that pays it off. Length follows the thought, 20 or 90 seconds.'),
    ('Every graphic adds something.', 'A note that repeats the caption is refused by the build. No sparkles, no glows, no filler words behind the head.'),
    ('Show the noun on the word.', 'Named company, real logo. Named paper, real screenshot. It lands on the frame the word is said.'),
    ('Sounds are literal.', 'Cash register on money, shutter on a photo, silence otherwise.'),
    ('Nothing covers a face.', 'Placement reads the cutout and the face boxes. The audit blocks anything that slips through.'),
    ('Fix the class, not the instance.', 'Every miss becomes a guard or an audit rule, tested on a broken clip.'),
]


def fx_card(m, pdf):
    cat = m.get('category', 'other')
    media = ''
    if pdf and m.get('_poster'):
        media = f'<img class="ph" src="{m["_poster"]}" alt="{E(m.get("name", ""))} preview frame">'
    elif m.get('_preview'):
        media = (f'<video class="ph" data-src="{m["_preview"]}" poster="{m.get("_poster", "")}" muted loop playsinline '
                 f'preload="none" aria-label="{E(m.get("name", ""))} preview"></video>')
    else:
        media = '<div class="ph empty">preview pending</div>'
    params = ''.join(f'<li><code>{E(k)}</code> {E(str(v))}</li>' for k, v in (m.get('params') or {}).items())
    snd = ', '.join(m.get('sfx') or []) or 'none'
    src = m.get('source', 'ours')
    badge = 'Ours' if src == 'ours' else E(src.split(':')[0])
    return f'''<article class="fx" data-cat="{E(cat)}">
  {media}
  <div class="fx-b">
    <div class="fx-top"><span class="tag">{E(CAT_NAME.get(cat, cat))}</span><span class="src">{badge}</span></div>
    <h3>{E(m.get("name", m["id"]))}</h3>
    <p class="when">{E(m.get("when", ""))}</p>
    <p class="never"><b>Never:</b> {E(m.get("never", ""))}</p>
    <details><summary>Use it</summary>
      <pre>{{"type": "{E(m["id"])}", "on": "the words that trigger it", ...}}</pre>
      <ul class="params">{params}</ul>
      <p class="snd">Sound: {E(snd)}</p>
    </details>
  </div>
</article>'''


def reg_row(r):
    r = {k: (v.replace(' \u2014 ', ', ').replace('\u2014', ', ') if isinstance(v, str) else v) for k, v in r.items()}
    link = f'<a href="{E(r["link"])}" target="_blank" rel="noopener">Source</a>' if r.get('link') else ''
    prev = f'<a href="{E(r["preview_url"])}" target="_blank" rel="noopener">Preview</a>' if r.get('preview_url') else ''
    return f'''<li class="rg" data-cat="{E(r.get("category", ""))}">
  <div class="rg-h"><b>{E(r.get("title") or r["name"])}</b><span class="tag">{E(CAT_NAME.get(r.get("category"), r.get("category", "")))}</span></div>
  <p>{E(r.get("what_it_does", ""))}</p>
  <p class="muted">Use it when: {E(r.get("use_it_when", ""))}</p>
  <div class="rg-a"><code class="cmd">{E(r.get("install", ""))}</code><button type="button" class="copy" data-copy="{E(r.get("install", ""))}">Copy</button>{prev}{link}</div>
</li>'''


def page(pdf=False):
    fx = effects()
    lk = looks()
    reg = json.load(open(os.path.join(REPO, 'gallery', 'registry.json'))) if os.path.exists(os.path.join(REPO, 'gallery', 'registry.json')) else []
    reg = reg['items'] if isinstance(reg, dict) else reg
    cats = [c for c in CAT_ORDER if any(m.get('category') == c for m in fx)]
    rcats = [c for c in CAT_ORDER if any(r.get('category') == c for r in reg)]
    look_html = ''
    for L in lk:
        use, what = LOOK_FACTS.get(L['id'], ('', L.get('summary', '')))
        if pdf and L.get('_poster'):
            v = f'<img class="lv" src="{L["_poster"]}" alt="{E(L["name"])} look">'
        elif L.get('_video'):
            v = f'<video class="lv" data-src="{L["_video"]}" poster="{L.get("_poster") or ""}" muted loop playsinline preload="none"></video>'
        else:
            v = '<div class="lv empty">render pending</div>'
        sw = ''.join(f'<i style="background:{E(L["vars"].get(k, "#000"))}" title="{E(k)}"></i>' for k in ('--c-text', '--c-accent', '--c-accent2', '--c-ink'))
        cap = L.get('captions', {})
        look_html += f'''<article class="look">{v}
  <h3>{E(L["name"])}</h3><p>{E(what)}</p>
  <dl><dt>Use for</dt><dd>{E(use)}</dd><dt>Captions</dt><dd>{E(cap.get("style", ""))}, {E(cap.get("case", ""))} case, {cap.get("words_per_cue", 3)} word{"s" if cap.get("words_per_cue", 3) != 1 else ""} max</dd>
  <dt>Grade</dt><dd><code>{E(L.get("grade", ""))}</code></dd><dt>Default colors</dt><dd class="sw">{sw}</dd></dl></article>'''
    steps = ''.join(f'<li><h3>{E(t)}</h3><p>{E(d)}</p><pre>{E(c)}</pre></li>' for t, d, c in STEPS)
    rules = ''.join(f'<li><b>{E(a)}</b> {E(b)}</li>' for a, b in RULES)
    chips = ''.join(f'<button type="button" class="chip" data-f="{c}">{CAT_NAME[c]}</button>' for c in cats)
    rchips = ''.join(f'<button type="button" class="chip" data-f="{c}">{CAT_NAME[c]}</button>' for c in rcats)
    cards = '\n'.join(fx_card(m, pdf) for m in fx)
    rows = '\n'.join(reg_row(r) for r in reg)
    n_looks = len(lk)
    n_looks = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six'}.get(n_looks, str(n_looks))
    n_ours = sum(1 for m in fx if m.get('source', 'ours') == 'ours')
    script = '' if pdf else SCRIPT
    return f'''<title>Reel Kit</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;900&family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,900;1,9..144,500;1,9..144,900&family=Fragment+Mono&display=swap">
<style>{CSS}{PDF_CSS if pdf else ''}</style>
<div class="wrap">
<header class="hero">
  <p class="eyebrow">Claude Code skills for talking-head reels</p>
  <h1>Reel <em>Kit</em></h1>
  <p class="lede">Turn a long interview or talking-head video into finished 9:16 reels in your brand. It picks the hot takes, cuts a tight script, adds graphics on the right words, and checks every frame before you watch.</p>
  <p class="note-ai">Every demo in this guide uses an AI-generated person made with Higgsfield (Kling 3.0). She is not a real person.</p>
  <p class="meta">{len(fx)} tested effects · {len(reg)} more from the HyperFrames registry · {len(lk)} looks · 4 skills</p>
</header>

<section id="how"><h2>How to use it</h2><ol class="steps">{steps}</ol></section>

<section id="looks"><h2>{n_looks} looks</h2><p class="note-ai">The woman in every demo here is not a real person. She was generated with AI (Kling 3.0 on Higgsfield), voice included, so the kit could be shown without anyone's real footage.</p><p class="sub">Same 15 seconds of footage in every look, each with its own signature graphics. Pick one as your default in setup. Your brand colors and fonts replace the defaults shown here.</p>
<div class="looks">{look_html}</div></section>

<section id="library"><h2>Animations library</h2><p class="sub">Every effect here lands on its word, passes the layout audit, and takes your colors and fonts. Tap "Use it" for the spec.</p>
<div class="chips" data-for="fxgrid"><button type="button" class="chip on" data-f="all">All {len(fx)}</button>{chips}</div>
<div class="grid" id="fxgrid">{cards}</div></section>

<section id="registry"><h2>More from GitHub</h2><p class="sub">Curated from the HyperFrames registry by HeyGen (Apache-2.0). Install one into a clip folder, then run /reel-qa on it, because these skip our build guards.</p>
<div class="chips" data-for="rglist"><button type="button" class="chip on" data-f="all">All {len(reg)}</button>{rchips}</div>
<ul class="rglist" id="rglist">{rows}</ul></section>

<section id="rules"><h2>The rules it follows</h2><p class="sub">Each one came from a real round of review notes. The full story is in docs/LEARNINGS.md.</p><ul class="rules">{rules}</ul></section>

<footer><p>Made by Natalia Correa. Built on HyperFrames (HeyGen, Apache-2.0) and faster-whisper (MIT). Ideas from master-skills and video-use (MIT), claude-reel-editor (MIT), and Marc at tenfold (inspiration only). Demo person and voice are AI-generated (Kling 3.0 on Higgsfield), not a real person. Sounds from Pixabay, downloaded on setup.</p></footer>
</div>
{script}'''


CSS = '''
/* Layout: one reading column; the library and looks break into wrapping grids of phone-shaped cards */
:root{--paper:#FAFAF7;--ink:#111114;--ultra:#2B21E5;--grey:#6E6E76;--hair:rgba(17,17,20,.14);--card:#FFFFFF;--codebg:#F1F0EA;
--f-display:'Fraunces',Georgia,serif;--f-body:'Archivo',Helvetica,Arial,sans-serif;--f-mono:'Fragment Mono','Courier New',monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0B0B10;--ink:#EDEDEA;--ultra:#8C85FF;--grey:#9A9AA2;--hair:rgba(237,237,234,.16);--card:#15151C;--codebg:#1B1B23;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#0B0B10;--ink:#EDEDEA;--ultra:#8C85FF;--grey:#9A9AA2;--hair:rgba(237,237,234,.16);--card:#15151C;--codebg:#1B1B23;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:500 16px/1.55 var(--f-body)}
.wrap{max-width:1120px;margin:0 auto;padding-inline:20px;padding-block:28px 64px}
h1,h2,h3{font-family:var(--f-display);text-wrap:balance;margin:0}
.hero{padding-block:24px 36px;border-bottom:1px solid var(--hair)}
.eyebrow,.meta,.tag,.src,code,pre,.cmd{font-family:var(--f-mono)}
.eyebrow{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--grey);margin:0 0 10px}
h1{font-size:clamp(56px,11vw,112px);font-weight:900;line-height:.92;font-variation-settings:"opsz" 144;letter-spacing:-.02em}
h1 em{color:var(--ultra);font-style:italic}
.lede{font-size:clamp(18px,2.2vw,21px);max-width:62ch;margin:18px 0 10px}
.meta{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--grey)}
section{padding-block:44px 8px;border-bottom:1px solid var(--hair)}
h2{font-size:clamp(30px,4.4vw,42px);font-weight:900;font-variation-settings:"opsz" 144}
.note-ai{margin:10px 0 0;padding:10px 14px;border-left:3px solid var(--ultra);background:var(--card);font-size:14px;max-width:66ch}
.sub{color:var(--grey);max-width:66ch;margin:8px 0 22px}
.steps{list-style:none;padding:0;margin:20px 0 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:18px}
.steps li{min-width:0;padding:18px;border:1px solid var(--hair);border-radius:12px;background:var(--card);display:flex;flex-direction:column;gap:8px}
.steps h3{font-size:22px} .steps p{margin:0;color:var(--grey)}
pre{background:var(--codebg);padding:10px 12px;border-radius:8px;font-size:13px;overflow-x:auto;margin:auto 0 0;white-space:pre}
.looks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:22px}
.look{min-width:0;display:flex;flex-direction:column;gap:10px}
.lv{width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:14px;background:#000;display:block}
.look h3{font-size:28px} .look p{margin:0}
dl{display:grid;grid-template-columns:1fr;gap:2px;margin:6px 0 0;font-size:14px} dd+dt{margin-top:8px}
dt{font-family:var(--f-mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--grey);padding-top:3px}
dd{margin:0;min-width:0;overflow-wrap:anywhere} dd code{font-size:12px}
.sw{display:flex;gap:6px} .sw i{width:22px;height:22px;border-radius:50%;border:1px solid var(--hair);display:inline-block}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}
.chip{font:600 13px var(--f-body);padding:7px 14px;border-radius:999px;border:1px solid var(--hair);background:transparent;color:var(--ink);cursor:pointer}
.chip.on,.chip:hover{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.chip:focus-visible,.copy:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--ultra);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,230px),1fr));gap:18px}
.fx{min-width:0;display:flex;flex-direction:column;background:var(--card);border:1px solid var(--hair);border-radius:14px;overflow:hidden}
.ph{width:100%;aspect-ratio:9/16;object-fit:cover;display:block;background:#000}
.ph.empty,.lv.empty{display:flex;align-items:center;justify-content:center;color:#888;font:12px var(--f-mono)}
.fx-b{padding:14px;display:flex;flex-direction:column;gap:6px}
.fx-top{display:flex;justify-content:space-between;gap:8px}
.tag,.src{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--grey)}
.src{color:var(--ultra)}
.fx h3{font-size:20px;line-height:1.15}
.when{margin:0;font-size:14px} .never{margin:0;font-size:13px;color:var(--grey)}
details{font-size:13px;margin-top:4px} summary{cursor:pointer;font-weight:700;color:var(--ultra)}
details pre{margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.params{padding-left:16px;margin:6px 0} .params code{font-size:12px} .snd{margin:4px 0 0;color:var(--grey)}
.rglist{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:14px}
.rg{min-width:0;padding:14px;border:1px solid var(--hair);border-radius:12px;display:flex;flex-direction:column;gap:6px}
.rg p{margin:0;font-size:14px} .muted{color:var(--grey)}
.rg-h{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.rg-a{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:4px;font-size:13px}
.cmd{font-size:12px;background:var(--codebg);padding:4px 8px;border-radius:6px;overflow-wrap:anywhere;min-width:0}
.copy{font:600 12px var(--f-body);border:1px solid var(--hair);background:transparent;color:var(--ink);border-radius:6px;padding:4px 10px;cursor:pointer}
a{color:var(--ultra)}
.rules{padding:0;list-style:none;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:12px 28px}
.rules li{padding-left:14px;border-left:2px solid var(--ultra)}
.rules b{font-family:var(--f-display);font-size:18px;display:block}
footer{padding-block:28px 0;color:var(--grey);font-size:13px;max-width:72ch}
[hidden]{display:none!important}
@media (prefers-reduced-motion:reduce){video{animation:none}}
'''

PDF_CSS = '''
@page{size:A4;margin:11mm 0}
html,body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-size:11.5px} .wrap{max-width:none;padding:0 13mm}
section{padding-block:18px 4px} .fx,.look,.steps li,.rg{break-inside:avoid}
.rules{display:block;columns:2;column-gap:24px} .rules li{margin-bottom:10px;break-inside:avoid}
h1{font-size:64px} h2{font-size:30px;break-after:avoid} .sub{margin:6px 0 14px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}
.steps{grid-template-columns:repeat(2,1fr);gap:10px} .steps li{padding:12px}
.looks{grid-template-columns:repeat(3,1fr);gap:14px} .lv{border-radius:10px}
.grid{grid-template-columns:repeat(2,1fr);gap:10px}
.fx{flex-direction:row} .fx .ph{width:96px;flex:none;aspect-ratio:9/16;height:auto}
.fx-b{padding:10px 12px;gap:4px} .fx h3{font-size:15px} .when{font-size:11px} .never{font-size:10.5px}
.rglist{grid-template-columns:repeat(2,1fr);gap:8px} .rg{padding:10px} .rg p{font-size:11px}
.chips,.copy,details summary{display:none} details{display:block} details>*{display:block}
details pre{font-size:10px;margin:4px 0} .params{font-size:10.5px}
'''

SCRIPT = '''<script>
document.querySelectorAll('.chips').forEach(function(bar){
  var list=document.getElementById(bar.dataset.for);
  bar.addEventListener('click',function(e){
    var b=e.target.closest('.chip'); if(!b) return;
    bar.querySelectorAll('.chip').forEach(function(c){c.classList.toggle('on',c===b)});
    var f=b.dataset.f;
    list.querySelectorAll('[data-cat]').forEach(function(el){el.hidden=!(f==='all'||el.dataset.cat===f)});
  });
});
document.addEventListener('click',function(e){
  var b=e.target.closest('.copy'); if(!b) return;
  var t=b.dataset.copy;
  navigator.clipboard.writeText(t).then(function(){b.textContent='Copied'},function(){
    var r=document.createRange(); r.selectNodeContents(b.previousElementSibling); var s=getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent='Selected'});
  setTimeout(function(){b.textContent='Copy'},1600);
});
// Load a video only near the viewport and unload it after, so Chrome never hits its media player cap (about 75 per page).
function on(v){if(!v.src){v.preload='auto';v.src=v.dataset.src}var p=v.play();if(p&&p.catch)p.catch(function(){})}
function off(v){if(v.src){v.pause();v.removeAttribute('src');v.load()}}
var io='IntersectionObserver' in window?new IntersectionObserver(function(es){es.forEach(function(en){en.isIntersecting?on(en.target):off(en.target)})},{rootMargin:'300px'}):null;
document.querySelectorAll('video[data-src]').forEach(function(v){if(io)io.observe(v);else v.src=v.dataset.src});
</script>'''


def main(argv):
    site = page(pdf=False)
    open(os.path.join(G, 'site.html'), 'w').write(site)
    repo = re.sub(r'media/fx-([a-z0-9-]+)\.mp4', r'../effects/\1/preview.mp4', site)
    repo = re.sub(r'media/fx-([a-z0-9-]+)\.jpg', r'../effects/\1/poster.jpg', repo)
    open(os.path.join(G, 'index.html'), 'w').write(repo)
    print('wrote guide/index.html (repo) and guide/site.html (publish)')
    if '--pdf' in argv:
        pr = os.path.join(G, 'print.html')
        open(pr, 'w').write('<!doctype html><meta charset="utf-8">' + page(pdf=True))
        chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        out = os.path.join(G, 'reel-kit-guide.pdf')
        subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--virtual-time-budget=8000',
                        f'--print-to-pdf={out}', 'file://' + pr], check=True, capture_output=True)
        print('wrote', os.path.relpath(out, REPO))


if __name__ == '__main__':
    main(sys.argv[1:])
