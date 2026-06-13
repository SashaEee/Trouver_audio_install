#!/bin/bash
# RoboVoice — one-command start
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "→ creating venv & installing deps…"
  python3 -m venv venv
  ./venv/bin/pip install -q --upgrade pip
  ./venv/bin/pip install -q -r requirements.txt
fi

# session cookie secret (ephemeral if unset)
export ROOMTONE_SECRET="${ROOMTONE_SECRET:-$(python3 -c 'import secrets;print(secrets.token_hex(16))')}"
# optional: GH_TOKEN to host your OWN custom packs (see docs/ADD_YOUR_PACK.md)
[ -f secret.env ] && source secret.env

command -v ffmpeg >/dev/null || echo "⚠  ffmpeg not found — needed only for building custom packs"

echo "RoboVoice → http://127.0.0.1:8765"
exec venv/bin/python app/server.py
