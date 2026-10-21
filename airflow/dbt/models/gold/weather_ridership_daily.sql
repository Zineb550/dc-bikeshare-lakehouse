-- Q2 Weather effect: rides lost to rain, heat or cold.
-- Grain: local date. ridership_index = trips / median trips of dry, mild days with the same
-- weekday and month (the "normal day" baseline); lost_trips = baseline - trips.
-- Dockless rides count here (they are real rides); flagged durations do not.
with trips as (
    select
        date({{ to_local('started_at') }}) as local_date,
        count(*) as trips,
        count_if(member_casual = 'member') as members,
        count_if(member_casual = 'casual') as casual
    from {{ ref('fct_trip') }}
    where not is_short and not is_long
    group by 1
),

weather as (
    select
        date({{ to_local('hour_ts') }}) as local_date,
        count(*) as hours,
        avg(temperature_c) as mean_temp_c,
        max(temperature_c) as max_temp_c,
        sum(precipitation_mm) as precipitation_mm,
        -- riding hours only: rain at 3 a.m. does not cost rides
        sum(case when hour({{ to_local('hour_ts') }}) between 7 and 21 then precipitation_mm else 0 end)
            as daytime_precipitation_mm,
        count_if(precipitation_mm >= 0.1) as rainy_hours
    from {{ ref('weather_hourly') }}
    where not is_forecast
    group by 1
),

days as (
    select
        t.local_date,
        day_of_week(t.local_date) as weekday,
        month(t.local_date) as month,
        t.trips,
        t.members,
        t.casual,
        w.mean_temp_c,
        w.max_temp_c,
        w.precipitation_mm,
        w.daytime_precipitation_mm,
        w.rainy_hours,
        case
            when w.daytime_precipitation_mm < 1 then 'dry'
            when w.daytime_precipitation_mm < 10 then 'light_rain'
            else 'heavy_rain'
        end as weather_bucket,
        case
            when w.mean_temp_c < 5 then 'cold'
            when w.max_temp_c >= 32 then 'hot'
            else 'mild'
        end as temp_bucket
    from trips as t
    -- complete weather days only (23-25 hours with DST)
    join weather as w on t.local_date = w.local_date and w.hours >= 23
),

baseline as (
    select weekday, month, approx_percentile(trips, 0.5) as baseline_trips, count(*) as baseline_days
    from days
    where weather_bucket = 'dry' and temp_bucket = 'mild'
    group by 1, 2
)

select
    d.local_date,
    d.trips,
    d.members,
    d.casual,
    d.mean_temp_c,
    d.max_temp_c,
    d.precipitation_mm,
    d.daytime_precipitation_mm,
    d.rainy_hours,
    d.weather_bucket,
    d.temp_bucket,
    b.baseline_trips,
    b.baseline_days,
    cast(d.trips as double) / b.baseline_trips as ridership_index,
    greatest(b.baseline_trips - d.trips, 0) as lost_trips
from days as d
left join baseline as b on d.weekday = b.weekday and d.month = b.month
