"""End-to-end test on synthetic data: `uv run pytest`."""

from __future__ import annotations

import pandas as pd
import pytest

from beds import config as C
from beds import cli, evaluate
from tests.synthetic import make_csv


@pytest.fixture()
def project(tmp_path, monkeypatch):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    csv_path = raw / "anag-cw7u.csv"
    info = make_csv(csv_path)
    monkeypatch.setattr(C, "RAW_CSV", csv_path)
    monkeypatch.setattr(C, "DB_PATH", tmp_path / "data" / "beds.duckdb")
    monkeypatch.setattr(C, "CLEAN_DIR", tmp_path / "data" / "clean")
    monkeypatch.setattr(C, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(evaluate, "PRED_DIR", tmp_path / "results" / "predictions")
    cli.main(["regenerate"])
    return tmp_path, info


def test_counts_add_up(project):
    root, info = project
    counts = pd.read_csv(root / "results" / "counts.csv").set_index("step")
    assert counts.loc["arrived", "rows"] == info["rows"]
    removed = counts.filter(like="removed:", axis=0)["rows"].sum()
    assert counts.loc["arrived", "rows"] + removed == counts.loc["survived", "rows"]
    for rule in ("r_missing_key", "r_bad_week", "r_duplicate", "r_target_missing"):
        assert counts.loc[f"removed: {rule}", "rows"] <= -1, rule
    assert counts.loc["flagged: r_used_gt_capacity", "rows"] >= 1
    assert counts.loc["flagged: r_target_suppressed", "rows"] >= 1  # incl. "-999,999"


def test_measured_and_filled_kept_apart(project):
    root, _ = project
    clean = pd.read_parquet(root / "data" / "clean" / "clean.parquet")
    assert (clean["y_measured"].dropna() >= 0).all()
    supp = clean[clean["is_suppressed"]]
    assert supp["y_measured"].isna().all() and (supp["y_fill_mid"] == C.SUPPRESSED_FILL).all()
    assert clean.loc[~clean["is_suppressed"], "y_fill_mid"].isna().all()
    assert not clean.duplicated(["hospital_pk", "collection_week"]).any()


def test_baselines_scored_on_test_only(project):
    root, _ = project
    m = pd.read_csv(root / "results" / "metrics.csv")
    assert set(m["model"]) == {"persistence", "seasonal_naive"}
    assert set(m["hospitals"]) == {"seen", "held-out"}
    assert (m["MAE"] > 0).all()
    # persistence must survive the 2023 weekday shift: no big hole in coverage
    p = m[m["model"] == "persistence"]["rows_scored"].sum()
    s = m[m["model"] == "seasonal_naive"]["rows_scored"].sum()
    assert p > 0.8 * s
    assert (root / "results" / "figures" / "test_mae_by_week.png").exists()
