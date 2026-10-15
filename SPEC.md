# reel-kit build spec (internal contract for everyone building this repo)

reel-kit turns a long talking-head or interview video into finished 9:16 reels with designed graphics, then checks them frame by frame before a human sees them. It is a plain git repo of Claude Code skills plus Python/Node scripts. People clone it and run `./install.sh`, which symlinks `skills/*` into `~/.claude/skills/`. No plugin packaging, no marketplace files.

Origin: an October 2026 project that cut eight reels from a 12-minute street interview over six rounds of review. The engine is a port of that pipeline with everything project-specific removed. The lessons are in `docs/LEARNINGS.md`.

## Hard rules
- No em dashes anywhere (code comments, docs, UI). Short plain sentences.
- No secrets, no absolute paths to anyone's home folder. Resolve paths from `__file__` or env vars.
- Nothing from tenfoldmarc/video-edit-skill (no license) is copied. Ideas may be credited as "inspired by" with a link. Code from heygen-com/hyperframes (Apache-2.0), Jakeschincariol/master-skills (MIT) and browser-use/video-use (MIT) may be used with credit in `CREDITS.md`.
- Sound files are NOT committed (Pixabay license forbids standalone redistribution). `engine/fetch_sfx.py` downloads them from `assets/sfx/manifest.json` on setup.
- Fonts in `assets/fonts/` are SIL OFL and may ship.
- Every guard in the original pipeline survives the port (echo-note guard, parallel-words guard, unknown-type exit, blank-window exit, serif hold, cue overlap, ARROW rule, beat-sheet clearing, etc.).
- macOS first (Vision face detector via `faces.swift`). If not on macOS, the face step must fail loudly with a clear message, never silently pass.

## Repo layout
```
reel-kit/
  README.md            what it is, install, 5-minute quickstart, credits pointer
  install.sh           symlink skills into ~/.claude/skills, run engine/doctor.py
  SPEC.md              this file
  CREDITS.md           every upstream source + license
  skills/
    reel-setup/SKILL.md     interview -> ~/.reel-kit/profile.json (brand, look, preferences)
    reel-edit/SKILL.md      the full workflow, long video -> reels, with the learnings as rules
    reel-qa/SKILL.md        run the gates on any composition, read beat sheets
    reel-effects/SKILL.md   browse the effects library and add effects to a reel
  engine/
    doctor.py          checks ffmpeg, node>=22, python3, faster-whisper, swift faces binary
    fetch_sfx.py       downloads sounds listed in assets/sfx/manifest.json
    transcribe.py      word-level transcript (faster-whisper), cached
    cut.py             script sentences -> shots with zoom cycle, segments.json, cut.words.json
    cutout.sh          npx hyperframes remove-background aroll.mp4 -> subject.webm
    tailpad.sh
    build.py           project + clip + look + profile -> index.html + plan.json
    fxlib.py           the Context object passed to effects (helpers below)
    render.sh          build -> audit gate -> hyperframes render -> two-pass master -14 LUFS -> phone copy -> beat sheet
    master.sh          fixed gain to -14 LUFS + limiter (no highpass in the meter)
    preview.py         render one effect from effects/<id>/demo.json over demo footage -> effects/<id>/preview.mp4 + poster.jpg
    audit/             probe.mjs, analyze.py, faces.swift, audit.sh, beatsheet.py, words_check.py
  effects/<id>/
    effect.py          META dict + build(g, ctx)
    style.css          CSS for this effect only, every selector prefixed .fx-<id>, colors and fonts ONLY via CSS vars
    demo.json          one example graphic spec, used by preview.py and the gallery
    preview.mp4, poster.jpg   (generated)
  looks/<id>.json      six looks: tokens + grade + caption style + hook style
  assets/fonts, assets/sfx/manifest.json
  guide/index.html     generated guide + effects gallery (ours + curated registry), guide/reel-kit-guide.pdf
  gallery/registry.json  curated HyperFrames registry picks with install commands and licenses
  guide/               the Looks guide (HTML -> PDF): six looks side by side with stills and exact specs
  docs/LEARNINGS.md    public version of the lessons
```

## Per-user profile: `~/.reel-kit/profile.json`
```json
{
  "name": "Alex Rivera", "handle": "alexrivera",
  "look": "editorial",
  "brand": {
    "colors": {"text": "#F3EBDD", "accent": "#6B2638", "accent2": "#24483A", "ink": "#1a1511", "card": "#FFFFFF"},
    "fonts": {"display": "Inter Tight", "serif": "Fraunces", "body": "Inter", "script": "Caveat", "mono": "JetBrains Mono"},
    "logo": "~/.reel-kit/brand/logo.svg", "eyebrow": "optional short text shown top-left"
  },
  "captions": {"style": "pill", "case": "lower", "words_per_cue": 3},
  "sfx": true, "music": false,
  "zooms": null,
  "avoid": ["sparkles", "glows", "full-body wide shots"],
  "platform": "instagram"
}
```
Brand values override the look's defaults. Missing keys fall back to the look.
`zooms` is optional. Leave it null and engine/cut.py measures the speaker's face and picks zooms that land a close-up at a face 13% of the frame tall and a medium at 10% (the framing a reviewer approved). A fixed list only works for the footage it was tuned on.

## Per-reel project folder (anywhere the user wants)
```
<project>/
  project.json   {"source": "/path/video.mov", "speakers": {"A": {"name": "...", "role": "...", "side": "left"}}, "eyebrow": "...", "profile": "~/.reel-kit/profile.json"}
  clips.json     {"clips": [{"slug", "hook": [small, big], "script": [...sentences...], "graphics": [ {type, on, ...} ]}]}
  clips/<slug>/  aroll.mp4 (assets/), subject.webm, segments.json, cut.words.json, index.html, plan.json
  renders/<slug>.mp4, renders/phone/<slug>.mp4
  audits/<slug>/report.md, beats/*.jpg
  review/state.json  local review page data: buckets, clips, reviews, notes (review/serve.py)
```
`clips.json` graphics are `{"type": "<effect id>", "on": "<spoken phrase>", ...params}`. See `demo/clips.json` for a working example.

## Look file: `looks/<id>.json`
```json
{"id": "editorial", "name": "Editorial", "summary": "...",
 "vars": {"--c-text": "#F3EBDD", "--c-accent": "#6B2638", "--c-accent2": "#24483A", "--c-ink": "#1a1511", "--c-card": "#fff",
          "--f-display": "'Inter Tight'", "--f-serif": "'Fraunces'", "--f-body": "'Inter'", "--f-script": "'Caveat'"},
 "grade": "sepia(.10) saturate(1.04) contrast(1.0) brightness(1.03)",
 "overlays": {"warm": true, "vignette": .30, "grad": true},
 "captions": {"style": "pill", "font": "body", "size": 58, "case": "lower"},
 "hook": {"small": "serif-italic", "big": "display-upper"},
 "punch": "scale",   "cut_punch": 1.05,
 "default_effects": ["serif", "behind", "logo", "ui-chat", "note", "stats"]}
```
Optional keys (all backwards compatible; a look without them renders exactly as before):
- `vars`: `--f-title` (a title font, for the cover and masthead hooks), `--title-stretch`, `--title-weight`; box caption colours `--cap-box-bg`, `--cap-box-ink`, `--cap-box-on` (spoken words), `--cap-box-dim` (words not yet spoken), `--cap-box-font`, `--cap-box-weight`, `--cap-box-radius`, `--cap-box-shadow`.
- `overlays.tint`: `{"color", "opacity", "blend"}`, a colour wash over the footage (default blend soft-light). `overlays.grad` as a number (0-1) sets how dark the bottom of the frame gets; `true` keeps the default.
- `captions.style`: `pill`, `stack`, `clean`, or `box` (a rounded plate behind the cue). `captions.fill`: spoken words stay lit and the rest of the cue waits dimmed (karaoke). `captions.font`: `serif`, `title` or `script` swaps the caption font. `captions.align`: `left` puts short cues beside the face instead of centred. `captions.adaptive`: cues over a plain bright wall switch to ink.
- `hook.style`: `stack` (default), `cover` (a sentence-case title serif in the top band with a handwritten line that writes itself on), `mixed` (heavy sans caps over an italic serif accent line, top band), `masthead` (a giant condensed serif title tucked behind the head, plus the small line and an optional third hook item as a tracked-caps kicker; under the chin on a plate when there is no headroom). Every style falls back to the default hook when it cannot place itself, and switches light type to ink on a plain bright wall. `clips.json` hooks may carry a third item for the kicker: `["small", "big", "kicker"]`.
- `css`: a string or list of CSS rules appended after the effects' styles, for restyling effects per look (for example the serif effect's punch line colour). Effects themselves never change.

Fonts: `assets/fonts/fonts.json` entries may carry `"stretch": "62.5% 100%"` for variable-width fonts, so `font-stretch` reaches the width axis.

The six looks:
1. `editorial`: the look the original interview reels shipped with. Warm grade, italic serif punch lines, word-pill captions, cream cards. Calm and premium.
2. `punch`: kinetic. Huge heavy display words behind the head, high-contrast grade, captions as big bold 1-2 word stacks, fast blur-pop entrances, cut punches.
3. `minimal`: documentary. Neutral grade, small clean lower captions, lower-thirds and thin-rule cards, slow push-ins, almost no decoration.
4. `golden-hour`: warm and soft, lifestyle premium. Honey sepia grade with a soft vignette, a sentence-case serif cover title with a handwritten line, tiny serif one-word captions beside the face, butter italic punch lines, handwritten notes with drawn arrows, the orbit carousel as its signature. No sparkles, no glows.
5. `masthead`: magazine cover. A giant condensed serif title (Noto Serif Display, condensed) tucked behind the head with a tracked-caps kicker, muted olive grade, small serif captions on a forest plate that fill in as spoken, condensed serif words behind the head. No film grain.
6. `native`: feed-native creator style. True-to-life grade, white box captions with black text that fill in word by word, heavy sans caps hooks with an orange italic serif accent word, stickers, tags and popups.
These are our own looks. Do not reuse Marc's look names or his exact values.

## Effect module contract: `effects/<id>/effect.py`
```python
META = {
  "id": "note", "name": "Handwritten note", "category": "annotation",   # categories: text, annotation, ui, media, data, social, structure, captions
  "when": "Adds a fact the speaker does not say (a number, a name, a date).",
  "never": "Never echo words spoken within 2 s. Never point at nothing.",
  "params": {"on": "phrase that triggers it", "text": "note text", "hold": "seconds, default 1.6"},
  "sfx": ["pen-scribble"],            # names from assets/sfx/manifest.json, literal to the object
  "source": "ours",                    # "ours" | "hyperframes-registry:<name>" | "master-skills" | ...
  "credit": "", "license": "MIT"
}
def build(g, ctx):
    a, b = ctx.at(g["on"])
    ...
    cid = ctx.clip(ctx.front, a, a + hold, html, style)   # returns element id
    ctx.tw(f"tl.fromTo('#{cid}', ...)")                     # GSAP lines
    ctx.sfx("pen-scribble", a, .5)
    ctx.busy.append((a, a + hold))                           # captions pause here if the effect replaces them
```
`ctx` (engine/fxlib.py) provides: `at(phrase, after=0)`, `words`, `said(t0,t1)`, `clip(layer, a, b, inner, style='', cls='')`, layers `wall` (behind cutout), `front`, `top`, `tw(line)`, `sfx(name, t, vol, cap=None)`, `place(w, h, t0, t1, cands)`, `face_hit(...)`, `alpha_cover(...)`, `head_top(t)`, `zoom_at(t)`, `speaker_at(t)`, `faces_at(t)`, `esc`, `q`, `DUR`, `F`, `busy`, `topbusy`, `lowbusy`, `parallel` dict, `profile`, `look`, `speakers`, `fail(msg)` (sys.exit with slug prefix), `warn(msg)`, `asset(path)` (copies a file into the clip folder and returns its relative url), `beat(kind, text, g)` / plan hooks, `plan_text` override via an optional `describe(g, beat)` function in the module.
Effects never hardcode colors or font names: use `var(--c-text)`, `var(--f-serif)`, etc. Every selector is prefixed `.fx-<id>`. Every timed element goes through `ctx.clip` (HyperFrames needs `class="clip"` windows; GSAP zero-duration sets get skipped by the renderer).
Safe zone on 1080x1920: text and key UI inside x 90-950, y 240-1470; right rail x>950 below y 1155 is off limits.

## Effects to ship (ported from the original pipeline unless marked NEW)
text: hook, behind (words behind head, parallel-size guard), serif (punch line, captions pause), words3 (word trio)
annotation: note (+ arrow to face, echo guard), highlight-paper (study screenshot with highlighted line)
ui: chat-prompt (types a prompt), chat-bubbles, chat-sidebar (projects list), notification-stack, agent-chat, pipeline, doc-attach (PDF + prompt), side-by-side windows, list-card (boards)
media: logo (drop card), photo (polaroid), screenshot, qr-tag
data: stats (count-up chips)
structure: lower-third, eyebrow, cut-punch, captions (pill / bold-stack / clean)
NEW social/popups: popup-comment (IG comment bubble pops in), popup-follow (follow button card), popup-dm (DM/iMessage bubble), poll-sticker, reaction-burst (one emoji pop, no glows)
NEW carousels: carousel-cards (3-5 cards slide past like a swipe carousel), carousel-stack (cards fan then flip one by one), screenshot-scroll (tall page scrolls inside a phone frame)
NEW other: checklist (items tick off on their words), progress-bar, before-after split, map-pin, quote-card, tweet-card, timeline (years drop on a line)
Each NEW effect follows the same rules: lands on its word, adds information, literal SFX or none, no sparkles or glows.
