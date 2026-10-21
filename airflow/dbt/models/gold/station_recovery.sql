-- Q6 Recovery time: once a station runs empty, how long until a bike is back?
-- Consecutive empty slots form one streak (gaps and islands); a missing slot ends the streak.
-- Streaks still open at the last snapshot are excluded (their length is unknown yet).
-- Duration = number of empty slots x 15 min (resolution of the snapshots).
-- Grain: station x day type x local hour of onset.
with snapshots as (
    select
        station_id,
        slot_ts,
        is_empty,
        lag(slot_ts) over (partition by station_id order by slot_ts) as prev_slot_ts,
        lag(is_empty) over (partition by station_id order by slot_ts) as prev_is_empty,
        lead(slot_ts) over (partition by station_id order by slot_ts) as next_slot_ts
    from {{ ref('station_status') }}
    where not is_stale and is_installed and is_renting
),

flagged as (
    select
        *,
        case
            when is_empty
                 and (prev_is_empty is null
                      or not prev_is_empty
                      or prev_slot_ts <> slot_ts - interval '15' minute)
            then 1 else 0
        end as is_streak_start
    from snapshots
),

empty_slots as (
    select
        *,
        sum(is_streak_start) over (
            partition by station_id order by slot_ts rows unbounded preceding
        ) as streak_id
    from flagged
    where is_empty
),

streaks as (
    select
        station_id,
        streak_id,
        min(slot_ts) as onset_ts,
        count(*) * 15 as duration_min,
        -- open = the last empty slot is the station's last snapshot (no recovery observed yet)
        bool_or(next_slot_ts is null) as is_open
    from empty_slots
    group by 1, 2
),

closed as (
    select
        station_id,
        {{ to_local('onset_ts') }} as onset_local,
        duration_min
    from streaks
    where not is_open
)

select
    c.station_id,
    s.station_name,
    s.region_name,
    {{ day_type('c.onset_local') }} as day_type,
    hour(c.onset_local) as onset_local_hour,
    count(*) as n_streaks,
    approx_percentile(c.duration_min, 0.5) as median_duration_min,
    approx_percentile(c.duration_min, 0.9) as p90_duration_min,
    avg(case when c.duration_min > 60 then 1.0 else 0.0 end) as share_over_60_min
from closed as c
join {{ ref('dim_station') }} as s on c.station_id = s.station_id
group by 1, 2, 3, 4, 5
