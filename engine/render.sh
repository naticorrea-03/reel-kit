#!/usr/bin/env bash
# render.sh <project_dir> <slug>... [--look id]
# build -> layout audit gate -> hyperframes render -> two-pass master to -14 LUFS -> phone copy -> beat sheet -> words check
#   FORCE=1      render even when the layout audit finds errors (the report still gets written)
#   WORDS=0      skip the words check (re-transcribes the master and diffs it against the cut)
#   HF_VERSION   hyperframes version (default 0.8.61)
# Outputs: <project>/renders/<slug>.mp4, renders/phone/<slug>.mp4, audits/<slug>/report.md, audits/<slug>/beats/sheet-*.jpg
# Read every beat sheet frame yourself before anyone sees the reel. Numbers only prove what they measure.
E="$(cd "$(dirname "$0")" && pwd)"
P="$(cd "${1:?usage: render.sh <project_dir> <slug>... [--look id]}" && pwd)"; shift
LOOK=(); SLUGS=()
while [ $# -gt 0 ]; do
  if [ "$1" = "--look" ]; then LOOK=(--look "$2"); shift 2; else SLUGS+=("$1"); shift; fi
done
HF_VERSION=${HF_VERSION:-0.8.61}
mkdir -p "$P/renders/phone" "$P/logs"
status=0
for s in "${SLUGS[@]}"; do
  C="$P/clips/$s"; L="$P/logs/$s"
  python3 -I "$E/build.py" "$P" "$s" "${LOOK[@]}" > "$L.build.log" 2>&1 || { cat "$L.build.log"; echo "$s BUILD FAILED"; status=1; continue; }
  grep -E "^(WARN|NOTE)" "$L.build.log"
  # gate 1: frame-by-frame layout audit (faces, overlaps, fit, safe zone, spacing, arrows, caption cues)
  if ! "$E/audit/audit.sh" "$P" "$s"; then
    if [ -z "$FORCE" ]; then echo "$s AUDIT FAILED: see audits/$s/report.md + issues-sheet.jpg (FORCE=1 renders anyway)"; status=1; continue; fi
    echo "$s audit failed, rendering anyway (FORCE=1)"
  fi
  raw="$P/renders/$s-raw.mp4"; rm -f "$raw"
  (cd "$C" && PRODUCER_BROWSER_GPU_MODE=${PRODUCER_BROWSER_GPU_MODE:-hardware} npx --yes hyperframes@$HF_VERSION render . -o "$raw" --fps 30 > "$L.render.log" 2>&1) \
    || { tail -20 "$L.render.log"; echo "$s RENDER FAILED: see logs/$s.render.log"; status=1; continue; }
  lv=$("$E/master.sh" "$raw" "$P/renders/$s.mp4") || { echo "$s MASTER FAILED"; status=1; continue; }
  ffmpeg -hide_banner -loglevel error -y -i "$P/renders/$s.mp4" -vf scale=720:1280 -c:v libx264 -crf 23 -preset fast -pix_fmt yuv420p \
    -c:a aac -b:a 160k -movflags +faststart "$P/renders/phone/$s.mp4"
  # gate 3: beat sheet, one labelled frame per graphic at entrance, middle and exit (never blocks; read every sheet)
  python3 "$E/audit/beatsheet.py" "$P" "$s" "$P/renders/$s.mp4" || echo "$s BEATSHEET FAILED"
  # gate 2: words check, the master re-transcribed against the cut (95% or better is normal)
  if [ "${WORDS:-1}" != "0" ]; then python3 "$E/audit/words_check.py" "$P" "$s" "$P/renders/$s.mp4" || echo "$s WORDS CHECK under 95%: listen to the flagged spots"; fi
  echo "DONE $s  $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$P/renders/$s.mp4" | cut -c1-5)s  $lv"
done
exit $status
