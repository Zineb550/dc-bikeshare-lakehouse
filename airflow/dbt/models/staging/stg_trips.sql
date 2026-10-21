-- One row per ride as published, typed. Trip files use local time (America/New_York);
-- converted to UTC here. Station ids in trip files are GBFS short_names.
with typed as (
    select
        month,
        ride_id,
        rideable_type,
        member_casual,
        cast(substr(started_at, 1, 19) as timestamp) as started_at_local,
        cast(substr(ended_at, 1, 19) as timestamp) as ended_at_local,
        nullif(trim(start_station_id), '') as start_short_name,
        nullif(trim(start_station_name), '') as start_station_name,
        nullif(trim(end_station_id), '') as end_short_name,
        nullif(trim(end_station_name), '') as end_station_name,
        try_cast(start_lat as double) as start_lat,
        try_cast(start_lng as double) as start_lng,
        try_cast(end_lat as double) as end_lat,
        try_cast(end_lng as double) as end_lng,
        source_file
    from {{ source('bronze', 'trips') }}
)

select
    month,
    ride_id,
    rideable_type,
    member_casual,
    started_at_local,
    ended_at_local,
    cast(with_timezone(started_at_local, 'America/New_York') at time zone 'UTC' as timestamp)
        as started_at,
    cast(with_timezone(ended_at_local, 'America/New_York') at time zone 'UTC' as timestamp)
        as ended_at,
    start_short_name,
    start_station_name,
    end_short_name,
    end_station_name,
    start_lat,
    start_lng,
    end_lat,
    end_lng,
    source_file
from typed
