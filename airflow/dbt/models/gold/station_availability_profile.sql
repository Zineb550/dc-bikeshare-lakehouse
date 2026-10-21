-- Q1 Availability: where and when riders find no bike (empty) or no dock (full).
-- Grain: station x day type x local hour. Stale snapshots and stations not installed or
-- not renting are excluded; cells with fewer than 8 snapshots are hidden (too thin).
with snapshots as (
    select
        station_id,
        {{ to_local('slot_ts') }} as slot_local,
        is_empty,
        is_full,
        fill_ratio
    from {{ ref('station_status') }}
    where not is_stale
      and is_installed
      and is_renting
),

profile as (
    select
        station_id,
        {{ day_type('slot_local') }} as day_type,
        hour(slot_local) as local_hour,
        count(*) as n_snapshots,
        avg(case when is_empty then 1.0 else 0.0 end) as pct_empty,
        avg(case when is_full then 1.0 else 0.0 end) as pct_full,
        avg(fill_ratio) as avg_fill
    from snapshots
    group by 1, 2, 3
    having count(*) >= 8
)

select
    p.station_id,
    s.station_name,
    s.region_name,
    s.lat,
    s.lon,
    s.capacity,
    p.day_type,
    p.local_hour,
    p.n_snapshots,
    p.pct_empty,
    p.pct_full,
    p.avg_fill
from profile as p
join {{ ref('dim_station') }} as s on p.station_id = s.station_id
