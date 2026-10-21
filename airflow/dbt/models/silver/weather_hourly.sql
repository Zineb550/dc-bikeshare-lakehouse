-- One row per hour (UTC) for Washington, DC. Each daily fetch covers 8 days, so an hour is
-- fetched several times; the latest fetch wins. Hours after the fetch time are forecasts
-- (is_forecast) and get replaced by later fetches.
{{ config(
    materialized='incremental',
    table_type='iceberg',
    incremental_strategy='merge',
    unique_key='hour_ts',
    update_condition='src.fetched_at >= target.fetched_at',
    partitioned_by=['month(hour_ts)'],
    on_schema_change='append_new_columns'
) }}

with fetched as (
    select * from {{ ref('stg_weather__hourly') }}
    {% if is_incremental() %}
    where fetch_date >= cast({{ window_start() }} as varchar)
      and fetch_date < cast({{ window_end() }} as varchar)
    {% endif %}
),

ranked as (
    select
        *,
        row_number() over (partition by hour_ts order by fetched_at desc) as fetch_rank
    from fetched
)

select
    cast(hour_ts as timestamp(6)) as hour_ts,
    temperature_c,
    precipitation_mm,
    rain_mm,
    snowfall_cm,
    wind_speed_kmh,
    weather_code,
    fetch_mode,
    cast(fetched_at as timestamp(6)) as fetched_at,
    hour_ts > fetched_at as is_forecast
from ranked
where fetch_rank = 1
