"""Gold-question eval for the NL->SQL helper.

Each gold item pairs an English question with a hand-written reference query
whose result is ground truth. The question is run through the validated helper
and its answer compared to the reference -- an honest, end-to-end text-to-SQL
accuracy number over the marts. The helper guarantees *safety* (read-only,
allowlisted, EXPLAIN-checked); this measures how often it is also *right*, which
is a separate and weaker guarantee, so the number is reported plainly.

A refused or mismatched question counts as a miss (fail loud, keep going).

Run: .venv-ai/bin/python -m ai.eval_nl_to_sql
Auth via env: DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN.
"""

from __future__ import annotations

from ai.nl_to_sql import CATALOG, MART_SCHEMA, _connect, answer

SCORED = f"{CATALOG}.{MART_SCHEMA}.fct_scored_applications"
ACTIONS = f"{CATALOG}.{MART_SCHEMA}.fct_adverse_actions"

# (question, reference SQL whose scalar result is the ground truth)
GOLD = [
    (
        "What is the average predicted probability of default across all scored "
        "applications, rounded to 4 decimals?",
        f"select round(avg(predicted_pd), 4) from {SCORED}",
    ),
    (
        "How many scored applications are there in total?",
        f"select count(*) from {SCORED}",
    ),
    (
        "How many scored applications have a predicted probability of default "
        "greater than 0.3?",
        f"select count(*) from {SCORED} where predicted_pd > 0.3",
    ),
    (
        "What is the highest predicted probability of default among scored "
        "applications, rounded to 4 decimals?",
        f"select round(max(predicted_pd), 4) from {SCORED}",
    ),
    (
        "How many applicants actually defaulted in the scored applications?",
        f"select count(*) from {SCORED} where is_default = 1",
    ),
    (
        "How many adverse-action explanations were generated?",
        f"select count(*) from {ACTIONS}",
    ),
]


def _eq(got, expected) -> bool:
    try:
        return abs(float(got) - float(expected)) < 1e-4
    except (TypeError, ValueError):
        return str(got).strip() == str(expected).strip()


def run() -> None:
    with _connect() as conn, conn.cursor() as cur:
        expected = []
        for _, ref_sql in GOLD:
            cur.execute(ref_sql)
            expected.append(cur.fetchone()[0])

    passed = 0
    for (question, _), want in zip(GOLD, expected):
        try:
            sql_text, rows = answer(question)
            got = rows[0][0] if rows and rows[0] else None
            ok = _eq(got, want)
        except Exception as exc:  # refused or execution error -> a miss
            sql_text, got, ok = f"(refused: {exc})", None, False
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {question}")
        print(f"       expected={want!r} got={got!r}")
        print(f"       sql: {sql_text.splitlines()[0] if isinstance(sql_text, str) else sql_text}\n")

    n = len(GOLD)
    print(f"NL->SQL gold-question accuracy: {passed}/{n} ({100 * passed / n:.0f}%)")


if __name__ == "__main__":
    run()
