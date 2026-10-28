"""Config flow for the SMN Argentina integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import (
    find_closest_station,
    load_stations,
    normalize_name,
)


def get_station_options() -> dict[str, str]:
    """Get sorted station dictionary: name -> 'Name (Province)'."""
    stations = load_stations()
    # Sort by province then name
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
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        station_options = get_station_options()

        if user_input is not None:
            station_name = user_input[CONF_STATION]
            unique_id = normalize_name(station_name)

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"SMN {station_name}",
                data=user_input,
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
        return SMNOptionsFlowHandler(config_entry)


class SMNOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for SMN Argentina integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        station_options = get_station_options()

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_station = self.config_entry.options.get(
            CONF_STATION,
            self.config_entry.data.get(CONF_STATION),
        )
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION, default=current_station): vol.In(
                    station_options
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=300, max=7200)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
