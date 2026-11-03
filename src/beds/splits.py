"""Train / validation / test split: by time (never shuffled) plus held-out hospitals.

Each row gets:
  split          train | val | test   (by collection_week)
  holdout_hosp   true for hospitals that are never used for training

Models train on   split='train' AND NOT holdout_hosp
and are scored on split='test', reported separately for seen and held-out hospitals.
"""

from __future__ import annotations

import hashlib

import duckdb
import pandas as pd

from beds import config as C


def is_holdout(hospital_pk: str, fraction: float = C.HOLDOUT_FRACTION) -> bool:
    """Deterministic: the same hospital is always in or out, on every machine.

    Uses a hash of the ID rather than a random draw, so adding or removing
    other hospitals never changes this one's assignment.
    """
    h = int(hashlib.sha256(hospital_pk.encode()).hexdigest()[:8], 16)
    return (h % 10_000) < fraction * 10_000


def add_splits(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    hosp = con.execute("SELECT DISTINCT hospital_pk FROM clean").df()
    hosp["holdout_hosp"] = hosp["hospital_pk"].map(is_holdout)
    con.register("hosp_holdout", hosp)
    con.execute(f"""
        CREATE OR REPLACE TABLE panel AS
        SELECT c.*,
               CASE WHEN c.collection_week <= DATE '{C.TRAIN_END}' THEN 'train'
                    WHEN c.collection_week <= DATE '{C.VAL_END}'   THEN 'val'
                    ELSE 'test' END AS split,
               h.holdout_hosp
        FROM clean c JOIN hosp_holdout h USING (hospital_pk)
    """)
    con.unregister("hosp_holdout")
    return con.execute("""
        SELECT split, holdout_hosp,
               count(*) AS rows,
               count(y_measured) AS rows_measured,
               count(DISTINCT hospital_pk) AS hospitals,
               min(collection_week) AS first_week,
               max(collection_week) AS last_week
        FROM panel GROUP BY ALL ORDER BY split DESC, holdout_hosp
    """).df()
