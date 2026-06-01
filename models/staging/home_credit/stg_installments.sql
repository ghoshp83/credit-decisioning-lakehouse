with source as (

    select * from {{ source('home_credit', 'installments_payments') }}

),

renamed as (

    select
        -- One row per prior-credit installment payment event. There is no
        -- natural single-column key: a scheduled installment can be paid in
        -- parts (same prior credit + version + number, different entry day /
        -- amount), so the grain is the full payment event. The verified-unique
        -- business key is (sk_id_prev, version, number, entry_day, amount) —
        -- hash it into one stable surrogate that the incremental MERGE keys on.
        {{ surrogate_key([
            'sk_id_prev',
            'num_instalment_version',
            'num_instalment_number',
            'days_entry_payment',
            'amt_payment'
        ]) }} as payment_id,
        cast(sk_id_prev as bigint) as prior_credit_id,
        cast(sk_id_curr as bigint) as application_id,
        cast(num_instalment_version as int) as installment_version,
        cast(num_instalment_number as int) as installment_number,
        cast(days_instalment as int) as installment_due_day,
        cast(days_entry_payment as int) as payment_entry_day,
        cast(amt_instalment as double) as installment_amount,
        cast(amt_payment as double) as payment_amount,
        -- Behaviour features. payment_shortfall > 0 = underpaid that
        -- installment; days_late > 0 = paid after the scheduled day (days are
        -- negative offsets from application, so a larger value is later).
        cast(amt_instalment as double) - cast(amt_payment as double) as payment_shortfall,
        cast(days_entry_payment as int) - cast(days_instalment as int) as days_late
    from source

)

select * from renamed
