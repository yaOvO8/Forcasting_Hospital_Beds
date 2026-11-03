"""Shared scoring. Every model, baseline or not, is scored here.

PREDICTION CONTRACT (the handoff between the model and integration halves)
--------------------------------------------------------------------------
Write one parquet file per model to results/predictions/<model>.parquet with:

    hospital_pk      str
    collection_week  date    the week being predicted (the target week)
    model            str     e.g. "persistence", "mlp_pinball"
    quantile         float   0.5 for a point forecast; add 0.1, 0.9, ... for intervals
    y_pred           float   predicted occupied inpatient beds

Rows can cover any split; only split='test' rows with a MEASURED target are
scored, so every model and every suppression variant is compared on the same
rows (see `common_rows` in the output).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from beds import config as C

PRED_DIR = C.RESULTS / "predictions"
CONTRACT = ["hospital_pk", "collection_week", "model", "quantile", "y_pred"]


def save_predictions(df: pd.DataFrame, name: str) -> Path:
    missing = set(CONTRACT) - set(df.columns)
    if missing:
        raise ValueError(f"predictions for {name} missing columns {missing}")
    out = df[CONTRACT].copy()
    out["hospital_pk"] = out["hospital_pk"].astype(str)
    out["collection_week"] = pd.to_datetime(out["collection_week"]).dt.date  # parquet date32
    out["quantile"] = out["quantile"].astype(float)
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    path = PRED_DIR / f"{name}.parquet"
    out.to_parquet(path, index=False)
    return path


def pinball(y: np.ndarray, q_pred: np.ndarray, q: float) -> float:
    d = y - q_pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def score(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    files = sorted(PRED_DIR.glob("*.parquet"))
    if not files:
        raise SystemExit("no predictions in results/predictions/")
    con.execute(f"""
        CREATE OR REPLACE TABLE preds AS
        SELECT * FROM read_parquet([{", ".join(f"'{f.as_posix()}'" for f in files)}], union_by_name = true)
    """)
    scored = con.execute("""
        SELECT p.model, p.quantile, p.y_pred, t.y_measured AS y, t.holdout_hosp,
               t.hospital_pk, t.collection_week
        FROM preds p JOIN panel t USING (hospital_pk, collection_week)
        WHERE t.split = 'test' AND t.y_measured IS NOT NULL
    """).df()

    # Rows every model has a median for: the fair head-to-head set.
    med = scored[scored["quantile"] == 0.5]
    n_models = med["model"].nunique()
    key = ["hospital_pk", "collection_week"]
    common = med.groupby(key)["model"].nunique().loc[lambda s: s == n_models].index

    out = []
    for (model, holdout), g in scored.groupby(["model", "holdout_hosp"]):
        m = g[g["quantile"] == 0.5]
        mc = m.set_index(key).loc[lambda d: d.index.isin(common)]
        row = {
            "model": model,
            "hospitals": "held-out" if holdout else "seen",
            "rows_scored": len(m),
            "MAE": float(np.mean(np.abs(m["y"] - m["y_pred"]))) if len(m) else np.nan,
            "WAPE": float(np.sum(np.abs(m["y"] - m["y_pred"])) / np.sum(m["y"])) if len(m) else np.nan,
            "common_rows": len(mc),
            "MAE_common": float(np.mean(np.abs(mc["y"] - mc["y_pred"]))) if len(mc) else np.nan,
        }
        qs = sorted(g["quantile"].unique())
        if len(qs) > 1:
            row["pinball_mean"] = float(np.mean([pinball(g.loc[g["quantile"] == q, "y"].to_numpy(),
                                                         g.loc[g["quantile"] == q, "y_pred"].to_numpy(), q)
                                                  for q in qs]))
            lo, hi = qs[0], qs[-1]
            w = g.pivot_table(index=key, columns="quantile", values="y_pred").join(
                m.set_index(key)["y"])
            row[f"coverage_{lo:g}_{hi:g}"] = float(((w["y"] >= w[lo]) & (w["y"] <= w[hi])).mean())
        out.append(row)
    return pd.DataFrame(out).sort_values(["hospitals", "MAE_common"])
