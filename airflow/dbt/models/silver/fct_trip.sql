-- One row per ride (UTC). Trip station ids are GBFS short_names; resolved to station_id
-- through dim_station. A month's file also holds rides that started in the previous month,
-- hence MERGE on ride_id (not partition overwrite).
{{ config(
    materialized='incremental',
    table_type='iceberg',
    incremental_strategy='merge',
    unique_key='ride_id',
    partitioned_by=['month(started_at)'],
    incremental_predicates=["target.started_at >= " ~ trip_month_start() ~ " - interval '2' month"],
    on_schema_change='append_new_columns'
) }}

with trips as (
    select * from {{ ref('stg_trips') }}
    {% if is_incremental() %}
    where {{ trip_months_filter('month') }}
    {% endif %}
),

-- One station_id per short_name (the most recently seen one), so the joins cannot fan out.
crosswalk as (
    select short_name, max_by(station_id, last_seen) as station_id
    from {{ ref('dim_station') }}
    where short_name is not null
    group by short_name
)

select
    t.ride_id,
    t.rideable_type,
    t.member_casual,
    cast(t.started_at as timestamp(6)) as started_at,
    cast(t.ended_at as timestamp(6)) as ended_at,
    date_diff('second', t.started_at, t.ended_at) / 60.0 as duration_min,
    t.start_short_name,
    s.station_id as start_station_id,
    t.start_station_name,
    t.end_short_name,
    e.station_id as end_station_id,
    t.end_station_name,
    t.start_lat,
    t.start_lng,
    t.end_lat,
    t.end_lng,
    t.start_short_name is null as is_dockless_start,
    t.end_short_name is null as is_dockless_end,
    date_diff('second', t.started_at, t.ended_at) < 60 as is_short,
    date_diff('second', t.started_at, t.ended_at) > 86400 as is_long,
    t.month as source_month,
    t.source_file
from trips as t
left join crosswalk as s on t.start_short_name = s.short_name
left join crosswalk as e on t.end_short_name = e.short_name
