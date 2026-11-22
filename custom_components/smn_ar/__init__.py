"""The Servicio Meteorológico Nacional (SMN Argentina) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

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
from .coordinator import SMNDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.WEATHER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SMN Argentina from a config entry."""
    station = entry.options.get(CONF_STATION, entry.data.get(CONF_STATION))
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    fallback_entity = (
        entry.options[CONF_FALLBACK_ENTITY]
        if CONF_FALLBACK_ENTITY in entry.options
        else entry.data.get(CONF_FALLBACK_ENTITY)
    )
    enable_open_meteo = entry.options.get(
        CONF_ENABLE_OPEN_METEO_FALLBACK,
        entry.data.get(
            CONF_ENABLE_OPEN_METEO_FALLBACK, DEFAULT_ENABLE_OPEN_METEO_FALLBACK
        ),
    )
    stale_threshold_hours = entry.options.get(
        CONF_STALE_THRESHOLD_HOURS,
        entry.data.get(CONF_STALE_THRESHOLD_HOURS, DEFAULT_STALE_THRESHOLD_HOURS),
    )

    coordinator = SMNDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        station_name=station,
        scan_interval=scan_interval,
        fallback_entity=fallback_entity,
        enable_open_meteo_fallback=enable_open_meteo,
        stale_threshold_hours=stale_threshold_hours,
    )

    await coordinator.async_config_entry_first_refresh()

    # Support modern runtime_data while maintaining backwards compatibility with hass.data
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
