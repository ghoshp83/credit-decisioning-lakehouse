-- Grounded adverse-action explanations -- the LLM half of the flow. For each
-- declined applicant in int_adverse_action_drivers, ai_query turns the fixed
-- driver_list into a compliant plain-language reason, entirely inside the
-- lakehouse (a Databricks foundation model), so no row or driver ever leaves
-- the governed layer and no external API/secret is involved. The prompt
-- hard-constrains the model to the listed factors; the reason-to-feature
-- consistency test measures whether it complied (it is not assumed). ai_query
-- is metered and runs at build time, so generation is bounded upstream by
-- decline_threshold + adverse_action_sample_size (see README honest disclaimer).
-- Materialized as a table: explanations persist and only regenerate on a run.

with drivers as (

    select * from {{ ref('int_adverse_action_drivers') }}

)

select
    application_id,
    predicted_pd,
    decline_rank,
    top1_feature,
    top1_label,
    top2_feature,
    top2_label,
    top3_feature,
    top3_label,
    driver_list,
    ai_query(
        '{{ var('aa_llm_endpoint', 'databricks-meta-llama-3-3-70b-instruct') }}',
        concat(
            'You are a lending compliance assistant. Write a short, respectful ',
            'adverse-action explanation (2 to 3 sentences) telling an applicant ',
            'why their loan application was declined. You may cite ONLY the ',
            'following factors, using their exact wording, and must not mention ',
            'any other factor, number, score, or specific value: ',
            driver_list,
            '. Do not invent specifics. Do not promise or imply any future ',
            'decision. Begin with exactly: "Your application was declined based ',
            'on the following factors:".'
        )
    ) as adverse_action_reason
from drivers
