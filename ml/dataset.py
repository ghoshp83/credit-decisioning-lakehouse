"""Shared dataset contract for the PD model.

Defining the feature list, the categorical columns, and the train/test split in
one place means training, calibration, and SHAP all see exactly the same data —
no silent divergence between steps.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

ID = "application_id"
TARGET = "is_default"
CATEGORICAL = ["contract_type"]
SEED = 42
TEST_SIZE = 0.2

FEATURES_PATH = Path(__file__).parent / "data" / "features.parquet"


def load_features(path: Path = FEATURES_PATH) -> pd.DataFrame:
    """Load the exported gold mart; type the categorical columns for LightGBM."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run ml/pull_features.py first")
    df = pd.read_parquet(path)
    for col in CATEGORICAL:
        df[col] = df[col].astype("category")
    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in (ID, TARGET)]


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified train/test split — deterministic so every step aligns."""
    return train_test_split(
        df, test_size=TEST_SIZE, stratify=df[TARGET], random_state=SEED
    )
