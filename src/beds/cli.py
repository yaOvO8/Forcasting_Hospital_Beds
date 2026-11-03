"""Command line entry point: `uv run beds <command>`.

  download     fetch the raw CSV and check SHA256SUMS
  build        raw CSV -> DuckDB -> validation -> data/clean/clean.parquet + counts
  baselines    persistence and seasonal-naive predictions
  evaluate     score everything in results/predictions/
  regenerate   build + baselines + evaluate + figure: every number in the talk
  package      the submission zip
"""

from __future__ import annotations

import argparse

import pandas as pd

from beds import config as C

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)


def _build(con) -> None:
    from beds import data, splits

    n = data.ingest(con)
    print(f"loaded raw: {n:,} rows")
    counts = data.build(con)
    C.RESULTS.mkdir(exist_ok=True)
    counts.to_csv(C.RESULTS / "counts.csv", index=False)
    print("\n== counts (results/counts.csv) ==\n" + counts.to_string(index=False))
    split = splits.add_splits(con)
    split.to_csv(C.RESULTS / "split_summary.csv", index=False)
    print("\n== split (results/split_summary.csv) ==\n" + split.to_string(index=False))


def _baselines(con) -> None:
    from beds import baselines, evaluate

    preds = baselines.predict_baselines(con)
    for name, g in preds.groupby("model"):
        evaluate.save_predictions(g, name)
    print(f"\nwrote baseline predictions: {sorted(preds['model'].unique())}")


def _evaluate(con) -> pd.DataFrame:
    from beds import evaluate

    metrics = evaluate.score(con)
    metrics.to_csv(C.RESULTS / "metrics.csv", index=False)
    print("\n== test metrics (results/metrics.csv) ==\n" + metrics.to_string(index=False))
    return metrics


def _figure(con) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = con.execute("""
        SELECT t.collection_week, p.model, avg(abs(t.y_measured - p.y_pred)) AS mae
        FROM preds p JOIN panel t USING (hospital_pk, collection_week)
        WHERE t.split = 'test' AND t.y_measured IS NOT NULL AND p.quantile = 0.5
        GROUP BY ALL ORDER BY 1
    """).df()
    fig, ax = plt.subplots(figsize=(8, 3.5))
    for model, g in df.groupby("model"):
        ax.plot(g["collection_week"], g["mae"], label=model, lw=1.5)
    ax.set_ylabel("MAE (beds)")
    ax.set_title("Test-period error by week")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = C.RESULTS / "figures" / "test_mae_by_week.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"\nwrote {out.relative_to(C.ROOT)}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="beds")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download")
    d.add_argument("--force", action="store_true", help="re-download even if the file exists")
    d.add_argument("--accept-new-checksum", action="store_true")
    for name in ("build", "baselines", "evaluate", "regenerate", "package"):
        sub.add_parser(name)
    args = p.parse_args(argv)

    if args.cmd == "download":
        from beds import data

        data.download(force=args.force, accept_new_checksum=args.accept_new_checksum)
        return
    if args.cmd == "package":
        from beds import package

        package.build_zip()
        return

    from beds import data

    con = data.connect()
    if args.cmd in ("build", "regenerate"):
        _build(con)
    if args.cmd in ("baselines", "regenerate"):
        _baselines(con)
    if args.cmd in ("evaluate", "regenerate"):
        _evaluate(con)
    if args.cmd == "regenerate":
        _figure(con)


if __name__ == "__main__":
    main()
