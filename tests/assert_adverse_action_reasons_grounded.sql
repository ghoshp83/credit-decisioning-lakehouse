-- Reason-to-feature grounding (singular test, the compliance gate). A grounded
-- adverse-action reason may mention only the applicant's own driver labels.
-- This returns every (applicant, label) pair where a generated reason cites a
-- feature_labels phrase that was NOT one of that applicant's top-3 SHAP drivers
-- -- i.e. the LLM introduced a factor the model did not use. Word-boundary
-- matching (rlike \b...\b) avoids false hits on short labels like "age" inside
-- other words. Zero rows == every reason is grounded in its real drivers; any
-- row fails the build, so an ungrounded explanation can never ship silently.

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

)

select
    reasons.application_id,
    labels.fl as foreign_label_cited
from reasons
cross join labels
where
    reasons.reason rlike concat('\\b', labels.fl, '\\b')
    and labels.fl not in (reasons.l1, reasons.l2, reasons.l3)
