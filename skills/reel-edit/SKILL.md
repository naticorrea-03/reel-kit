---
name: reel-edit
description: "Turns a long talking-head or interview video into finished 9:16 reels: finds the hot takes, cuts a tight script, zooms, cuts the speaker out for words behind the head, adds designed graphics from the effects library, masters audio, and runs the QA gates before anyone watches. Trigger with /reel-edit, 'cut this into reels', 'find the viral clips in this video', 'edit this interview'."
---

# reel-edit

Read `~/.reel-kit/kit_path` and call that folder KIT. Read `~/.reel-kit/profile.json`. No profile yet: run the reel-setup skill first.

Before the first reel in a session, read `KIT/docs/LEARNINGS.md`. Every rule below exists because breaking it cost a real person a round of review.

You cannot watch or listen. You measure, read transcripts, and look at still frames. Say plainly what you checked and what you could not.

## 1. Brief (one round of questions)
Ask with AskUserQuestion: who is speaking (names and roles for name tags, which side of frame), the platform, any brand or product names that will be said, and whether they want to approve clip picks first or "just cut and show me". Make a project folder (ask where; default `~/reels/<date>-<topic>/`) with `project.json` (shape in `KIT/SPEC.md`).

## 2. Transcribe and read all of it
`python3 "$KIT/engine/transcribe.py" <project>` writes word timings. Read the whole transcript before choosing anything. Proofread names and brands (Whisper mishears them) into `caption_fixes`.

## 3. Pick hot takes, not topics
- A clip is one sharp claim plus the line that pays it off. Stories that go around in circles lose people.
- In an interview, the guest is the point. Drop host-only clips.
- No length cap. The clip ends on the finished thought, at 20, 45, or 90 seconds. Shorter is better only when nothing is missing. Cutting before the payoff is worse than running long.
- Write each clip as a script of the speaker's exact sentences in `clips.json`. Cut fillers, restarts, and detours mid-sentence. Silence trimming alone is not editing.

## 4. Plan graphics from the words
For each clip, list beats in `clips.json` `graphics`, each keyed to the exact phrase (`on`) where it lands. Browse effects with the reel-effects skill or `KIT/guide/index.html`.
- Every named company, product, paper, or person gets a real visual: their logo, their page, a real screenshot. Real UI at real proportions.
- Every graphic must add information or land the payoff. If you cannot say what it adds, cut it.
- Words behind the head: only the payoff words, never filler. Never on wide shots.
- Handwritten notes add a fact the speaker does not say. A note that repeats the caption is banned (the build refuses it).
- Parallel lines get parallel treatment ("start over", "go back", "create something" all big, or none).
- Sounds are literal to a noun on screen (cash register on money, shutter on a photo, page flip on a paper). Silence otherwise. No whooshes, risers, or random pops.
- No sparkles, glows, sheens, or pulse rings.
Post the beat table (time, words, effect, why) in chat and keep going unless they asked to approve first.

## 5. Cut, cut out, build, render
```
python3 "$KIT/engine/cut.py" <project> <slug>        # shots with the zoom cycle from the profile
bash "$KIT/engine/cutout.sh" <project> <slug>         # speaker cutout for words behind the head
bash "$KIT/engine/render.sh" <project> <slug> [...]   # build, audit gate, render, master, phone copy, beat sheet
```
The build fails loudly on any guard (echo note, unknown effect, blank window, unequal parallel words, behind words on a wide shot). Fix the cause. Never silence a guard to get a render out.

## 6. The gates, before anyone sees it
Run the reel-qa skill. It is not optional. In short:
1. Layout audit at 0 errors (faces, overlaps, overflow, clipping, safe zone, arrows).
2. Words check at 95% or better.
3. Loudness at -14 LUFS.
4. You read every beat sheet image yourself and fix anything off.
Report gate numbers, never "looks good".

## 7. Hand over
Load the batch onto the review page with /reel-review, then give the link, one line per clip on what it says, the gate numbers, and anything you could not check (you cannot hear SFX timing). Before each round of fixes, read the page's reviews and notes. When they give notes, fix the class of the problem (a rule or a guard), not just the one instance, and add the lesson to `KIT/docs/LEARNINGS.md` under "Lessons from users".

## Rules
- No em dashes in on-screen text or in chat.
- Never upscale past 1.2x. Framing comes from the measured face size (close 13% of frame height, medium 10%), not from fixed zoom numbers. No full-body wide shots.
- Their profile wins over the look. Their words win over the profile.
