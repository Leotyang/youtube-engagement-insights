"""Black-box baseline: raw engagement metrics -> log(views).

A sanity-check model before any trait features exist. Chronological split (train on
older videos, test on newer) per README §4.8 to avoid lookahead bias.

Usage:  python -m src.model
Colab:  from src import model; rf = model.fit_or_skip(df_videos)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

BASELINE_FEATURES = ["like_count", "comment_count", "duration_seconds"]
BASELINE_TARGET = "view_count"


def fit_baseline_model(df_videos):
    df_model = df_videos.dropna(subset=BASELINE_FEATURES + [BASELINE_TARGET]).copy()
    df_model["published_at"] = pd.to_datetime(df_model["published_at"])
    df_model = df_model.sort_values("published_at")

    split_at = int(len(df_model) * 0.8)
    df_train = df_model.iloc[:split_at]
    df_test = df_model.iloc[split_at:]

    rf = RandomForestRegressor(n_estimators=200, random_state=0)
    rf.fit(df_train[BASELINE_FEATURES], np.log1p(df_train[BASELINE_TARGET]))
    preds = rf.predict(df_test[BASELINE_FEATURES])
    y_test = np.log1p(df_test[BASELINE_TARGET])

    print(f"Train: {len(df_train)} videos through {df_train['published_at'].max().date()}; test: {len(df_test)} newer videos")
    print(f"R^2 (log views): {r2_score(y_test, preds):.3f}")
    print(f"MAE (log views): {mean_absolute_error(y_test, preds):.3f}")
    for feature, importance in sorted(zip(BASELINE_FEATURES, rf.feature_importances_), key=lambda pair: -pair[1]):
        print(f"  {feature}: {importance:.3f}")
    return rf


def fit_or_skip(df_videos):
    if df_videos.empty or len(df_videos) < 10:
        print("Need at least ~10 ingested videos to fit the baseline model; run ingest first.")
        return None
    return fit_baseline_model(df_videos)


if __name__ == "__main__":
    from src import ingest

    fit_or_skip(ingest.load_or_ingest())
