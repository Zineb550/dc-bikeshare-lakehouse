{#- Share of docked trip starts whose short_name resolves to a GBFS station, per monthly file.
    Returns the files below min_rate. Measured baseline: August 2026 = 100%. -#}
{% test crosswalk_rate(model, min_rate) %}
select
    source_month,
    count(*) as docked_starts,
    avg(case when start_station_id is not null then 1.0 else 0.0 end) as resolved_rate
from {{ model }}
where not is_dockless_start
group by 1
having avg(case when start_station_id is not null then 1.0 else 0.0 end) < {{ min_rate }}
{% endtest %}
