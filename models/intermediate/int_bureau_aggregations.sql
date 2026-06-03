-- Roll up the many bureau credits per applicant into one feature row.
-- Multi-row -> one-row-per-application aggregation: the core feature-mart
-- building block. Materialized as a view (the intermediate-layer default) so
-- the aggregation is isolated, independently queryable, and mockable as an
-- input when unit-testing fct_applications.

with bureau as (

    select * from {{ ref('stg_bureau') }}

),

aggregated as (

    select
        application_id,
        count(*) as prior_credit_count,
        count_if(credit_status = 'Active') as active_credit_count,
        sum(credit_debt) as total_credit_debt,
        sum(credit_overdue) as total_credit_overdue,
        max(days_overdue) as max_days_overdue
    from bureau
    group by application_id

)

select * from aggregated
