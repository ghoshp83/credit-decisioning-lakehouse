-- Gold scored-applications product: the feature mart joined to its model
-- prediction and top SHAP drivers. The queryable surface for portfolio
-- analytics and the grounded adverse-action explanation — every cited reason
-- resolves to a real driver on the same row. Inner join: a row appears once it
-- has been scored, keeping features and prediction strictly aligned.

with applications as (

    select * from {{ ref('fct_applications') }}

),

predictions as (

    select * from {{ ref('stg_pd_predictions') }}

)

select
    applications.*,
    predictions.predicted_pd,
    predictions.top1_feature,
    predictions.top1_shap,
    predictions.top2_feature,
    predictions.top2_shap,
    predictions.top3_feature,
    predictions.top3_shap
from applications
inner join predictions
    on applications.application_id = predictions.application_id
