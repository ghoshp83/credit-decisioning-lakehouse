"""Calibrate the PD model's probabilities and measure fairness slices.

A ranking model can separate defaulters well (good AUC/KS) yet output
probabilities that do not match observed default rates — useless for a lending
decision that must reason about *actual* risk. Isotonic calibration maps raw
scores onto well-calibrated probabilities; Brier score and a reliability table
quantify the improvement. Fairness is reported per available proxy slice so the
model card states real numbers, not a hand-wave.

Run from the repo root (after ml/train.py):

    .venv-ml/bin/python -m ml.calibrate
"""

from __future__ import annotations

from pathlib import Path

import joblib
import mlflow
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

from ml.dataset import SEED, TARGET, feature_columns

DATA_DIR = Path(__file__).parent / "data"
MODEL_PATH = DATA_DIR / "model.joblib"
TEST_PATH = DATA_DIR / "test.parquet"
CALIBRATOR_PATH = DATA_DIR / "calibrator.joblib"
EXPERIMENT = "credit_pd"


def main() -> None:
    import pandas as pd

    model = joblib.load(MODEL_PATH)
    test_df = pd.read_parquet(TEST_PATH)
    for col in ("contract_type",):
        test_df[col] = test_df[col].astype("category")
    features = feature_columns(test_df)

    # Split the holdout into a calibration fold (fit the calibrator) and an
    # evaluation fold (measure calibration honestly on unseen rows).
    cal_df, eval_df = train_test_split(
        test_df, test_size=0.5, stratify=test_df[TARGET], random_state=SEED
    )
    cal_raw = model.predict_proba(cal_df[features])[:, 1]
    eval_raw = model.predict_proba(eval_df[features])[:, 1]
    eval_y = eval_df[TARGET].to_numpy()

    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(cal_raw, cal_df[TARGET].to_numpy())
    eval_cal = iso.predict(eval_raw)

    brier_raw = brier_score_loss(eval_y, eval_raw)
    brier_cal = brier_score_loss(eval_y, eval_cal)
    auc = roc_auc_score(eval_y, eval_cal)

    print(f"AUC (eval)        = {auc:.4f}")
    print(f"Brier raw         = {brier_raw:.4f}")
    print(f"Brier calibrated  = {brier_cal:.4f}  ({'better' if brier_cal < brier_raw else 'worse'})")

    print("\nReliability (calibrated, deciles): pred -> observed")
    frac_pos, mean_pred = calibration_curve(eval_y, eval_cal, n_bins=10, strategy="quantile")
    for p, o in zip(mean_pred, frac_pos):
        print(f"  {p:.3f} -> {o:.3f}")

    print("\nFairness slices by contract_type: n, observed_rate, mean_pred, auc")
    for slice_val, grp in eval_df.assign(_cal=eval_cal).groupby("contract_type", observed=True):
        y = grp[TARGET].to_numpy()
        rate = y.mean()
        mean_pred_s = grp["_cal"].mean()
        slice_auc = roc_auc_score(y, grp["_cal"]) if len(np.unique(y)) > 1 else float("nan")
        print(f"  {slice_val:<16} n={len(grp):>6,}  rate={rate:.4f}  pred={mean_pred_s:.4f}  auc={slice_auc:.4f}")

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="calibration"):
        mlflow.log_metric("auc_eval", auc)
        mlflow.log_metric("brier_raw", brier_raw)
        mlflow.log_metric("brier_calibrated", brier_cal)

    joblib.dump(iso, CALIBRATOR_PATH)
    print(f"\nSaved calibrator -> {CALIBRATOR_PATH}")


if __name__ == "__main__":
    main()
