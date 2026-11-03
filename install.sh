#!/usr/bin/env bash
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/.local/share/soundpad_linux"
BIN="$HOME/.local/bin/soundpad_linux"
DESKTOP="$HOME/.local/share/applications/soundpad_linux.desktop"

if [ "$1" = "--uninstall" ]; then
    pkill -f "python3 -m soundpad_linux" 2>/dev/null || true
    rm -rf "$APP_DIR" "$BIN" "$DESKTOP"
    echo "Soundpad_Linux removed. Your settings are kept in ~/.config/soundpad_linux"
    exit 0
fi

pkgs=()
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || pkgs+=(ffmpeg)
command -v pactl  >/dev/null && command -v pacat   >/dev/null || pkgs+=(pulseaudio-utils)
python3 -c "import PySide6" 2>/dev/null || pkgs+=(python3-pyside6)

if [ ${#pkgs[@]} -gt 0 ]; then
    echo "Missing packages: ${pkgs[*]}"
    if command -v dnf >/dev/null; then
        sudo dnf install -y "${pkgs[@]}"
    else
        echo "Please install these packages with your package manager and run this script again."
        exit 1
    fi
    if ! python3 -c "import PySide6" 2>/dev/null; then
        python3 -m pip install --user PySide6-Essentials
    fi
fi

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR" "$(dirname "$BIN")" "$(dirname "$DESKTOP")"
cp -r "$SRC/src/soundpad_linux" "$APP_DIR/"
find "$APP_DIR" -name "__pycache__" -type d -prune -exec rm -rf {} +

cat > "$BIN" <<EOF
#!/bin/sh
PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m soundpad_linux "\$@"
EOF
chmod 755 "$BIN"

sed "s|^Exec=.*|Exec=$BIN|" "$SRC/data/soundpad_linux.desktop" > "$DESKTOP"
update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true

echo
echo "Done! Start Soundpad_Linux from your application menu or with: soundpad_linux"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "Note: ~/.local/bin is not in your PATH – use the full path $BIN for hotkeys." ;;
esac
