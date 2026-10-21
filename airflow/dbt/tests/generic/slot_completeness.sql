{#- Share of the 96 expected 15-minute slots present per UTC day. Returns days below min_rate.
    Skips the first collection day (started mid-day) and today (still in progress). -#}
{% test slot_completeness(model, min_rate) %}
with per_day as (
    select date(slot_ts) as day, count(distinct slot_ts) as slots
    from {{ model }}
    group by 1
)
select day, slots, slots / 96.0 as completeness
from per_day
where day > (select min(day) from per_day)
  and day < current_date
  and slots / 96.0 < {{ min_rate }}
{% endtest %}
