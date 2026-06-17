-- Gold scored-applications product: the feature mart joined to its model
-- prediction and top SHAP drivers. The queryable surface for portfolio
-- analytics and the grounded adverse-action explanation — every cited reason
-- resolves to a real driver on the same row. Inner join: a row appears once it
-- has been scored, keeping features and prediction strictly aligned.
--
-- liquid_clustered_by predicted_pd: the access pattern here is risk-ranked --
-- int_adverse_action_drivers filters `where predicted_pd >= decline_threshold`
-- and portfolio analytics slice/sort by PD -- so clustering on predicted_pd is
-- the deliberate choice matching how this product is actually queried.
-- Clustering applies on the next live `dbt build` (CI parses offline only).
{{ config(liquid_clustered_by='predicted_pd') }}

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
