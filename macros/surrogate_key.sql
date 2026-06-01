{#
  Deterministic surrogate key over a list of columns: md5 of the
  separator-joined, null-safe string casts (the same shape as
  dbt_utils.generate_surrogate_key). Defined locally rather than calling the
  package macro so the SQL renders under sqlfluff's offline jinja templater in
  CI (dbt_utils macros are not available to sqlfluff), and so the key's exact
  composition is explicit and reviewable. Stable across runs — safe as the
  unique_key of an incremental MERGE.
#}
{% macro surrogate_key(field_list) -%}
    md5(concat_ws('||',
        {%- for field in field_list %}
        coalesce(cast({{ field }} as string), '_null_'){% if not loop.last %},{% endif %}
        {%- endfor %}
    ))
{%- endmacro %}
