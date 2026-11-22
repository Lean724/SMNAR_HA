"""Config flow for the SMN Argentina integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

from .const import (
    CONF_ENABLE_OPEN_METEO_FALLBACK,
    CONF_FALLBACK_ENTITY,
    CONF_SCAN_INTERVAL,
    CONF_STALE_THRESHOLD_HOURS,
    CONF_STATION,
    DEFAULT_ENABLE_OPEN_METEO_FALLBACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_THRESHOLD_HOURS,
    DOMAIN,
)
from .coordinator import (
    find_closest_station,
    load_stations,
    normalize_name,
)
from .fallback import get_entry_weather_entities


def get_station_options() -> dict[str, str]:
    """Get sorted station dictionary: name -> 'Name (Province)'."""
    stations = load_stations()
    sorted_st = sorted(stations, key=lambda s: (s["province"], s["name"]))
    return {
        s["name"]: f"{s['name']} ({s['province']})"
        for s in sorted_st
    }


class SMNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMN Argentina."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        station_options = get_station_options()

        if user_input is not None:
            station_name = user_input[CONF_STATION]
            unique_id = normalize_name(station_name)

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            cleaned = dict(user_input)
            cleaned[CONF_FALLBACK_ENTITY] = user_input.get(CONF_FALLBACK_ENTITY) or None

            return self.async_create_entry(
                title=f"SMN {station_name}",
                data=cleaned,
            )

        # Detect closest station as default
        default_station = None
        if self.hass.config.latitude and self.hass.config.longitude:
            closest = find_closest_station(
                self.hass.config.latitude, self.hass.config.longitude
            )
            if closest and closest["name"] in station_options:
                default_station = closest["name"]

        if not default_station and station_options:
            default_station = next(iter(station_options.keys()))

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION, default=default_station): vol.In(
                    station_options
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=300, max=7200)),
                vol.Optional(CONF_FALLBACK_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(
                    CONF_ENABLE_OPEN_METEO_FALLBACK,
                    default=DEFAULT_ENABLE_OPEN_METEO_FALLBACK,
                ): bool,
                vol.Optional(
                    CONF_STALE_THRESHOLD_HOURS,
                    default=DEFAULT_STALE_THRESHOLD_HOURS,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        if hasattr(config_entries.OptionsFlow, "config_entry"):
            return SMNOptionsFlowHandler()
        return SMNOptionsFlowHandler(config_entry)


class SMNOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for SMN Argentina integration."""

    def __init__(
        self, config_entry: config_entries.ConfigEntry | None = None
    ) -> None:
        """Initialize the options flow without overriding OptionsFlow.config_entry."""
        self._init_config_entry = config_entry

    @property
    def _entry(self) -> config_entries.ConfigEntry:
        """Return the active config entry across HA versions."""
        if self._init_config_entry is not None:
            return self._init_config_entry
        return self.config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        station_options = get_station_options()
        entry = self._entry
        own_entities = get_entry_weather_entities(
            getattr(self, "hass", None), getattr(entry, "entry_id", None)
        )

        if user_input is not None:
            fallback_entity = user_input.get(CONF_FALLBACK_ENTITY) or None
            if fallback_entity and fallback_entity in own_entities:
                errors[CONF_FALLBACK_ENTITY] = "invalid_fallback_entity"
            else:
                cleaned = dict(user_input)
                cleaned[CONF_FALLBACK_ENTITY] = fallback_entity
                return self.async_create_entry(title="", data=cleaned)

        current_station = entry.options.get(
            CONF_STATION,
            entry.data.get(CONF_STATION),
        )
        current_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_fallback = (
            entry.options[CONF_FALLBACK_ENTITY]
            if CONF_FALLBACK_ENTITY in entry.options
            else entry.data.get(CONF_FALLBACK_ENTITY)
        )
        current_open_meteo = entry.options.get(
            CONF_ENABLE_OPEN_METEO_FALLBACK,
            entry.data.get(
                CONF_ENABLE_OPEN_METEO_FALLBACK, DEFAULT_ENABLE_OPEN_METEO_FALLBACK
            ),
        )
        current_stale_hours = entry.options.get(
            CONF_STALE_THRESHOLD_HOURS,
            entry.data.get(CONF_STALE_THRESHOLD_HOURS, DEFAULT_STALE_THRESHOLD_HOURS),
        )

        fallback_kwargs: dict[str, Any] = {}
        if current_fallback:
            fallback_kwargs["description"] = {"suggested_value": current_fallback}

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION, default=current_station): vol.In(
                    station_options
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=300, max=7200)),
                vol.Optional(
                    CONF_FALLBACK_ENTITY,
                    **fallback_kwargs,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="weather",
                        exclude_entities=sorted(own_entities),
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_OPEN_METEO_FALLBACK,
                    default=current_open_meteo,
                ): bool,
                vol.Optional(
                    CONF_STALE_THRESHOLD_HOURS,
                    default=current_stale_hours,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
