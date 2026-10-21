{#- Trip rows per monthly file vs the previous file; returns files that moved more than
    max_change (0.5 = ±50%). Grouped by source file, not by UTC month: rides late on the
    last local evening of a month fall in the next month in UTC. Catches a truncated file. -#}
{% test month_over_month_rows(model, max_change) %}
with per_file as (
    select date_parse(source_month, '%Y-%m') as month, count(*) as rides
    from {{ model }}
    group by 1
),
compared as (
    select
        month,
        rides,
        lag(rides) over (order by month) as prev_rides,
        lag(month) over (order by month) as prev_month
    from per_file
)
select month, rides, prev_rides
from compared
where prev_rides is not null
  and prev_month = month - interval '1' month
  and abs(cast(rides as double) / prev_rides - 1) > {{ max_change }}
{% endtest %}
