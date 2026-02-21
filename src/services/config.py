"""
Configuration management for Weather Buddy
"""
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import logging

log = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "weather-buddy"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Location:
    """A configured location"""
    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    display_name: str = ""  # User-friendly name for the contact

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Location":
        return cls(**data)


@dataclass
class Config:
    """Application configuration"""
    locations: list[Location]
    temperature_unit: str  # "celsius" or "fahrenheit"
    update_interval: int  # seconds
    show_feels_like: bool
    show_humidity: bool
    show_wind: bool
    theme: str = "system"  # "system", "light", "dark"

    def to_dict(self):
        return {
            "locations": [loc.to_dict() for loc in self.locations],
            "temperature_unit": self.temperature_unit,
            "update_interval": self.update_interval,
            "show_feels_like": self.show_feels_like,
            "show_humidity": self.show_humidity,
            "show_wind": self.show_wind,
            "theme": self.theme
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        locations = [Location.from_dict(loc) for loc in data.get("locations", [])]
        return cls(
            locations=locations,
            temperature_unit=data.get("temperature_unit", "celsius"),
            update_interval=data.get("update_interval", 300),  # 5 minutes
            show_feels_like=data.get("show_feels_like", True),
            show_humidity=data.get("show_humidity", True),
            show_wind=data.get("show_wind", False),
            theme=data.get("theme", "system")
        )

    @classmethod
    def default(cls) -> "Config":
        """Create default configuration with sample locations"""
        return cls(
            locations=[
                Location(
                    name="Frisco",
                    country="United States",
                    latitude=33.1507,
                    longitude=-96.8236,
                    timezone="America/Chicago",
                    display_name="Frisco, TX"
                ),
                Location(
                    name="Chennai",
                    country="India",
                    latitude=13.0827,
                    longitude=80.2707,
                    timezone="Asia/Kolkata",
                    display_name="Chennai, India"
                ),
                Location(
                    name="Budapest",
                    country="Hungary",
                    latitude=47.4979,
                    longitude=19.0402,
                    timezone="Europe/Budapest",
                    display_name="Budapest, Hungary"
                ),
            ],
            temperature_unit="celsius",
            update_interval=300,
            show_feels_like=True,
            show_humidity=True,
            show_wind=False,
        )


class ConfigManager:
    """Manages application configuration"""

    def __init__(self):
        self._config: Optional[Config] = None

    def load(self) -> Config:
        """Load configuration from file"""
        if self._config is not None:
            return self._config

        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                self._config = Config.from_dict(data)
                log.info(f"Loaded config from {CONFIG_FILE}")
            else:
                self._config = Config.default()
                self.save()
                log.info("Created default config")
        except Exception as e:
            log.error(f"Error loading config: {e}")
            self._config = Config.default()

        return self._config

    def save(self):
        """Save configuration to file"""
        if self._config is None:
            return

        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._config.to_dict(), f, indent=2)
            log.info(f"Saved config to {CONFIG_FILE}")
        except Exception as e:
            log.error(f"Error saving config: {e}")

    @property
    def config(self) -> Config:
        if self._config is None:
            self.load()
        return self._config

    @config.setter
    def config(self, value: Config):
        self._config = value


# Global instance
config_manager = ConfigManager()
