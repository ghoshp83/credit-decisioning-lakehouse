"""Validated natural-language -> SQL over the governed marts.

The anti-fake-AI contract for this layer: the LLM only *drafts* SQL from a plain
question; it never touches data directly and its output is never trusted. Every
draft passes three deterministic gates before it runs --

  1. read-only        -- must be a single SELECT/WITH statement, no DML/DDL.
  2. table allowlist   -- may reference only the published marts.
  3. server EXPLAIN    -- Databricks must accept the plan (real columns/types).

Any gate failing raises -- the question is refused, never answered with
unvalidated or hallucinated SQL. The LLM call itself is ai_query run through the
same SQL connection, so the whole flow stays inside the lakehouse with no
external API or secret.

Run:  .venv-ai/bin/python -m ai.nl_to_sql "how many applicants were declined?"
Auth via env: DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN.
"""

from __future__ import annotations

import os
import re
import sys

from databricks import sql

CATALOG = os.environ.get("DBT_CATALOG", "workspace")
MART_SCHEMA = os.environ.get("MART_SCHEMA", "credit_dev_marts")
LLM_ENDPOINT = os.environ.get("NL_SQL_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")

# The only tables the generated SQL may read. Unqualified and catalog-qualified
# forms are both accepted so the model can write either.
ALLOWED_TABLES = {"fct_applications", "fct_scored_applications", "fct_adverse_actions"}

# Statement-level write/DDL verbs that must never appear in a read-only query.
FORBIDDEN = [
    "insert", "update", "delete", "merge", "drop", "alter", "create",
    "truncate", "grant", "revoke", "replace", "refresh", "copy", "into",
]


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(f"Missing required env var: {name}")
    return val


def _connect():
    return sql.connect(
        server_hostname=_require("DATABRICKS_HOST"),
        http_path=_require("DATABRICKS_HTTP_PATH"),
        access_token=_require("DATABRICKS_TOKEN"),
    )


def schema_context(cur) -> str:
    """Build a compact schema description of the allowed marts from
    information_schema, so the prompt is grounded in the real columns and can
    never drift from what the marts actually expose."""
    table_list = ", ".join(f"'{t}'" for t in sorted(ALLOWED_TABLES))
    cur.execute(
        f"""
        select table_name, column_name, data_type
        from {CATALOG}.information_schema.columns
        where table_schema = '{MART_SCHEMA}' and table_name in ({table_list})
        order by table_name, ordinal_position
        """
    )
    cols: dict[str, list[str]] = {}
    for table_name, column_name, data_type in cur.fetchall():
        cols.setdefault(table_name, []).append(f"{column_name} {data_type}")
    if not cols:
        raise SystemExit(
            f"No columns found for {sorted(ALLOWED_TABLES)} in "
            f"{CATALOG}.{MART_SCHEMA} -- are the marts built?"
        )
    lines = [
        f"{CATALOG}.{MART_SCHEMA}.{t} ({', '.join(cols[t])})"
        for t in sorted(cols)
    ]
    return "\n".join(lines)


def generate_sql(cur, question: str, schema: str) -> str:
    """Ask the in-lakehouse LLM to draft one read-only SELECT for the question."""
    prompt = (
        "You are a Databricks SQL assistant. Given the schema below, write ONE "
        "read-only SELECT query (Databricks SQL dialect) that answers the "
        "question. Use only the listed tables and columns. Do not modify data. "
        "Return ONLY the SQL, with no markdown fences and no explanation.\n\n"
        f"Schema:\n{schema}\n\nQuestion: {question}"
    )
    cur.execute(
        f"select ai_query('{LLM_ENDPOINT}', :prompt) as sql_text",
        {"prompt": prompt},
    )
    return _strip(cur.fetchone()[0])


def _strip(text: str) -> str:
    """Remove markdown fences / stray prose the model may wrap around the SQL."""
    text = text.strip()
    fence = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return text.rstrip(";").strip()


def validate(sql_text: str) -> None:
    """Three deterministic gates. Raise on any violation -- fail loud, never
    run unvalidated SQL."""
    lowered = sql_text.lower()

    if ";" in sql_text.rstrip(";"):
        raise ValueError(f"Refused: multiple statements.\n{sql_text}")

    if not re.match(r"^\s*(select|with)\b", lowered):
        raise ValueError(f"Refused: not a SELECT/WITH query.\n{sql_text}")

    for verb in FORBIDDEN:
        if re.search(rf"\b{verb}\b", lowered):
            raise ValueError(f"Refused: contains forbidden keyword '{verb}'.\n{sql_text}")

    referenced = set(re.findall(r"\b(?:from|join)\s+([a-zA-Z0-9_.]+)", lowered))
    for table in referenced:
        bare = table.split(".")[-1]
        if bare not in ALLOWED_TABLES:
            raise ValueError(
                f"Refused: references non-allowlisted table '{table}'.\n{sql_text}"
            )


def explain(cur, sql_text: str) -> None:
    """Final gate: the server must accept the plan. A hallucinated column or
    type mismatch surfaces here as an error rather than as a wrong answer."""
    cur.execute(f"explain {sql_text}")
    plan = "\n".join(str(row[0]) for row in cur.fetchall())
    if "Error" in plan or "cannot resolve" in plan.lower():
        raise ValueError(f"Refused: EXPLAIN reported an error.\n{plan}")


def answer(question: str) -> tuple[str, list[tuple]]:
    """End-to-end: draft -> validate -> EXPLAIN -> execute. Returns the SQL and
    rows, or raises if the draft fails any gate."""
    with _connect() as conn, conn.cursor() as cur:
        schema = schema_context(cur)
        sql_text = generate_sql(cur, question, schema)
        validate(sql_text)
        explain(cur, sql_text)
        cur.execute(sql_text)
        rows = cur.fetchall()
    return sql_text, rows


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m ai.nl_to_sql "your question"')
    question = " ".join(sys.argv[1:])
    sql_text, rows = answer(question)
    print(f"-- validated SQL\n{sql_text}\n")
    for row in rows[:50]:
        print(row)
    print(f"\n({len(rows)} row(s))")


if __name__ == "__main__":
    main()
