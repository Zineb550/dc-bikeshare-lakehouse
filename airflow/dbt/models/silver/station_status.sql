-- One row per station per 15-minute slot (UTC), with availability flags and the previous
-- slot's values (used by truck-visit inference in gold). Iceberg MERGE on (station_id, slot_ts).
{{ config(
    materialized='incremental',
    table_type='iceberg',
    incremental_strategy='merge',
    unique_key=['station_id', 'slot_ts'],
    partitioned_by=['day(slot_ts)'],
    incremental_predicates=["target.slot_ts >= " ~ window_start() ~ " - interval '1' day"],
    on_schema_change='append_new_columns'
) }}

with snapshots as (
    select * from {{ ref('stg_gbfs__station_status') }}
    {% if is_incremental() %}
    -- one extra day before the window so the first slot still gets its previous slot
    where dt >= cast({{ window_start() }} - interval '1' day as varchar)
      and dt < cast({{ window_end() }} as varchar)
    {% endif %}
),

with_prev as (
    select
        *,
        lag(slot_ts) over (partition by station_id order by slot_ts) as prev_slot_ts,
        lag(bikes_available) over (partition by station_id order by slot_ts) as prev_bikes_available,
        lag(bikes_disabled) over (partition by station_id order by slot_ts) as prev_bikes_disabled,
        lag(docks_available) over (partition by station_id order by slot_ts) as prev_docks_available,
        lag(is_installed) over (partition by station_id order by slot_ts) as prev_is_installed,
        lag(is_renting) over (partition by station_id order by slot_ts) as prev_is_renting
    from snapshots
)

select
    station_id,
    cast(slot_ts as timestamp(6)) as slot_ts,
    bikes_available,
    ebikes_available,
    bikes_disabled,
    docks_available,
    docks_disabled,
    is_installed,
    is_renting,
    is_returning,
    cast(last_reported_at as timestamp(6)) as last_reported_at,
    is_renting and bikes_available = 0 as is_empty,
    is_returning and docks_available = 0 as is_full,
    coalesce(last_reported_at < slot_ts - interval '1' hour, true) as is_stale,
    case
        when bikes_available + docks_available > 0
            then cast(bikes_available as double) / (bikes_available + docks_available)
    end as fill_ratio,
    cast(prev_slot_ts as timestamp(6)) as prev_slot_ts,
    prev_bikes_available,
    prev_bikes_disabled,
    prev_docks_available,
    prev_is_installed,
    prev_is_renting,
    cast(feed_updated_at as timestamp(6)) as feed_updated_at
from with_prev
{% if is_incremental() %}
where slot_ts >= {{ window_start() }}
{% endif %}
