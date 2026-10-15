---
name: reel-effects
description: "Browse and use the reel-kit effects library: our tested effects (captions, behind-head words, serif punch lines, notes with arrows, chat windows, logos, stats, popups, carousels) and curated HyperFrames registry effects. Trigger with /reel-effects, 'what effects can I use', 'add a popup', 'show me the animations library'."
---

# reel-effects

Read `~/.reel-kit/kit_path` and call that folder KIT.

## Two libraries
1. **Ours**, in `KIT/effects/<id>/`. Each has `effect.py` (META says what it is for, when never to use it, its params, and its sounds), `style.css`, `demo.json` (a working example spec), and `preview.mp4` / `poster.jpg`. These plug straight into `clips.json` as `{"type": "<id>", "on": "<phrase>", ...}` and pass the QA gates.
2. **HyperFrames registry picks**, in `KIT/gallery/registry.json`: curated blocks and components from heygen-com/hyperframes (Apache-2.0) with install commands. Install one with `npx hyperframes@0.8.61 add <name>` inside the clip folder, then wire it as its own timed `.clip` window. These are not guarded by our build rules, so check them with the reel-qa skill.

The visual gallery is `KIT/guide/index.html`. Open it for the person when they want to browse.

## Answering "what can I use for X"
Match the spoken noun to the effect. Read META `when` and `never` before recommending. Offer at most three options, each with one line on what it adds. Show the poster image.

## Adding an effect to a reel
Add the entry to the clip's `graphics` in `clips.json`, keyed to the exact phrase. Rebuild with `KIT/engine/render.sh`. If the build refuses it, the guard message says why. Fix the spec, never the guard.

## Making a new effect
Copy the closest effect folder, rename it, and follow the contract in `KIT/SPEC.md` (Effect module contract): colors and fonts only through CSS vars, every selector prefixed `.fx-<id>`, every timed element through `ctx.clip`, safe zone x 90-950 and y 240-1470. Write `demo.json`, run `python3 "$KIT/engine/preview.py" <id>`, look at the poster, and run the layout audit on a test clip before using it for real.
