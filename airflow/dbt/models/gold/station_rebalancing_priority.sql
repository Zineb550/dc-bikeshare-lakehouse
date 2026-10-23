-- Q3 Rebalancing priority: which stations lose the most rides to being empty or full.
-- Grain: station. Availability from the trailing 28 days of snapshots; demand ("typical
-- departures / arrivals per hour") from trip history. Joined on station x day type x local hour:
--   missed_pickups = sum(pct_empty x typical departures), missed_returns = sum(pct_full x typical arrivals)
-- scaled to a week (5 weekdays + 2 weekend days). Demand observed while a station was empty is
-- itself undercounted, so this is a lower bound.
with bounds as (
    select max(slot_ts) - interval '28' day as since from {{ ref('station_status') }}
),

availability as (
    select
        station_id,
        {{ day_type(to_local('slot_ts')) }} as day_type,
        hour({{ to_local('slot_ts') }}) as local_hour,
        avg(case when is_empty then 1.0 else 0.0 end) as pct_empty,
        avg(case when is_full then 1.0 else 0.0 end) as pct_full
    from {{ ref('station_status') }}
    where slot_ts >= (select since from bounds)
      and not is_stale and is_installed and is_renting
    group by 1, 2, 3
    having count(*) >= 8
),

trips as (
    select
        start_station_id,
        end_station_id,
        is_dockless_start,
        is_dockless_end,
        {{ to_local('started_at') }} as start_local,
        {{ to_local('ended_at') }} as end_local
    from {{ ref('fct_trip') }}
    where not is_short and not is_long
      and source_month = (select max(source_month) from {{ ref('fct_trip') }})
),

days_observed as (
    select {{ day_type('start_local') }} as day_type, count(distinct date(start_local)) as n_days
    from trips
    group by 1
),

departures as (
    select start_station_id as station_id, {{ day_type('start_local') }} as day_type,
           hour(start_local) as local_hour, count(*) as n
    from trips
    where not is_dockless_start and start_station_id is not null
    group by 1, 2, 3
),

arrivals as (
    select end_station_id as station_id, {{ day_type('end_local') }} as day_type,
           hour(end_local) as local_hour, count(*) as n
    from trips
    where not is_dockless_end and end_station_id is not null
    group by 1, 2, 3
),

cells as (
    select
        a.station_id,
        a.day_type,
        a.pct_empty * coalesce(cast(d.n as double) / o.n_days, 0) as missed_pickups_per_day,
        a.pct_full * coalesce(cast(r.n as double) / o.n_days, 0) as missed_returns_per_day
    from availability as a
    join days_observed as o on a.day_type = o.day_type
    left join departures as d
        on a.station_id = d.station_id and a.day_type = d.day_type and a.local_hour = d.local_hour
    left join arrivals as r
        on a.station_id = r.station_id and a.day_type = r.day_type and a.local_hour = r.local_hour
),

per_station as (
    select
        station_id,
        sum(missed_pickups_per_day * case when day_type = 'weekday' then 5 else 2 end)
            as missed_pickups_per_week,
        sum(missed_returns_per_day * case when day_type = 'weekday' then 5 else 2 end)
            as missed_returns_per_week
    from cells
    group by 1
)

select
    p.station_id,
    s.station_name,
    s.region_name,
    s.lat,
    s.lon,
    s.capacity,
    p.missed_pickups_per_week,
    p.missed_returns_per_week,
    p.missed_pickups_per_week + p.missed_returns_per_week as lost_trips_per_week,
    rank() over (order by p.missed_pickups_per_week + p.missed_returns_per_week desc) as priority_rank,
    cast((select since from bounds) as timestamp) as availability_since_utc
from per_station as p
join {{ ref('dim_station') }} as s on p.station_id = s.station_id
