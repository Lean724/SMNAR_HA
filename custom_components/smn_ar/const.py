"""Constants for the SMN Argentina integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)

DOMAIN: Final = "smn_ar"
ATTRIBUTION: Final = "Servicio Meteorológico Nacional (SMN Argentina)"

# Configuration keys
CONF_STATION: Final = "station"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 1800  # 30 minutes in seconds
DEFAULT_TIMEOUT: Final = 20  # 20 seconds timeout for downloads

# Open Data Endpoints (SMN Argentina)
URL_CURRENT_WEATHER: Final = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=tiepre"
URL_FORECAST: Final = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=pron5d"
URL_STATIONS: Final = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=estaciones"

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

# Station name aliases between estaciones_smn.txt, tiepre, and pron5d
STATION_ALIASES: Final = {
    "SAUCE VIEJO": "SANTA FE",
    "SANTA FE SAUCE VIEJO": "SANTA FE",
    "PCIA ROQUE SAENZ PENA": "PRESIDENCIA ROQUE SAENZ PENA",
    "ESC AVIACION MILITAR": "ESCUELA DE AVIACION MILITAR",
    "AEROPARQUE": "AEROPARQUE BUENOS AIRES",
}
