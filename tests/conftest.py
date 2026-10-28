"""Pytest configuration and Home Assistant mocks for standalone testing."""
import sys
from unittest.mock import MagicMock

# If homeassistant is not installed, mock the required modules
if "homeassistant" not in sys.modules:
    ha = MagicMock()
    
    # Components weather
    weather = MagicMock()
    weather.ATTR_CONDITION_CLEAR_NIGHT = "clear-night"
    weather.ATTR_CONDITION_CLOUDY = "cloudy"
    weather.ATTR_CONDITION_FOG = "fog"
    weather.ATTR_CONDITION_HAIL = "hail"
    weather.ATTR_CONDITION_LIGHTNING = "lightning"
    weather.ATTR_CONDITION_LIGHTNING_RAINY = "lightning-rainy"
    weather.ATTR_CONDITION_PARTLYCLOUDY = "partlycloudy"
    weather.ATTR_CONDITION_POURING = "pouring"
    weather.ATTR_CONDITION_RAINY = "rainy"
    weather.ATTR_CONDITION_SNOWY = "snowy"
    weather.ATTR_CONDITION_SNOWY_RAINY = "snowy-rainy"
    weather.ATTR_CONDITION_SUNNY = "sunny"
    weather.ATTR_CONDITION_WINDY = "windy"
    weather.ATTR_CONDITION_WINDY_VARIANT = "windy-variant"
    weather.ATTR_CONDITION_EXCEPTIONAL = "exceptional"
    
    class WeatherEntity:
        pass
        
    class WeatherEntityFeature:
        FORECAST_DAILY = 1
        FORECAST_HOURLY = 2
        FORECAST_TWICE_DAILY = 4
        
    weather.WeatherEntity = WeatherEntity
    weather.WeatherEntityFeature = WeatherEntityFeature
    weather.Forecast = dict
    
    # Constants
    const = MagicMock()
    class UnitOfTemperature:
        CELSIUS = "°C"
        FAHRENHEIT = "°F"
    class UnitOfPressure:
        HPA = "hPa"
    class UnitOfSpeed:
        KILOMETERS_PER_HOUR = "km/h"
    class UnitOfLength:
        KILOMETERS = "km"
    class Platform:
        WEATHER = "weather"
        SENSOR = "sensor"
        
    const.UnitOfTemperature = UnitOfTemperature
    const.UnitOfPressure = UnitOfPressure
    const.UnitOfSpeed = UnitOfSpeed
    const.UnitOfLength = UnitOfLength
    const.Platform = Platform
    const.PERCENTAGE = "%"
    
    # Helpers update_coordinator
    class DataUpdateCoordinator:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
        def __class_getitem__(cls, item):
            return cls
        def __init__(self, hass, logger, name, update_interval):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = {}
            
    class CoordinatorEntity:
        def __class_getitem__(cls, item):
            return cls
        def __init__(self, coordinator):
            self.coordinator = coordinator
            
    class UpdateFailed(Exception):
        pass
        
    update_coord = MagicMock()
    update_coord.DataUpdateCoordinator = DataUpdateCoordinator
    update_coord.CoordinatorEntity = CoordinatorEntity
    update_coord.UpdateFailed = UpdateFailed
    
    # Helpers device registry
    class DeviceEntryType:
        SERVICE = "service"
    dev_reg = MagicMock()
    dev_reg.DeviceEntryType = DeviceEntryType
    dev_reg.DeviceInfo = dict

    # Components sensor
    class SensorEntity:
        pass
    class SensorDeviceClass:
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ATMOSPHERIC_PRESSURE = "atmospheric_pressure"
        WIND_SPEED = "wind_speed"
        DISTANCE = "distance"
    class SensorStateClass:
        MEASUREMENT = "measurement"
        
    sensor = MagicMock()
    sensor.SensorEntity = SensorEntity
    sensor.SensorDeviceClass = SensorDeviceClass
    sensor.SensorStateClass = SensorStateClass
    
    # Config entries
    class ConfigEntry:
        def __init__(self):
            self.entry_id = "test_entry"
            self.data = {}
            self.options = {}
            
    config_entries = MagicMock()
    config_entries.ConfigEntry = ConfigEntry
    
    class ConfigFlow:
        pass
    class OptionsFlow:
        pass
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
    
    # Register mock modules
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.components"] = MagicMock()
    sys.modules["homeassistant.components.weather"] = weather
    sys.modules["homeassistant.components.sensor"] = sensor
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.core"] = MagicMock()
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.helpers"] = MagicMock()
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coord
    sys.modules["homeassistant.helpers.device_registry"] = dev_reg
    sys.modules["homeassistant.helpers.aiohttp_client"] = MagicMock()
    sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
    sys.modules["homeassistant.data_entry_flow"] = MagicMock()
