#!/bin/bash
# Start Locky Focus Widget

# Resolve the directory containing this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Add bundled libs to Python path
export PYTHONPATH="$DIR/libs"

# Force X11 (xcb) backend for better movability/positioning on Linux (including Wayland sessions)
# Wayland's security model restricts absolute positioning which the widget needs.
export QT_QPA_PLATFORM=xcb

# Use virtual environment if it exists
if [ -f "$DIR/venv/bin/python3" ]; then
    PYTHON_EXEC="$DIR/venv/bin/python3"
else
    PYTHON_EXEC="python3"
fi

# Launch the app
$PYTHON_EXEC "$DIR/main.py"
