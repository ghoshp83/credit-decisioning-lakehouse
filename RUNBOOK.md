# Runbook — credit-decisioning-lakehouse

Operating and failure-handling guide for the dbt transformation layer. It
assumes the [README](README.md) setup is done: tooling installed, the
`DATABRICKS_HOST` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN` environment
variables exported, and `profiles.yml` in place (it reads those env vars — no
secrets in files).

## Normal operation

```bash
dbt deps                 # install package dependencies (one-time / on change)
dbt build                # run all models + their data tests, in dependency order
dbt test                 # run tests only (no model rebuild)
dbt test --select test_type:unit   # run dbt unit tests (executes vs fixtures)
dbt docs generate        # regenerate lineage / documentation
```

`dbt build` is the primary command: it materialises every model and runs its
tests in DAG order, stopping a downstream model if its upstream failed. A clean
run ends with `Completed successfully` and `PASS=<n> ... ERROR=0`.

## When a run fails

1. **Read the failing node, not just the summary.** dbt prints the failing
   model/test and the compiled SQL path under `target/`. Re-run just that node:
   `dbt build --select <model_name>`.
2. **Connection / auth errors** (`Runtime Error ... Could not connect`,
   `403`, `Invalid access token`) — the warehouse is asleep or the token
   expired. Tokens here are short-lived by design; mint a fresh one and re-export
   `DATABRICKS_TOKEN`. Confirm `DATABRICKS_HTTP_PATH` points at a running SQL
   warehouse.
3. **Recover from a partial build** without redoing the whole DAG:
   `dbt build --select result:error+ --state target/` re-runs only the failed
   nodes and everything downstream of them. (Save the prior `target/` first.)
4. **Compile-only check** (no warehouse needed for parsing): `dbt parse`. This
   is what CI runs — if it fails locally it will fail in CI.

## When a test fails

A failing data test means the **data violated an invariant we asserted on
purpose** — treat it as a real signal, not noise.

- **`not_null` / `unique`** on a key (e.g. `application_id`,
  `payment_id`) — the grain assumption broke. Inspect duplicates:
  the test's compiled SQL under `target/compiled/.../<test>.sql` is a ready-to-run
  query that returns the offending rows.
- **`accepted_range`** (e.g. `employment_years` 0–100) — an upstream sentinel or
  unit-conversion slipped through. The `DAYS_EMPLOYED = 365243` "not employed"
  sentinel is scrubbed to `null` in `stg_applications`; a range failure there
  means a new sentinel or a regression in that logic.
- **Unit test failure** (`dbt test --select test_type:unit`) — the *transform
  logic itself* changed and no longer matches its documented intent (the
  fixtures encode the expected behaviour). Fix the model or, if the behaviour
  change is intended, update the fixture **and** its description. Unit tests run
  against fixtures on the warehouse; they are not part of the offline CI run.

Do **not** make a test pass by loosening it without understanding the cause —
that defeats its purpose.

## When a source looks stale

Source **freshness checks are intentionally disabled** (`freshness: null` in
[models/staging/home_credit/_sources.yml](models/staging/home_credit/_sources.yml)):
this is a static historical dataset with no ingestion clock, so there is nothing
to be stale against. If a live feed is ever attached, re-enable freshness by
adding a `loaded_at_field` and a `freshness:` threshold to the relevant source
table, then gate runs with `dbt source freshness`.

## Incremental model — `fct_installment_payments`

This is the one incremental model (Delta `MERGE`, `unique_key = payment_id`).

- **Re-running is safe.** The merge is idempotent on the surrogate key: a second
  run over the same input leaves the row count unchanged.
- **Suspected bad/late data already merged in** — do a full refresh to rebuild
  from scratch: `dbt build --select fct_installment_payments --full-refresh`.
- **Schema/contract change** on an incremental model needs `--full-refresh` (a
  `MERGE` cannot alter the table shape in place).

## When a contract is violated

Marts (`fct_applications`, `fct_installment_payments`) have **enforced model
contracts**. A build that fails with a type/column mismatch means a staging cast
drifted from the declared contract — e.g. `read_files` inferring `INT` where the
contract declares `bigint`. Fix it at the **staging cast** (the contract is the
source of truth), not by relaxing the contract. Example already in the code:
`cast(sk_id_curr as bigint) as application_id` in `stg_applications` /
`stg_bureau`.

## Before pushing

- `dbt parse` + `sqlfluff lint models analyses tests` + `ruff check` — the same gates CI runs,
  all offline (no warehouse connection needed). A local mirror via `uv` keeps a
  Python 3.11 virtualenv for this.
- Never commit secrets. `profiles.yml` and any token live outside tracked files;
  authentication is via environment variables only.

## Known limitations

See the **Honest disclaimer** in the [README](README.md#honest-disclaimer): the
dataset is static historical (not live origination), adverse-action wording is
illustrative (not legal advice), fairness is assessed on proxy attributes only,
and some Databricks features may be paid-tier only.
