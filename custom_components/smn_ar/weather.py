"""Weather entity platform for the SMN Argentina integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SMNDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SMN weather platform from a config entry."""
    coordinator: SMNDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SMNWeather(coordinator, entry)])


class SMNWeather(CoordinatorEntity[SMNDataUpdateCoordinator], WeatherEntity):
    """Implementation of a weather entity for SMN Argentina."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        coordinator: SMNDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._entry = entry
        st_meta = coordinator.data.get("station", {})
        station_id = st_meta.get("station_id") or coordinator.station_name

        self._attr_unique_id = f"{DOMAIN}_{station_id}_weather"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.station_name)},
            name=f"SMN {coordinator.station_name}",
            manufacturer="Servicio Meteorológico Nacional",
            model="Estación Meteorológica Oficial",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def condition(self) -> str | None:
        """Return the current weather condition."""
        return self.coordinator.data.get("current", {}).get("condition")

    @property
    def native_temperature(self) -> float | None:
        """Return the current temperature in Celsius."""
        return self.coordinator.data.get("current", {}).get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the current apparent temperature (feels like / ST)."""
        return self.coordinator.data.get("current", {}).get("apparent_temperature")

    @property
    def native_pressure(self) -> float | None:
        """Return the atmospheric pressure in hPa."""
        return self.coordinator.data.get("current", {}).get("pressure")

    @property
    def humidity(self) -> float | None:
        """Return the relative humidity in %."""
        return self.coordinator.data.get("current", {}).get("humidity")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed in km/h."""
        return self.coordinator.data.get("current", {}).get("wind_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing direction."""
        return self.coordinator.data.get("current", {}).get("wind_bearing")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility distance in km."""
        return self.coordinator.data.get("current", {}).get("visibility")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional weather state attributes."""
        current = self.coordinator.data.get("current", {})
        station = self.coordinator.data.get("station", {})
        return {
            "estacion": current.get("station_name"),
            "provincia": station.get("province"),
            "descripcion": current.get("description"),
            "viento_direccion": current.get("wind_direction"),
            "sensacion_termica": current.get("apparent_temperature"),
            "fecha_reporte": current.get("date"),
            "hora_reporte": current.get("time"),
        }

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily weather forecast."""
        return self.coordinator.data.get("daily_forecast")

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly/3-hourly weather forecast."""
        return self.coordinator.data.get("hourly_forecast")
