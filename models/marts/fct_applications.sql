-- Gold-layer applicant-level feature mart (one row per application): the
-- tested, contracted data product the PD model trains on. Joins the cleaned
-- application with the rolled-up bureau credit history and derives ratio
-- features. Left join + coalesce so applicants with no bureau history keep a
-- row with zeroed credit-history counts rather than dropping out.

with applications as (

    select * from {{ ref('stg_applications') }}

),

bureau as (

    select * from {{ ref('int_bureau_aggregations') }}

),

joined as (

    select
        applications.application_id,
        applications.is_default,
        applications.contract_type,
        applications.income_total,
        applications.credit_amount,
        applications.annuity_amount,
        applications.age_years,
        applications.employment_years,
        coalesce(bureau.prior_credit_count, 0) as prior_credit_count,
        coalesce(bureau.active_credit_count, 0) as active_credit_count,
        coalesce(bureau.total_credit_debt, 0) as total_credit_debt,
        coalesce(bureau.total_credit_overdue, 0) as total_credit_overdue,
        coalesce(bureau.max_days_overdue, 0) as max_days_overdue,
        {{ safe_divide('applications.credit_amount', 'applications.income_total') }} as credit_to_income_ratio,
        {{ safe_divide('applications.annuity_amount', 'applications.income_total') }} as annuity_to_income_ratio
    from applications
    left join bureau
        on applications.application_id = bureau.application_id

)

select * from joined
