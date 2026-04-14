# Locky

**Locky** is an aggressive, high-tech productivity widget for Linux (GNOME/Wayland/X11) that enforces extreme focus during deep work sessions. Rather than merely acting as a timer, Locky physically seizes control of the GNOME desktop environment, shuts down distractions, and physically traps the user inside their designated work applications until the session finishes.

## Features Let Loose
- **Absolute Desktop Lockdown:** Intercepts and blanks out GNOME Shell keys including `Super/Windows Key`, `Alt+Tab`, `Alt+F4`, and all Workspace Shifting operations to prevent escaping the active window.
- **Dynamic Browser Enforcement:** Enter "browser" in your mission objective, and Locky will spawn a custom zero-day Chrome/Brave extension on the spot. It forces the browser to remain only on the URLs you explicitly whitelist, destroying any newly opened distracting tabs.
- **Distraction Terminations:** Locky actively monitors your process list. If apps like Steam, Discord, Telegram, or Spotify are detected during a session, they are killed on sight.
- **Futuristic PyQt6 UI:** A minimalist, widget-based HUD that stays on top, transparent, and aesthetically tracks your focus session safely over your work.
- **Failsafe Support:** For sudden glitches during lockdown, the standalone `emergency_unlock.py` serves as a quick system-state restore.

## Requirements
- \`python3\`
- PyQt6
- psutil
- GNOME Desktop Environment (\`gsettings\` enabled)
- (Optional) Google Chrome, Chromium, or Brave for browser-locked sessions

## Setup & Running

1. **Install Dependencies:**
   ```bash
   pip install PyQt6 psutil
   ```
2. **Run Locky:**
   ```bash
   python3 main.py
   ```

## How to used
1. Launch Locky. The sleek HUD window will spawn in the center of your screen (feel free to drag it anywhere).
2. Enter your **Mission Objective** (E.g., \`coding\`, \`reading\`, \`browser\`).
3. Enter your **Duration in Minutes**.
   - *If your task is "browser", an extra field appears letting you specify allowed URLs (e.g., \`github.com, stackoverflow.com\`).*
4. Hit **Initiate Protocol**.

*Locky takes control. No exiting, no workspace switching. Work until the system unlocks.*

## Failsafe Restore
Should your machine forcefully shut down during a session, leaving your workspace commands neutralized:
```bash
python3 emergency_unlock.py
```
This forces an immediate system restore over your keybindings.
