-- Staging view over the model-output Delta table: types and documents the
-- scored predictions so the governed layer can consume model results with
-- lineage intact (raw application -> feature mart -> model -> back into dbt).

with source as (

    select * from {{ source('model_outputs', 'pd_predictions') }}

)

select
    cast(application_id as bigint) as application_id,
    cast(predicted_pd as double) as predicted_pd,
    top1_feature,
    cast(top1_shap as double) as top1_shap,
    top2_feature,
    cast(top2_shap as double) as top2_shap,
    top3_feature,
    cast(top3_shap as double) as top3_shap
from source
