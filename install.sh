#!/bin/bash
# Installation script for Weather Buddy

set -e

echo "Installing Weather Buddy..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check for pip
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is required but not installed."
    exit 1
fi

# Detect OS and install system dependencies
if [ -f /etc/debian_version ]; then
    echo "Detected Debian/Ubuntu-based system"
    echo "Installing system dependencies..."
    sudo apt update
    sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
elif [ -f /etc/fedora-release ]; then
    echo "Detected Fedora"
    echo "Installing system dependencies..."
    sudo dnf install -y python3-gobject gtk4 libadwaita
elif [ -f /etc/arch-release ]; then
    echo "Detected Arch Linux"
    echo "Installing system dependencies..."
    sudo pacman -S --needed python-gobject gtk4 libadwaita
else
    echo "Warning: Could not detect OS. Please install these dependencies manually:"
    echo "  - PyGObject (python3-gi)"
    echo "  - GTK 4.0"
    echo "  - libadwaita"
    echo ""
    read -p "Press Enter to continue with Python dependencies only..."
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Create desktop entry and bin symlink
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DESKTOP_FILE="$HOME/.local/share/applications/weather-buddy.desktop"

echo "Setting up symlinks and desktop entry..."
mkdir -p "$BIN_DIR"
mkdir -p "$HOME/.local/share/applications"

# Create symlink in ~/.local/bin
chmod +x "$SCRIPT_DIR/src/main.py"
ln -sf "$SCRIPT_DIR/src/main.py" "$BIN_DIR/weather-buddy"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Weather Buddy
Comment=Weather app for tracking remote colleagues' conditions
Exec=$BIN_DIR/weather-buddy
Path=$SCRIPT_DIR
Icon=weather-clear-symbolic
Terminal=false
Type=Application
Categories=GNOME;GTK;Utility;
StartupNotify=true
Keywords=weather;temperature;time;remote;
EOF

echo ""
echo "Installation complete!"
echo ""
echo "To run Weather Buddy:"
echo "  - From terminal: python3 $SCRIPT_DIR/src/main.py"
echo "  - From desktop: Search for 'Weather Buddy' in your applications"
echo ""
echo "Configuration will be stored in: ~/.config/weather-buddy/"
