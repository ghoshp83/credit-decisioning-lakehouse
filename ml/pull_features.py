"""Pull the gold feature mart from Databricks into a local parquet.

The dbt mart ``fct_applications`` is the single source of truth for model
features — training reads from it rather than re-deriving features in pandas, so
there is exactly one definition of every feature (lineage stays intact from raw
row to model input). This script is the train/serve boundary: it materialises
one snapshot of the mart locally for offline training.

Auth is via environment variables (never hard-coded) — see README. Run:

    DATABRICKS_HOST=dbc-xxxx.cloud.databricks.com \
    DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxx \
    DATABRICKS_TOKEN=<short-lived PAT> \
    .venv-ml/bin/python ml/pull_features.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from databricks import sql

CATALOG = os.environ.get("DBT_CATALOG", "workspace")
MART_SCHEMA = os.environ.get("MART_SCHEMA", "credit_dev_marts")
TABLE = "fct_applications"
OUT = Path(__file__).parent / "data" / "features.parquet"


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(
            f"FATAL: environment variable {name} is not set (see README auth section)"
        )
    return val


def main() -> None:
    host = _require("DATABRICKS_HOST")
    http_path = _require("DATABRICKS_HTTP_PATH")
    token = _require("DATABRICKS_TOKEN")

    fqtn = f"{CATALOG}.{MART_SCHEMA}.{TABLE}"
    print(f"Pulling {fqtn} from {host} ...")

    with sql.connect(
        server_hostname=host, http_path=http_path, access_token=token
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select * from {fqtn}")
            df = cur.fetchall_arrow().to_pandas()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    default_rate = df["is_default"].mean()
    print(
        f"Wrote {OUT}  rows={len(df):,}  cols={df.shape[1]}  default_rate={default_rate:.4f}"
    )


if __name__ == "__main__":
    main()
