# Forecasting Next Week's Hospital Beds

06-763 final project. Can a probabilistic forecast of a hospital's occupied
inpatient beds one week ahead beat "next week looks like this week" on unseen
weeks and hospitals, and does staffing to its upper quantile reduce shortfalls?

Data: US HHS, *COVID-19 Reported Patient Impact and Hospital Capacity by Facility*
([healthdata.gov `anag-cw7u`](https://healthdata.gov/d/anag-cw7u)), public domain
(U.S. Government work). Weekly reports per hospital, July 2020 to April 2024.

## Reproduce every number

Requires [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
uv sync                    # exact environment from uv.lock (Python 3.12)
uv run beds download       # raw CSV -> data/raw/, checked against SHA256SUMS
uv run beds regenerate     # clean data, splits, baselines, models, metrics, figures
```

Outputs land in `results/`:

| File | What it is |
|---|---|
| `counts.csv` | rows arrived → removed by each rule → survived, plus flagged rows |
| `split_summary.csv` | rows and hospitals per split, seen vs held-out hospitals |
| `predictions/<model>.parquet` | every model's predictions, one shared format |
| `metrics.csv` | test-set scores for every model |
| `figures/` | figures used in the talk |

`uv sync --no-group model` skips PyTorch and MLflow if you only work on data.
`uv run pytest` runs the pipeline end to end on a small synthetic file (no download needed).

## Pipeline

```
download ─► sql/01_raw.sql ─► 02_staging.sql ─► 03_validate.sql ─► 04_clean.sql ─► splits ─► baselines / models ─► evaluate
 (CSV +      (as received,     (typed columns,    (one boolean per    (data/clean/     (time +     (results/predictions/)  (results/metrics.csv)
 SHA256)      all text)         nothing dropped)   rule, per row)      clean.parquet)   hospitals)
```

Everything goes into one DuckDB file, `data/beds.duckdb` (tables `raw`,
`staging`, `validation`, `clean`, `panel`, `preds`), so any count can be
checked with SQL.

## Data decisions (current)

All project-wide choices live in [`src/beds/config.py`](src/beds/config.py). Change them there and log the change in [`docs/decisions.md`](docs/decisions.md).

- **Target:** `inpatient_beds_used_7_day_avg` (occupied staffed inpatient beds, weekly average).
- **Suppression:** HHS replaces values below 4 with `-999999`. Those rows are kept with `y_measured = NULL`, `is_suppressed = true`, and our fill-in (2.0, the midpoint of [0, 4)) in a separate column `y_fill_mid`. Measured and filled-in values are never mixed in one column.
- **Rows removed (hard rules):** missing hospital key, unparseable week, outside the study window, duplicate hospital-week, missing or negative target. Each is counted in `results/counts.csv`.
- **Rows kept but flagged:** suppressed target, beds used > beds available, capacity unknown.
- **Split:** by time, never shuffled — train 2020-08 to 2022-12, validate 2023-01 to 2023-06, test 2023-07 to 2024-04 — plus 20% of hospitals held out entirely (chosen by a hash of the hospital ID, so the assignment is identical on every machine).
- **Scoring:** only test rows with a *measured* target, so every model and every suppression treatment is compared on the same rows. Metrics are reported separately for seen and held-out hospitals.
- **Previous week:** the report 4–10 days earlier, not exactly 7. HHS changed which weekday a collection week starts on in June 2023, and an exact 7-day match would silently drop those weeks.

## Repository layout and owners

| Path | Contents | Lead |
|---|---|---|
| `sql/`, `src/beds/data.py` | download, cleaning SQL, validation, counts | Data (Vidhi) |
| `src/beds/models/` | PyTorch quantile model, MLflow runs | Model (Madhav) |
| `src/beds/baselines.py`, `splits.py` | trivial baselines, the split | Model (Madhav) |
| `src/beds/decision/` | interval coverage, newsvendor staffing | Uncertainty + decision (Suhani) |
| `src/beds/evaluate.py`, `cli.py`, `package.py`, `tests/` | scoring, `regenerate`, submission zip | Integration (Jiyao) |
| `docs/` | decisions log, handoff notes | everyone |

### The handoff contract

Any model plugs in by writing `results/predictions/<model>.parquet` with columns
`hospital_pk, collection_week, model, quantile, y_pred` (use
`beds.evaluate.save_predictions`). `quantile = 0.5` is the point forecast; add more
quantiles for intervals. `regenerate` scores every file in that folder with the same code.

## Working together

1. Branch per task: `git switch -c data/validation-rules`.
2. Run `uv run pytest` before pushing.
3. Open a pull request; one teammate reviews.
4. After each task, add a handoff note: copy `docs/handoff/TEMPLATE.md` to `docs/handoff/YYYY-MM-DD-<topic>.md`.
5. If you change a decision, add a line to `docs/decisions.md`.

Never commit data, `.env` files or API keys. `.gitignore` blocks the usual ones.

## Submission

`uv run beds package` builds `submission/hospital-beds-submission.zip` from
git-tracked files plus `data/clean/` and `results/`. The raw CSV is included only
if the zip stays under the size limit; otherwise graders run `uv run beds download`,
which checks `SHA256SUMS`.

## AI use

Parts of this repository's scaffolding were drafted with an AI assistant (Claude) and reviewed by the team.
