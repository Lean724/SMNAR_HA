<p align="center">
  <img src="images/logo.png" alt="Servicio Meteorológico Nacional" width="220">
</p>

# Servicio Meteorológico Nacional (SMN Argentina) para Home Assistant (Integración independiente)

Integración de **Home Assistant para el clima de Argentina**. Consulta las condiciones actuales y el pronóstico meteorológico del **Servicio Meteorológico Nacional (SMN)** mediante sus datos abiertos, con selección automática de estaciones meteorológicas cercanas.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/Lean724/SMNAR_HA?style=for-the-badge)](https://github.com/Lean724/SMNAR_HA/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Validate with hassfest](https://img.shields.io/github/actions/workflow/status/Lean724/SMNAR_HA/hassfest.yml?label=Hassfest&style=for-the-badge)](https://github.com/Lean724/SMNAR_HA/actions)
[![HACS Action](https://img.shields.io/github/actions/workflow/status/Lean724/SMNAR_HA/hacs.yml?label=HACS%20Action&style=for-the-badge)](https://github.com/Lean724/SMNAR_HA/actions)

---

## Características

* **Entidad de Clima (`weather`)**: Cumple con los estándares actuales de Home Assistant con soporte de pronóstico diario y horario (`async_forecast_daily` y `async_forecast_hourly`) e icono nocturno (`clear-night`) cuando está despejado de noche.
* **Condiciones en Tiempo Real**:
  * Temperatura actual (°C).
  * Sensación térmica (°C), con respaldo automático a la temperatura actual cuando el SMN informa `"No se calcula"` en temperaturas templadas.
  * Humedad relativa (%).
  * Presión atmosférica al nivel de la estación (hPa).
  * Viento (velocidad en km/h, dirección y grados).
  * Visibilidad (km).
  * Condición meteorológica oficial con icono dinámico.
* **Continuidad Nocturna y Respaldo Híbrido (Anti-Baches)**:
  * Detecta automáticamente cuándo el reporte de la estación SMN supera el umbral de antigüedad configurable (por defecto `3` horas, frecuente en estaciones que cierran de noche) o falta en `tiepre`.
  * **Prioridad 1 (SMN vigente)**: Usa los datos oficiales abiertos del SMN.
  * **Prioridad 2 (Entidad `weather.*` opcional)**: Si configurás otra entidad climática en Home Assistant (Google Weather, Met.no, Weather.com, etc.), cubre el bache convirtiendo unidades automáticamente.
  * **Prioridad 3 (Open-Meteo automático)**: Si no hay entidad de respaldo disponible y está habilitado (activo por defecto), consulta Open-Meteo sin necesidad de API keys usando presión al nivel de la superficie (`surface_pressure`) para mantener coherencia con el SMN.
* **Pronóstico Extendido a 5 Días**:
  * Pronóstico horario (cada 3 horas): temperatura, precipitación acumulada (mm), viento y condición.
  * Pronóstico diario: temperaturas máximas y mínimas estimadas agrupadas por día local de Argentina (`UTC-3`), precipitación total estimada y condición predominante.
  * Enriquecimiento de iconos del cielo en pronóstico: cuando `pron5d` no reporta precipitaciones ni vientos fuertes, completa la condición del cielo (despejado, nublado, etc.) usando la entidad de respaldo (`B1`) o Open-Meteo (`B2`), conservando siempre las temperaturas, vientos y precipitaciones del SMN.
* **Cobertura Nacional**: Más de 118 estaciones meteorológicas oficiales en todas las provincias de Argentina y bases antárticas.
* **Detección Automática de Cercanía**: Calcula por geolocalización (fórmula Haversine) la estación oficial más cercana a las coordenadas de Home Assistant.
* **Sensores Individuales**: 8 entidades tipo `sensor` independientes para Temperatura, Sensación Térmica, Humedad, Presión, Velocidad del Viento, Dirección del Viento, Visibilidad y Condición Actual para tableros y automatizaciones, con atributos de diagnóstico (`fuente_datos`, `respaldo_activo`, `sensacion_termica_fuente`).
* **Conexión Directa y Confiable**: Consume los datos oficiales abiertos del SMN sin necesidad de claves de acceso ni scraping.
* **Configuración Gráfica y Multilingüe**: Config Flow y Options Flow en 10 idiomas para configurar estación, intervalo, umbral de antigüedad y opciones de respaldo.

---

## Instalación

### Método 1: Mediante HACS (Recomendado)

1. Abre **Home Assistant** y entra en **HACS**.
2. En la sección **Integraciones**, abre el menú de tres puntos (arriba a la derecha) y selecciona **Repositorios personalizados**.
3. Ingresa los siguientes datos:
   * **Repositorio**: `https://github.com/Lean724/SMNAR_HA`
   * **Tipo**: `Integración`
4. Haz clic en **Añadir**.
5. Busca **Servicio Meteorológico Nacional (SMN Argentina)** y pulsa en **Descargar**.
6. Reinicia Home Assistant.

### Método 2: Instalación Manual

1. Descarga el repositorio como archivo ZIP.
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

## Configuración

1. En Home Assistant, dirígete a **Ajustes** -> **Dispositivos y servicios** -> **Añadir integración**.
2. Busca **Servicio Meteorológico Nacional (Argentina)**.
3. El asistente preseleccionará la estación más cercana según las coordenadas de tu hogar. Puedes confirmarla o seleccionar cualquier otra estación de la lista.
4. Define el intervalo de actualización deseado (por defecto: 1800 segundos / 30 minutos).
5. *(Opcional)* Selecciona una entidad climática de respaldo en Home Assistant (`weather.*`), ajusta el umbral de antigüedad de reportes SMN (por defecto: `3` horas) y decide si mantener activo el respaldo automático con Open-Meteo.
6. Confirma para crear el dispositivo con su entidad de clima y sensores asociados.

> Para cambiar la estación, el intervalo o las opciones de respaldo más adelante, accede a **Ajustes** -> **Dispositivos y servicios** -> **SMN Argentina** -> **Configurar**.

---

## Entidades Generadas

| Plataforma | Identificador | Descripción |
| :--- | :--- | :--- |
| `weather` | `weather.smn_<estacion>` | Entidad de clima principal con pronóstico horario y diario |
| `sensor` | `sensor.smn_<estacion>_temperatura` | Temperatura ambiente (°C) |
| `sensor` | `sensor.smn_<estacion>_sensacion_termica` | Sensación térmica (°C) |
| `sensor` | `sensor.smn_<estacion>_humedad` | Humedad relativa (%) |
| `sensor` | `sensor.smn_<estacion>_presion_atmosferica` | Presión atmosférica (hPa) |
| `sensor` | `sensor.smn_<estacion>_velocidad_del_viento` | Velocidad del viento (km/h) |
| `sensor` | `sensor.smn_<estacion>_direccion_del_viento` | Dirección cardinal del viento (ej. Noreste) |
| `sensor` | `sensor.smn_<estacion>_visibilidad` | Visibilidad (km) |
| `sensor` | `sensor.smn_<estacion>_condicion_actual` | Descripción oficial del estado del cielo |

---

## Ejemplos en el Tablero (Lovelace)

### Tarjeta de Clima Estándar (Pronóstico Diario)

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

## Fuente de Datos y Atribución

Los datos meteorológicos son provistos por el **Servicio Meteorológico Nacional** de la República Argentina a través de su plataforma de datos abiertos. Cuando una estación del SMN presenta demoras o interrupciones nocturnas y el respaldo automático está habilitado sin entidad local asignada, se utilizan datos abiertos de [Open-Meteo](https://open-meteo.com/) ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)).

Este desarrollo es una integración comunitaria de código abierto para Home Assistant y no posee afiliación oficial con el Servicio Meteorológico Nacional.

**Logo del Servicio Meteorológico Nacional:** “SMN Logo Alta.png”, procedente del sitio web de Casa Rosada (Presidencia de la Nación Argentina), disponible en [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:SMN_Logo_Alta.png), bajo licencia [Creative Commons Atribución 2.5 Argentina (CC BY 2.5 AR)](https://creativecommons.org/licenses/by/2.5/ar/). El uso de la imagen no implica respaldo ni afiliación oficial con este proyecto.
---

## Licencia

Este proyecto se distribuye bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más información.
