#!/bin/bash
# Start Locky Focus Widget
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
export PYTHONPATH="$DIR/libs"
export QT_QPA_PLATFORM=wayland
python3 "$DIR/main.py"
