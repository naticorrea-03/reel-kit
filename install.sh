#!/usr/bin/env bash
# reel-kit installer: links the skills into Claude Code and checks the machine.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
mkdir -p "$DEST" "$HOME/.reel-kit"
for s in "$KIT"/skills/*/; do
  name="$(basename "$s")"
  if [ -e "$DEST/$name" ] && [ ! -L "$DEST/$name" ]; then
    echo "skip $name: $DEST/$name exists and is not a link"
    continue
  fi
  ln -sfn "${s%/}" "$DEST/$name"
  echo "linked $name"
done
printf '%s\n' "$KIT" > "$HOME/.reel-kit/kit_path"
python3 "$KIT/engine/doctor.py" || true
echo
echo "Next: open Claude Code and run /reel-setup"
