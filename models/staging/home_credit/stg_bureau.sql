with source as (

    select * from {{ source('home_credit', 'bureau') }}

),

renamed as (

    select
        cast(sk_id_curr as bigint) as application_id,
        sk_id_bureau as bureau_credit_id,
        credit_active as credit_status,
        credit_type,
        cast(-days_credit as int) as days_since_credit_opened,
        cast(credit_day_overdue as int) as days_overdue,
        cast(amt_credit_sum as double) as credit_sum,
        cast(amt_credit_sum_debt as double) as credit_debt,
        cast(amt_credit_sum_overdue as double) as credit_overdue
    from source

)

select * from renamed
