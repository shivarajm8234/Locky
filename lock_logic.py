import subprocess
import json
import os

class GnomeLock:
    def __init__(self):
        self.keys_to_lock = [
            # App Switching
            ("org.gnome.desktop.wm.keybindings", "switch-applications"),
            ("org.gnome.desktop.wm.keybindings", "switch-applications-backward"),
            ("org.gnome.desktop.wm.keybindings", "switch-windows"),
            ("org.gnome.desktop.wm.keybindings", "switch-windows-backward"),
            ("org.gnome.shell.keybindings", "toggle-overview"),
            ("org.gnome.desktop.wm.keybindings", "close"), # Blocking Alt+F4
            
            # Workspaces
            ("org.gnome.desktop.wm.keybindings", "switch-to-workspace-left"),
            ("org.gnome.desktop.wm.keybindings", "switch-to-workspace-right"),
            ("org.gnome.desktop.wm.keybindings", "switch-to-workspace-up"),
            ("org.gnome.desktop.wm.keybindings", "switch-to-workspace-down"),
            ("org.gnome.desktop.wm.keybindings", "switch-to-workspace-last"),
            ("org.gnome.desktop.wm.keybindings", "move-to-workspace-left"),
            ("org.gnome.desktop.wm.keybindings", "move-to-workspace-right"),
            ("org.gnome.desktop.wm.keybindings", "move-to-workspace-up"),
            ("org.gnome.desktop.wm.keybindings", "move-to-workspace-down"),
            ("org.gnome.desktop.wm.keybindings", "move-to-workspace-last"),
            ("org.gnome.mutter", "overlay-key"), # Blocks Super Key alone
            ("org.gnome.shell.keybindings", "shift-overview-up"),
            ("org.gnome.shell.keybindings", "shift-overview-down"),
            ("org.gnome.shell.keybindings", "toggle-overview"),
        ]
        
        for i in range(1, 13):
            self.keys_to_lock.append(("org.gnome.desktop.wm.keybindings", f"switch-to-workspace-{i}"))
            self.keys_to_lock.append(("org.gnome.desktop.wm.keybindings", f"move-to-workspace-{i}"))

        self.backup_file = os.path.expanduser("~/Desktop/Locky/keybindings_backup.json")

    def get_setting(self, schema, key):
        try:
            result = subprocess.run(["gsettings", "get", schema, key], capture_output=True, text=True)
            return result.stdout.strip()
        except: return None

    def set_setting(self, schema, key, value):
        try:
            subprocess.run(["gsettings", "set", schema, key, value], check=True)
        except: pass

    def lock(self):
        if os.path.exists(self.backup_file):
            return

        backup = {}
        for schema, key in self.keys_to_lock:
            val = self.get_setting(schema, key)
            if val:
                backup[f"{schema}:{key}"] = val
                # Determine if string or array
                if val.startswith("'") or val.startswith('"'):
                    self.set_setting(schema, key, "''")
                else:
                    self.set_setting(schema, key, "[]")
        
        with open(self.backup_file, "w") as f:
            json.dump(backup, f)

    def unlock(self):
        if not os.path.exists(self.backup_file):
            return

        with open(self.backup_file, "r") as f:
            backup = json.load(f)

        for schema_key, val in backup.items():
            schema, key = schema_key.split(":")
            # Quote the value if it's a string literal to be safely set via gsettings
            if val.startswith("'") or val.startswith('"'):
                self.set_setting(schema, key, val)
            else:
                self.set_setting(schema, key, val)
        
        try:
            os.remove(self.backup_file)
        except OSError:
            pass
