-- Gold event-grain fact: one row per prior-credit installment payment.
-- Incremental + Delta MERGE on the payment_id surrogate so re-runs are
-- idempotent (the boundary partition is re-merged, never duplicated) and a
-- real append only processes newer installments. The source is a static
-- historical dump, so the incremental watermark demonstrates the mechanics
-- rather than live ingestion (see README honest disclaimer) — the MERGE key is
-- what guarantees correctness on every re-run.
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='payment_id',
        on_schema_change='fail',
    )
}}

with payments as (

    select * from {{ ref('stg_installments') }}

)

select * from payments

{% if is_incremental() %}
-- Only (re)process installments at or after the latest scheduled day already
-- loaded. >= (not >) keeps boundary rows that share the max day; the MERGE
-- dedupes them by payment_id, so reprocessing the boundary stays idempotent.
where installment_due_day >= (select max(loaded.installment_due_day) from {{ this }} as loaded)
{% endif %}
