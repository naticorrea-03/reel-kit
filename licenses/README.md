# Third-party licenses

reel-kit is MIT (see `../LICENSE`). These parts keep their own licenses. Where each project came from and what it contributed is in `../CREDITS.md`.

| Files | License | Text |
|---|---|---|
| `assets/fonts/Inter-*` | SIL OFL 1.1 | `OFL-inter.txt` |
| `assets/fonts/InterTight-*` | SIL OFL 1.1 | `OFL-intertight.txt` |
| `assets/fonts/Fraunces-*` | SIL OFL 1.1 | `OFL-fraunces.txt` |
| `assets/fonts/Caveat-*` | SIL OFL 1.1 | `OFL-caveat.txt` |
| `assets/fonts/JetBrainsMono-*` | SIL OFL 1.1 | `OFL-jetbrainsmono.txt` |
| `assets/fonts/NotoSerifDisplay-*` | SIL OFL 1.1 | `OFL-notoserifdisplay.txt` |
| `effects/carousel-orbit/`, `effects/carousel-circle/`, `effects/carousel-vision/`, `effects/carousel-path/`, `effects/_lib/carousel_rig.py` | Apache License 2.0, Copyright HeyGen | `Apache-2.0-hyperframes.txt` |
| `effects/title/`, `effects/tag/`, `effects/cta/`, `effects/sticker/`, `effects/backdrop/`, `effects/caption-follow/` | MIT, Copyright (c) 2026 Nicola Pocock | `MIT-claude-reel-editor.txt` |

## Changes to the HyperFrames carousels (Apache 2.0, section 4b)

Ported from the HyperFrames registry blocks carousel-orbit-1, carousel-circle-1, carousel-vision-1 and carousel-path-1 (https://github.com/heygen-com/hyperframes):
- The rig math (keyframe curves, Fibonacci sphere, bezier paths, depth scaling, tangent rotation) is reimplemented in Python in `effects/_lib/carousel_rig.py`.
- Poses are computed at build time and baked into GSAP keyframes.
- The 16:9 layouts are re-laid out around the speaker's head for 9:16 video.
- Cards come from parameters instead of image slots. Wall cards dim while covered, and labels show only on readable cards.
- The registry's sample images are not used or shipped. The demo art is our own.
