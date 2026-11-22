"""Unit tests for SMN parsing, geographic helpers, and fallback resilience."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.smn_ar.const import (
    ARGENTINA_TIMEZONE,
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SUNNY,
    SOURCE_CACHE,
    SOURCE_FALLBACK_ENTITY,
    SOURCE_OPEN_METEO,
    SOURCE_SMN,
    ST_SOURCE_OPEN_METEO,
    ST_SOURCE_SMN,
    ST_SOURCE_TEMPERATURE_FALLBACK,
    URL_CURRENT_WEATHER,
    URL_FORECAST,
)
from custom_components.smn_ar.coordinator import (
    SMNDataUpdateCoordinator,
    haversine_distance,
    is_report_stale,
    map_weather_condition,
    normalize_name,
    parse_smn_report_datetime,
    wind_direction_to_bearing,
)
from custom_components.smn_ar.fallback import (
    parse_open_meteo_current,
    read_fallback_weather_entity,
    safe_float,
)


def _make_zip_bytes(filename: str, content: bytes) -> bytes:
    """Create an in-memory ZIP archive containing a single file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


class _FakeResponse:
    """Minimal async aiohttp response stub."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    async def read(self) -> bytes:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


def test_normalize_station_names() -> None:
    assert normalize_name("Aeroparque Jorge Newbery (AERO)") == "AEROPARQUE JORGE NEWBERY"
    assert normalize_name("  Córdoba_Aero  ") == "CORDOBA"
    assert normalize_name("MERCEDES AERO (CTES)") == "MERCEDES"
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
    assert map_weather_condition(None, is_night=True) == ATTR_CONDITION_CLEAR_NIGHT
    assert map_weather_condition("Despejado", is_night=False) == ATTR_CONDITION_SUNNY
    assert map_weather_condition("Despejado", is_night=True) == ATTR_CONDITION_CLEAR_NIGHT
    assert map_weather_condition("lluvia intensa") == ATTR_CONDITION_RAINY
    assert map_weather_condition("texto desconocido") == ATTR_CONDITION_PARTLYCLOUDY


def test_safe_float() -> None:
    assert safe_float(21) == 21.0
    assert safe_float(" -3.5 ") == -3.5
    assert safe_float("18,2") == 18.2
    assert safe_float("No se calcula") is None
    assert safe_float("S/D") is None
    assert safe_float("---") is None
    assert safe_float("") is None
    assert safe_float(True) is None
    assert safe_float(None) is None
    assert safe_float(float("nan")) is None
    assert safe_float("inf") is None


def test_apparent_temperature_fallback_and_defensive_parsing() -> None:
    """When SMN reports 'No se calcula', apparent_temperature falls back to temp (A1)."""
    sample_tp = (
        "Aeroparque Buenos Aires;22-noviembre-2026;10:00;Despejado;10 km;21.8;No se calcula; 49;Direcciones Variables  9;1010.4 / \n"
        "Bariloche;22-noviembre-2026;10:00;Parcialmente nublado;10 km;9.0;4.9;S/D;Oeste  35;/// / \n"
    )
    hass = MagicMock()
    entry = MagicMock()
    coord_aero = SMNDataUpdateCoordinator(hass, entry, "AEROPARQUE AERO")
    res_aero = coord_aero._parse_current_weather(sample_tp)

    assert res_aero is not None
    assert res_aero["temperature"] == 21.8
    assert res_aero["apparent_temperature"] == 21.8
    assert res_aero["apparent_temperature_source"] == ST_SOURCE_TEMPERATURE_FALLBACK
    assert res_aero["condition"] == ATTR_CONDITION_SUNNY

    coord_bari = SMNDataUpdateCoordinator(hass, entry, "BARILOCHE AERO")
    res_bari = coord_bari._parse_current_weather(sample_tp)

    assert res_bari is not None
    assert res_bari["temperature"] == 9.0
    assert res_bari["apparent_temperature"] == 4.9
    assert res_bari["apparent_temperature_source"] == ST_SOURCE_SMN
    assert res_bari["humidity"] is None
    assert res_bari["pressure"] is None


def test_parse_smn_report_datetime_and_staleness() -> None:
    """Spanish report timestamps parse in UTC-3 and evaluate staleness cleanly."""
    dt = parse_smn_report_datetime("22-noviembre-2026", "09:00")
    assert dt == datetime(2026, 11, 22, 9, 0, tzinfo=ARGENTINA_TIMEZONE)
    assert parse_smn_report_datetime("15-setiembre-2026", "21:00") == datetime(
        2026, 9, 15, 21, 0, tzinfo=ARGENTINA_TIMEZONE
    )
    assert parse_smn_report_datetime("invalid", "09:00") is None

    now_fresh = datetime(2026, 11, 22, 11, 30, tzinfo=ARGENTINA_TIMEZONE)
    now_stale = datetime(2026, 11, 22, 12, 0, tzinfo=ARGENTINA_TIMEZONE)
    assert is_report_stale(dt, threshold_hours=3, now=now_fresh) is False
    assert is_report_stale(dt, threshold_hours=3, now=now_stale) is True
    assert is_report_stale(None, threshold_hours=3, now=now_fresh) is True


@pytest.mark.asyncio
async def test_fetch_zip_text_utf8_and_cp1252() -> None:
    """ZIP extraction decodes UTF-8 (pron5d) and falls back to CP1252 (tiepre)."""
    utf8_zip = _make_zip_bytes(
        "pronostico.txt", "pronóstico número 1\n".encode()
    )
    cp1252_zip = _make_zip_bytes(
        "estado.txt", "Bahía Blanca;Peña;Córdoba\n".encode("cp1252")
    )

    session = MagicMock()
    session.get = MagicMock(
        side_effect=[_FakeResponse(utf8_zip), _FakeResponse(cp1252_zip)]
    )

    with patch(
        "custom_components.smn_ar.coordinator.async_get_clientsession",
        return_value=session,
    ):
        coord = SMNDataUpdateCoordinator(MagicMock(), MagicMock(), "AEROPARQUE AERO")
        text_utf8 = await coord._fetch_zip_text(URL_FORECAST, "Forecast")
        text_cp1252 = await coord._fetch_zip_text(URL_CURRENT_WEATHER, "Current")

    assert "pronóstico número 1" in text_utf8
    assert "Bahía Blanca;Peña;Córdoba" in text_cp1252


def test_forecast_daily_grouping_argentina_local_date() -> None:
    """21Hs ART (00:00 UTC next day) must remain grouped in the Argentina local day."""
    sample_fc = (
        " AEROPARQUE\n"
        " ================================================================================================\n"
        "      FECHA *          TEMPERATURA      VIENTO      PRECIPITACION(mm)\n"
        "                                     (DIR | KM/H)                        \n"
        " ================================================================================================\n"
        "  28/OCT/2026 15Hs.        24.0       100 |  15         0.0 \n"
        "  28/OCT/2026 21Hs.        17.0       110 |  10         0.0 \n"
        "  29/OCT/2026 09Hs.        19.0       120 |  12         1.0 \n"
        " ================================================================================================\n"
    )
    coord = SMNDataUpdateCoordinator(MagicMock(), MagicMock(), "AEROPARQUE AERO")
    hourly, daily = coord._parse_forecast(sample_fc)

    assert len(hourly) == 3
    assert len(daily) == 2
    assert daily[0]["datetime"].startswith("2026-10-28")
    assert daily[0]["native_temperature"] == 24.0
    assert daily[0]["native_templow"] == 17.0
    assert daily[1]["datetime"].startswith("2026-10-29")
    assert daily[1]["native_temperature"] == 19.0


def test_read_fallback_weather_entity_conversions_and_guards() -> None:
    """B1 reader converts non-metric units, applies A1, and rejects invalid/self states."""
    state_imperial = MagicMock()
    state_imperial.state = "clear-night"
    state_imperial.last_updated = datetime(2026, 11, 22, 3, 15, tzinfo=ARGENTINA_TIMEZONE)
    state_imperial.attributes = {
        "temperature": 77.0,
        "temperature_unit": "°F",
        "humidity": 60,
        "pressure": 29.92,
        "pressure_unit": "inHg",
        "wind_speed": 5.0,
        "wind_speed_unit": "m/s",
        "wind_bearing": 45,
        "visibility": 10.0,
        "visibility_unit": "mi",
    }

    hass = MagicMock()
    hass.states.get = MagicMock(return_value=state_imperial)

    res = read_fallback_weather_entity(hass, "weather.google_home")
    assert res is not None
    assert res["temperature"] == 25.0
    assert res["apparent_temperature"] == 25.0
    assert res["apparent_temperature_source"] == ST_SOURCE_TEMPERATURE_FALLBACK
    assert res["pressure"] == 1013.2
    assert res["wind_speed"] == 18.0
    assert res["wind_direction"] == "Noreste"
    assert res["visibility"] == 16.1
    assert res["condition"] == ATTR_CONDITION_CLEAR_NIGHT
    assert res["data_source"] == SOURCE_FALLBACK_ENTITY

    # Self-reference blocked
    assert (
        read_fallback_weather_entity(
            hass,
            "weather.smn_aeroparque",
            excluded_entity_ids={"weather.smn_aeroparque"},
        )
        is None
    )

    # Unavailable entity rejected
    state_imperial.state = "unavailable"
    assert read_fallback_weather_entity(hass, "weather.google_home") is None


def test_parse_open_meteo_current_day_and_night() -> None:
    """Open-Meteo parser converts visibility m->km, maps WMO codes, and detects night."""
    payload = {
        "current": {
            "time": "2026-11-22T02:15",
            "temperature_2m": 16.4,
            "relative_humidity_2m": 78,
            "apparent_temperature": 16.1,
            "weather_code": 0,
            "surface_pressure": 919.8,
            "wind_speed_10m": 12.3,
            "wind_direction_10m": 270,
            "is_day": 0,
            "visibility": 24500.0,
        }
    }
    res = parse_open_meteo_current(payload)
    assert res is not None
    assert res["temperature"] == 16.4
    assert res["apparent_temperature"] == 16.1
    assert res["apparent_temperature_source"] == ST_SOURCE_OPEN_METEO
    assert res["pressure"] == 919.8
    assert res["wind_direction"] == "Oeste"
    assert res["visibility"] == 24.5
    assert res["condition"] == ATTR_CONDITION_CLEAR_NIGHT
    assert res["data_source"] == SOURCE_OPEN_METEO
    assert res["date"] == "2026-11-22"
    assert res["time"] == "02:15"


@pytest.mark.asyncio
async def test_coordinator_fresh_smn_skips_open_meteo() -> None:
    """When SMN report is fresh, Open-Meteo is not invoked."""
    now_ar = datetime.now(ARGENTINA_TIMEZONE)
    months_es = [
        "",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    date_str = f"{now_ar.day:02d}-{months_es[now_ar.month]}-{now_ar.year}"
    time_str = now_ar.strftime("%H:%M")

    tiepre_fresh = (
        f"Aeroparque Buenos Aires;{date_str};{time_str};Despejado;10 km;20.5;No se calcula; 55;Norte  12;1012.0 / \n"
    )

    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    coord = SMNDataUpdateCoordinator(hass, MagicMock(), "AEROPARQUE AERO")

    with (
        patch.object(
            coord,
            "_fetch_zip_text",
            new=AsyncMock(side_effect=[tiepre_fresh, ""]),
        ),
        patch(
            "custom_components.smn_ar.coordinator.async_fetch_open_meteo",
            new=AsyncMock(),
        ) as mock_om,
    ):
        data = await coord._async_update_data()

    mock_om.assert_not_awaited()
    assert data["current"]["data_source"] == SOURCE_SMN
    assert data["current"]["fallback_active"] is False
    assert data["current"]["smn_stale"] is False
    assert data["current"]["apparent_temperature"] == 20.5
    assert data["current"]["apparent_temperature_source"] == ST_SOURCE_TEMPERATURE_FALLBACK


@pytest.mark.asyncio
async def test_coordinator_stale_smn_uses_b1_then_b2() -> None:
    """Stale SMN report triggers B1 entity first, and falls through to B2 Open-Meteo if B1 unavailable."""
    stale_tp = (
        "Dolores;20-noviembre-2025;21:00;Despejado;10 km;18.1;No se calcula; 74;Calma;1006.8 / \n"
    )

    # 1. Valid B1 fallback entity
    b1_state = MagicMock()
    b1_state.state = "partlycloudy"
    b1_state.last_updated = datetime(2026, 11, 22, 3, 0, tzinfo=ARGENTINA_TIMEZONE)
    b1_state.attributes = {
        "temperature": 15.2,
        "apparent_temperature": 14.8,
        "humidity": 82,
        "pressure": 1009.0,
        "wind_speed": 11.0,
        "wind_bearing": 180,
    }
    hass = MagicMock()
    hass.states.get = MagicMock(side_effect=lambda eid: b1_state if eid == "weather.local" else None)

    coord = SMNDataUpdateCoordinator(
        hass,
        MagicMock(entry_id="e1"),
        "DOLORES AERO",
        fallback_entity="weather.local",
        enable_open_meteo_fallback=True,
        stale_threshold_hours=3,
    )

    with (
        patch.object(
            coord,
            "_fetch_zip_text",
            new=AsyncMock(side_effect=[stale_tp, ""]),
        ),
        patch(
            "custom_components.smn_ar.coordinator.async_fetch_open_meteo",
            new=AsyncMock(),
        ) as mock_om,
    ):
        data_b1 = await coord._async_update_data()

    mock_om.assert_not_awaited()
    assert data_b1["current"]["data_source"] == SOURCE_FALLBACK_ENTITY
    assert data_b1["current"]["fallback_active"] is True
    assert data_b1["current"]["smn_stale"] is True
    assert data_b1["current"]["temperature"] == 15.2
    assert data_b1["current"]["visibility"] == 10.0  # Preserved from SMN when B1 omitted it
    assert data_b1["current"]["smn_last_report_time"] == "21:00"

    # 2. B1 unavailable -> falls through to B2 Open-Meteo
    b1_state.state = "unavailable"
    om_result = {
        "date": "2026-11-22",
        "time": "03:30",
        "description": "Despejado",
        "condition": ATTR_CONDITION_CLEAR_NIGHT,
        "temperature": 14.5,
        "apparent_temperature": 14.0,
        "apparent_temperature_source": ST_SOURCE_OPEN_METEO,
        "humidity": 85.0,
        "wind_speed": 8.0,
        "wind_direction": "Sur",
        "wind_bearing": 180,
        "pressure": 1010.0,
        "visibility": 20.0,
        "data_source": SOURCE_OPEN_METEO,
    }

    with (
        patch.object(
            coord,
            "_fetch_zip_text",
            new=AsyncMock(side_effect=[stale_tp, ""]),
        ),
        patch(
            "custom_components.smn_ar.coordinator.async_fetch_open_meteo",
            new=AsyncMock(return_value=om_result),
        ) as mock_om,
    ):
        data_b2 = await coord._async_update_data()

    mock_om.assert_awaited_once()
    assert data_b2["current"]["data_source"] == SOURCE_OPEN_METEO
    assert data_b2["current"]["fallback_active"] is True
    assert data_b2["current"]["temperature"] == 14.5
    assert data_b2["current"]["condition"] == ATTR_CONDITION_CLEAR_NIGHT


@pytest.mark.asyncio
async def test_coordinator_missing_station_preserves_cache_and_raises_without_cache() -> None:
    """Missing station from tiepre preserves valid cache and raises UpdateFailed on initial failure."""
    now_ar = datetime.now(ARGENTINA_TIMEZONE)
    months_es = [
        "",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    date_str = f"{now_ar.day:02d}-{months_es[now_ar.month]}-{now_ar.year}"
    time_str = now_ar.strftime("%H:%M")

    fresh_tp = f"Aeroparque Buenos Aires;{date_str};{time_str};Despejado;10 km;20.0;20.0; 50;Norte  10;1015.0 / \n"
    missing_tp = f"Cordoba Aero;{date_str};{time_str};Despejado;10 km;22.0;22.0; 45;Norte  8;1012.0 / \n"

    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    coord = SMNDataUpdateCoordinator(
        hass,
        MagicMock(),
        "AEROPARQUE AERO",
        enable_open_meteo_fallback=False,
    )

    # First run succeeds
    with patch.object(
        coord, "_fetch_zip_text", new=AsyncMock(side_effect=[fresh_tp, ""])
    ):
        first = await coord._async_update_data()
    assert first["current"]["temperature"] == 20.0

    # Second run station absent -> cache returned rather than None values
    with patch.object(
        coord, "_fetch_zip_text", new=AsyncMock(side_effect=[missing_tp, ""])
    ):
        second = await coord._async_update_data()
    assert second["current"]["temperature"] == 20.0
    assert second["current"]["data_source"] == SOURCE_CACHE
    assert second["current"]["smn_stale"] is True

    # Fresh coordinator without cache raises UpdateFailed if SMN fails & fallbacks disabled
    coord_no_cache = SMNDataUpdateCoordinator(
        hass,
        MagicMock(),
        "AEROPARQUE AERO",
        enable_open_meteo_fallback=False,
    )
    with (
        patch.object(
            coord_no_cache,
            "_fetch_zip_text",
            new=AsyncMock(side_effect=[UpdateFailed("down"), ""]),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coord_no_cache._async_update_data()
