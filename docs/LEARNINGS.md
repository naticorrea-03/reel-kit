# What we learned making reels with Claude

reel-kit came out of one real project in October 2026: eight reels cut from a 12-minute street interview, across six rounds of review. Every rule and guard in this kit exists because something below went wrong first. Read this before your first reel. Add your own lessons at the bottom.

## The short version
Claude kept handing over reels it had measured but never looked at, and the person reviewing found the mistakes. Each round fixed what they pointed at and nothing else, so the next round failed somewhere new. What finally worked was turning every miss into a rule that runs before anyone watches: a frame-by-frame layout audit, a words check, beat sheets that Claude reads itself, and build guards that refuse bad input. Every guard was tested on a deliberately broken input.

## Round by round

### 1. Silence trimming is not editing
- **First cut:** five clips of 48 to 68 seconds, with silence removed, captions, and a few quote cards.
- **The verdict:** boring and long, "going around in circles." Named things got no visuals: a company logo, a newspaper article.
- **Fix:** build each clip as a script of the speaker's sharpest sentences, pick hot takes instead of topics, change the zoom on every cut, and give a real visual to every named company, product, and paper.
- **Also:** start from the transcript, never from a template effect. The first instinct was to copy another creator's signature effect, and it did not fit this content.

### 2. Short is not the goal. Complete is.
- **Second cut:** nine clips of 18 to 28 seconds.
- **The notes:** some had "no payout", some were "cut too short", one was only the host ("this is a street interview"), and some graphics had "no intention."
- **Fix:** every clip ends on the line that answers its hook, and the guest is the point. Words behind the head go only on the payoff word, never as filler.

### 3. Graphics landed on faces
- **The problem:** placement used fixed coordinates, so cards covered faces, labels hid behind heads, and text was sliced at the edges.
- **The ask:** "I don't really want to keep watching videos that have these stupid mistakes."
- **Fix:** placement reads the speaker cutout and the face boxes. Then came the layout audit, which steps every composition 6 times a second and blocks the render on any error.

### 4. A video model watching the reel was half right
- **What we tried:** a second model that watched and listened to each reel.
- **Wrong:** every claim it made about positions, and its caption-word claims once two transcription passes disagreed with it.
- **Right:** a mumbled ending, and an unreadable line over a busy background.
- **Lesson:** each checker owns only what it is good at. Geometry goes to the audit. Every model claim gets verified on the frame before anyone acts on it. The model was later dropped when its free quota ran out.

### 5. Decoration is noise
- **The notes:** these were called "useless filler" or "don't make any sense":
  - notes that labelled what was being said
  - filler words behind the head
  - generic whooshes and pops
  - twinkling sparkles on every serif line
  - a whistle sound that matched nothing
- **Fix:** every element adds information or lands the payoff. Sounds are literal to a noun on screen, and otherwise there is silence. There are no sparkles or glows.
- **Also:** a 30-second cap nobody asked for had made clips feel unfinished. Length now follows the thought.

### 6. Each gate catches only what it was written for
- **The miss:** a handwritten "5 a.m.!!" note repeated the caption, and its arrow pointed at the wall. The watching model had been told to ignore geometry, and the audit had no arrow rule, so nothing flagged it.
- **Fixes:**
  - the build refuses a note whose words are spoken nearby
  - arrows now draw to the speaker's face
  - an ARROW audit rule fails any tip more than 120 px from a face
- **Beat sheets:** then came beat sheets, with frames at the entrance, middle, and exit of every graphic. Claude reads them before handing over. Their first pass caught seven more problems, and each became a rule:
  - a hidden screenshot title
  - lines leaving before their last word
  - two captions at once
  - blank windows
  - a redundant photo of the speaker
  - unequal parallel words
  - two graphics that never drew

### 7. No full-body wide shots
- **The note:** "I don't like when it zooms out fully."
- **Fix:** the zoom cycle went to 2.4, 1.9, 2.2, and 1.8 on 4K footage, and 1.8 is the floor. Bigger heads caused new collisions, which the audit caught before anyone saw them.

### 8. Numbers tuned on one video break on the next
- **The miss:** the first test of the kit on new footage, a waist-up selfie instead of a wide event shot, failed the audit 12 times. The zoom list filled the frame with a face, and cards placed "under the heads" landed on it.
- **Why:** the zoom numbers, the "wide shot" threshold, and the card positions were all tuned on one wide shot where heads sat high in the frame.
- **Fix:** the cut measures each speaker's face and picks zooms from a target face size. "Wide" means a small face, not a zoom number. Placement scans the whole safe zone when its usual spots are taken, and windows shrink until they clear the face. The demo went from 12 audit errors to 0. The original interview reels came back with the same results as the shipped versions.
- **Also caught by looking, not by the audit:** a dark scrim behind the serif lines was designed for a busy venue. On a plain bright wall it read as a brown smudge. The audit cannot judge contrast. Now the serif and word-trio effects measure how bright and how busy the wall behind them is, and switch to dark text with no scrim on a plain bright wall.
- **Every effect preview now runs the layout audit.** That caught three effects whose fixed positions landed on a centred face.

## The patterns
1. **Showing work nobody looked at.** Numbers prove only what they measure. Read the beat sheets.
2. **Fixing the instance, not the class.** Every miss becomes a guard or an audit rule, tested on a broken input.
3. **Starting from a template.** Read the whole transcript first.
4. **Decoration as filler.** If you can't say what an element adds, cut it.
5. **Trusting one checker.** Each tool owns what it is good at, and claims are verified on the frame.
6. **Stale outputs passing as fresh.** Any report a script writes clears its old output first.
7. **Not answering the question asked.** Answer first, then work.
8. **Sprawl.** One project folder, scripts in git, and logs in `logs/`.
9. **Tuning on one video.** Test every change on a second kind of footage before calling it done.

## Technical notes
- **HyperFrames:** overlays need `class="clip"` windows with `data-start` and `data-duration`. GSAP zero-duration `set` calls get skipped by the frame-stepping renderer.
- **Loudness:** apply one fixed gain to -14 LUFS, then a limiter. Measure true peak without a highpass, because it adds about 1.4 dB of fake overshoot.
- **Whisper:** it mishears brand names. Proofread them into `caption_fixes`.
- **Sound files:** they must start on the sound. Dead air at the head makes every hit late.
- **Zoom:** 4K allows a 2x crop without upscaling, and 2.4 (a 1.2x upscale) still looks sharp on a phone.

## Lessons from users
Add yours here: date, what was wrong, the rule or guard that now prevents it.
