-- One row per GBFS station (type 1: latest attributes win). Rebuilt each run from the
-- hourly station_information documents, which are small.
{{ config(materialized='table', table_type='iceberg') }}

with info as (
    select * from {{ ref('stg_gbfs__station_information') }}
),

latest as (
    select
        station_id,
        max_by(short_name, slot_ts) as short_name,
        max_by(station_name, slot_ts) as station_name,
        max_by(lat, slot_ts) as lat,
        max_by(lon, slot_ts) as lon,
        max_by(capacity, slot_ts) as capacity,
        max_by(region_id, slot_ts) as region_id,
        min(slot_ts) as first_seen,
        max(slot_ts) as last_seen
    from info
    group by station_id
)

select
    l.station_id,
    l.short_name,
    l.station_name,
    l.lat,
    l.lon,
    l.capacity,
    l.region_id,
    coalesce(r.region_name, 'Unknown') as region_name,
    cast(l.first_seen as timestamp(6)) as first_seen,
    cast(l.last_seen as timestamp(6)) as last_seen
from latest as l
left join {{ ref('seed_regions') }} as r on l.region_id = r.region_id
