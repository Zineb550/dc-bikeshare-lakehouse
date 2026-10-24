{#- Silver is UTC; gold reports in Washington, DC local time (DST-aware). -#}
{% macro to_local(column) -%}
    cast(date_format(at_timezone(with_timezone({{ column }}, 'UTC'), 'America/New_York'), '%Y-%m-%d %H:%i:%s') as timestamp)
{%- endmacro %}

{#- weekday / weekend from a local timestamp (US holidays are not treated separately). -#}
{% macro day_type(local_column) -%}
    case when day_of_week({{ local_column }}) in (6, 7) then 'weekend' else 'weekday' end
{%- endmacro %}
