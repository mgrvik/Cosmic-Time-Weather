"""
Weather card widget for displaying a single location's weather
"""
from gi.repository import Gtk, Adw, GLib, Gio, Gdk
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging

from services.weather_api import WeatherData

log = logging.getLogger(__name__)


class WeatherLocationCard(Gtk.Box):
    """A beautiful card displaying weather for one location"""

    def __init__(self, weather_data: WeatherData = None, temp_unit: str = "celsius",
                 show_feels_like: bool = True, show_humidity: bool = True, show_wind: bool = False,
                 on_delete=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.weather_data = weather_data
        self.temp_unit = temp_unit
        self.show_feels_like = show_feels_like
        self.show_humidity = show_humidity
        self.show_wind = show_wind
        self.on_delete = on_delete

        self._setup_ui()
        self.add_css_class("weather-card")

        if weather_data:
            self.update_weather(weather_data)

        # Start time update timer
        GLib.timeout_add(1000, self._update_time)

    def _setup_ui(self):
        """Create the card UI"""
        # Main container with padding
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        # Card frame with CSS class
        self.frame = Gtk.Frame()
        self.frame.add_css_class("card")
        self.frame.add_css_class("weather-card-frame")
        self.append(self.frame)

        # Inner box
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        inner.set_margin_top(16)
        inner.set_margin_bottom(16)
        inner.set_margin_start(16)
        inner.set_margin_end(16)
        inner.set_spacing(8)
        self.frame.set_child(inner)

        # Top row: Name and time
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        top_row.set_spacing(8)

        # Contact name
        self.name_label = Gtk.Label()
        self.name_label.add_css_class("title-2")
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.set_hexpand(True)
        top_row.append(self.name_label)

        # Local time badge
        self.time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.time_box.add_css_class("time-badge")
        self.time_box.set_spacing(4)

        time_icon = Gtk.Image()
        time_icon.set_from_icon_name("clock-outline-symbolic")
        time_icon.set_pixel_size(14)
        self.time_box.append(time_icon)

        self.time_label = Gtk.Label()
        self.time_label.add_css_class("caption")
        self.time_label.add_css_class("numeric")
        self.time_box.append(self.time_label)

        top_row.append(self.time_box)

        # Delete button (red trash icon)
        delete_btn = Gtk.Button()
        delete_btn.set_icon_name("user-trash-symbolic")
        delete_btn.add_css_class("flat")
        delete_btn.add_css_class("circular")
        delete_btn.add_css_class("delete-btn")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn.set_tooltip_text("Remove location")
        delete_btn.connect("clicked", self._on_delete_clicked)
        top_row.append(delete_btn)

        inner.append(top_row)

        # Location subtitle
        self.location_label = Gtk.Label()
        self.location_label.add_css_class("dim-label")
        self.location_label.add_css_class("caption")
        self.location_label.set_halign(Gtk.Align.START)
        inner.append(self.location_label)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(4)
        separator.set_margin_bottom(4)
        inner.append(separator)

        # Weather main display
        weather_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        weather_row.set_spacing(12)
        weather_row.set_margin_top(8)
        weather_row.set_margin_bottom(8)

        # Weather icon (large)
        self.weather_icon = Gtk.Image()
        self.weather_icon.set_pixel_size(64)
        self.weather_icon.add_css_class("weather-icon")
        weather_row.append(self.weather_icon)

        # Temperature and description
        temp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        temp_box.set_spacing(2)
        temp_box.set_hexpand(True)
        temp_box.set_valign(Gtk.Align.CENTER)

        self.temp_label = Gtk.Label()
        self.temp_label.add_css_class("temperature-display")
        self.temp_label.set_halign(Gtk.Align.START)
        self.temp_label.set_valign(Gtk.Align.CENTER)
        temp_box.append(self.temp_label)

        self.desc_label = Gtk.Label()
        self.desc_label.add_css_class("weather-description")
        self.desc_label.set_halign(Gtk.Align.START)
        temp_box.append(self.desc_label)

        weather_row.append(temp_box)
        inner.append(weather_row)

        # Forecast row: High/Low
        self.forecast_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.forecast_box.set_spacing(8)
        self.forecast_box.set_margin_bottom(4)
        
        self.high_label = Gtk.Label()
        self.high_label.add_css_class("caption")
        self.high_label.add_css_class("numeric")
        self.forecast_box.append(self.high_label)
        
        self.low_label = Gtk.Label()
        self.low_label.add_css_class("caption")
        self.low_label.add_css_class("numeric")
        self.low_label.add_css_class("dim-label")
        self.forecast_box.append(self.low_label)
        
        inner.append(self.forecast_box)

        # Details row
        self.details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.details_box.set_spacing(16)
        self.details_box.set_margin_top(8)
        inner.append(self.details_box)

        # Feels like
        self.feels_like_box = self._create_detail_item("thermometer-symbolic", "Feels like")
        self.details_box.append(self.feels_like_box)

        # Humidity
        self.humidity_box = self._create_detail_item("humidity-symbolic", "Humidity")
        self.details_box.append(self.humidity_box)

        # Wind
        self.wind_box = self._create_detail_item("weather-windy-symbolic", "Wind")
        self.details_box.append(self.wind_box)

        self._update_visibility()

    def _update_visibility(self):
        """Update visibility of details based on settings"""
        self.feels_like_box.set_visible(self.show_feels_like)
        self.humidity_box.set_visible(self.show_humidity)
        self.wind_box.set_visible(self.show_wind)
        self.details_box.set_visible(self.show_feels_like or self.show_humidity or self.show_wind)

    def _create_detail_item(self, icon_name: str, label: str) -> Gtk.Box:
        """Create a detail display item"""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_spacing(4)

        icon = Gtk.Image()
        icon.set_from_icon_name(icon_name)
        icon.set_pixel_size(14)
        icon.add_css_class("dim-label")
        box.append(icon)

        value_label = Gtk.Label()
        value_label.add_css_class("caption")
        value_label.add_css_class("numeric")
        box.append(value_label)

        # Store reference to update later
        box.value_label = value_label

        return box

    def _format_temp(self, temp_celsius: float) -> str:
        """Format temperature with unit"""
        if self.temp_unit == "fahrenheit":
            temp = temp_celsius * 9/5 + 32
            return f"{temp:.0f}°F"
        return f"{temp_celsius:.0f}°C"

    def update_weather(self, data: WeatherData):
        """Update card with new weather data"""
        self.weather_data = data

        # Update name
        self.name_label.set_text(data.display_name if hasattr(data, 'display_name') and data.display_name else data.location_name)

        # Update location
        self.location_label.set_text(f"{data.location_name}, {data.country}")

        # Update weather icon
        icon_name = data.weather_icon
        if not data.is_day:
            # Use night variants for some icons
            night_icons = {
                "weather-clear": "weather-clear-night",
                "weather-few-clouds": "weather-few-clouds-night",
            }
            icon_name = night_icons.get(icon_name, icon_name)

        self.weather_icon.set_from_icon_name(icon_name + "-symbolic")

        # Update temperature
        self.temp_label.set_text(self._format_temp(data.temperature))

        # Update description
        self.desc_label.set_text(data.weather_description)

        # Update details
        self.feels_like_box.value_label.set_text(self._format_temp(data.feels_like))
        self.humidity_box.value_label.set_text(f"{data.humidity}%")
        self.wind_box.value_label.set_text(f"{data.wind_speed:.0f} km/h")

        # Update forecast
        self.high_label.set_markup(f"<b>H: {self._format_temp(data.temp_max)}</b>")
        self.low_label.set_text(f"L: {self._format_temp(data.temp_min)}")

        # Update time
        self._update_time()

    def _on_delete_clicked(self, button):
        """Handle delete button click — show confirmation dialog"""
        if not self.on_delete or not self.weather_data:
            return

        city = self.weather_data.location_name

        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Remove Location",
            body=f"Do you want to delete {city}?"
        )
        dialog.add_response("no", "No")
        dialog.add_response("yes", "Yes")
        dialog.set_response_appearance("yes", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("no", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("no")
        dialog.connect("response", self._on_delete_confirmed)
        dialog.present()

    def _on_delete_confirmed(self, dialog, response):
        """Handle confirmation dialog response"""
        if response == "yes" and self.on_delete:
            self.on_delete(self)

    def set_temperature_unit(self, unit: str):
        """Update temperature unit and refresh UI"""
        if self.temp_unit != unit:
            self.temp_unit = unit
            if self.weather_data:
                self.update_weather(self.weather_data)

    def _update_time(self) -> bool:
        """Update the local time display"""
        if self.weather_data:
            # Get current time in the location's timezone
            try:
                tz = ZoneInfo(self.weather_data.timezone)
                local_time = datetime.now(tz)
                time_str = local_time.strftime("%I:%M %p")
                self.time_label.set_text(time_str)
            except Exception as e:
                log.error(f"Error updating time: {e}")
        return True  # Continue timer

    def set_show_details(self, show_feels_like: bool, show_humidity: bool, show_wind: bool):
        """Update visibility of weather details"""
        self.show_feels_like = show_feels_like
        self.show_humidity = show_humidity
        self.show_wind = show_wind
        self._update_visibility()
