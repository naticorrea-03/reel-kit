---
name: reel-setup
description: "First-run setup for reel-kit. Interviews the user about their brand, look, and editing taste, then writes ~/.reel-kit/profile.json that every reel uses. Trigger with /reel-setup, 'set up reel-kit', 'change my reel brand', or 'switch my reel look'."
---

# reel-setup

You are setting up reel-kit for one person. The goal is a profile that makes every future reel look like theirs without them repeating themselves. Ask in rounds of multiple-choice questions (AskUserQuestion, up to 4 per round), never a wall of open questions. Recommend an option when you have a reason.

The kit folder path is in `~/.reel-kit/kit_path` (written by `install.sh`). Read it first and call it KIT below. If the file is missing, tell them to run `./install.sh` from the reel-kit folder.

## 0. Check the machine
Run `python3 "$KIT/engine/doctor.py"`. It checks ffmpeg, Node 22+, Python 3, faster-whisper, and the macOS face detector. Fix what it can, and give the exact install command for what it cannot. Do not install anything without asking. Then run `python3 "$KIT/engine/fetch_sfx.py"` for the sound effects.

## 1. If a profile exists
Read `~/.reel-kit/profile.json`. Show it in five lines (name, look, colors, fonts, preferences) and ask what to change. Change only that.

## 2. Round 1: who and where
- Name to show on name tags, and their handle (optional).
- Main platform: Instagram Reels (default), TikTok, YouTube Shorts. This sets the safe zone.
- What they mostly film: solo talking head, interviews with guests, event recaps.
- Do they have brand guidelines? (A file or link, colors only, or nothing yet.)

If they have a brand file, site, or logo, read it before asking about colors and fonts. Pull exact hex values and font names from the real source. Never invent a palette when a real one exists.

## 3. Round 2: the look
Open `KIT/guide/index.html` at the Six looks section (or the PDF `KIT/guide/reel-kit-guide.pdf`). The six looks:
- **Editorial**: warm grade, italic serif punch lines, word-pill captions, cream cards. Calm and premium.
- **Punch**: huge heavy words behind the head, high contrast, big bold caption stacks, fast entrances.
- **Minimal**: neutral grade, small clean captions, lower-thirds and thin-rule cards, slow push-ins.
- **Golden Hour**: warm honey grade, a serif title with a handwritten line, tiny serif word captions, butter italic punch lines, tiles orbiting the head.
- **Masthead**: magazine cover, a giant condensed serif title tucked behind the head, muted olive grade, serif captions on a forest plate.
- **Native**: feed-native, true-to-life grade, white box captions that fill in as spoken, heavy caps hooks with an orange italic accent, stickers and popups.
Ask which is their default. Any reel can still switch looks later.

## 4. Round 3: brand
- Colors: text on video, accent (the caption highlight and key cards), second accent, ink (dark text on cards). Offer their brand colors if found, else the look's defaults.
- Fonts: display (big words), serif (punch lines), body (captions), script (handwritten notes). Google Fonts names. If a font is not in `KIT/assets/fonts`, download the latin woff2 with the Google Fonts CSS2 API and a Chrome user agent into `~/.reel-kit/brand/fonts/`.
- Logo: path to an SVG or PNG for the small top-left eyebrow (optional). Copy it into `~/.reel-kit/brand/`.

## 5. Round 4: taste
- Captions: pill highlight on the spoken word, bold 1-2 word stacks, clean small lines, or a box (a rounded plate whose words fill in as they are spoken). Lowercase or sentence case.
- Sound effects: literal sounds on real on-screen actions (recommended), or none. Music: none (recommended for talking heads) or a quiet bed.
- Framing: close and medium only (recommended). Leave `zooms` out of the profile: the cut measures each speaker's face and frames from that, so it works on a wide event shot and on a selfie alike. Only set a fixed `zooms` list if they insist.
- Things they never want to see. Offer the ones we learned: sparkles and glows, full-body wide shots, notes that repeat the caption, filler words behind the head, random whooshes.

## 6. Write the profile
Write `~/.reel-kit/profile.json` in the shape shown in `KIT/SPEC.md` (Per-user profile). Then build a sample: `python3 "$KIT/engine/preview.py" serif --look <their look>` and show them `poster.jpg` so they see their colors and fonts on a real frame. Adjust until they like it.

## Rules
- No em dashes in anything you write for them.
- Their words win over the look's defaults, every time.
- Save exactly what they said. Do not "improve" a color or a font they chose.
