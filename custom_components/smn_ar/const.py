"""Constants for the SMN Argentina integration."""
from __future__ import annotations

from datetime import timedelta, timezone
from typing import Final

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)

DOMAIN: Final = "smn_ar"
ATTRIBUTION: Final = "Servicio Meteorológico Nacional (SMN Argentina)"

# Argentina standard time (UTC-3)
ARGENTINA_TIMEZONE: Final = timezone(timedelta(hours=-3))

# Configuration keys
CONF_STATION: Final = "station"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_FALLBACK_ENTITY: Final = "fallback_weather_entity"
CONF_ENABLE_OPEN_METEO_FALLBACK: Final = "enable_open_meteo_fallback"
CONF_STALE_THRESHOLD_HOURS: Final = "stale_threshold_hours"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 1800  # 30 minutes in seconds
DEFAULT_TIMEOUT: Final = 20  # 20 seconds timeout for downloads
DEFAULT_ENABLE_OPEN_METEO_FALLBACK: Final = True
DEFAULT_STALE_THRESHOLD_HOURS: Final = 3

# Open Data Endpoints (SMN Argentina) and Open-Meteo fallback
URL_CURRENT_WEATHER: Final = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=tiepre"
URL_FORECAST: Final = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
URL_STATIONS: Final = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=estaciones"
URL_OPEN_METEO: Final = "https://api.open-meteo.com/v1/forecast"

# Data sources and apparent temperature sources
SOURCE_SMN: Final = "smn"
SOURCE_FALLBACK_ENTITY: Final = "fallback_entity"
SOURCE_OPEN_METEO: Final = "open_meteo"
SOURCE_CACHE: Final = "cache"

ST_SOURCE_SMN: Final = "smn"
ST_SOURCE_TEMPERATURE_FALLBACK: Final = "temperature_fallback"
ST_SOURCE_FALLBACK_ENTITY: Final = "fallback_entity"
ST_SOURCE_OPEN_METEO: Final = "open_meteo"

# Spanish Month Abbreviations mapping for forecast date parsing
MONTHS_MAP: Final = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}

# Full Spanish month names for tiepre report date parsing
SPANISH_MONTHS_FULL: Final[dict[str, int]] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# Weather condition text mappings (SMN Spanish descriptions -> HA conditions)
# Specific/compound phrases MUST appear before shorter substrings
CONDITION_TEXT_MAP: Final = {
    "tormentas aisladas": ATTR_CONDITION_LIGHTNING_RAINY,
    "tormentas fuertes": ATTR_CONDITION_LIGHTNING_RAINY,
    "tormenta": ATTR_CONDITION_LIGHTNING_RAINY,
    "chaparrones": ATTR_CONDITION_POURING,
    "chaparron": ATTR_CONDITION_POURING,
    "lluvias fuertes": ATTR_CONDITION_POURING,
    "lluvias aisladas": ATTR_CONDITION_RAINY,
    "lluvias y nevadas": ATTR_CONDITION_SNOWY_RAINY,
    "llovizna": ATTR_CONDITION_RAINY,
    "lluvias": ATTR_CONDITION_RAINY,
    "lluvia": ATTR_CONDITION_RAINY,
    "niebla helada": ATTR_CONDITION_FOG,
    "niebla": ATTR_CONDITION_FOG,
    "neblina": ATTR_CONDITION_FOG,
    "humo": ATTR_CONDITION_FOG,
    "nevadas": ATTR_CONDITION_SNOWY,
    "nevada": ATTR_CONDITION_SNOWY,
    "nieve": ATTR_CONDITION_SNOWY,
    "ventoso": ATTR_CONDITION_WINDY,
    "parcialmente nublado": ATTR_CONDITION_PARTLYCLOUDY,
    "algo nublado": ATTR_CONDITION_PARTLYCLOUDY,
    "ligeramente nublado": ATTR_CONDITION_PARTLYCLOUDY,
    "mayormente nublado": ATTR_CONDITION_CLOUDY,
    "nublado": ATTR_CONDITION_CLOUDY,
    "cubierto": ATTR_CONDITION_CLOUDY,
    "despejado": ATTR_CONDITION_SUNNY,
    "soleado": ATTR_CONDITION_SUNNY,
}

# Home Assistant condition -> Spanish description for fallback weather entities
HA_CONDITION_DESCRIPTION_ES: Final[dict[str, str]] = {
    ATTR_CONDITION_SUNNY: "Despejado",
    ATTR_CONDITION_CLEAR_NIGHT: "Despejado",
    ATTR_CONDITION_PARTLYCLOUDY: "Parcialmente nublado",
    ATTR_CONDITION_CLOUDY: "Nublado",
    ATTR_CONDITION_RAINY: "Lluvia",
    ATTR_CONDITION_POURING: "Lluvia intensa",
    ATTR_CONDITION_LIGHTNING_RAINY: "Tormenta",
    ATTR_CONDITION_LIGHTNING: "Tormenta eléctrica",
    ATTR_CONDITION_SNOWY: "Nieve",
    ATTR_CONDITION_SNOWY_RAINY: "Aguanieve",
    ATTR_CONDITION_FOG: "Niebla",
    ATTR_CONDITION_WINDY: "Ventoso",
    ATTR_CONDITION_WINDY_VARIANT: "Ventoso y nublado",
    ATTR_CONDITION_HAIL: "Granizo",
    ATTR_CONDITION_EXCEPTIONAL: "Condición excepcional",
}

# Open-Meteo WMO weather interpretation codes -> Home Assistant conditions
WMO_CODE_CONDITION_MAP: Final[dict[int, str]] = {
    0: ATTR_CONDITION_SUNNY,
    1: ATTR_CONDITION_PARTLYCLOUDY,
    2: ATTR_CONDITION_PARTLYCLOUDY,
    3: ATTR_CONDITION_CLOUDY,
    45: ATTR_CONDITION_FOG,
    48: ATTR_CONDITION_FOG,
    51: ATTR_CONDITION_RAINY,
    53: ATTR_CONDITION_RAINY,
    55: ATTR_CONDITION_RAINY,
    56: ATTR_CONDITION_SNOWY_RAINY,
    57: ATTR_CONDITION_SNOWY_RAINY,
    61: ATTR_CONDITION_RAINY,
    63: ATTR_CONDITION_RAINY,
    65: ATTR_CONDITION_POURING,
    66: ATTR_CONDITION_SNOWY_RAINY,
    67: ATTR_CONDITION_SNOWY_RAINY,
    71: ATTR_CONDITION_SNOWY,
    73: ATTR_CONDITION_SNOWY,
    75: ATTR_CONDITION_SNOWY,
    77: ATTR_CONDITION_SNOWY,
    80: ATTR_CONDITION_RAINY,
    81: ATTR_CONDITION_RAINY,
    82: ATTR_CONDITION_POURING,
    85: ATTR_CONDITION_SNOWY,
    86: ATTR_CONDITION_SNOWY,
    95: ATTR_CONDITION_LIGHTNING_RAINY,
    96: ATTR_CONDITION_LIGHTNING_RAINY,
    99: ATTR_CONDITION_LIGHTNING_RAINY,
}

# Open-Meteo WMO weather interpretation codes -> Spanish descriptions
WMO_CODE_DESCRIPTION_MAP: Final[dict[int, str]] = {
    0: "Despejado",
    1: "Mayormente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con cencellada",
    51: "Llovizna débil",
    53: "Llovizna moderada",
    55: "Llovizna intensa",
    56: "Llovizna helada débil",
    57: "Llovizna helada intensa",
    61: "Lluvia débil",
    63: "Lluvia moderada",
    65: "Lluvia fuerte",
    66: "Lluvia helada débil",
    67: "Lluvia helada intensa",
    71: "Nevada débil",
    73: "Nevada moderada",
    75: "Nevada intensa",
    77: "Granos de nieve",
    80: "Chaparrones débiles",
    81: "Chaparrones moderados",
    82: "Chaparrones intensos",
    85: "Chaparrones de nieve débiles",
    86: "Chaparrones de nieve intensos",
    95: "Tormenta",
    96: "Tormenta con granizo débil",
    99: "Tormenta con granizo fuerte",
}

# Stopwords ignored during station name token matching
STATION_STOPWORDS: Final[frozenset[str]] = frozenset(
    {"DE", "DEL", "LA", "LAS", "EL", "LOS", "Y"}
)

# Station name aliases between estaciones_smn.txt, tiepre, and pron5d
STATION_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "AEROPARQUE": ("AEROPARQUE BUENOS AIRES",),
    "BUENOS AIRES OBSERVATORIO": ("BUENOS AIRES",),
    "ESC AVIACION MILITAR": ("ESCUELA DE AVIACION MILITAR",),
    "ESCUELA DE AVIACION MILITAR": ("ESC AVIACION MILITAR",),
    "ESCUELA DE AVIACION MILITAR AE": (
        "ESC AVIACION MILITAR",
        "ESCUELA DE AVIACION MILITAR",
    ),
    "JUJUY U N": ("JUJUY",),
    "LA QUIACA OBSERVATORIO": ("LA QUIACA OBS", "LA QUIACA"),
    "PCIA ROQUE SAENZ PENA": ("PRESIDENCIA ROQUE SAENZ PENA",),
    "PILAR OBSERVATORIO": ("PILAR OBS",),
    "PRESIDENCIA ROQUE SAENZ PENA": ("PCIA ROQUE SAENZ PENA",),
    "PRESIDENCIA ROQUE SAENZ PENA A": (
        "PCIA ROQUE SAENZ PENA",
        "PRESIDENCIA ROQUE SAENZ PENA",
    ),
    "SANTA FE SAUCE VIEJO": ("SANTA FE", "SAUCE VIEJO"),
    "SAUCE VIEJO": ("SANTA FE",),
    "VILLA DE MARIA DEL RIO SECO": ("VILLA MARIA DEL RIO SECO",),
}
