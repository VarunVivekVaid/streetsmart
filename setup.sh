#!/usr/bin/env bash
set -euo pipefail

# 1) Remove old venv if it exists
if [[ -d "venv" ]]; then
  echo "🗑  Removing old virtualenv…"
  rm -rf venv
fi

# 2) Create & activate
echo "🛠  Creating new virtualenv…"
python3 -m venv venv
source venv/bin/activate

# 3) Upgrade pip & install everything from requirements.txt
echo "⬆️  Upgrading pip & installing dependencies…"
pip install --upgrade pip
pip install -r requirements.txt

echo "✅  Setup complete!  
👉  Activate with:  source venv/bin/activate"
