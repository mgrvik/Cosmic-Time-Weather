"""
Main application window
"""
from gi.repository import Gtk, Adw, GLib, Gio, Gdk
import asyncio
import logging
from datetime import datetime

from ui.location_card import WeatherLocationCard
from ui.settings_dialog import SettingsDialog
from services.config import config_manager, Config
from services.weather_api import weather_api, WeatherData

log = logging.getLogger(__name__)


class WeatherBuddyWindow(Adw.ApplicationWindow):
    """Main application window"""

    def __init__(self, app, **kwargs):
        super().__init__(application=app, **kwargs)
        self.app = app
        self.weather_cards = []
        self._update_timeout_id = None

        self._setup_window()
        self._load_config()
        self._setup_ui()
        self._start_weather_update()

    def _setup_window(self):
        """Configure window properties"""
        self.set_title("Weather Buddy")
        self.set_default_size(900, 500)
        self.set_size_request(700, 400)

        # Apply CSS
        self._load_css()

    def _load_css(self):
        """Load custom CSS for styling"""
        css_provider = Gtk.CssProvider()

        css = """
        /* Main window styling */
        weather-window {
            background-color: @background;
        }

        /* Weather card styling */
        .weather-card-frame {
            border-radius: 16px;
            border: 1px solid alpha(@borders, 0.3);
            padding: 8px;
        }

        /* Temperature display */
        .temperature-display {
            font-size: 2.5rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: @accent_color;
        }

        /* Weather icon glow effect */
        .weather-icon {
            -gtk-icon-shadow: 0 2px 8px alpha(@accent_color, 0.3);
        }

        /* Time badge */
        .time-badge {
            background: alpha(@accent_bg_color, 0.15);
            border-radius: 12px;
            padding: 4px 10px;
        }

        /* Weather description */
        .weather-description {
            font-size: 1.1rem;
            color: @window_fg_color;
            font-weight: 500;
        }

        /* Cards container */
        .cards-flow {
            padding: 12px;
        }

        /* Header styling */
        .header-title {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.01em;
        }

        .header-subtitle {
            font-size: 0.9rem;
        }

        /* Status overlay */
        .status-overlay {
            background: alpha(@background, 0.85);
        }

        /* Card gradient variations based on time of day */
        .card-morning {
            background: linear-gradient(145deg, alpha(#FFE4B5, 0.3), alpha(#FFA500, 0.15));
        }

        .card-afternoon {
            background: linear-gradient(145deg, alpha(#87CEEB, 0.3), alpha(#4169E1, 0.15));
        }

        .card-evening {
            background: linear-gradient(145deg, alpha(#DDA0DD, 0.3), alpha(#8B008B, 0.15));
        }

        .card-night {
            background: linear-gradient(145deg, alpha(#191970, 0.4), alpha(#000080, 0.25));
        }

        .card-night .temperature-display {
            color: #E0E0FF;
        }

        .card-night .weather-description {
            color: #D0D0FF;
        }

        /* Delete button on cards */
        .delete-btn {
            color: #e74c3c;
            opacity: 0.7;
            min-width: 28px;
            min-height: 28px;
        }

        .delete-btn:hover {
            opacity: 1.0;
            color: #c0392b;
            background: alpha(#e74c3c, 0.15);
        }
        """

        css_provider.load_from_data(css.encode())

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _setup_ui(self):
        """Create the main UI"""
        # Main vertical box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Header bar with buttons
        self._setup_header()

        # Main content with toolbar view
        self.toolbar_view = Adw.ToolbarView()
        self.toolbar_view.add_top_bar(self.header_bar)
        self.main_box.append(self.toolbar_view)

        # Content page
        self.content_page = Adw.StatusPage()
        self.content_page.set_icon_name("weather-clear-symbolic")
        self.content_page.set_title("Weather Buddy")
        self.content_page.set_description("Loading weather data...")

        # Cards container (vertical box with spacing)
        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.cards_box.set_spacing(12)
        self.cards_box.set_margin_start(24)
        self.cards_box.set_margin_end(24)
        self.cards_box.set_margin_top(12)
        self.cards_box.set_margin_bottom(24)

        # Clamp for centering content
        clamp = Adw.Clamp()
        clamp.set_maximum_size(1200)
        clamp.set_child(self.cards_box)

        # Use a stack to switch between loading and content
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        
        # Add loading page (StatusPage)
        self.stack.add_named(self.content_page, "loading")

        # Scrolled window for many cards
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_child(clamp)

        # Add content page
        self.stack.add_named(scrolled, "content")
        
        self.toolbar_view.set_content(self.stack)
        
        # Initially show loading if no cards, otherwise content
        self.stack.set_visible_child_name("loading")
        
        # Apply initial theme
        self._apply_theme(self.config.theme)

        # Loading overlay
        self._setup_loading_overlay()

    def _setup_header(self):
        """Set up the header bar"""
        self.header_bar = Adw.HeaderBar()
        self.header_bar.add_css_class("flat")

        # Menu button
        menu = Gio.Menu()

        # Settings action
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self._on_settings)
        self.app.add_action(settings_action)
        menu.append("Settings", "app.settings")

        # Refresh action
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self._on_refresh)
        self.app.add_action(refresh_action)
        menu.append("Refresh Now", "app.refresh")

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.app.add_action(about_action)
        menu.append("About", "app.about")

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(menu)
        self.header_bar.pack_end(menu_button)

        # Refresh button
        self.refresh_button = Gtk.Button()
        self.refresh_button.set_icon_name("view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Refresh Weather")
        self.refresh_button.connect("clicked", lambda b: self._refresh_weather())
        self.header_bar.pack_end(self.refresh_button)

    def _setup_loading_overlay(self):
        """Create loading overlay"""
        self.overlay = Gtk.Overlay()
        self.loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.loading_box.set_spacing(12)
        self.loading_box.set_halign(Gtk.Align.CENTER)
        self.loading_box.set_valign(Gtk.Align.CENTER)
        self.loading_box.add_css_class("status-overlay")
        self.loading_box.set_visible(False)

        spinner = Gtk.Spinner()
        spinner.set_spinning(True)
        spinner.set_size_request(48, 48)
        self.loading_box.append(spinner)

        label = Gtk.Label(label="Updating weather...")
        label.add_css_class("title-4")
        self.loading_box.append(label)

        # Can't directly overlay with Adw.ToolbarView
        # So we'll use status_page for loading states

    def _load_config(self):
        """Load configuration"""
        self.config = config_manager.load()

    def _start_weather_update(self):
        """Start periodic weather updates"""
        self._refresh_weather()

        # Schedule periodic updates
        interval = self.config.update_interval * 1000  # Convert to milliseconds
        self._update_timeout_id = GLib.timeout_add(
            interval,
            self._scheduled_update
        )

    def _scheduled_update(self) -> bool:
        """Called periodically to update weather"""
        self._refresh_weather()
        return True  # Continue the timer

    def _refresh_weather(self):
        """Refresh weather data for all locations"""
        self._set_loading(True)

        async def fetch_all():
            tasks = []
            for location in self.config.locations:
                tasks.append(
                    weather_api.get_weather(
                        location.latitude,
                        location.longitude,
                        location.name,
                        location.country,
                        location.timezone
                    )
                )

            return await asyncio.gather(*tasks, return_exceptions=True)

        def on_fetch_done(future):
            try:
                results = future.result()
                GLib.idle_add(self._update_ui, results)
            except Exception as e:
                log.error(f"Error fetching weather: {e}")
                GLib.idle_add(self._show_error, str(e))
            finally:
                GLib.idle_add(self._set_loading, False)

        from services.async_utils import run_async
        future = run_async(fetch_all())
        future.add_done_callback(on_fetch_done)

    def _set_loading(self, loading: bool):
        """Set loading state"""
        self.refresh_button.set_sensitive(not loading)
        if loading:
            self.content_page.set_description("Updating weather data...")
            # Don't switch to loading if we already have cards showing
            if not self.weather_cards:
                self.stack.set_visible_child_name("loading")

    def _update_ui(self, results):
        """Update UI with new weather data"""
        # Clear existing cards
        while card := self.cards_box.get_first_child():
            self.cards_box.remove(card)

        self.weather_cards = []

        # Create/update cards
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.error(f"Error for location {i}: {result}")
                continue

            if isinstance(result, WeatherData):
                # Add display name from config
                if i < len(self.config.locations):
                    result.display_name = self.config.locations[i].display_name

                card = WeatherLocationCard(
                    weather_data=result,
                    temp_unit=self.config.temperature_unit,
                    show_feels_like=self.config.show_feels_like,
                    show_humidity=self.config.show_humidity,
                    show_wind=self.config.show_wind,
                    on_delete=self._on_card_delete
                )

                # Add time-of-day class
                hour = result.local_time.hour
                if 6 <= hour < 12:
                    card.add_css_class("card-morning")
                elif 12 <= hour < 17:
                    card.add_css_class("card-afternoon")
                elif 17 <= hour < 21:
                    card.add_css_class("card-evening")
                else:
                    card.add_css_class("card-night")

                self.cards_box.append(card)
                self.weather_cards.append(card)

        # Switch to content view
        if self.weather_cards:
            self.stack.set_visible_child_name("content")
        else:
            self.stack.set_visible_child_name("loading")
            self.content_page.set_description("No locations configured or error fetching data")

        # Update status
        now = datetime.now().strftime("%I:%M %p")
        self.content_page.set_description(f"Last updated: {now}")

    def _show_error(self, message: str):
        """Show error message"""
        self.content_page.set_description(f"Error: {message}")
        self.content_page.set_icon_name("dialog-warning-symbolic")

    def _on_settings(self, action, param):
        """Open settings dialog"""
        log.info("Opening settings dialog")

        def on_change(config):
            log.info(f"Main window received live change with temp_unit={config.temperature_unit}")
            self.config = config
            config_manager.config = config

            # Check if locations changed (simple count or name check)
            current_count = len(self.weather_cards)
            new_count = len(config.locations)

            if current_count != new_count:
                # Trigger full refresh for location changes
                self._refresh_weather()
            else:
                # Update existing cards with new unit and display flags
                for card in self.weather_cards:
                    card.set_temperature_unit(config.temperature_unit)
                    card.set_show_details(
                        config.show_feels_like,
                        config.show_humidity,
                        config.show_wind
                    )
            
            # Apply theme change live
            self._apply_theme(config.theme)

        def on_save(config):
            log.info(f"Main window received config save with temp_unit={config.temperature_unit}")
            self.config = config
            config_manager.config = config
            config_manager.save()

            # Restart update timer with new interval
            if self._update_timeout_id:
                GLib.source_remove(self._update_timeout_id)

            interval = self.config.update_interval * 1000
            self._update_timeout_id = GLib.timeout_add(
                interval,
                self._scheduled_update
            )

            # Final refresh to be sure
            self._refresh_weather()

        try:
            dialog = SettingsDialog(
                parent=self,
                config=self.config,
                on_save=on_save,
                on_change=on_change
            )
            dialog.present()
            log.info("Settings dialog presented")
        except Exception as e:
            log.error(f"Error opening settings: {e}")

    def _on_card_delete(self, card):
        """Handle deletion of a weather card from the main view"""
        if card in self.weather_cards:
            idx = self.weather_cards.index(card)
            if idx < len(self.config.locations):
                removed = self.config.locations.pop(idx)
                log.info(f"Removed location: {removed.name}")
                config_manager.config = self.config
                config_manager.save()
                self._refresh_weather()

    def _apply_theme(self, theme: str):
        """Apply theme preference to the application"""
        try:
            style_manager = Adw.StyleManager.get_default()
            if theme == "light":
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            elif theme == "dark":
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            else:
                # Use DEFAULT or PREFER_LIGHT depending on availability
                if hasattr(Adw.ColorScheme, 'PREFER_LIGHT'):
                    style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
                else:
                    style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        except Exception as e:
            log.warning(f"Could not apply theme: {e}")

    def _on_refresh(self, action, param):
        """Force refresh"""
        self._refresh_weather()

    def _on_about(self, action, param):
        """Show about dialog with fallback for older Libadwaita"""
        try:
            # Try Adw.AboutWindow (1.2+)
            if hasattr(Adw, 'AboutWindow'):
                about = Adw.AboutWindow()
                about.set_application_name("Weather Buddy")
                about.set_application_icon("weather-clear-symbolic")
                about.set_version("1.0.0")
                about.set_developer_name("Weather Buddy Team")
                about.set_license_type(Gtk.License.GTK_LICENSE_GPL_3_0)
                about.set_website("https://github.com/weather-buddy")
                about.set_issue_url("https://github.com/weather-buddy/issues")
                about.set_developers(["Weather Buddy Team"])
                about.set_comments(
                    "A beautiful weather app for keeping track of weather "
                    "conditions for your remote colleagues."
                )
                about.set_transient_for(self)
                about.present()
                return
        except Exception:
            pass

        # Fallback to Gtk.AboutDialog
        about = Gtk.AboutDialog()
        about.set_program_name("Weather Buddy")
        about.set_logo_icon_name("weather-clear-symbolic")
        about.set_version("1.0.0")
        about.set_authors(["Weather Buddy Team"])
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_website("https://github.com/weather-buddy")
        about.set_comments(
            "A beautiful weather app for keeping track of weather "
            "conditions for your remote colleagues."
        )
        about.set_transient_for(self)
        about.present()

    def cleanup(self):
        """Clean up resources"""
        if self._update_timeout_id:
            GLib.source_remove(self._update_timeout_id)
