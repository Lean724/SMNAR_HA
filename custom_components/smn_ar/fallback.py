"""Fallback weather providers (HA weather entity and Open-Meteo) and unit helpers."""
from __future__ import annotations

import inspect
import logging
import math
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

import aiohttp
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_SUNNY,
    WeatherEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    ARGENTINA_TIMEZONE,
    DEFAULT_TIMEOUT,
    HA_CONDITION_DESCRIPTION_ES,
    SOURCE_FALLBACK_ENTITY,
    SOURCE_OPEN_METEO,
    ST_SOURCE_FALLBACK_ENTITY,
    ST_SOURCE_OPEN_METEO,
    ST_SOURCE_TEMPERATURE_FALLBACK,
    URL_OPEN_METEO,
    WMO_CODE_CONDITION_MAP,
    WMO_CODE_DESCRIPTION_MAP,
)

_LOGGER = logging.getLogger(__name__)

_NON_NUMERIC_TOKENS = {
    "no se calcula",
    "s/d",
    "n/d",
    "na",
    "n/a",
    "nan",
    "inf",
    "-inf",
    "+inf",
    "none",
    "null",
    "unknown",
    "unavailable",
}

_COMPASS_DIRECTIONS_ES = (
    "Norte",
    "Noreste",
    "Este",
    "Sudeste",
    "Sur",
    "Sudoeste",
    "Oeste",
    "Noroeste",
)


def safe_float(value: Any) -> float | None:
    """Safely convert a value to a finite float, returning None if invalid."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) else None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or "_" in cleaned:
            return None
        if cleaned.lower() in _NON_NUMERIC_TOKENS or set(cleaned) <= {"-", "/", "."}:
            return None
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            num = float(cleaned)
        except ValueError:
            return None
        return num if math.isfinite(num) else None
    return None


def degrees_to_compass_es(
    bearing: float | None, wind_speed: float | None = None
) -> str:
    """Convert bearing degrees (0-360) to Spanish 8-point compass direction."""
    if wind_speed is not None and wind_speed == 0:
        return "Calma"
    num_bearing = safe_float(bearing)
    if num_bearing is None:
        return ""
    idx = int(((num_bearing % 360) + 22.5) // 45) % 8
    return _COMPASS_DIRECTIONS_ES[idx]


def wmo_code_to_condition(code: float | None, *, is_night: bool = False) -> str:
    """Map an Open-Meteo WMO code to a Home Assistant weather condition."""
    if code is None:
        return ATTR_CONDITION_PARTLYCLOUDY
    try:
        code_int = int(code)
    except (TypeError, ValueError):
        return ATTR_CONDITION_PARTLYCLOUDY
    condition = WMO_CODE_CONDITION_MAP.get(code_int, ATTR_CONDITION_PARTLYCLOUDY)
    if condition == ATTR_CONDITION_SUNNY and is_night:
        return ATTR_CONDITION_CLEAR_NIGHT
    return condition


def wmo_code_to_description(code: float | None) -> str:
    """Map an Open-Meteo WMO code to a Spanish description."""
    if code is None:
        return "Parcialmente nublado"
    try:
        code_int = int(code)
    except (TypeError, ValueError):
        return "Parcialmente nublado"
    return WMO_CODE_DESCRIPTION_MAP.get(code_int, "Parcialmente nublado")


def _convert_temperature_to_c(val: float | None, unit: str | None) -> float | None:
    """Convert temperature to Celsius."""
    if val is None:
        return None
    u = (unit or "").strip().lower()
    if u in ("°f", "f"):
        return round((val - 32.0) * 5.0 / 9.0, 1)
    if u == "k":
        return round(val - 273.15, 1)
    return round(val, 1)


def _convert_pressure_to_hpa(val: float | None, unit: str | None) -> float | None:
    """Convert atmospheric pressure to hPa."""
    if val is None:
        return None
    u = (unit or "").strip().lower()
    if u == "pa":
        return round(val / 100.0, 1)
    if u in ("kpa", "cbar"):
        return round(val * 10.0, 1)
    if u == "inhg":
        return round(val * 33.86389, 1)
    if u == "mmhg":
        return round(val * 1.33322, 1)
    if u == "psi":
        return round(val * 68.94757, 1)
    if u == "bar":
        return round(val * 1000.0, 1)
    return round(val, 1)


def _convert_speed_to_kmh(val: float | None, unit: str | None) -> float | None:
    """Convert wind speed to km/h."""
    if val is None:
        return None
    u = (unit or "").strip().lower()
    if u in ("m/s", "mps"):
        return round(val * 3.6, 1)
    if u in ("mph", "mi/h"):
        return round(val * 1.60934, 1)
    if u in ("kn", "kt", "kts"):
        return round(val * 1.852, 1)
    if u == "ft/s":
        return round(val * 1.09728, 1)
    return round(val, 1)


def _convert_distance_to_km(val: float | None, unit: str | None) -> float | None:
    """Convert visibility distance to km."""
    if val is None:
        return None
    u = (unit or "").strip().lower()
    if u == "m":
        return round(val / 1000.0, 1)
    if u in ("mi", "mi."):
        return round(val * 1.60934, 1)
    if u == "yd":
        return round(val * 0.0009144, 1)
    if u == "ft":
        return round(val * 0.0003048, 1)
    return round(val, 1)


def get_entry_weather_entities(
    hass: HomeAssistant | None, entry_id: str | None
) -> set[str]:
    """Return weather entity IDs owned by a config entry to prevent self-reference."""
    if hass is None or not entry_id:
        return set()
    try:
        registry = er.async_get(hass)
        if registry is None:
            return set()
        entries = er.async_entries_for_config_entry(registry, entry_id)
        if not isinstance(entries, (list, tuple, set)):
            return set()
        return {
            item.entity_id
            for item in entries
            if getattr(item, "domain", None) == "weather"
            and isinstance(getattr(item, "entity_id", None), str)
        }
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        return set()


def _resolve_unit(
    attrs: Mapping[str, Any], attr_key: str, hass: HomeAssistant | None, cfg_attr: str
) -> str | None:
    """Resolve unit string from entity attributes or Home Assistant config."""
    unit = attrs.get(attr_key)
    if isinstance(unit, str):
        return unit
    cfg_units = getattr(getattr(hass, "config", None), "units", None)
    cfg_unit = getattr(cfg_units, cfg_attr, None)
    return cfg_unit if isinstance(cfg_unit, str) else None


def read_fallback_weather_entity(
    hass: HomeAssistant | None,
    entity_id: str | None,
    *,
    excluded_entity_ids: set[str] | None = None,
    wind_bearing_parser: Callable[[str | None], int | None] | None = None,
) -> dict[str, Any] | None:
    """Read and normalize current weather from another HA weather entity (B1)."""
    if hass is None or not entity_id:
        return None
    if entity_id in (excluded_entity_ids or set()):
        _LOGGER.warning(
            "Ignoring fallback weather entity %s because it belongs to this entry",
            entity_id,
        )
        return None

    states = getattr(hass, "states", None)
    state = states.get(entity_id) if states is not None else None
    if state is None:
        return None

    condition = getattr(state, "state", None)
    if not isinstance(condition, str) or condition in ("unknown", "unavailable", ""):
        return None

    raw_attrs = getattr(state, "attributes", None)
    attrs: Mapping[str, Any] = raw_attrs if isinstance(raw_attrs, Mapping) else {}

    temp_unit = _resolve_unit(attrs, "temperature_unit", hass, "temperature_unit")
    press_unit = _resolve_unit(attrs, "pressure_unit", hass, "pressure_unit")
    wind_unit = _resolve_unit(attrs, "wind_speed_unit", hass, "wind_speed_unit")
    vis_unit = _resolve_unit(attrs, "visibility_unit", hass, "length_unit")

    temperature = _convert_temperature_to_c(
        safe_float(attrs.get("temperature")), temp_unit
    )
    if temperature is None:
        return None

    apparent_temp = _convert_temperature_to_c(
        safe_float(attrs.get("apparent_temperature")), temp_unit
    )
    if apparent_temp is None:
        apparent_temp = temperature
        st_source = ST_SOURCE_TEMPERATURE_FALLBACK
    else:
        st_source = ST_SOURCE_FALLBACK_ENTITY

    humidity = safe_float(attrs.get("humidity"))
    pressure = _convert_pressure_to_hpa(safe_float(attrs.get("pressure")), press_unit)
    wind_speed = _convert_speed_to_kmh(safe_float(attrs.get("wind_speed")), wind_unit)
    visibility = _convert_distance_to_km(safe_float(attrs.get("visibility")), vis_unit)

    raw_bearing = attrs.get("wind_bearing")
    num_bearing = safe_float(raw_bearing)
    if num_bearing is not None:
        wind_bearing: int | None = round(num_bearing) % 360
        wind_direction = degrees_to_compass_es(wind_bearing, wind_speed)
    elif isinstance(raw_bearing, str) and raw_bearing.strip():
        wind_direction = raw_bearing.strip()
        wind_bearing = wind_bearing_parser(wind_direction) if wind_bearing_parser else None
    else:
        wind_bearing = None
        wind_direction = "Calma" if wind_speed == 0 else ""

    last_updated = getattr(state, "last_updated", None)
    if isinstance(last_updated, datetime):
        dt_ar = (
            last_updated.astimezone(ARGENTINA_TIMEZONE)
            if last_updated.tzinfo
            else last_updated.replace(tzinfo=ARGENTINA_TIMEZONE)
        )
    else:
        dt_ar = datetime.now(ARGENTINA_TIMEZONE)

    return {
        "date": dt_ar.strftime("%Y-%m-%d"),
        "time": dt_ar.strftime("%H:%M"),
        "description": HA_CONDITION_DESCRIPTION_ES.get(condition, condition),
        "condition": condition,
        "temperature": temperature,
        "apparent_temperature": apparent_temp,
        "apparent_temperature_source": st_source,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "wind_bearing": wind_bearing,
        "pressure": pressure,
        "visibility": visibility,
        "data_source": SOURCE_FALLBACK_ENTITY,
    }


def parse_open_meteo_current(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Parse Open-Meteo current JSON payload into normalized SMN weather fields."""
    current = payload.get("current")
    if not isinstance(current, Mapping):
        return None

    temperature = safe_float(current.get("temperature_2m"))
    if temperature is None:
        return None
    temperature = round(temperature, 1)

    raw_st = safe_float(current.get("apparent_temperature"))
    if raw_st is not None:
        apparent_temp = round(raw_st, 1)
        st_source = ST_SOURCE_OPEN_METEO
    else:
        apparent_temp = temperature
        st_source = ST_SOURCE_TEMPERATURE_FALLBACK

    humidity = safe_float(current.get("relative_humidity_2m"))
    if humidity is not None:
        humidity = round(humidity, 1)

    pressure = safe_float(current.get("surface_pressure"))
    if pressure is not None:
        pressure = round(pressure, 1)

    wind_speed = safe_float(current.get("wind_speed_10m"))
    if wind_speed is not None:
        wind_speed = round(wind_speed, 1)

    raw_bearing = safe_float(current.get("wind_direction_10m"))
    wind_bearing = round(raw_bearing) % 360 if raw_bearing is not None else None
    wind_direction = degrees_to_compass_es(wind_bearing, wind_speed)

    vis_meters = safe_float(current.get("visibility"))
    visibility = round(vis_meters / 1000.0, 1) if vis_meters is not None else None

    wmo_code = safe_float(current.get("weather_code"))
    is_night = current.get("is_day") == 0
    condition = wmo_code_to_condition(wmo_code, is_night=is_night)
    description = wmo_code_to_description(wmo_code)

    time_raw = current.get("time")
    if isinstance(time_raw, str) and "T" in time_raw:
        date_part, time_part = time_raw.split("T", 1)
        time_part = time_part[:5]
    else:
        now_ar = datetime.now(ARGENTINA_TIMEZONE)
        date_part = now_ar.strftime("%Y-%m-%d")
        time_part = now_ar.strftime("%H:%M")

    return {
        "date": date_part,
        "time": time_part,
        "description": description,
        "condition": condition,
        "temperature": temperature,
        "apparent_temperature": apparent_temp,
        "apparent_temperature_source": st_source,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "wind_bearing": wind_bearing,
        "pressure": pressure,
        "visibility": visibility,
        "data_source": SOURCE_OPEN_METEO,
    }


async def async_fetch_open_meteo(
    session: aiohttp.ClientSession,
    latitude: float,
    longitude: float,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any] | None:
    """Fetch current weather conditions from Open-Meteo as automatic fallback (B2)."""
    params = {
        "latitude": f"{latitude}",
        "longitude": f"{longitude}",
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "weather_code,surface_pressure,wind_speed_10m,wind_direction_10m,"
            "is_day,visibility"
        ),
        "wind_speed_unit": "kmh",
        "timezone": "America/Argentina/Buenos_Aires",
    }
    try:
        async with session.get(
            URL_OPEN_METEO,
            params=params,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={"User-Agent": "HomeAssistant-SMNAR/1.0"},
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        if not isinstance(payload, Mapping):
            return None
        return parse_open_meteo_current(payload)
    except (TimeoutError, aiohttp.ClientError, ValueError, KeyError) as err:
        _LOGGER.warning("Open-Meteo fallback request failed: %s", err)
        return None


def merge_weather_with_fallback(
    smn_current: dict[str, Any] | None,
    fallback_data: dict[str, Any],
    station_name: str,
    *,
    fallback_entity_id: str | None = None,
) -> dict[str, Any]:
    """Merge fallback readings with SMN metadata and missing secondary fields."""
    smn = smn_current or {}
    merged = dict(fallback_data)
    merged["station_name"] = smn.get("station_name") or station_name

    # Keep SMN secondary measurements if fallback omitted them (e.g. visibility in B1)
    for field in ("humidity", "pressure", "wind_speed", "visibility"):
        if merged.get(field) is None and smn.get(field) is not None:
            merged[field] = smn[field]

    if merged.get("wind_bearing") is None and not merged.get("wind_direction"):
        if smn.get("wind_bearing") is not None:
            merged["wind_bearing"] = smn["wind_bearing"]
        if smn.get("wind_direction"):
            merged["wind_direction"] = smn["wind_direction"]

    if (
        merged.get("apparent_temperature") is None
        and merged.get("temperature") is not None
    ):
        merged["apparent_temperature"] = merged["temperature"]
        merged["apparent_temperature_source"] = ST_SOURCE_TEMPERATURE_FALLBACK

    merged["fallback_active"] = True
    merged["smn_stale"] = True
    if fallback_entity_id:
        merged["fallback_entity"] = fallback_entity_id
    merged["smn_last_report_date"] = smn.get("date")
    merged["smn_last_report_time"] = smn.get("time")
    return merged


def parse_open_meteo_forecast_conditions(
    payload: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    """Parse Open-Meteo hourly and daily WMO weather codes into condition maps."""
    hourly_conditions: dict[str, str] = {}
    hourly = payload.get("hourly")
    if isinstance(hourly, Mapping):
        times = hourly.get("time")
        codes = hourly.get("weather_code")
        is_days = hourly.get("is_day")
        if isinstance(times, list) and isinstance(codes, list):
            for idx, time_raw in enumerate(times):
                if idx >= len(codes) or not isinstance(time_raw, str):
                    continue
                if len(time_raw) < 13:
                    continue
                is_day_val = (
                    is_days[idx]
                    if isinstance(is_days, list) and idx < len(is_days)
                    else 1
                )
                code_val = safe_float(codes[idx])
                if code_val is None:
                    continue
                hourly_conditions[time_raw[:13]] = wmo_code_to_condition(
                    code_val, is_night=(is_day_val == 0)
                )

    daily_conditions: dict[str, str] = {}
    daily = payload.get("daily")
    if isinstance(daily, Mapping):
        times = daily.get("time")
        codes = daily.get("weather_code")
        if isinstance(times, list) and isinstance(codes, list):
            for idx, time_raw in enumerate(times):
                if idx >= len(codes) or not isinstance(time_raw, str):
                    continue
                if len(time_raw) < 10:
                    continue
                code_val = safe_float(codes[idx])
                if code_val is None:
                    continue
                daily_conditions[time_raw[:10]] = wmo_code_to_condition(
                    code_val, is_night=False
                )

    return hourly_conditions, daily_conditions


async def async_fetch_open_meteo_forecast_conditions(
    session: aiohttp.ClientSession,
    latitude: float,
    longitude: float,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[dict[str, str], dict[str, str]]:
    """Fetch Open-Meteo daily and hourly sky conditions to enrich SMN pron5d icons."""
    params = {
        "latitude": f"{latitude}",
        "longitude": f"{longitude}",
        "daily": "weather_code",
        "hourly": "weather_code,is_day",
        "forecast_days": "6",
        "timezone": "America/Argentina/Buenos_Aires",
    }
    try:
        async with session.get(
            URL_OPEN_METEO,
            params=params,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={"User-Agent": "HomeAssistant-SMNAR/1.0"},
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        if not isinstance(payload, Mapping):
            return {}, {}
        return parse_open_meteo_forecast_conditions(payload)
    except (TimeoutError, aiohttp.ClientError, ValueError, KeyError) as err:
        _LOGGER.debug("Open-Meteo forecast condition fetch failed: %s", err)
        return {}, {}


def _parse_forecast_dt_to_argentina(dt_raw: Any) -> tuple[datetime | None, str | None]:
    """Parse a forecast item datetime string into Argentina local time or date key."""
    if not isinstance(dt_raw, str) or not dt_raw.strip():
        return None, None
    cleaned = dt_raw.strip()
    if "T" not in cleaned and " " not in cleaned and len(cleaned) >= 10:
        return None, cleaned[:10]
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None, cleaned[:10] if len(cleaned) >= 10 else None
    dt_ar = (
        dt.astimezone(ARGENTINA_TIMEZONE)
        if dt.tzinfo
        else dt.replace(tzinfo=ARGENTINA_TIMEZONE)
    )
    return dt_ar, dt_ar.strftime("%Y-%m-%d")


async def async_fetch_fallback_entity_forecast_conditions(
    hass: HomeAssistant | None,
    entity_id: str | None,
    *,
    excluded_entity_ids: set[str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Fetch daily and hourly sky conditions from an HA weather fallback entity (B1)."""
    if hass is None or not entity_id:
        return {}, {}
    if entity_id in (excluded_entity_ids or set()):
        return {}, {}

    states = getattr(hass, "states", None)
    state = states.get(entity_id) if states is not None else None
    if state is None:
        return {}, {}
    state_val = getattr(state, "state", None)
    if not isinstance(state_val, str) or state_val in ("unknown", "unavailable", ""):
        return {}, {}

    services = getattr(hass, "services", None)
    if services is None or services.has_service("weather", "get_forecasts") is not True:
        return {}, {}

    attrs = getattr(state, "attributes", None)
    supported = attrs.get("supported_features") if isinstance(attrs, Mapping) else None
    if isinstance(supported, int) and not isinstance(supported, bool):
        try_daily = bool(supported & WeatherEntityFeature.FORECAST_DAILY)
        try_hourly = bool(supported & WeatherEntityFeature.FORECAST_HOURLY)
    else:
        try_daily = True
        try_hourly = True

    hourly_conditions: dict[str, str] = {}
    daily_conditions: dict[str, str] = {}

    for ftype, enabled in (("daily", try_daily), ("hourly", try_hourly)):
        if not enabled:
            continue
        try:
            call_res = services.async_call(
                "weather",
                "get_forecasts",
                {"type": ftype},
                target={"entity_id": entity_id},
                blocking=True,
                return_response=True,
            )
            response = await call_res if inspect.isawaitable(call_res) else call_res
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as err:
            _LOGGER.debug(
                "Failed reading %s forecast from fallback entity %s: %s",
                ftype,
                entity_id,
                err,
            )
            continue

        if not isinstance(response, Mapping):
            continue
        entity_payload = response.get(entity_id)
        if not isinstance(entity_payload, Mapping):
            continue
        forecast_items = entity_payload.get("forecast")
        if not isinstance(forecast_items, list):
            continue

        for item in forecast_items:
            if not isinstance(item, Mapping):
                continue
            cond = item.get("condition")
            if not isinstance(cond, str) or not cond:
                continue
            dt_ar, date_key = _parse_forecast_dt_to_argentina(item.get("datetime"))
            if ftype == "daily" and date_key:
                daily_conditions.setdefault(date_key, cond)
            elif ftype == "hourly" and dt_ar is not None:
                hourly_conditions.setdefault(dt_ar.strftime("%Y-%m-%dT%H"), cond)

    return hourly_conditions, daily_conditions


def enrich_forecast_conditions(
    hourly_forecast: list[dict[str, Any]],
    daily_forecast: list[dict[str, Any]],
    hourly_conditions: Mapping[str, str],
    daily_conditions: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Enrich dry/calm SMN forecast entries with sky conditions without altering SMN rain/wind."""
    enriched_hourly: list[dict[str, Any]] = []
    for slot in hourly_forecast:
        new_slot = dict(slot)
        if new_slot.get("condition") == ATTR_CONDITION_PARTLYCLOUDY:
            dt_raw = new_slot.get("datetime")
            if isinstance(dt_raw, str):
                try:
                    slot_ar = datetime.fromisoformat(dt_raw).astimezone(
                        ARGENTINA_TIMEZONE
                    )
                    hour_key = slot_ar.strftime("%Y-%m-%dT%H")
                    day_key = slot_ar.strftime("%Y-%m-%d")
                    cond = hourly_conditions.get(hour_key)
                    if cond is None and day_key in daily_conditions:
                        cond = daily_conditions[day_key]
                        if cond == ATTR_CONDITION_SUNNY and (
                            slot_ar.hour >= 20 or slot_ar.hour < 6
                        ):
                            cond = ATTR_CONDITION_CLEAR_NIGHT
                    if cond is not None:
                        new_slot["condition"] = cond
                except ValueError:
                    pass
        enriched_hourly.append(new_slot)

    enriched_daily: list[dict[str, Any]] = []
    for day in daily_forecast:
        new_day = dict(day)
        if new_day.get("condition") == ATTR_CONDITION_PARTLYCLOUDY:
            dt_raw = new_day.get("datetime")
            if isinstance(dt_raw, str) and len(dt_raw) >= 10:
                cond = daily_conditions.get(dt_raw[:10])
                if cond is not None:
                    new_day["condition"] = cond
        enriched_daily.append(new_day)

    return enriched_hourly, enriched_daily
