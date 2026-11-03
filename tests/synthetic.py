"""Small fake CSV with the real file's column names and its known problems,
so the pipeline can be tested without the 1M-row download."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np

COLUMNS = [
    "hospital_pk", "collection_week", "state", "ccn", "hospital_name", "hospital_subtype",
    "is_metro_micro", "is_corrected",
    "inpatient_beds_used_7_day_avg", "inpatient_beds_7_day_avg", "inpatient_beds_used_7_day_coverage",
    "total_beds_7_day_avg", "inpatient_beds_used_covid_7_day_avg",
    "total_patients_hospitalized_confirmed_influenza_7_day_avg",
    "icu_beds_used_7_day_avg", "total_icu_beds_7_day_avg", "address",
]


def weeks() -> list[date]:
    """Sunday-start weeks, then a 2-day shift in mid-2023 like the HHS change."""
    out, d = [], date(2019, 12, 29)
    while d <= date(2024, 4, 21):
        out.append(d)
        d += timedelta(days=7)
    return [w if w < date(2023, 6, 19) else w + timedelta(days=2) for w in out]


def make_csv(path: Path, n_hosp: int = 40, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    rows, expected = [], {"duplicate": 0, "missing_key": 0, "bad_week": 0, "suppressed": 0,
                          "used_gt_capacity": 0, "target_missing": 0}
    ws = weeks()
    for h in range(n_hosp):
        pk = f"{100000 + h}"
        cap = float(rng.integers(8, 400))
        level = cap * rng.uniform(0.5, 0.85)
        for i, w in enumerate(ws):
            if rng.random() < 0.03:  # reporting gap
                continue
            season = 1 + 0.1 * np.sin(2 * np.pi * i / 52)
            y = max(0.0, level * season + rng.normal(0, cap * 0.03))
            y_txt = f"{y:.1f}"
            if y < 4:
                y_txt = "-999999"
            rows.append({
                "hospital_pk": pk, "collection_week": w.strftime("%Y/%m/%d"), "state": "PA",
                "ccn": pk, "hospital_name": f"Hospital {h}, Inc.", "hospital_subtype": "Short Term",
                "is_metro_micro": "true", "is_corrected": "false",
                "inpatient_beds_used_7_day_avg": y_txt, "inpatient_beds_7_day_avg": f"{cap:.1f}",
                "inpatient_beds_used_7_day_coverage": "7", "total_beds_7_day_avg": f"{cap * 1.1:.1f}",
                "inpatient_beds_used_covid_7_day_avg": "-999999" if rng.random() < 0.3 else f"{rng.uniform(4, 20):.1f}",
                "total_patients_hospitalized_confirmed_influenza_7_day_avg": "",
                "icu_beds_used_7_day_avg": "5.0", "total_icu_beds_7_day_avg": "10.0",
                "address": "1 Main St, Pittsburgh",
            })
    # Inject the known problems inside the study window (rows ~100-170 are
    # hospital 0 in 2021-2023), so no earlier rule removes them first.
    assert rows[170]["hospital_pk"] == "100000" and rows[100]["collection_week"] > "2020/08/01"
    rows[100]["inpatient_beds_used_7_day_avg"] = "-999,999"    # comma form of the sentinel
    rows[110]["inpatient_beds_used_7_day_avg"] = "100.9"       # used > capacity
    rows[110]["inpatient_beds_7_day_avg"] = "96.1"
    rows[120]["inpatient_beds_used_7_day_avg"] = ""            # missing target
    rows[130]["hospital_pk"] = ""                              # missing key
    rows[140]["collection_week"] = "not a date"                # bad week
    rows.append(dict(rows[160]))                               # exact duplicate
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return {"rows": len(rows)}
