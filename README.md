# 🇦🇷 Servicio Meteorológico Nacional (SMN Argentina) para Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/Lean724/SMNAR_HA?style=for-the-badge)](https://github.com/Lean724/SMNAR_HA/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Validate with hassfest](https://img.shields.io/github/actions/workflow/status/Lean724/SMNAR_HA/hassfest.yml?label=Hassfest&style=for-the-badge)](https://github.com/Lean724/SMNAR_HA/actions)
[![HACS Action](https://img.shields.io/github/actions/workflow/status/Lean724/SMNAR_HA/hacs.yml?label=HACS%20Action&style=for-the-badge)](https://github.com/Lean724/SMNAR_HA/actions)

Integración personalizada para **Home Assistant** que provee el estado del tiempo actual y pronóstico extendido a 5 días directamente desde los servicios oficiales del **Servicio Meteorológico Nacional (SMN)** de la República Argentina.

Compatible e instalable a través de **HACS (Home Assistant Community Store)**.

---

## ✨ Características Principales

* 🌦️ **Entidad de Clima (`weather`) Moderna**: Implementa las especificaciones modernas de Home Assistant con soporte de pronóstico diario y horario (`async_forecast_daily` y `async_forecast_hourly`).
* 🌡️ **Condiciones Actuales en Tiempo Real**:
  * Temperatura actual (°C).
  * Sensación Térmica / ST (°C).
  * Humedad relativa (%).
  * Presión atmosférica al nivel de la estación (hPa).
  * Viento (velocidad en km/h, dirección y grados).
  * Visibilidad (km).
  * Condición meteorológica oficial con icono dinámico.
* 📅 **Pronóstico Extendido a 5 Días**:
  * **Pronóstico Horario (cada 3 horas)**: Temperatura, probabilidad/milímetros de precipitación y viento.
  * **Pronóstico Diario**: Temperaturas máximas y mínimas estimadas, acumulación diaria de lluvia (mm) y condición predominante.
* 📍 **Más de 118 Estaciones Oficiales**: Cobertura en todas las provincias de Argentina y bases antárticas.
* 🧭 **Detección Automática de Cercanía**: Calcula por geolocalización (fórmula Haversine) la estación meteorológica del SMN más cercana a tu hogar en Home Assistant.
* 📊 **8 Sensores Individuales Dedicados**: Entidades tipo `sensor` independientes para Temperatura, Sensación Térmica, Humedad, Presión, Viento y Visibilidad para su uso en medidores tipo Gauge, gráficos de histórico y automatizaciones.
* 🛡️ **Conexión Abierta y Estable**: Consume los datos oficiales de datos abiertos del SMN sin requerir tokens efímeros ni sufrir bloqueos por Cloudflare.
* ⚙️ **Configuración 100% Gráfica (UI)**: Config Flow y Options Flow para instalar y modificar la estación o intervalo de actualización en cualquier momento.

---

## 📦 Instalación

### Método 1: Mediante HACS (Recomendado)

1. Abre **Home Assistant** y dirígete a **HACS**.
2. En la sección **Integraciones**, haz clic en el menú de los 3 puntos (esquina superior derecha) y selecciona **Repositorios personalizados** (*Custom repositories*).
3. Agrega la siguiente información:
   * **Repositorio**: `https://github.com/Lean724/SMNAR_HA`
   * **Tipo**: `Integración` (Integration)
4. Haz clic en **Añadir**.
5. Busca **Servicio Meteorológico Nacional (SMN Argentina)** en la lista de HACS y selecciona **Descargar**.
6. Reinicia Home Assistant.

### Método 2: Instalación Manual

1. Descarga el archivo comprimido del repositorio o clónalo.
2. Copia la carpeta `custom_components/smn_ar` dentro del directorio `custom_components/` de tu instalación de Home Assistant:
   ```text
   config/
   └── custom_components/
       └── smn_ar/
           ├── __init__.py
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── manifest.json
           ├── sensor.py
           ├── stations.json
           ├── strings.json
           ├── weather.py
           └── translations/
   ```
3. Reinicia Home Assistant.

---

## ⚙️ Configuración

Una vez instalada la integración:

1. Ve a **Ajustes** -> **Dispositivos y servicios** -> **Añadir integración**.
2. Busca **Servicio Meteorológico Nacional (Argentina)**.
3. El sistema sugerirá automáticamente la estación oficial más cercana a las coordenadas de tu hogar. Puedes confirmarla o seleccionar cualquier otra estación del listado desplegable.
4. Establece el intervalo de actualización deseado (por defecto: 1800 segundos / 30 minutos).
5. ¡Listo! Se creará el dispositivo con la entidad de clima y todos los sensores asociados.

> [!TIP]
> Si deseas cambiar de estación meteorológica o cambiar la frecuencia de refresco más adelante, puedes hacerlo desde **Ajustes** -> **Dispositivos y servicios** -> **SMN Argentina** -> **Configurar**.

---

## 📊 Entidades Generadas

Para cada estación configurada se crean automáticamente las siguientes entidades:

| Plataforma | Nombre de Entidad | Descripción |
| :--- | :--- | :--- |
| `weather` | `weather.smn_<estacion>` | Entidad de clima con pronóstico horario y diario |
| `sensor` | `sensor.smn_<estacion>_temperatura` | Temperatura ambiente en °C |
| `sensor` | `sensor.smn_<estacion>_sensacion_termica` | Sensación térmica en °C |
| `sensor` | `sensor.smn_<estacion>_humedad` | Humedad relativa en % |
| `sensor` | `sensor.smn_<estacion>_presion_atmosferica` | Presión atmosférica en hPa |
| `sensor` | `sensor.smn_<estacion>_velocidad_del_viento` | Velocidad del viento en km/h |
| `sensor` | `sensor.smn_<estacion>_direccion_del_viento` | Dirección cardinal del viento (ej. Noreste) |
| `sensor` | `sensor.smn_<estacion>_visibilidad` | Visibilidad en km |
| `sensor` | `sensor.smn_<estacion>_condicion_actual` | Texto oficial del SMN sobre el estado del cielo |

---

## 🎨 Ejemplos en el Tablero (Lovelace)

### Tarjeta de Pronóstico del Tiempo Estándar

```yaml
type: weather-forecast
entity: weather.smn_aeroparque_aero
forecast_type: daily
name: SMN Aeroparque
```

### Tarjeta con Pronóstico Horario

```yaml
type: weather-forecast
entity: weather.smn_aeroparque_aero
forecast_type: hourly
name: SMN Pronóstico por Horas
```

---

## 🏛️ Fuente de Datos y Atribución

Los datos meteorológicos son provistos por el **Servicio Meteorológico Nacional** de la República Argentina a través de su plataforma oficial de datos abiertos.

Este proyecto es una integración comunitaria de código abierto sin fines de lucro desarrollada para Home Assistant y no cuenta con afiliación oficial ni dependencia gubernamental del SMN.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
