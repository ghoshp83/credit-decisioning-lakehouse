{#
  Null-safe division. nullif(denominator, 0) yields null when the denominator
  is zero, and dividing by null is already null, so the ratio degrades
  gracefully to null (never an error or +/-inf) instead of poisoning
  downstream models. Reused across the feature marts.
#}
{% macro safe_divide(numerator, denominator) -%}
    {{ numerator }} / nullif({{ denominator }}, 0)
{%- endmacro %}
