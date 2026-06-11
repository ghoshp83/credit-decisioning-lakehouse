# Model Card — Probability-of-Default (PD) Model

A LightGBM classifier that estimates the probability a loan applicant will have
payment difficulties, trained on the governed `fct_applications` gold mart. This
card follows the spirit of the [Model Cards](https://arxiv.org/abs/1810.03993)
framework. All numbers below are reproducible from `ml/train.py` + `ml/calibrate.py`.

## Model details

- **Type:** Gradient-boosted decision trees (LightGBM, binary objective).
- **Inputs:** ~13 features from the gold mart — cleaned application attributes
  (income, credit/annuity amounts, age, employment years), rolled-up bureau
  credit history (prior/active credit counts, debt, overdue), and two derived
  ratio features (credit-to-income, annuity-to-income).
- **Output:** A probability in [0, 1] that `is_default = 1`.
- **Training:** Stratified 80/20 split (246,008 train / 61,503 holdout), early
  stopping on holdout AUC (best iteration 236). Tracked in MLflow.
- **The LLM is never in the prediction path** — see the repo README.

## Intended use

- **In scope:** Illustrating a governed, explainable, calibrated PD pipeline on
  a static historical dataset; generating per-applicant SHAP drivers that feed a
  grounded adverse-action explanation.
- **Out of scope:** Live underwriting or any real lending decision. This is a
  portfolio artifact on the static Home Credit dataset, not a production scorecard.

## Training data

- **Home Credit Default Risk** — a static historical dataset, not live loan
  origination. Target prevalence (default rate): **8.07%**.
- Features are sourced exclusively from the dbt-governed gold mart, so every
  model input is a tested, documented, lineage-tracked column.

## Evaluation

Measured on a held-out evaluation fold disjoint from training and calibration.

| Metric | Value | Reading |
|--------|-------|---------|
| AUC | **0.679** | Moderate ranking power on a deliberately compact feature set. |
| KS | **0.265** | Separation between defaulter / non-defaulter score distributions. |
| Brier (raw) | **0.0715** | Probability accuracy of the raw model. |
| Brier (isotonic-calibrated) | **0.0716** | No improvement — see below. |

### Calibration — measured, and honestly reported

LightGBM trained with the log-loss objective already produces **well-calibrated**
probabilities here: isotonic recalibration moved the Brier score by +0.0001
(marginally *worse*, from fitting noise), so the **raw probabilities are used as-is**.
The reliability table (predicted vs. observed default rate, by decile of
predicted PD) tracks the diagonal closely:

| Predicted | Observed |
|-----------|----------|
| 0.025 | 0.027 |
| 0.036 | 0.044 |
| 0.051 | 0.047 |
| 0.057 | 0.054 |
| 0.066 | 0.063 |
| 0.073 | 0.073 |
| 0.087 | 0.094 |
| 0.112 | 0.098 |
| 0.135 | 0.150 |
| 0.238 | 0.218 |

The calibration step stays in the pipeline as a measured safeguard: if a future
feature or data change degrades calibration, `ml/calibrate.py` surfaces it rather
than letting miscalibrated probabilities reach a decision.

## Fairness slices

Per-slice metrics on the available proxy attribute (`contract_type`). Predicted
PD tracks the observed default rate within each slice, and ranking power (AUC) is
comparable across slices:

| Slice | n | Observed rate | Mean predicted | AUC |
|-------|---|---------------|----------------|-----|
| Cash loans | 27,779 | 0.0837 | 0.0841 | 0.675 |
| Revolving loans | 2,973 | 0.0531 | 0.0545 | 0.688 |

This is a **proxy-attribute** check on available columns, **not** a substitute
for a regulated fairness audit (which would require protected attributes this
dataset does not expose).

## Adverse-action explanation grounding

The downstream LLM explanations are constrained to this model's own evidence and
the constraint is **measured, not assumed**. Each declined applicant's top-3
SHAP drivers are mapped to fixed labels, and `ai_query` may cite only those; the
`assert_adverse_action_reasons_grounded` dbt test fails the build on any
violation. Over the 500 generated reasons:

| Grounding metric | Value |
|------------------|-------|
| Reasons citing ≥1 of the applicant's real drivers | **500 / 500 (100%)** |
| Reasons citing a factor the model did *not* use | **0** |
| Mean real drivers cited per reason | **2.5 / 3** |

So the explanation layer reflects the model's drivers rather than inventing
plausible-sounding ones — the reason↔feature consistency the design requires.

## Limitations

- Modest AUC by design: the compact governed feature set favors a legible lineage
  story over a leaderboard score (published Home Credit solutions reach higher
  AUC with hundreds of engineered features).
- Static historical data — no temporal validation, no population-drift handling.
- Fairness assessed only on proxy attributes present in the data.
- Adverse-action explanations built on this model's drivers are **illustrative**,
  not legal advice.
