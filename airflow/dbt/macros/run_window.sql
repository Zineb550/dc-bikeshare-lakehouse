{#-
  The window an incremental run processes, as SQL date expressions.
  Airflow passes --vars '{start: YYYY-MM-DD, end: YYYY-MM-DD}' (end exclusive), derived
  from the run's logical date, so reruns and backfills reprocess exactly that period.
  Without vars (a manual run), the window is the last 2 days.
-#}
{% macro window_start() -%}
    {%- if var('start', none) -%} date '{{ var("start") }}'
    {%- else -%} (current_date - interval '2' day)
    {%- endif -%}
{%- endmacro %}

{% macro window_end() -%}
    {%- if var('end', none) -%} date '{{ var("end") }}'
    {%- else -%} (current_date + interval '1' day)
    {%- endif -%}
{%- endmacro %}

{#- Trips are processed per month: --vars '{month: YYYY-MM}'. Without it, the last 2 months. -#}
{% macro trip_months_filter(column='month') -%}
    {%- if var('month', none) -%} {{ column }} = '{{ var("month") }}'
    {%- else -%} {{ column }} >= format_datetime(current_date - interval '2' month, 'yyyy-MM')
    {%- endif -%}
{%- endmacro %}

{% macro trip_month_start() -%}
    {%- if var('month', none) -%} date '{{ var("month") }}-01'
    {%- else -%} date_trunc('month', current_date - interval '2' month)
    {%- endif -%}
{%- endmacro %}
