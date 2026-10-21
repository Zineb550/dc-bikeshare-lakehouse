-- Staging views use plain timestamp: Athena views (Hive metadata) reject timestamp(6).
-- One row per hour per fetch. Fetch windows overlap on purpose (8 days per daily run);
-- weather_hourly keeps the latest fetch for each hour. Open-Meteo is requested in GMT.
select
    w.fetch_date,
    w.ingest_meta.mode as fetch_mode,
    cast(replace(substr(w.ingest_meta.fetched_at, 1, 19), 'T', ' ') as timestamp) as fetched_at,
    cast(date_parse(h.time_str, '%Y-%m-%dT%H:%i') as timestamp) as hour_ts,
    h.temperature_c,
    h.precipitation_mm,
    h.rain_mm,
    h.snowfall_cm,
    h.wind_speed_kmh,
    h.weather_code
from {{ source('bronze', 'weather_raw') }} as w
cross join unnest(
    w.hourly.time,
    w.hourly.temperature_2m,
    w.hourly.precipitation,
    w.hourly.rain,
    w.hourly.snowfall,
    w.hourly.wind_speed_10m,
    w.hourly.weather_code
) as h (
    time_str,
    temperature_c,
    precipitation_mm,
    rain_mm,
    snowfall_cm,
    wind_speed_kmh,
    weather_code
)
