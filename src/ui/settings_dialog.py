"""
Settings dialog for configuring locations and preferences
"""
from gi.repository import Gtk, Adw, GLib, Gio
import asyncio
import logging

from services.config import Config, Location
from services.weather_api import weather_api

log = logging.getLogger(__name__)


class LocationRow(Adw.ExpanderRow):
    """A row for configuring a single location"""

    def __init__(self, location: Location = None, on_changed=None, **kwargs):
        super().__init__(**kwargs)
        self.location = location
        self.on_changed = on_changed
        self._setup_ui()

    def _setup_ui(self):
        """Create the row UI"""

        # Search entry with completion
        self.search_row = Adw.EntryRow()
        self.search_row.set_title("Search City")
        self.search_row.set_show_apply_button(True)
        self.search_row.connect("apply", self._on_search)
        self.search_row.connect("changed", self._on_search_changed)
        if self.location:
            self.search_row.set_text(f"{self.location.name}, {self.location.country}")
        self.add_row(self.search_row)

        # Search results dropdown
        self.results_box = Gtk.ListBox()
        self.results_box.add_css_class("boxed-list")
        self.results_box.set_margin_top(6)
        self.results_box.set_margin_bottom(6)
        self.results_box.set_margin_start(12)
        self.results_box.set_margin_end(12)
        self.results_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.results_box.connect("row-activated", self._on_result_selected)
        self.results_box.set_visible(False)

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.add_css_class("dim-label")
        self.status_label.add_css_class("caption")
        self.status_label.set_margin_top(4)
        self.status_label.set_visible(False)

        # Container for results + status
        results_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        results_container.append(self.results_box)
        results_container.append(self.status_label)
        self.add_row(results_container)

        # Hidden fields to store coordinates
        self._lat = self.location.latitude if self.location else 0
        self._lon = self.location.longitude if self.location else 0
        self._timezone = self.location.timezone if self.location else ""
        self._country = self.location.country if self.location else ""
        self._city_name = self.location.name if self.location else ""

    def _on_search_changed(self, entry):
        """Handle search text changes with debounce"""
        # Cancel any pending search
        if hasattr(self, '_search_timeout_id') and self._search_timeout_id:
            GLib.source_remove(self._search_timeout_id)

        text = entry.get_text().strip()
        if len(text) < 2:
            self.results_box.set_visible(False)
            self.status_label.set_visible(False)
            return

        # Debounce search
        self._search_timeout_id = GLib.timeout_add(300, self._do_search, text)

    def _do_search(self, text: str) -> bool:
        """Perform the actual search"""
        self.status_label.set_text("Searching...")
        self.status_label.set_visible(True)

        async def search():
            return await weather_api.search_location(text)

        def on_search_done(future):
            try:
                results = future.result()
                # Must update UI on main thread
                GLib.idle_add(self._show_search_results, results)
            except Exception as e:
                log.error(f"Search error: {e}")
                GLib.idle_add(self._show_search_error, str(e))

        from services.async_utils import run_async
        future = run_async(search())
        future.add_done_callback(on_search_done)
        return False

    def _show_search_results(self, results):
        """Show search results (must be called on main thread)"""
        # Clear existing results
        while child := self.results_box.get_first_child():
            self.results_box.remove(child)

        for result in results[:5]:
            row = Adw.ActionRow()
            row.set_title(result["name"])
            row.set_subtitle(f"{result.get('admin1', '')} {result.get('country', '')}".strip())
            row.set_activatable(True)
            row.result_data = result
            self.results_box.append(row)

        self.results_box.set_visible(len(results) > 0)
        self.status_label.set_visible(len(results) == 0)
        if len(results) == 0:
            self.status_label.set_text("No results found")

    def _show_search_error(self, message):
        """Show search error (must be called on main thread)"""
        self.status_label.set_text(f"Search failed: {message}")
        self.status_label.set_visible(True)

    def _on_search(self, entry):
        """Handle search apply"""
        pass  # Handled by changed signal with debounce

    def _on_result_selected(self, listbox, row):
        """Handle selection of a search result"""
        data = row.result_data

        self._lat = data["latitude"]
        self._lon = data["longitude"]
        self._timezone = data["timezone"]
        self._country = data.get("country", "")
        self._city_name = data["name"]

        self.search_row.set_text(f"{data['name']}, {data.get('country', '')}")
        self.results_box.set_visible(False)
        self.status_label.set_visible(False)

        self._on_changed()

    def _on_changed(self, *args):
        """Handle any change"""
        if self.on_changed:
            self.on_changed(self)

    def get_location(self) -> Location:
        """Get the configured location"""
        return Location(
            name=self._city_name,
            country=self._country,
            latitude=self._lat,
            longitude=self._lon,
            timezone=self._timezone,
            display_name=self._city_name
        )

    def is_valid(self) -> bool:
        """Check if location is valid"""
        return bool(self._city_name and self._timezone)


class SettingsDialog(Adw.PreferencesWindow):
    """Settings window for the application"""

    def __init__(self, parent, config: Config, on_save=None, on_change=None, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Weather Buddy Settings")
        self.set_default_size(500, 600)

        self.config = config
        self.on_save = on_save
        self.on_change = on_change
        self.location_rows = []

        self._setup_ui()

    def _setup_ui(self):
        """Create the settings UI"""

        # General settings page
        general_page = Adw.PreferencesPage()
        general_page.set_title("General")
        general_page.set_icon_name("preferences-system-symbolic")
        self.add(general_page)

        # Appearance group
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title("Appearance")
        general_page.add(appearance_group)

        # Temperature unit
        self.unit_row = Adw.ComboRow()
        self.unit_row.set_title("Temperature Unit")
        self.unit_row.set_model(Gtk.StringList.new(["Celsius", "Fahrenheit"]))
        self.unit_row.set_selected(0 if self.config.temperature_unit == "celsius" else 1)
        self.unit_row.connect("notify::selected", self._on_ui_changed)
        appearance_group.add(self.unit_row)

        # Theme selection
        self.theme_row = Adw.ComboRow()
        self.theme_row.set_title("Application Theme")
        self.theme_row.set_model(Gtk.StringList.new(["System", "Light", "Dark"]))
        theme_map = {"system": 0, "light": 1, "dark": 2}
        self.theme_row.set_selected(theme_map.get(self.config.theme, 0))
        self.theme_row.connect("notify::selected", self._on_ui_changed)
        appearance_group.add(self.theme_row)

        # Details group
        details_group = Adw.PreferencesGroup()
        details_group.set_title("Weather Details")
        general_page.add(details_group)

        # Show feels like
        self.feels_like_row = Adw.SwitchRow()
        self.feels_like_row.set_title("Show \"Feels Like\" Temperature")
        self.feels_like_row.set_active(self.config.show_feels_like)
        self.feels_like_row.connect("notify::active", self._on_ui_changed)
        details_group.add(self.feels_like_row)

        # Show humidity
        self.humidity_row = Adw.SwitchRow()
        self.humidity_row.set_title("Show Humidity")
        self.humidity_row.set_active(self.config.show_humidity)
        self.humidity_row.connect("notify::active", self._on_ui_changed)
        details_group.add(self.humidity_row)

        # Show wind
        self.wind_row = Adw.SwitchRow()
        self.wind_row.set_title("Show Wind Speed")
        self.wind_row.set_active(self.config.show_wind)
        self.wind_row.connect("notify::active", self._on_ui_changed)
        details_group.add(self.wind_row)

        # Update interval
        interval_group = Adw.PreferencesGroup()
        interval_group.set_title("Updates")
        general_page.add(interval_group)

        self.interval_row = Adw.SpinRow()
        self.interval_row.set_title("Update Interval")
        self.interval_row.set_subtitle("How often to refresh weather data (seconds)")
        adj = Gtk.Adjustment.new(self.config.update_interval, 60, 3600, 60, 300, 0)
        self.interval_row.set_adjustment(adj)
        self.interval_row.connect("notify::value", self._on_ui_changed)
        interval_group.add(self.interval_row)

        # Locations page
        locations_page = Adw.PreferencesPage()
        locations_page.set_title("Locations")
        locations_page.set_icon_name("mark-location-symbolic")
        self.add(locations_page)

        self.locations_group = Adw.PreferencesGroup()
        self.locations_group.set_title("Contacts")
        self.locations_group.set_description("Configure locations for your colleagues")
        locations_page.add(self.locations_group)

        # Add existing locations
        for location in self.config.locations:
            self._add_location_row(location)

        # Add button
        add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        add_box.set_halign(Gtk.Align.CENTER)
        add_box.set_margin_top(12)

        self.add_button = Gtk.Button()
        self.add_button.set_label("Add Location")
        self.add_button.add_css_class("pill")
        self.add_button.add_css_class("suggested-action")
        self.add_button.connect("clicked", self._on_add_location)

        add_box.append(self.add_button)
        self.locations_group.add(add_box)

        # Add a save button at the bottom
        save_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        save_box.set_halign(Gtk.Align.CENTER)
        save_box.set_margin_top(16)
        save_box.set_margin_bottom(16)

        save_button = Gtk.Button()
        save_button.set_label("Save Changes")
        save_button.add_css_class("pill")
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", self._on_save_clicked)
        save_box.append(save_button)

        # Add to the locations page as a separate group
        save_group = Adw.PreferencesGroup()
        save_group.add(save_box)
        locations_page.add(save_group)

    def _on_save_clicked(self, button):
        """Handle save button click"""
        log.info("Save button clicked!")
        if not self._on_save():
            log.info("Save successful, closing dialog")
            self.close()
        else:
            log.info("Save validation failed")

    def _on_ui_changed(self, *args):
        """Handle UI changes and notify parent if callback exists"""
        if self.on_change:
            # Update a temporary or shared config object
            # For simplicity, we'll update the current config object
            # and let the main window react
            self._apply_current_settings()
            self.on_change(self.config)

    def _apply_current_settings(self):
        """Apply current UI state to the config object"""
        if not hasattr(self, 'unit_row') or not hasattr(self, 'theme_row'):
            return

        unit_index = self.unit_row.get_selected()
        self.config.temperature_unit = "celsius" if unit_index == 0 else "fahrenheit"
        
        theme_idx = self.theme_row.get_selected()
        theme_list = ["system", "light", "dark"]
        self.config.theme = theme_list[theme_idx]

        if hasattr(self, 'interval_row'):
            adj = self.interval_row.get_adjustment()
            self.config.update_interval = int(adj.get_value())

        if hasattr(self, 'feels_like_row'):
            self.config.show_feels_like = self.feels_like_row.get_active()
        if hasattr(self, 'humidity_row'):
            self.config.show_humidity = self.humidity_row.get_active()
        if hasattr(self, 'wind_row'):
            self.config.show_wind = self.wind_row.get_active()

        valid_locations = []
        for row in self.location_rows:
            if row.is_valid():
                valid_locations.append(row.get_location())
        self.config.locations = valid_locations

    def _add_location_row(self, location: Location = None):
        """Add a new location row"""
        index = len(self.location_rows)
        row = LocationRow(
            location=location,
            on_changed=self._on_location_data_changed
        )
        row.set_title(f"Location {index + 1}")

        # Add delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.add_css_class("flat")
        delete_button.set_valign(Gtk.Align.CENTER)
        delete_button.connect("clicked", self._on_delete_location, row)
        row.add_prefix(delete_button)

        self.locations_group.add(row)
        self.location_rows.append(row)

        self._update_titles()
        self._on_ui_changed()

    def _on_location_data_changed(self, row):
        """Handle location data change within a row"""
        self._update_titles()
        self._on_ui_changed()

    def _update_titles(self):
        """Update row titles based on content"""
        for i, row in enumerate(self.location_rows):
            if row._city_name:
                row.set_title(f"{row._city_name}, {row._country}")
            else:
                row.set_title(f"Location {i + 1}")

    def _on_add_location(self, button):
        """Add a new empty location row"""
        self._add_location_row()
        self._on_ui_changed()

    def _on_delete_location(self, button, row):
        """Delete a location row"""
        self.locations_group.remove(row)
        self.location_rows.remove(row)
        self._update_titles()
        self._on_ui_changed()

    def _on_save(self, button=None):
        """Save settings and close"""
        # Validate locations
        valid_locations = []
        for row in self.location_rows:
            if row.is_valid():
                valid_locations.append(row.get_location())

        if not valid_locations:
            # Show error dialog
            dialog = Adw.AlertDialog()
            dialog.set_heading("No Valid Locations")
            dialog.set_body("Please configure at least one valid location.")
            dialog.add_response("ok", "OK")
            dialog.present(self)
            return True  # Prevent close

        # Final application of settings
        self._apply_current_settings()

        log.info(f"Config after save: temp_unit={self.config.temperature_unit}")

        if self.on_save:
            self.on_save(self.config)

        return False  # Allow close

    def _on_close_request(self):
        """Handle window close request - don't auto-save, user must click Save"""
        return False  # Allow close without saving
