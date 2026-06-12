"""Score every applicant and write predictions + top SHAP drivers back to Delta.

This closes the lineage loop: the model's outputs re-enter the governed lakehouse
as a Delta table (wired into dbt as a source in the next layer), instead of
escaping into a notebook. For each applicant we keep the predicted PD and the
three features that pushed risk *up* the most (largest positive SHAP value) —
exactly the drivers a grounded adverse-action explanation may cite.

Write path mirrors the repo's raw-load pattern: stage the parquet into a Unity
Catalog Volume via the SQL connector's PUT, then CREATE TABLE AS read_files.
Auth via env vars only. Run from the repo root (after ml/train.py):

    DATABRICKS_HOST=... DATABRICKS_HTTP_PATH=... DATABRICKS_TOKEN=... \
      .venv-ml/bin/python -m ml.shap_drivers
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

from ml.dataset import ID, feature_columns, load_features

DATA_DIR = Path(__file__).parent / "data"
MODEL_PATH = DATA_DIR / "model.joblib"
PRED_PATH = DATA_DIR / "predictions.parquet"

CATALOG = os.environ.get("DBT_CATALOG", "workspace")
ML_SCHEMA = os.environ.get("ML_SCHEMA", "credit_ml")
VOLUME = "staging"
TABLE = "pd_predictions"
TOP_N = 3


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(
            f"FATAL: environment variable {name} is not set (see README auth section)"
        )
    return val


def compute_drivers() -> pd.DataFrame:
    """Predicted PD + the TOP_N most risk-increasing SHAP drivers per applicant."""
    model = joblib.load(MODEL_PATH)
    df = load_features()
    features = feature_columns(df)
    x = df[features]

    pd_hat = model.predict_proba(x)[:, 1]

    shap_vals = shap.TreeExplainer(model).shap_values(x)
    # LGBMClassifier binary: newer shap returns (n, n_features); older returns
    # [class0, class1]. Normalise to the positive-class matrix.
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]
    shap_vals = np.asarray(shap_vals)

    # Per row, rank features by SHAP descending (most risk-increasing first).
    order = np.argsort(-shap_vals, axis=1)[:, :TOP_N]
    feat_arr = np.array(features)

    out = pd.DataFrame({ID: df[ID].to_numpy(), "predicted_pd": pd_hat})
    for rank in range(TOP_N):
        idx = order[:, rank]
        out[f"top{rank + 1}_feature"] = feat_arr[idx]
        out[f"top{rank + 1}_shap"] = shap_vals[np.arange(len(df)), idx]
    return out


def write_delta(out: pd.DataFrame) -> None:
    from databricks import sql

    host = _require("DATABRICKS_HOST")
    http_path = _require("DATABRICKS_HTTP_PATH")
    token = _require("DATABRICKS_TOKEN")

    out.to_parquet(PRED_PATH, index=False)
    volume_path = f"/Volumes/{CATALOG}/{ML_SCHEMA}/{VOLUME}/{PRED_PATH.name}"
    fqtn = f"{CATALOG}.{ML_SCHEMA}.{TABLE}"

    with sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
        staging_allowed_local_path=str(DATA_DIR),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(f"create schema if not exists {CATALOG}.{ML_SCHEMA}")
            cur.execute(f"create volume if not exists {CATALOG}.{ML_SCHEMA}.{VOLUME}")
            cur.execute(f"put '{PRED_PATH}' into '{volume_path}' overwrite")
            cur.execute(
                f"create or replace table {fqtn} as "
                f"select * from read_files('{volume_path}', format => 'parquet')"
            )
            cur.execute(f"select count(*) from {fqtn}")
            n = cur.fetchone()[0]

    print(f"Wrote {fqtn}  rows={n:,}")


def main() -> None:
    out = compute_drivers()
    print(
        f"Scored {len(out):,} applicants  "
        f"mean_pd={out['predicted_pd'].mean():.4f}  "
        f"top1 drivers: {out['top1_feature'].value_counts().head(3).to_dict()}"
    )
    write_delta(out)


if __name__ == "__main__":
    main()
