-- One row per station per status document (15-minute slot). Times in UTC.
-- slot_ts comes from the S3 key (slot=HHMM), the scheduled slot, so it is deterministic.
with documents as (
    select
        dt,
        regexp_extract("$path", 'slot=(\d{4})', 1) as slot_hhmm,
        last_updated,
        data.stations as stations
    from {{ source('bronze', 'gbfs_station_status') }}
)

select
    d.dt,
    cast(date_parse(d.dt || ' ' || d.slot_hhmm, '%Y-%m-%d %H%i') as timestamp) as slot_ts,
    cast(from_unixtime(d.last_updated) as timestamp) as feed_updated_at,
    s.station_id,
    s.num_bikes_available as bikes_available,
    s.num_ebikes_available as ebikes_available,
    s.num_bikes_disabled as bikes_disabled,
    s.num_docks_available as docks_available,
    s.num_docks_disabled as docks_disabled,
    s.is_installed = 1 as is_installed,
    s.is_renting = 1 as is_renting,
    s.is_returning = 1 as is_returning,
    cast(from_unixtime(s.last_reported) as timestamp) as last_reported_at
from documents as d
-- Athena unnests an array of structs into one struct column; fields are read with s.<field>.
cross join unnest(d.stations) as t (s)
