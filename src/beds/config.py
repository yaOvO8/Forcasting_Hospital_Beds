"""Every project-wide choice in one place.

If the team changes a decision (target, split dates, holdout fraction ...),
change it here and log it in docs/decisions.md. Nothing else should hard-code
these values.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW_DIR = DATA / "raw"
CLEAN_DIR = DATA / "clean"
RESULTS = ROOT / "results"
SQL_DIR = ROOT / "sql"
DB_PATH = DATA / "beds.duckdb"
SHA256SUMS = ROOT / "SHA256SUMS"

# ---------------------------------------------------------------- source
DATASET_ID = "anag-cw7u"
DATASET_URL = f"https://healthdata.gov/d/{DATASET_ID}"
# Socrata full CSV export. The dataset stopped updating in May 2024, so the
# file should be stable; SHA256SUMS pins the exact bytes we used.
DOWNLOAD_URL = f"https://healthdata.gov/api/views/{DATASET_ID}/rows.csv?accessType=DOWNLOAD"
RAW_CSV = RAW_DIR / f"{DATASET_ID}.csv"

# HHS replaces sums and averages below 4 with this value (privacy suppression).
SUPPRESSED = -999999.0

# ---------------------------------------------------------------- target
# OPEN DECISION (team meeting): all inpatient beds vs ICU beds.
TARGET = "inpatient_beds_used_7_day_avg"
CAPACITY = "inpatient_beds_7_day_avg"

# ---------------------------------------------------------------- split
# Time split (never shuffled) plus a set of hospitals held out entirely.
TRAIN_START = date(2020, 8, 1)  # HHS: data available from 2020-07-31
TRAIN_END = date(2022, 12, 31)
VAL_END = date(2023, 6, 30)
TEST_END = date(2024, 4, 30)
HOLDOUT_FRACTION = 0.20  # share of hospitals never seen in training

# A "previous week" report is any report 4-10 days earlier. Matching on an
# exact 7-day gap breaks when HHS changed which weekday a collection week
# starts on (June 2023), so we match a window instead.
LAG_MIN_DAYS, LAG_MAX_DAYS = 4, 10
# Seasonal naive: the report closest to 52 weeks (364 days) earlier.
SEASONAL_DAYS, SEASONAL_TOL = 364, 3

# ---------------------------------------------------------------- suppression ablation
# How suppressed target values are treated before training. Evaluation is
# ALWAYS on measured (non-suppressed) rows, so every variant is scored on the
# same test set.
SUPPRESSION_VARIANTS = ("drop", "impute_mid", "impute_mid_flag")
# Suppressed means the true value was below 4, so 2.0 is the midpoint of [0, 4).
SUPPRESSED_FILL = 2.0
