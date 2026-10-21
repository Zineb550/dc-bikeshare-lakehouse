-- Q4 Inferred truck visits: a jump in total bikes (available + disabled) between two
-- consecutive 15-minute slots that riders alone cannot explain.
-- Threshold per station x local hour = max(6, p99 of 15-minute rider departures or arrivals).
-- Skipped: a missing slot in between, or is_installed / is_renting changed.
with trips as (
    select start_station_id, end_station_id, is_dockless_start, is_dockless_end,
           {{ to_local('started_at') }} as start_local, {{ to_local('ended_at') }} as end_local
    from {{ ref('fct_trip') }}
    where not is_short and not is_long
),

flows as (
    select start_station_id as station_id, hour(start_local) as local_hour,
           date_trunc('hour', start_local) + (minute(start_local) / 15) * interval '15' minute as bucket
    from trips
    where not is_dockless_start and start_station_id is not null
    union all
    select end_station_id, hour(end_local),
           date_trunc('hour', end_local) + (minute(end_local) / 15) * interval '15' minute
    from trips
    where not is_dockless_end and end_station_id is not null
),

-- departures and arrivals counted separately; buckets with no rides are absent, which only
-- makes the p99 (and so the threshold) more conservative
bucket_counts as (
    select station_id, local_hour, bucket, count(*) as rides
    from flows
    group by 1, 2, 3
),

thresholds as (
    select station_id, local_hour, greatest(6, approx_percentile(rides, 0.99)) as threshold
    from bucket_counts
    group by 1, 2
),

steps as (
    select
        station_id,
        slot_ts,
        {{ to_local('slot_ts') }} as slot_local,
        prev_bikes_available + prev_bikes_disabled as prev_total_bikes,
        bikes_available + bikes_disabled as total_bikes,
        (bikes_available + bikes_disabled) - (prev_bikes_available + prev_bikes_disabled)
            as delta_total_bikes
    from {{ ref('station_status') }}
    where prev_slot_ts = slot_ts - interval '15' minute
      and is_installed = prev_is_installed
      and is_renting = prev_is_renting
)

select
    s.station_id,
    cast(s.slot_ts as timestamp) as slot_ts,
    s.slot_local,
    s.prev_total_bikes,
    s.total_bikes,
    s.delta_total_bikes,
    case when s.delta_total_bikes > 0 then 'drop_off' else 'pickup' end as visit_type,
    coalesce(t.threshold, 6) as threshold
from steps as s
left join thresholds as t
    on s.station_id = t.station_id and hour(s.slot_local) = t.local_hour
where abs(s.delta_total_bikes) > coalesce(t.threshold, 6)
