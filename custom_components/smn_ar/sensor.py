"""Sensor platform for the SMN Argentina integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
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


@dataclass(frozen=True, kw_only=True)
class SMNSensorEntityDescription(SensorEntityDescription):
    """Describes an SMN sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSOR_DESCRIPTIONS: tuple[SMNSensorEntityDescription, ...] = (
    SMNSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        name="Temperatura",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current", {}).get("temperature"),
    ),
    SMNSensorEntityDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        name="Sensación térmica",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current", {}).get("apparent_temperature"),
    ),
    SMNSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        name="Humedad",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current", {}).get("humidity"),
    ),
    SMNSensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        name="Presión atmosférica",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current", {}).get("pressure"),
    ),
    SMNSensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        name="Velocidad del viento",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current", {}).get("wind_speed"),
    ),
    SMNSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        name="Dirección del viento",
        icon="mdi:compass-outline",
        value_fn=lambda data: data.get("current", {}).get("wind_direction"),
    ),
    SMNSensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        name="Visibilidad",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current", {}).get("visibility"),
    ),
    SMNSensorEntityDescription(
        key="description",
        translation_key="description",
        name="Condición actual",
        icon="mdi:weather-partly-cloudy",
        value_fn=lambda data: data.get("current", {}).get("description"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMN sensors based on a config entry."""
    coordinator: SMNDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SMNSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SMNSensor(CoordinatorEntity[SMNDataUpdateCoordinator], SensorEntity):
    """Representation of an SMN sensor."""

    entity_description: SMNSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SMNDataUpdateCoordinator,
        entry: ConfigEntry,
        description: SMNSensorEntityDescription,
    ) -> None:
        """Initialize the SMN sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        st_meta = coordinator.data.get("station", {})
        station_id = st_meta.get("station_id") or coordinator.station_name

        self._attr_unique_id = f"{DOMAIN}_{station_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.station_name)},
            name=f"SMN {coordinator.station_name}",
            manufacturer="Servicio Meteorológico Nacional",
            model="Estación Meteorológica Oficial",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
