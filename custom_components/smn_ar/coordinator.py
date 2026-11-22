"""DataUpdateCoordinator for the SMN Argentina integration."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import math
import os
import re
import unicodedata
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ARGENTINA_TIMEZONE,
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    CONDITION_TEXT_MAP,
    DEFAULT_ENABLE_OPEN_METEO_FALLBACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_THRESHOLD_HOURS,
    DEFAULT_TIMEOUT,
    MONTHS_MAP,
    SOURCE_CACHE,
    SOURCE_SMN,
    SPANISH_MONTHS_FULL,
    ST_SOURCE_SMN,
    ST_SOURCE_TEMPERATURE_FALLBACK,
    STATION_ALIASES,
    STATION_STOPWORDS,
    URL_CURRENT_WEATHER,
    URL_FORECAST,
)
from .fallback import (
    async_fetch_fallback_entity_forecast_conditions,
    async_fetch_open_meteo,
    async_fetch_open_meteo_forecast_conditions,
    enrich_forecast_conditions,
    get_entry_weather_entities,
    merge_weather_with_fallback,
    read_fallback_weather_entity,
    safe_float,
)

_LOGGER = logging.getLogger(__name__)

_STATIONS_CACHE: list[dict[str, Any]] | None = None

COMPASS_DIRECTIONS = {
    "N": 0,
    "NNE": 22,
    "NE": 45,
    "ENE": 67,
    "E": 90,
    "ESE": 112,
    "SE": 135,
    "SSE": 157,
    "S": 180,
    "SSW": 202,
    "SW": 225,
    "WSW": 247,
    "W": 270,
    "WNW": 292,
    "NW": 315,
    "NNW": 337,
    "NORTE": 0,
    "NORESTE": 45,
    "ESTE": 90,
    "SUDESTE": 135,
    "SURESTE": 135,
    "SUR": 180,
    "SUDOESTE": 225,
    "SUROESTE": 225,
    "OESTE": 270,
    "NOROESTE": 315,
    "CALMA": 0,
}


def normalize_name(text: str) -> str:
    """Normalize a station name for consistent lookup."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("_", " ").replace("-", " ").replace(".", " ").strip()
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = re.sub(r"\s+AERO$", "", s)
    s = re.sub(r"\s+AEROPUERTO$", "", s)
    s = re.sub(r"[^A-Z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def wind_direction_to_bearing(direction: str | None) -> int | None:
    """Convert Spanish/standard wind direction to bearing degrees."""
    if not direction:
        return None
    d = direction.strip().upper()
    if d in COMPASS_DIRECTIONS:
        return COMPASS_DIRECTIONS[d]
    for token in re.findall(r"[A-Z]+", d):
        if token in COMPASS_DIRECTIONS:
            return COMPASS_DIRECTIONS[token]
    return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in kilometers between two coordinates."""
    earth_radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def load_stations() -> list[dict[str, Any]]:
    """Load precompiled stations list from stations.json (cached in memory)."""
    global _STATIONS_CACHE
    if _STATIONS_CACHE is not None:
        return _STATIONS_CACHE
    json_path = os.path.join(os.path.dirname(__file__), "stations.json")
    try:
        with open(json_path, encoding="utf-8") as file:
            _STATIONS_CACHE = json.load(file)
            return _STATIONS_CACHE
    except (OSError, ValueError) as err:
        _LOGGER.error("Failed to load stations.json: %s", err)
        return []


def find_closest_station(lat: float, lon: float) -> dict[str, Any] | None:
    """Find the closest station to given latitude and longitude."""
    stations = load_stations()
    if not stations:
        return None
    return min(
        stations,
        key=lambda s: haversine_distance(lat, lon, s["latitude"], s["longitude"]),
    )


def parse_smn_report_datetime(
    date_str: str | None, time_str: str | None
) -> datetime | None:
    """Parse SMN tiepre Spanish date and time strings into Argentina datetime."""
    if not date_str or not time_str:
        return None
    date_match = re.match(
        r"^\s*(\d{1,2})-([a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]+)-(\d{4})\s*$", date_str
    )
    time_match = re.match(r"^\s*(\d{1,2}):(\d{2})", time_str)
    if not date_match or not time_match:
        return None
    day_s, month_name, year_s = date_match.groups()
    hour_s, minute_s = time_match.groups()
    month = SPANISH_MONTHS_FULL.get(month_name.lower())
    if month is None:
        return None
    try:
        return datetime(
            int(year_s),
            month,
            int(day_s),
            int(hour_s),
            int(minute_s),
            tzinfo=ARGENTINA_TIMEZONE,
        )
    except ValueError:
        return None


def is_report_stale(
    report_dt: datetime | None,
    threshold_hours: int = DEFAULT_STALE_THRESHOLD_HOURS,
    now: datetime | None = None,
) -> bool:
    """Return True if an SMN report datetime is missing or older than threshold."""
    if report_dt is None:
        return True
    dt_report = (
        report_dt.astimezone(ARGENTINA_TIMEZONE)
        if report_dt.tzinfo
        else report_dt.replace(tzinfo=ARGENTINA_TIMEZONE)
    )
    current_now = now or datetime.now(ARGENTINA_TIMEZONE)
    dt_now = (
        current_now.astimezone(ARGENTINA_TIMEZONE)
        if current_now.tzinfo
        else current_now.replace(tzinfo=ARGENTINA_TIMEZONE)
    )
    return (dt_now - dt_report) >= timedelta(hours=threshold_hours)


def is_night_time(
    hass: HomeAssistant | None, reference_dt: datetime | None = None
) -> bool:
    """Determine whether it is currently nighttime via sun.sun or local hour."""
    states = getattr(hass, "states", None) if hass is not None else None
    if states is not None:
        sun_state = states.get("sun.sun")
        sun_val = getattr(sun_state, "state", None)
        if isinstance(sun_val, str) and sun_val in (
            "below_horizon",
            "above_horizon",
        ):
            return sun_val == "below_horizon"
    if reference_dt is not None:
        dt_ar = (
            reference_dt.astimezone(ARGENTINA_TIMEZONE)
            if reference_dt.tzinfo
            else reference_dt.replace(tzinfo=ARGENTINA_TIMEZONE)
        )
        return dt_ar.hour >= 20 or dt_ar.hour < 6
    return False


def map_weather_condition(
    description: str | None, *, is_night: bool = False
) -> str:
    """Map SMN weather description text to Home Assistant condition."""
    if not description:
        return ATTR_CONDITION_CLEAR_NIGHT if is_night else ATTR_CONDITION_SUNNY
    desc_lower = description.lower()
    for key, condition in CONDITION_TEXT_MAP.items():
        if key in desc_lower:
            if condition == ATTR_CONDITION_SUNNY and is_night:
                return ATTR_CONDITION_CLEAR_NIGHT
            return condition
    return ATTR_CONDITION_PARTLYCLOUDY


class SMNDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch and manage SMN weather and forecast data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        station_name: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        *,
        fallback_entity: str | None = None,
        enable_open_meteo_fallback: bool = DEFAULT_ENABLE_OPEN_METEO_FALLBACK,
        stale_threshold_hours: int = DEFAULT_STALE_THRESHOLD_HOURS,
    ) -> None:
        """Initialize the SMN coordinator."""
        self.entry = entry
        self.station_name = station_name
        self._norm_station = normalize_name(station_name)
        self._stations = load_stations()
        self._station_info = self._get_station_metadata(station_name)
        self._session = async_get_clientsession(hass)
        self._last_valid_data: dict[str, Any] | None = None
        self._fallback_entity = fallback_entity or None
        self._enable_open_meteo_fallback = enable_open_meteo_fallback
        self._stale_threshold_hours = stale_threshold_hours

        super().__init__(
            hass,
            _LOGGER,
            name=f"SMN Weather ({station_name})",
            update_interval=timedelta(seconds=scan_interval),
        )

    def _get_station_metadata(self, name: str) -> dict[str, Any]:
        """Lookup station details in the stations database."""
        norm_name = normalize_name(name)
        for st in self._stations:
            if normalize_name(st["name"]) == norm_name:
                return st
        return {
            "name": name,
            "province": "",
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0,
            "station_id": "",
            "oaci": "",
        }

    def _get_own_weather_entity_ids(self) -> set[str]:
        """Return weather entity IDs belonging to this config entry."""
        return get_entry_weather_entities(
            self.hass, getattr(self.entry, "entry_id", None)
        )

    def _get_fallback_coordinates(self) -> tuple[float, float] | None:
        """Resolve station or Home Assistant coordinates for Open-Meteo fallback."""
        lat = safe_float(self._station_info.get("latitude"))
        lon = safe_float(self._station_info.get("longitude"))
        if lat is not None and lon is not None and (lat != 0.0 or lon != 0.0):
            return lat, lon
        cfg = getattr(self.hass, "config", None)
        cfg_lat = safe_float(getattr(cfg, "latitude", None))
        cfg_lon = safe_float(getattr(cfg, "longitude", None))
        if (
            cfg_lat is not None
            and cfg_lon is not None
            and (cfg_lat != 0.0 or cfg_lon != 0.0)
        ):
            return cfg_lat, cfg_lon
        return None

    def _fill_missing_smn_fields(
        self, current_weather: dict[str, Any]
    ) -> dict[str, Any]:
        """Fill missing secondary fields on fresh SMN data from B1 if available."""
        optional_fields = ("humidity", "pressure", "wind_speed", "visibility")
        needs_fill = any(
            current_weather.get(field) is None for field in optional_fields
        ) or (
            current_weather.get("wind_bearing") is None
            and not current_weather.get("wind_direction")
        )
        if not self._fallback_entity or not needs_fill:
            return current_weather

        b1_data = read_fallback_weather_entity(
            self.hass,
            self._fallback_entity,
            excluded_entity_ids=self._get_own_weather_entity_ids(),
            wind_bearing_parser=wind_direction_to_bearing,
        )
        if not b1_data:
            return current_weather

        for field in optional_fields:
            if current_weather.get(field) is None and b1_data.get(field) is not None:
                current_weather[field] = b1_data[field]

        if (
            current_weather.get("wind_bearing") is None
            and not current_weather.get("wind_direction")
            and b1_data.get("wind_bearing") is not None
        ):
            current_weather["wind_bearing"] = b1_data["wind_bearing"]
            current_weather["wind_direction"] = b1_data.get("wind_direction", "")

        return current_weather

    async def _resolve_current_weather(
        self,
        smn_current: dict[str, Any] | None,
        current_err: BaseException | None,
    ) -> dict[str, Any]:
        """Resolve current weather using fresh SMN or the B1 -> B2 fallback chain."""
        smn_missing = smn_current is None or smn_current.get("temperature") is None
        smn_stale = (
            True
            if smn_missing
            else is_report_stale(
                smn_current.get("report_datetime"), self._stale_threshold_hours
            )
        )

        if not smn_stale and not smn_missing and smn_current is not None:
            current_weather = dict(smn_current)
            current_weather["smn_stale"] = False
            current_weather["fallback_active"] = False
            current_weather["data_source"] = SOURCE_SMN
            return self._fill_missing_smn_fields(current_weather)

        _LOGGER.debug(
            "SMN current weather for '%s' is %s; evaluating fallback chain",
            self.station_name,
            "missing" if smn_missing else "stale",
        )

        # Priority 2 (B1): Configured Home Assistant weather entity
        if self._fallback_entity:
            b1_data = read_fallback_weather_entity(
                self.hass,
                self._fallback_entity,
                excluded_entity_ids=self._get_own_weather_entity_ids(),
                wind_bearing_parser=wind_direction_to_bearing,
            )
            if b1_data is not None:
                return merge_weather_with_fallback(
                    smn_current,
                    b1_data,
                    self.station_name,
                    fallback_entity_id=self._fallback_entity,
                )

        # Priority 3 (B2): Automatic Open-Meteo fallback
        if self._enable_open_meteo_fallback:
            coords = self._get_fallback_coordinates()
            if coords is not None:
                b2_data = await async_fetch_open_meteo(
                    self._session, coords[0], coords[1]
                )
                if b2_data is not None:
                    return merge_weather_with_fallback(
                        smn_current, b2_data, self.station_name
                    )

        # Priority 4: Degrade gracefully to stale SMN or cached data
        if smn_current is not None:
            degraded = dict(smn_current)
            degraded["smn_stale"] = True
            degraded["fallback_active"] = False
            degraded["data_source"] = SOURCE_SMN
            return degraded

        if self._last_valid_data is not None and self._last_valid_data.get("current"):
            cached_current = dict(self._last_valid_data["current"])
            cached_current["data_source"] = SOURCE_CACHE
            cached_current["smn_stale"] = True
            cached_current["fallback_active"] = False
            return cached_current

        raise UpdateFailed(
            f"Error communicating with SMN API: {current_err or 'station data unavailable'}"
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and parse current weather and forecast data from SMN Open Data."""
        current_res, forecast_res = await asyncio.gather(
            self._fetch_zip_text(URL_CURRENT_WEATHER, "Current Weather"),
            self._fetch_zip_text(URL_FORECAST, "Forecast"),
            return_exceptions=True,
        )

        if isinstance(current_res, asyncio.CancelledError):
            raise current_res
        if isinstance(forecast_res, asyncio.CancelledError):
            raise forecast_res

        hourly_forecast: list[dict[str, Any]] = []
        daily_forecast: list[dict[str, Any]] = []
        if isinstance(forecast_res, BaseException):
            _LOGGER.warning(
                "Error updating SMN forecast (%s): %s",
                self.station_name,
                forecast_res,
            )
        else:
            hourly_forecast, daily_forecast = self._parse_forecast(forecast_res)

        if not hourly_forecast and self._last_valid_data is not None:
            hourly_forecast = self._last_valid_data.get("hourly_forecast", [])
            daily_forecast = self._last_valid_data.get("daily_forecast", [])

        hourly_forecast, daily_forecast = await self._async_enrich_forecasts(
            hourly_forecast, daily_forecast
        )

        current_err: BaseException | None = None
        if isinstance(current_res, BaseException):
            current_err = current_res
            _LOGGER.warning(
                "Error updating SMN current weather (%s): %s",
                self.station_name,
                current_res,
            )
            smn_current = None
        else:
            smn_current = self._parse_current_weather(current_res)

        current_weather = await self._resolve_current_weather(
            smn_current, current_err
        )

        data = {
            "current": current_weather,
            "hourly_forecast": hourly_forecast,
            "daily_forecast": daily_forecast,
            "station": self._station_info,
        }

        self._last_valid_data = data
        return data

    async def _fetch_zip_text(self, url: str, label: str) -> str:
        """Download and extract first text file from an SMN open data zip."""
        try:
            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
                headers={"User-Agent": "HomeAssistant-SMNAR/1.0"},
            ) as response:
                response.raise_for_status()
                content = await response.read()

            with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
                names = zip_file.namelist()
                if not names:
                    raise UpdateFailed(f"Empty zip archive received for {label}")
                raw_bytes = zip_file.read(names[0])
                try:
                    return raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    return raw_bytes.decode("cp1252", errors="replace")

        except TimeoutError as err:
            raise UpdateFailed(f"Timeout while downloading {label} from SMN") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"HTTP error downloading {label}: {err}") from err
        except zipfile.BadZipFile as err:
            raise UpdateFailed(f"Corrupted zip archive for {label}: {err}") from err

    async def _async_enrich_forecasts(
        self,
        hourly_forecast: list[dict[str, Any]],
        daily_forecast: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Enrich dry/calm SMN forecast entries with sky conditions from B1 -> B2."""
        dry_hourly = [
            slot
            for slot in hourly_forecast
            if slot.get("condition") == ATTR_CONDITION_PARTLYCLOUDY
        ]
        dry_daily = [
            day
            for day in daily_forecast
            if day.get("condition") == ATTR_CONDITION_PARTLYCLOUDY
        ]
        if not dry_hourly and not dry_daily:
            return hourly_forecast, daily_forecast

        hourly_conds: dict[str, str] = {}
        daily_conds: dict[str, str] = {}

        if self._fallback_entity:
            b1_h, b1_d = await async_fetch_fallback_entity_forecast_conditions(
                self.hass,
                self._fallback_entity,
                excluded_entity_ids=self._get_own_weather_entity_ids(),
            )
            hourly_conds.update(b1_h)
            daily_conds.update(b1_d)

        def _has_uncovered_slots() -> bool:
            for day in dry_daily:
                dt_raw = day.get("datetime")
                if isinstance(dt_raw, str) and dt_raw[:10] not in daily_conds:
                    return True
            for slot in dry_hourly:
                dt_raw = slot.get("datetime")
                if isinstance(dt_raw, str):
                    try:
                        slot_ar = datetime.fromisoformat(dt_raw).astimezone(
                            ARGENTINA_TIMEZONE
                        )
                    except ValueError:
                        continue
                    if slot_ar.strftime("%Y-%m-%dT%H") not in hourly_conds:
                        return True
            return False

        if self._enable_open_meteo_fallback and _has_uncovered_slots():
            coords = self._get_fallback_coordinates()
            if coords is not None:
                om_h, om_d = await async_fetch_open_meteo_forecast_conditions(
                    self._session, coords[0], coords[1]
                )
                for k, v in om_h.items():
                    hourly_conds.setdefault(k, v)
                for k, v in om_d.items():
                    daily_conds.setdefault(k, v)

        if not hourly_conds and not daily_conds:
            return hourly_forecast, daily_forecast

        return enrich_forecast_conditions(
            hourly_forecast, daily_forecast, hourly_conds, daily_conds
        )

    def _find_matching_key(self, candidates: dict[str, Any]) -> str | None:
        """Find the matching key for the configured station in a dictionary."""
        target = self._norm_station
        if not target:
            return None

        # 1. Exact match
        if target in candidates:
            return target

        # 2. Explicit alias lookup
        for alias in STATION_ALIASES.get(target, ()):
            norm_alias = normalize_name(alias)
            if norm_alias in candidates:
                return norm_alias

        # 3. Conservative token matching (ignore stopwords, isolate Antarctic bases)
        target_tokens = set(target.split())
        target_is_base = "BASE" in target_tokens
        target_sig = target_tokens - STATION_STOPWORDS or target_tokens

        best_match: str | None = None
        best_score = 0.0
        for key in candidates:
            key_tokens = set(key.split())
            if target_is_base != ("BASE" in key_tokens):
                continue
            key_sig = key_tokens - STATION_STOPWORDS or key_tokens
            if target_sig == key_sig:
                return key

            common = target_sig & key_sig
            if len(common) < 2:
                continue
            jaccard = len(common) / len(target_sig | key_sig)
            if jaccard >= 0.75 and jaccard > best_score:
                best_score = jaccard
                best_match = key

        return best_match

    def _parse_current_weather(self, text: str) -> dict[str, Any] | None:
        """Parse tiepre text into current weather dictionary, or None if missing."""
        stations_data: dict[str, dict[str, Any]] = {}

        for line in text.splitlines():
            line_str = line.strip()
            if not line_str or ";" not in line_str:
                continue

            parts = [p.strip() for p in line_str.split(";")]
            if len(parts) < 9:
                continue

            st_name = parts[0]
            date_str = parts[1]
            time_str = parts[2]
            desc = parts[3]
            vis_str = parts[4]
            temp_str = parts[5]
            st_str = parts[6]
            hum_str = parts[7]
            wind_str = parts[8]
            press_str = parts[9].replace("/", "").strip() if len(parts) > 9 else ""

            # Parse wind
            wind_parts = wind_str.split()
            wind_speed = None
            wind_dir_str = ""
            if wind_parts:
                parsed_speed = safe_float(wind_parts[-1])
                if parsed_speed is not None:
                    wind_speed = parsed_speed
                    wind_dir_str = " ".join(wind_parts[:-1])
                elif "calma" in wind_str.lower():
                    wind_speed = 0.0
                    wind_dir_str = "Calma"

            # Parse visibility
            vis_val = None
            vis_km = re.search(r"([\d\.,]+)\s*km\b", vis_str, re.IGNORECASE)
            if vis_km:
                vis_val = safe_float(vis_km.group(1))
            else:
                vis_m = re.search(r"([\d\.,]+)\s*m\b", vis_str, re.IGNORECASE)
                if vis_m:
                    vis_meters = safe_float(vis_m.group(1))
                    if vis_meters is not None:
                        vis_val = round(vis_meters / 1000.0, 2)

            temp = safe_float(temp_str)
            raw_st = safe_float(st_str)
            if raw_st is not None:
                apparent_temp: float | None = raw_st
                st_source: str | None = ST_SOURCE_SMN
            elif temp is not None:
                apparent_temp = temp
                st_source = ST_SOURCE_TEMPERATURE_FALLBACK
            else:
                apparent_temp = None
                st_source = None

            humidity = safe_float(hum_str)
            pressure = safe_float(press_str)
            report_dt = parse_smn_report_datetime(date_str, time_str)
            is_night = is_night_time(self.hass, report_dt)

            norm_k = normalize_name(st_name)
            stations_data[norm_k] = {
                "station_name": st_name,
                "date": date_str,
                "time": time_str,
                "description": desc,
                "condition": map_weather_condition(desc, is_night=is_night),
                "temperature": temp,
                "apparent_temperature": apparent_temp,
                "apparent_temperature_source": st_source,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "wind_direction": wind_dir_str,
                "wind_bearing": wind_direction_to_bearing(wind_dir_str),
                "pressure": pressure,
                "visibility": vis_val,
                "report_datetime": report_dt,
                "data_source": SOURCE_SMN,
                "fallback_active": False,
                "smn_stale": False,
                "smn_last_report_date": date_str,
                "smn_last_report_time": time_str,
            }

        matched_key = self._find_matching_key(stations_data)
        if matched_key and matched_key in stations_data:
            return stations_data[matched_key]

        _LOGGER.warning(
            "Station '%s' (normalized: '%s') not found in current weather. Available: %s",
            self.station_name,
            self._norm_station,
            list(stations_data.keys())[:10],
        )
        return None

    def _parse_forecast(
        self, text: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse pron5d text into hourly and daily forecast lists."""
        stations_forecast: dict[str, list[dict[str, Any]]] = {}
        current_st = None
        lines = text.splitlines()

        for i, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue

            # Detect station header (station name line followed by ====)
            if (
                i + 1 < len(lines)
                and lines[i + 1].startswith(" ==")
                and not line_str.startswith("=")
                and "(DIR" not in line_str
                and "FECHA" not in line_str
                and not line_str.startswith("*")
                and "Hs." not in line_str
            ):
                current_st = normalize_name(line_str)
                stations_forecast[current_st] = []
                continue

            # Detect forecast slot
            m = re.match(
                r"(\d{2})/([A-Z]{3})/(\d{4})\s+(\d{2})Hs\.\s+([\-\d\.]+)\s+(\d+)\s*\|\s*(\d+)\s+([\-\d\.]+)",
                line_str,
            )
            if m and current_st is not None:
                day, month_str, year, hour, temp, wind_dir, wind_spd, precip = (
                    m.groups()
                )
                month = MONTHS_MAP.get(month_str, 1)
                dt = datetime(
                    int(year), month, int(day), int(hour), 0, tzinfo=ARGENTINA_TIMEZONE
                )
                utc_iso = dt.astimezone(UTC).isoformat()

                temp_val = safe_float(temp)
                precip_val = safe_float(precip)
                wind_spd_val = safe_float(wind_spd)
                if temp_val is None or precip_val is None or wind_spd_val is None:
                    continue
                wind_dir_val = int(wind_dir)

                # Assign condition based on precipitation and temperature
                if precip_val > 5.0:
                    cond = ATTR_CONDITION_POURING
                elif precip_val > 0.0:
                    cond = (
                        ATTR_CONDITION_SNOWY
                        if temp_val < 0.0
                        else ATTR_CONDITION_RAINY
                    )
                elif wind_spd_val > 40.0:
                    cond = ATTR_CONDITION_WINDY
                else:
                    cond = ATTR_CONDITION_PARTLYCLOUDY

                stations_forecast[current_st].append(
                    {
                        "datetime": utc_iso,
                        "native_temperature": temp_val,
                        "temperature": temp_val,
                        "wind_bearing": wind_dir_val,
                        "native_wind_speed": wind_spd_val,
                        "wind_speed": wind_spd_val,
                        "native_precipitation": precip_val,
                        "precipitation": precip_val,
                        "condition": cond,
                    }
                )

        matched_key = self._find_matching_key(stations_forecast)
        hourly_forecast: list[dict[str, Any]] = []
        if matched_key and matched_key in stations_forecast:
            hourly_forecast = stations_forecast[matched_key]

        # Aggregate hourly forecast into daily forecast using Argentina local date (UTC-3)
        daily_groups: dict[str, list[dict[str, Any]]] = {}
        for slot in hourly_forecast:
            slot_dt_ar = datetime.fromisoformat(slot["datetime"]).astimezone(
                ARGENTINA_TIMEZONE
            )
            day_str = slot_dt_ar.strftime("%Y-%m-%d")
            if day_str not in daily_groups:
                daily_groups[day_str] = []
            daily_groups[day_str].append(slot)

        daily_forecast: list[dict[str, Any]] = []
        for day_str, slots in daily_groups.items():
            temps = [s["native_temperature"] for s in slots]
            precips = [s["native_precipitation"] for s in slots]
            winds = [s["native_wind_speed"] for s in slots]
            tot_precip = round(sum(precips), 1)

            if tot_precip > 15.0:
                cond = ATTR_CONDITION_POURING
            elif tot_precip > 0.0:
                cond = ATTR_CONDITION_RAINY
            elif max(winds) > 40.0:
                cond = ATTR_CONDITION_WINDY
            else:
                cond = ATTR_CONDITION_PARTLYCLOUDY

            dt_daily = datetime(
                int(day_str[:4]),
                int(day_str[5:7]),
                int(day_str[8:10]),
                12,
                0,
                tzinfo=UTC,
            )

            daily_forecast.append(
                {
                    "datetime": dt_daily.isoformat(),
                    "native_temperature": round(max(temps), 1),
                    "temperature": round(max(temps), 1),
                    "native_templow": round(min(temps), 1),
                    "templow": round(min(temps), 1),
                    "native_precipitation": tot_precip,
                    "precipitation": tot_precip,
                    "native_wind_speed": round(sum(winds) / len(winds), 1),
                    "wind_speed": round(sum(winds) / len(winds), 1),
                    "wind_bearing": slots[0]["wind_bearing"],
                    "condition": cond,
                }
            )

        return hourly_forecast, daily_forecast
