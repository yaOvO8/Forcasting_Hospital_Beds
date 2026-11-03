"""Trivial baselines every model must beat.

  persistence     next week = this week (the report 4-10 days earlier)
  seasonal_naive  next week = the same week last year (report 361-367 days earlier)

Both write predictions in the shared contract (see evaluate.py), so they are
scored by exactly the same code as the neural model.

The previous report's value is its measured value, or the filled-in value when
it was suppressed: a planner looking at last week sees "below 4", not nothing.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from beds import config as C


def _lagged(con: duckdb.DuckDBPyConnection, name: str, min_days: int, max_days: int) -> pd.DataFrame:
    """For each target row, the latest report at least `min_days` earlier,
    kept only if it is at most `max_days` earlier (otherwise no prediction).
    ASOF matching tolerates gaps and the 2023 change in collection-week weekday."""
    return con.execute(f"""
        WITH prior AS (
            SELECT hospital_pk,
                   collection_week AS src_week,
                   collection_week + INTERVAL {min_days} DAY AS avail_from,
                   COALESCE(y_measured, y_fill_mid) AS y_prev
            FROM panel
        )
        SELECT t.hospital_pk, t.collection_week,
               '{name}' AS model, 0.5 AS quantile,
               CASE WHEN date_diff('day', p.src_week, t.collection_week) <= {max_days}
                    THEN p.y_prev END AS y_pred
        FROM panel t
        ASOF LEFT JOIN prior p
          ON t.hospital_pk = p.hospital_pk AND t.collection_week >= p.avail_from
    """).df()


def predict_baselines(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    persistence = _lagged(con, "persistence", C.LAG_MIN_DAYS, C.LAG_MAX_DAYS)
    seasonal = _lagged(con, "seasonal_naive", C.SEASONAL_DAYS - C.SEASONAL_TOL, C.SEASONAL_DAYS + C.SEASONAL_TOL)
    preds = pd.concat([persistence, seasonal], ignore_index=True)
    return preds.dropna(subset=["y_pred"])
