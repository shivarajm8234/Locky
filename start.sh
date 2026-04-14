#!/bin/bash
# Start Locky Focus Widget

# Resolve the directory containing this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Add bundled libs to Python path
export PYTHONPATH="$DIR/libs"

# Auto-detect display server: use Wayland if running, otherwise fall back to X11
if [ -n "$WAYLAND_DISPLAY" ]; then
    export QT_QPA_PLATFORM=wayland
else
    export QT_QPA_PLATFORM=xcb
fi

# Launch the app
python3 "$DIR/main.py"
