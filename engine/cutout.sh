#!/usr/bin/env bash
# cutout.sh <clip_dir> : cut the speakers out of assets/aroll.mp4 into assets/subject.webm (VP9 with alpha).
# Uses HyperFrames' local background remover (free, runs on this machine). The cutout lets words sit behind heads
# and lets the engine read where the speakers are.
set -eo pipefail
D="${1:?usage: cutout.sh <clip_dir>}"
HF_VERSION=${HF_VERSION:-0.8.61}
[ -f "$D/assets/aroll.mp4" ] || { echo "cutout: $D/assets/aroll.mp4 missing (run engine/cut.py first)"; exit 1; }
rm -f "$D/assets/subject.webm" "$D/assets/.tailpad"
npx --yes hyperframes@$HF_VERSION remove-background "$D/assets/aroll.mp4" -o "$D/assets/subject.webm" 2>&1 \
  | tr '\r' '\n' | grep -v -E "Frame [0-9]+/|Loading model|onnxruntime|VerifyEachNode|^\s*$" || true
[ -f "$D/assets/subject.webm" ] || { echo "cutout: no subject.webm written"; exit 1; }
echo "cutout: $D/assets/subject.webm"
