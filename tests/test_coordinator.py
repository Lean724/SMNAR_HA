"""Unit tests for SMN parsing and geographic helpers."""

from custom_components.smn_ar.coordinator import (
    haversine_distance,
    map_weather_condition,
    normalize_name,
    wind_direction_to_bearing,
)
from custom_components.smn_ar.const import (
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SUNNY,
)


def test_normalize_station_names() -> None:
    assert normalize_name("Aeroparque Jorge Newbery (AERO)") == "AEROPARQUE JORGE NEWBERY"
    assert normalize_name("  Córdoba_Aero  ") == "CORDOBA"
    assert normalize_name("") == ""


def test_wind_direction_to_bearing() -> None:
    assert wind_direction_to_bearing("N") == 0
    assert wind_direction_to_bearing("Noreste") == 45
    assert wind_direction_to_bearing("SUDOESTE") == 225
    assert wind_direction_to_bearing("variable") is None
    assert wind_direction_to_bearing(None) is None


def test_haversine_distance() -> None:
    assert haversine_distance(-34.6, -58.4, -34.6, -58.4) == 0
    # Buenos Aires to Córdoba: approximately 647 km.
    assert 640 < haversine_distance(-34.6037, -58.3816, -31.4201, -64.1888) < 655


def test_map_weather_condition() -> None:
    assert map_weather_condition(None) == ATTR_CONDITION_SUNNY
    assert map_weather_condition("lluvia intensa") == ATTR_CONDITION_RAINY
    assert map_weather_condition("texto desconocido") == ATTR_CONDITION_PARTLYCLOUDY
