#!/bin/bash
# Install tool for Locky Focus Widget systemd service

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
SERVICE_NAME="locky.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "Setting up Locky background service..."

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_DIR"

# Step 1: Fix paths in the service file to match current directory
sed -i "s|ExecStart=.*|ExecStart=$DIR/start.sh|" "$DIR/$SERVICE_NAME"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$DIR|" "$DIR/$SERVICE_NAME"

# Step 2: Copy service file to systemd directory
cp "$DIR/$SERVICE_NAME" "$SYSTEMD_DIR/"

# Step 3: Reload systemd and enable service
echo "Reloading systemd daemon..."
systemctl --user daemon-reload

echo "Enabling Locky service..."
systemctl --user enable "$SERVICE_NAME"

echo "Starting Locky service..."
systemctl --user restart "$SERVICE_NAME"

echo "------------------------------------------------"
echo "Installation Complete!"
echo "Locky will now start automatically upon login."
echo "To check status: systemctl --user status $SERVICE_NAME"
echo "To stop: systemctl --user stop $SERVICE_NAME"
echo "To view logs: journalctl --user -u $SERVICE_NAME -f"
echo "------------------------------------------------"
