#!/usr/bin/env bash
# tailpad.sh <clip_dir> : adds a 1.0 s hold of the last frame to assets/aroll.mp4 (silent audio) and assets/subject.webm (alpha kept).
# Idempotent via a marker file. Run after cutout.sh so the reel does not end on a cut-off word.
set -e
D="${1:?usage: tailpad.sh <clip_dir>}"; cd "$D/assets"
[ -f .tailpad ] && { echo "already padded"; exit 0; }
ffmpeg -hide_banner -loglevel error -y -i aroll.mp4 -vf "tpad=stop_mode=clone:stop_duration=1" -af "apad=pad_dur=1" \
  -c:v libx264 -crf 16 -preset fast -pix_fmt yuv420p -g 30 -keyint_min 30 -c:a aac -b:a 256k -movflags +faststart aroll_pad.mp4
mv aroll.mp4 aroll_nopad.mp4; mv aroll_pad.mp4 aroll.mp4
if [ -f subject.webm ]; then
  ffmpeg -hide_banner -loglevel error -y -c:v libvpx-vp9 -i subject.webm -vf "tpad=stop_mode=clone:stop_duration=1,format=yuva420p" \
    -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 30 -row-mt 1 -auto-alt-ref 0 subject_pad.webm
  mv subject.webm subject_nopad.webm; mv subject_pad.webm subject.webm
fi
touch .tailpad
a=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 aroll.mp4)
s=$( [ -f subject.webm ] && ffprobe -v error -c:v libvpx-vp9 -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 subject.webm || echo none)
echo "$D padded: aroll $a frames, subject $s frames"
