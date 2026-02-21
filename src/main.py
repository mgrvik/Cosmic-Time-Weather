#!/usr/bin/env python3
"""
Weather Buddy - A beautiful weather app for GNOME/COSMIC

Quickly see weather conditions for your remote colleagues before calls.
"""
import sys
import os
import gi
import asyncio
import logging
import concurrent.futures

# Add the src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.async_utils import run_async, shutdown_executor

# GTK imports
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib

# Local imports
from ui.main_window import WeatherBuddyWindow
from services.weather_api import weather_api

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Thread pool for async operations - Moved to async_utils


class WeatherBuddyApp(Adw.Application):
    """Main application class"""

    def __init__(self):
        super().__init__(
            application_id="com.github.weatherbuddy",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

        self.window = None

        # Set up actions
        self._setup_actions()

        # Style manager for dark mode support
        self.style_manager = Adw.StyleManager.get_default()
        self.style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

    def _setup_actions(self):
        """Set up application actions"""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)

        # Keyboard shortcut
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self):
        """Called when app is activated"""
        if self.window is None:
            self.window = WeatherBuddyWindow(self)

        self.window.present()

    def do_shutdown(self):
        """Clean up on shutdown"""
        if self.window:
            self.window.cleanup()

        # Shutdown executor
        shutdown_executor()

        # Call parent shutdown - GTK4 requires this pattern
        Adw.Application.do_shutdown(self)

    def _on_quit(self, action, param):
        """Quit the application"""
        self.quit()




def main():
    """Main entry point"""
    # Create and run app
    app = WeatherBuddyApp()

    exit_code = app.run(sys.argv)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
