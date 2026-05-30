with source as (

    select * from {{ source('home_credit', 'application_train') }}

),

renamed as (

    select
        cast(sk_id_curr as bigint) as application_id,
        target as is_default,
        name_contract_type as contract_type,
        code_gender as gender,
        flag_own_car as owns_car,
        flag_own_realty as owns_realty,
        cast(cnt_children as int) as children_count,
        cast(amt_income_total as double) as income_total,
        cast(amt_credit as double) as credit_amount,
        cast(amt_annuity as double) as annuity_amount,
        cast(amt_goods_price as double) as goods_price,
        name_income_type as income_type,
        name_education_type as education_type,
        name_family_status as family_status,
        cast(-days_birth / 365.25 as int) as age_years,
        -- DAYS_EMPLOYED = 365243 is Home Credit's "not employed" sentinel;
        -- dividing it would yield ~ -1000 years, so null it out here.
        case
            when days_employed = 365243 then null
            else cast(-days_employed / 365.25 as double)
        end as employment_years
    from source

)

select * from renamed
