-- Adverse-action grounding metrics (an analysis: dbt compiles it but does not
-- materialize it). Quantifies how well the LLM-generated reasons stay grounded
-- in each applicant's real SHAP drivers -- the number reported in the README /
-- model card. avg_own_drivers_cited = mean count of the applicant's own three
-- driver labels that appear in the reason; reasons_citing_any_driver should
-- equal n_reasons (every reason references at least one real driver);
-- reasons_with_foreign_factor must be 0 (it is the same condition the
-- assert_adverse_action_reasons_grounded gate enforces, here counted not gated).

with reasons as (

    select
        application_id,
        lower(adverse_action_reason) as reason,
        lower(top1_label) as l1,
        lower(top2_label) as l2,
        lower(top3_label) as l3
    from {{ ref('fct_adverse_actions') }}

),

labels as (

    select lower(feature_label) as fl from {{ ref('feature_labels') }}

),

per_reason as (

    select
        reasons.application_id,
        cast(reasons.reason rlike concat('\\b', reasons.l1, '\\b') as int)
        + cast(reasons.reason rlike concat('\\b', reasons.l2, '\\b') as int)
        + cast(reasons.reason rlike concat('\\b', reasons.l3, '\\b') as int) as own_cited,
        count_if(
            labels.fl not in (reasons.l1, reasons.l2, reasons.l3)
            and reasons.reason rlike concat('\\b', labels.fl, '\\b')
        ) as foreign_cited
    from reasons
    cross join labels
    group by
        reasons.application_id,
        reasons.reason,
        reasons.l1,
        reasons.l2,
        reasons.l3

)

select
    count(*) as n_reasons,
    round(avg(own_cited), 2) as avg_own_drivers_cited,
    sum(case when own_cited >= 1 then 1 else 0 end) as reasons_citing_any_driver,
    sum(case when foreign_cited > 0 then 1 else 0 end) as reasons_with_foreign_factor
from per_reason
