-- Deterministic assembly of each declined applicant's grounded adverse-action
-- drivers. No LLM here: this selects the highest-risk applicants (predicted_pd
-- at or above the illustrative decline threshold), keeps a bounded sample by
-- descending risk, and maps each of the model's top-3 SHAP drivers to a
-- regulator-friendly label from the feature_labels seed. fct_adverse_actions
-- feeds driver_list to ai_query and the consistency eval checks the generated
-- reason against these labels -- so the set of factors the LLM may cite is
-- fixed here, in SQL, never invented by the model.

with scored as (

    select
        application_id,
        predicted_pd,
        top1_feature,
        top1_shap,
        top2_feature,
        top2_shap,
        top3_feature,
        top3_shap
    from {{ ref('fct_scored_applications') }}
    where predicted_pd >= {{ var('decline_threshold', 0.30) }}

),

ranked as (

    select
        *,
        row_number() over (order by predicted_pd desc, application_id asc) as decline_rank
    from scored
    qualify
        row_number() over (order by predicted_pd desc, application_id asc)
        <= {{ var('adverse_action_sample_size', 500) }}

),

labels as (

    select
        feature_name,
        feature_label
    from {{ ref('feature_labels') }}

)

select
    ranked.application_id,
    ranked.predicted_pd,
    ranked.decline_rank,
    ranked.top1_feature,
    l1.feature_label as top1_label,
    ranked.top1_shap,
    ranked.top2_feature,
    l2.feature_label as top2_label,
    ranked.top2_shap,
    ranked.top3_feature,
    l3.feature_label as top3_label,
    ranked.top3_shap,
    concat_ws(
        '; ',
        concat('1. ', l1.feature_label),
        concat('2. ', l2.feature_label),
        concat('3. ', l3.feature_label)
    ) as driver_list
from ranked
left join labels as l1 on ranked.top1_feature = l1.feature_name
left join labels as l2 on ranked.top2_feature = l2.feature_name
left join labels as l3 on ranked.top3_feature = l3.feature_name
