-- Q5 Members vs casual: when and where casual riders ride (conversion targeting).
-- Grain: member_casual x day type x local hour. Flagged durations excluded; top stations
-- are docked starts only.
with trips as (
    select
        member_casual,
        {{ day_type(to_local('started_at')) }} as day_type,
        hour({{ to_local('started_at') }}) as local_hour,
        duration_min,
        rideable_type,
        start_station_id
    from {{ ref('fct_trip') }}
    where not is_short and not is_long
),

segments as (
    select
        member_casual,
        day_type,
        local_hour,
        count(*) as trips,
        approx_percentile(duration_min, 0.5) as median_duration_min,
        avg(case when rideable_type = 'electric_bike' then 1.0 else 0.0 end) as ebike_share
    from trips
    group by 1, 2, 3
),

station_ranks as (
    select
        t.member_casual,
        t.day_type,
        t.local_hour,
        s.station_name,
        count(*) as station_trips,
        row_number() over (
            partition by t.member_casual, t.day_type, t.local_hour
            order by count(*) desc, s.station_name
        ) as station_rank
    from trips as t
    join {{ ref('dim_station') }} as s on t.start_station_id = s.station_id
    group by 1, 2, 3, 4
),

top_stations as (
    select
        member_casual,
        day_type,
        local_hour,
        array_join(array_agg(station_name order by station_rank), ' | ') as top_start_stations
    from station_ranks
    where station_rank <= 3
    group by 1, 2, 3
)

select
    s.member_casual,
    s.day_type,
    s.local_hour,
    s.trips,
    s.median_duration_min,
    s.ebike_share,
    t.top_start_stations
from segments as s
left join top_stations as t
    on s.member_casual = t.member_casual
    and s.day_type = t.day_type
    and s.local_hour = t.local_hour
