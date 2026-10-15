---
name: reel-qa
description: "Checks a reel frame by frame before a person watches it: layout audit (faces covered, overlaps, overflow, clipped text, safe zone, arrows), words check against a fresh transcript, loudness, and beat sheets you read yourself. Trigger with /reel-qa, 'check this reel', 'audit the reel', or before handing any reel over."
---

# reel-qa

Read `~/.reel-kit/kit_path` and call that folder KIT. Works on any reel-kit clip folder, and the layout audit works on any HyperFrames composition.

## Gate 1: layout audit (free, about a minute per clip)
`bash "$KIT/engine/audit/audit.sh" <project> <slug>` steps the composition 6 times a second in headless Chrome, finds faces with the macOS Vision detector, and writes `audits/<slug>/report.md`.
Rules: FACE (graphic over a face), HIDDEN (text behind the speaker), OVERLAP, OVERFLOW (text outside its box), CLIPPED, SAFEZONE, SPACING, EMPTY, TINY (text under 28 px), CUES (two captions at once), ARROW (a note arrow that does not land within 120 px of a face).
Errors block the render. Warnings get a look and a decision.

## Gate 2: words check
`python3 "$KIT/engine/audit/words_check.py" <project> <slug>` transcribes the final render again and diffs it against the script. 95% or better is normal. Every listed word gets checked: a real miss, a name Whisper hears wrong, or a cut that clipped a word.

## Gate 3: beat sheets (you, by eye)
`python3 "$KIT/engine/audit/beatsheet.py" <project> <slug>` writes one image per graphic with frames at its entrance, middle, and exit. Open every image with the Read tool. Look for: text hidden by a head, a graphic that never drew, captions doubled, blank windows, words that leave before they are said, unequal parallel words, anything that looks off. The audit only catches what it was written to catch. Your eyes cover the rest.

## Gate 4: loudness
Master is -14 LUFS integrated, true peak at or under -1.5 dBTP. Measure without a highpass in the meter chain.

## When a gate misses something a person later catches
Write a new rule. Either a build guard that refuses the bad input, or an audit rule that blocks the render. Test it on a deliberately broken clip so you know it fires. Then add the story to `KIT/docs/LEARNINGS.md`.

## What no gate covers
Nothing here listens to the audio. Sound effect timing is checked against the timeline, not by ear. Say so in the handover.
