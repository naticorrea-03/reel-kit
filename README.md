# reel-kit

Claude Code skills that turn a long talking-head or interview video into finished 9:16 reels. reel-kit finds the hot takes and cuts a tight script. It zooms in on the speaker and cuts them out so words can sit behind their head, then adds designed graphics in your brand. Then it checks every frame before you watch.

It came out of a real project: eight reels from a 12-minute interview, after six rounds of review. Every rule and guard in it exists because something went wrong first. The full story is in [docs/LEARNINGS.md](docs/LEARNINGS.md).

## What you get
- **/reel-setup** interviews you once about your brand, your look, and your taste. It saves your answers to `~/.reel-kit/profile.json`.
- **/reel-edit** takes a long video and returns finished reels.
- **/reel-qa** runs the gates before you watch:
  - a frame-by-frame layout audit (faces covered, overlaps, text out of its box, safe zone, arrows)
  - a words check
  - loudness
  - beat sheets that Claude reads itself
- **/reel-review** puts finished reels on a review page in your brand: approve or redo each one, leave notes pinned to a moment, and comment on each storyboard beat. Claude reads your notes back before the next round. It runs as a private claude.ai page you can share with a client, or on your Mac with no account.
- **/reel-effects** gives you the effects library. There are our tested effects (captions, words behind the head, serif punch lines, handwritten notes with arrows, chat windows, logos, stats, popups, carousels) and about 80 curated HyperFrames registry effects.
- **Six looks:** Editorial, Punch, Minimal, Golden Hour, Masthead, and Native. See `guide/`.

## Install (macOS)
You need Claude Code, ffmpeg, Node 22+, and Python 3.10+.
```
git clone <this repo> ~/reel-kit
cd ~/reel-kit && ./install.sh
```
Then open Claude Code and run `/reel-setup`.

## Quickstart
1. Put your video somewhere and run `/reel-edit`.
2. Answer one round of questions (who is speaking, the platform, any names that will be said).
3. Claude reads the transcript, picks the clips, plans the graphics, renders, and runs the gates.
4. Run `/reel-review` and watch the reels on the review page. Approve, ask for a redo, or leave notes at the exact second. Plain-word notes in chat work too.

## How it works
`engine/` holds the scripts:
- `transcribe.py`: transcription with faster-whisper
- `cut.py`: script cuts and zooms
- `cutout.sh`: speaker cutout with HyperFrames
- `build.py`: builds the composition from `effects/`
- `render.sh`: render, audit gate, master to -14 LUFS, phone copy, and beat sheets

Effects are small Python modules with their own CSS. See [SPEC.md](SPEC.md) to write your own.

## Limits
- Claude cannot watch or listen. It measures, reads transcripts, and looks at still frames, and it tells you what it could not check.
- Sound effect timing is checked against the timeline, not by ear.
- Face detection uses macOS Vision, so the layout audit is macOS only for now.

## Credits
See [CREDITS.md](CREDITS.md). Built on HyperFrames by HeyGen (Apache-2.0). Ideas from master-skills (MIT), video-use (MIT), claude-reel-editor (MIT), and Marc at tenfold (inspiration only, nothing copied).

## License
MIT. See [LICENSE](LICENSE). Fonts and a few ported effects keep their own licenses, listed in [licenses/](licenses/README.md).
