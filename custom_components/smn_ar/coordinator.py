"""DataUpdateCoordinator for the SMN Argentina integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import io
import json
import logging
import math
import os
import re
from typing import Any
import unicodedata
import zipfile

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    CONDITION_TEXT_MAP,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MONTHS_MAP,
    STATION_ALIASES,
    URL_CURRENT_WEATHER,
    URL_FORECAST,
)

_LOGGER = logging.getLogger(__name__)

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
    s = s.upper().replace("_", " ").replace("-", " ").strip()
    s = re.sub(r"\s+AERO$", "", s)
    s = re.sub(r"\s+AEROPUERTO$", "", s)
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = re.sub(r"[^A-Z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s)


def wind_direction_to_bearing(direction: str | None) -> int | None:
    """Convert Spanish/standard wind direction to bearing degrees."""
    if not direction:
        return None
    d = direction.strip().upper()
    if d in COMPASS_DIRECTIONS:
        return COMPASS_DIRECTIONS[d]
    for key, bearing in COMPASS_DIRECTIONS.items():
        if key in d:
            return bearing
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
    """Load precompiled stations list from stations.json."""
    json_path = os.path.join(os.path.dirname(__file__), "stations.json")
    try:
        with open(json_path, encoding="utf-8") as file:
            return json.load(file)
    except Exception as err:
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


def map_weather_condition(description: str | None) -> str:
    """Map SMN weather description text to Home Assistant condition."""
    if not description:
        return ATTR_CONDITION_SUNNY
    desc_lower = description.lower()
    for key, condition in CONDITION_TEXT_MAP.items():
        if key in desc_lower:
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
    ) -> None:
        """Initialize the SMN coordinator."""
        self.entry = entry
        self.station_name = station_name
        self._norm_station = normalize_name(station_name)
        self._stations = load_stations()
        self._station_info = self._get_station_metadata(station_name)
        self._session = async_get_clientsession(hass)
        self._last_valid_data: dict[str, Any] | None = None

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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and parse current weather and forecast data from SMN Open Data."""
        try:
            current_raw, forecast_raw = await asyncio.gather(
                self._fetch_zip_text(URL_CURRENT_WEATHER, "Current Weather"),
                self._fetch_zip_text(URL_FORECAST, "Forecast"),
            )

            current_weather = self._parse_current_weather(current_raw)
            hourly_forecast, daily_forecast = self._parse_forecast(forecast_raw)

            data = {
                "current": current_weather,
                "hourly_forecast": hourly_forecast,
                "daily_forecast": daily_forecast,
                "station": self._station_info,
            }

            self._last_valid_data = data
            return data

        except Exception as err:
            if self._last_valid_data is not None:
                _LOGGER.warning(
                    "Error updating SMN data (%s), returning last valid cache: %s",
                    self.station_name,
                    err,
                )
                return self._last_valid_data
            raise UpdateFailed(f"Error communicating with SMN API: {err}") from err

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
                # Decode using cp1252 to preserve Spanish characters
                return zip_file.read(names[0]).decode("cp1252", errors="ignore")

        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout while downloading {label} from SMN") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"HTTP error downloading {label}: {err}") from err
        except zipfile.BadZipFile as err:
            raise UpdateFailed(f"Corrupted zip archive for {label}: {err}") from err

    def _find_matching_key(self, candidates: dict[str, Any]) -> str | None:
        """Find the matching key for the configured station in a dictionary."""
        target = self._norm_station

        # Check explicit alias
        if target in STATION_ALIASES:
            alias = normalize_name(STATION_ALIASES[target])
            if alias in candidates:
                return alias

        # 1. Exact match
        if target in candidates:
            return target

        # 2. Substring matching
        for key in candidates:
            if target in key or key in target:
                return key

        # 3. Token overlap matching
        target_tokens = set(target.split())
        best_match = None
        best_score = 0
        for key in candidates:
            common = target_tokens & set(key.split())
            if len(common) > best_score:
                best_score = len(common)
                best_match = key

        return best_match

    def _parse_current_weather(self, text: str) -> dict[str, Any]:
        """Parse tiepre text into current weather dictionary."""
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
                if wind_parts[-1].replace(".", "").isdigit():
                    wind_speed = float(wind_parts[-1])
                    wind_dir_str = " ".join(wind_parts[:-1])
                elif "calma" in wind_str.lower():
                    wind_speed = 0.0
                    wind_dir_str = "Calma"

            # Parse visibility
            vis_val = None
            vis_m = re.search(r"([\d\.]+)\s*km", vis_str, re.IGNORECASE)
            if vis_m:
                vis_val = float(vis_m.group(1))

            temp = (
                float(temp_str)
                if temp_str and temp_str != "No se calcula"
                else None
            )
            apparent_temp = (
                float(st_str) if st_str and st_str != "No se calcula" else None
            )
            humidity = (
                float(hum_str)
                if hum_str and hum_str.replace(".", "").isdigit()
                else None
            )
            pressure = (
                float(press_str)
                if press_str and press_str.replace(".", "").isdigit()
                else None
            )

            norm_k = normalize_name(st_name)
            stations_data[norm_k] = {
                "station_name": st_name,
                "date": date_str,
                "time": time_str,
                "description": desc,
                "condition": map_weather_condition(desc),
                "temperature": temp,
                "apparent_temperature": apparent_temp,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "wind_direction": wind_dir_str,
                "wind_bearing": wind_direction_to_bearing(wind_dir_str),
                "pressure": pressure,
                "visibility": vis_val,
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
        return {
            "station_name": self.station_name,
            "description": "N/D",
            "condition": ATTR_CONDITION_PARTLYCLOUDY,
            "temperature": None,
            "apparent_temperature": None,
            "humidity": None,
            "wind_speed": None,
            "wind_direction": None,
            "wind_bearing": None,
            "pressure": None,
            "visibility": None,
        }

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
            if i + 1 < len(lines) and lines[i + 1].startswith(" =="):
                if (
                    not line_str.startswith("=")
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
                dt = datetime(int(year), month, int(day), int(hour), 0)

                temp_val = float(temp)
                precip_val = float(precip)
                wind_spd_val = float(wind_spd)
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
                        "datetime": dt.isoformat(),
                        "temperature": temp_val,
                        "wind_bearing": wind_dir_val,
                        "wind_speed": wind_spd_val,
                        "precipitation": precip_val,
                        "condition": cond,
                    }
                )

        matched_key = self._find_matching_key(stations_forecast)
        hourly_forecast: list[dict[str, Any]] = []
        if matched_key and matched_key in stations_forecast:
            hourly_forecast = stations_forecast[matched_key]

        # Aggregate hourly forecast into daily forecast
        daily_groups: dict[str, list[dict[str, Any]]] = {}
        for slot in hourly_forecast:
            day_str = slot["datetime"][:10]
            if day_str not in daily_groups:
                daily_groups[day_str] = []
            daily_groups[day_str].append(slot)

        daily_forecast: list[dict[str, Any]] = []
        for day_str, slots in daily_groups.items():
            temps = [s["temperature"] for s in slots]
            precips = [s["precipitation"] for s in slots]
            winds = [s["wind_speed"] for s in slots]
            tot_precip = round(sum(precips), 1)

            if tot_precip > 15.0:
                cond = ATTR_CONDITION_POURING
            elif tot_precip > 0.0:
                cond = ATTR_CONDITION_RAINY
            elif max(winds) > 40.0:
                cond = ATTR_CONDITION_WINDY
            else:
                cond = ATTR_CONDITION_PARTLYCLOUDY

            daily_forecast.append(
                {
                    "datetime": f"{day_str}T12:00:00",
                    "temperature": round(max(temps), 1),
                    "templow": round(min(temps), 1),
                    "precipitation": tot_precip,
                    "wind_speed": round(sum(winds) / len(winds), 1),
                    "wind_bearing": slots[0]["wind_bearing"],
                    "condition": cond,
                }
            )

        return hourly_forecast, daily_forecast
