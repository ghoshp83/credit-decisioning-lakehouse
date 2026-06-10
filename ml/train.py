"""Train the LightGBM probability-of-default model with MLflow tracking.

Gradient boosting is the honest state-of-the-art for tabular credit risk — this
is where traditional ML beats an LLM on accuracy, cost, and latency, so the LLM
stays out of the prediction path. Runs are tracked in a local MLflow file store
(``mlruns/``); the fitted model and the holdout are persisted to the local
training boundary for the calibration and SHAP steps that follow.

Run from the repo root:

    .venv-ml/bin/python -m ml.train
"""

from __future__ import annotations

from pathlib import Path

import joblib
import lightgbm as lgb
import mlflow
import mlflow.lightgbm
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score

from ml.dataset import TARGET, feature_columns, load_features, split

DATA_DIR = Path(__file__).parent / "data"
MODEL_PATH = DATA_DIR / "model.joblib"
TEST_PATH = DATA_DIR / "test.parquet"
EXPERIMENT = "credit_pd"

PARAMS = {
    "objective": "binary",
    "n_estimators": 500,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
}


def ks_statistic(y_true, scores) -> float:
    """Kolmogorov-Smirnov separation between defaulter and non-defaulter scores."""
    return ks_2samp(scores[y_true == 1], scores[y_true == 0]).statistic


def main() -> None:
    df = load_features()
    train_df, test_df = split(df)
    features = feature_columns(df)

    x_train, y_train = train_df[features], train_df[TARGET]
    x_test, y_test = test_df[features], test_df[TARGET]

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run() as run:
        model = lgb.LGBMClassifier(**PARAMS)
        model.fit(
            x_train,
            y_train,
            eval_set=[(x_test, y_test)],
            eval_metric="auc",
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )

        scores = model.predict_proba(x_test)[:, 1]
        auc = roc_auc_score(y_test, scores)
        ks = ks_statistic(y_test.to_numpy(), scores)

        mlflow.log_params(PARAMS)
        mlflow.log_metric("auc", auc)
        mlflow.log_metric("ks", ks)
        mlflow.log_metric("best_iteration", model.best_iteration_)
        mlflow.lightgbm.log_model(model.booster_, name="model")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        test_df.to_parquet(TEST_PATH, index=False)

        print(
            f"run_id={run.info.run_id}  AUC={auc:.4f}  KS={ks:.4f}  "
            f"best_iter={model.best_iteration_}  test_n={len(y_test):,}"
        )


if __name__ == "__main__":
    main()
