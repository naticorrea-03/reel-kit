#!/usr/bin/env bash
# master.sh <in.mp4> <out.mp4> : two-pass fixed gain to -14 LUFS integrated, then a true-peak limiter.
# The meter has NO highpass in its chain: a highpass in the meter adds about 1.4 dB of fake overshoot.
# The output chain keeps a gentle 75 Hz highpass (mic rumble) before the gain.
set -e
in="${1:?usage: master.sh <in.mp4> <out.mp4>}"; out="${2:?usage: master.sh <in.mp4> <out.mp4>}"
TARGET=${TARGET:--14}
meas(){ ffmpeg -hide_banner -nostats -i "$1" -map 0:a:0 -af "ebur128=peak=true:framelog=verbose" -f null - 2>&1 | grep -E "^\s+(I|Peak):" | awk '{print $2}' | tr '\n' ' '; }
set -- $(meas "$in"); G=$(python3 -c "print(round($TARGET - ($1), 2))")
for pass in 1 2; do
  ffmpeg -hide_banner -loglevel error -y -i "$in" -map 0:v -map 0:a -c:v copy \
    -af "highpass=f=75,volume=${G}dB,aresample=192000,alimiter=limit=0.80:attack=5:release=50:level=false:latency=true,aresample=48000" \
    -c:a aac -b:a 256k -movflags +faststart "$out"
  set -- $(meas "$out"); [ $pass = 1 ] && G=$(python3 -c "print(round($G + ($TARGET - ($1)), 2))")
done
echo "I=$1 peak=$2"
