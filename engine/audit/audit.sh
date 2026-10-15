#!/usr/bin/env bash
# audit.sh <project_dir> <slug>... : frame-by-frame layout audit of the built composition (run before render).
# Writes <project>/audits/<slug>/report.md + report.json + issues-sheet.jpg. Exit 1 if any clip has errors.
# AUDIT_FPS (default 6) sets the sampling rate. HF_VERSION (default 0.8.61) picks the hyperframes build whose Chrome is used.
shopt -s nullglob
A="$(cd "$(dirname "$0")" && pwd)"
P="$(cd "${1:?usage: audit.sh <project_dir> <slug>...}" && pwd)"; shift
HF_VERSION=${HF_VERSION:-0.8.61}; export HF_VERSION
export HF_CHROME=${HF_CHROME:-$(npx --yes hyperframes@$HF_VERSION browser path 2>/dev/null | tail -1)}
[ -x "$HF_CHROME" ] || { echo "audit: no headless Chrome from hyperframes@$HF_VERSION (got '$HF_CHROME'). Run python3 engine/doctor.py"; exit 2; }
fail=0
for s in "$@"; do
  C="$P/clips/$s"; O="$P/audits/$s"
  [ -f "$C/index.html" ] || { echo "$s: no index.html (build first)"; fail=1; continue; }
  mkdir -p "$O"
  # stale outputs from an older build must never pass as fresh
  rm -f "$O"/full-*.jpg "$O"/mask-*.png "$O"/stage-*.png "$O"/faces.json "$O"/samples.json "$O"/report.* "$O"/issues-sheet.jpg
  node "$A/probe.mjs" "$C" "$O" "${AUDIT_FPS:-6}" 2>&1 | grep -v REQFAIL | tail -1
  [ -f "$O/samples.json" ] || { echo "$s probe crashed, retrying once"; node "$A/probe.mjs" "$C" "$O" "${AUDIT_FPS:-6}" 2>&1 | grep -v REQFAIL | tail -3; }
  [ -f "$O/samples.json" ] || { echo "$s: probe failed twice"; fail=1; continue; }
  python3 "$A/analyze.py" "$O" "$s" "$C/index.html" || fail=1
  rm -f "$O"/stage-*.png   # faces.json caches the face boxes; masks stay for re-analysis
done
exit $fail
