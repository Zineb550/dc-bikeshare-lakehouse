-- Q4 Truck summary: are trucks visiting where they are most needed?
-- Over the same trailing 28 days as the priority ranking:
--   visits_per_week, peak visit hours, priority_rank, and
--   is_underserved = top 10% of priority AND fewer truck visits per week than days per week
--   with a peak-hour (7-9, 16-19 local) empty or full episode.
with bounds as (
    select max(slot_ts) - interval '28' day as since from {{ ref('station_status') }}
),

observed as (
    select
        station_id,
        count(distinct date({{ to_local('slot_ts') }})) as observed_days,
        count(distinct case
            when (is_empty or is_full)
                 and hour({{ to_local('slot_ts') }}) in (7, 8, 9, 16, 17, 18, 19)
            then date({{ to_local('slot_ts') }})
        end) as peak_episode_days
    from {{ ref('station_status') }}
    where slot_ts >= (select since from bounds)
      and not is_stale and is_installed and is_renting
    group by 1
),

visits as (
    select station_id, hour(slot_local) as local_hour, count(*) as n
    from {{ ref('inferred_truck_visits') }}
    where slot_ts >= (select since from bounds)
    group by 1, 2
),

visit_totals as (
    select
        station_id,
        sum(n) as visits,
        array_join(
            slice(array_agg(cast(local_hour as varchar) order by n desc, local_hour), 1, 2), ', '
        ) as peak_visit_hours
    from visits
    group by 1
),

priority as (
    select
        station_id,
        station_name,
        region_name,
        lat,
        lon,
        lost_trips_per_week,
        priority_rank,
        count(*) over () as n_stations
    from {{ ref('station_rebalancing_priority') }}
)

select
    p.station_id,
    p.station_name,
    p.region_name,
    p.lat,
    p.lon,
    p.lost_trips_per_week,
    p.priority_rank,
    o.observed_days,
    coalesce(v.visits, 0) * 7.0 / o.observed_days as visits_per_week,
    o.peak_episode_days * 7.0 / o.observed_days as peak_episode_days_per_week,
    v.peak_visit_hours,
    p.priority_rank <= ceil(0.1 * p.n_stations)
        and coalesce(v.visits, 0) * 7.0 / o.observed_days
            < o.peak_episode_days * 7.0 / o.observed_days as is_underserved
from priority as p
join observed as o on p.station_id = o.station_id
left join visit_totals as v on p.station_id = v.station_id
