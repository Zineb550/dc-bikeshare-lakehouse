-- One row per station per information document (hourly). short_name is the id used in trip files.
with documents as (
    select
        dt,
        regexp_extract("$path", 'slot=(\d{4})', 1) as slot_hhmm,
        data.stations as stations
    from {{ source('bronze', 'gbfs_station_information') }}
)

select
    d.dt,
    cast(date_parse(d.dt || ' ' || d.slot_hhmm, '%Y-%m-%d %H%i') as timestamp) as slot_ts,
    s.station_id,
    s.short_name,
    s.name as station_name,
    s.lat,
    s.lon,
    s.capacity,
    s.region_id
from documents as d
-- Athena unnests an array of structs into one struct column; fields are read with s.<field>.
cross join unnest(d.stations) as t (s)
