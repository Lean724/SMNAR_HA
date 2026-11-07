"""Unit tests for SMN Argentina integration."""
import json
import os
import sys
from unittest.mock import MagicMock

# Add custom_components to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.smn_ar.config_flow import get_station_options
from custom_components.smn_ar.coordinator import (
    SMNDataUpdateCoordinator,
    find_closest_station,
    haversine_distance,
    load_stations,
    map_weather_condition,
    normalize_name,
    wind_direction_to_bearing,
)
from custom_components.smn_ar.sensor import SENSOR_DESCRIPTIONS, SMNSensor
from custom_components.smn_ar.weather import SMNWeather


def test_manifest():
    """Test manifest.json conforms to HA standards."""
    manifest_path = os.path.join(
        os.path.dirname(__file__), "..", "custom_components", "smn_ar", "manifest.json"
    )
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["domain"] == "smn_ar"
    assert manifest["name"] == "Servicio Meteorológico Nacional (Argentina)"
    assert manifest["config_flow"] is True
    assert manifest["codeowners"] == ["@Lean724"]
    assert manifest["version"] == "1.0.2"
    assert manifest["iot_class"] == "cloud_polling"


def test_hacs_json():
    """Test hacs.json."""
    hacs_path = os.path.join(os.path.dirname(__file__), "..", "hacs.json")
    with open(hacs_path, encoding="utf-8") as f:
        hacs = json.load(f)

    assert "name" in hacs


def test_haversine_distance():
    """Test distance calculation."""
    # Distance between Obelisco (-34.6037, -58.3816) and Aeroparque (-34.55, -58.4167) is ~6.8 km
    dist = haversine_distance(-34.6037, -58.3816, -34.55, -58.4167)
    assert 6.0 < dist < 8.0

    # Distance to same point is 0
    assert haversine_distance(-34.0, -58.0, -34.0, -58.0) == 0.0


def test_normalize_name():
    """Test station name normalization."""
    assert normalize_name("Aeroparque Aero") == "AEROPARQUE"
    assert normalize_name("EZEIZA AERO") == "EZEIZA"
    assert normalize_name("Bahía Blanca") == "BAHIA BLANCA"
    assert normalize_name("CORDOBA OBS.") == "CORDOBA OBS"


def test_wind_direction_to_bearing():
    """Test wind direction conversion."""
    assert wind_direction_to_bearing("Norte") == 0
    assert wind_direction_to_bearing("Este") == 90
    assert wind_direction_to_bearing("Sur") == 180
    assert wind_direction_to_bearing("Oeste") == 270
    assert wind_direction_to_bearing("Noreste") == 45
    assert wind_direction_to_bearing("Calma") == 0
    assert wind_direction_to_bearing(None) is None


def test_load_stations():
    """Test loading stations from stations.json."""
    stations = load_stations()
    assert len(stations) >= 110
    station_names = [s["name"] for s in stations]
    assert any("AEROPARQUE" in name for name in station_names)
    assert any("EZEIZA" in name for name in station_names)
    assert any("CORDOBA" in name for name in station_names)


def test_find_closest_station():
    """Test finding the nearest station to coordinates."""
    # Buenos Aires Downtown
    closest = find_closest_station(-34.6037, -58.3816)
    assert closest is not None
    assert "AEROPARQUE" in closest["name"] or "CENTRO" in closest["name"]


def test_map_weather_condition():
    """Test weather condition mapping."""
    assert map_weather_condition("Despejado") == "sunny"
    assert map_weather_condition("Parcialmente nublado") == "partlycloudy"
    assert map_weather_condition("Cubierto con lluvia") == "rainy"
    assert map_weather_condition("Tormenta fuerte") == "lightning-rainy"
    assert map_weather_condition("Niebla densa") == "fog"
    assert map_weather_condition(None) == "sunny"


def test_parse_current_weather():
    """Test parsing tiepre current weather text."""
    sample_tp = (
        "Aeroparque Buenos Aires;28-octubre-2026;10:00;Parcialmente nublado con neblina;10 km;18.5;18.0; 65;Noreste  12;1018.4 / \n"
        "Cordoba Aero;28-octubre-2026;10:00;Despejado;15 km;22.0;No se calcula; 45;Norte  8;1015.0 / \n"
    )

    hass = MagicMock()
    entry = MagicMock()
    coord = SMNDataUpdateCoordinator(hass, entry, "AEROPARQUE AERO")
    result = coord._parse_current_weather(sample_tp)

    assert result["station_name"] == "Aeroparque Buenos Aires"
    assert result["temperature"] == 18.5
    assert result["apparent_temperature"] == 18.0
    assert result["humidity"] == 65.0
    assert result["wind_speed"] == 12.0
    assert result["wind_bearing"] == 45
    assert result["pressure"] == 1018.4
    assert result["visibility"] == 10.0
    assert result["condition"] == "fog"


def test_parse_forecast():
    """Test parsing pron5d forecast text into hourly and daily lists."""
    sample_fc = (
        " AEROPARQUE\n"
        " ================================================================================================\n"
        "      FECHA *          TEMPERATURA      VIENTO      PRECIPITACION(mm)\n"
        "                                     (DIR | KM/H)                        \n"
        " ================================================================================================\n"
        "  28/OCT/2026 12Hs.        20.0        90 |  10         0.0 \n"
        "  28/OCT/2026 15Hs.        24.0       100 |  15         0.0 \n"
        "  28/OCT/2026 18Hs.        18.0       110 |  12         2.5 \n"
        " ================================================================================================\n"
    )

    hass = MagicMock()
    entry = MagicMock()
    coord = SMNDataUpdateCoordinator(hass, entry, "AEROPARQUE AERO")
    hourly, daily = coord._parse_forecast(sample_fc)

    assert len(hourly) == 3
    assert hourly[0]["temperature"] == 20.0
    assert hourly[0]["native_temperature"] == 20.0
    assert hourly[0]["wind_speed"] == 10.0
    assert hourly[0]["native_wind_speed"] == 10.0
    assert hourly[0]["wind_bearing"] == 90
    assert hourly[2]["precipitation"] == 2.5
    assert hourly[2]["native_precipitation"] == 2.5
    assert hourly[2]["condition"] == "rainy"
    # Ensure UTC timezone offset (+00:00)
    assert "+00:00" in hourly[0]["datetime"]

    assert len(daily) == 1
    assert daily[0]["temperature"] == 24.0  # Max
    assert daily[0]["native_temperature"] == 24.0
    assert daily[0]["templow"] == 18.0     # Min
    assert daily[0]["native_templow"] == 18.0
    assert daily[0]["precipitation"] == 2.5
    assert daily[0]["native_precipitation"] == 2.5
    assert "+00:00" in daily[0]["datetime"]


def test_entities_and_config_options():
    """Test weather entity, sensor entities, and station options helper."""
    options = get_station_options()
    assert "AEROPARQUE AERO" in options

    hass = MagicMock()
    entry = MagicMock()
    coord = SMNDataUpdateCoordinator(hass, entry, "AEROPARQUE AERO")
    coord.data = {
        "current": {
            "station_name": "Aeroparque Buenos Aires",
            "date": "28-octubre-2026",
            "time": "10:00",
            "description": "Despejado",
            "condition": "sunny",
            "temperature": 21.5,
            "apparent_temperature": 21.0,
            "humidity": 55.0,
            "wind_speed": 14.0,
            "wind_direction": "Norte",
            "wind_bearing": 0,
            "pressure": 1016.2,
            "visibility": 15.0,
        },
        "hourly_forecast": [],
        "daily_forecast": [],
        "station": coord._station_info,
    }

    weather_entity = SMNWeather(coord, entry)
    assert weather_entity.condition == "sunny"
    assert weather_entity.native_temperature == 21.5
    assert weather_entity.native_apparent_temperature == 21.0
    assert weather_entity.humidity == 55.0
    assert weather_entity.native_pressure == 1016.2
    assert weather_entity.native_wind_speed == 14.0
    assert weather_entity.wind_bearing == 0
    assert weather_entity.native_visibility == 15.0

    sensors = {
        desc.key: SMNSensor(coord, entry, desc) for desc in SENSOR_DESCRIPTIONS
    }
    assert sensors["temperature"].native_value == 21.5
    assert sensors["apparent_temperature"].native_value == 21.0
    assert sensors["humidity"].native_value == 55.0
    assert sensors["pressure"].native_value == 1016.2
    assert sensors["wind_speed"].native_value == 14.0
    assert sensors["wind_direction"].native_value == "Norte"
    assert sensors["visibility"].native_value == 15.0
    assert sensors["description"].native_value == "Despejado"
