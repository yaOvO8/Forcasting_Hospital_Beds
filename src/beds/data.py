"""Data half of the pipeline: download -> raw -> staging -> validation -> clean.

Owner: Data lead. Integration lead keeps the CLI and regenerate working.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import duckdb
import pandas as pd

from beds import config as C


# ---------------------------------------------------------------- download
def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def read_sums(path: Path = C.SHA256SUMS) -> dict[str, str]:
    """Parse a SHA256SUMS file: '<hash>  <relative path>' per line."""
    if not path.exists():
        return {}
    sums = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            digest, name = line.split(maxsplit=1)
            sums[name.lstrip("*")] = digest
    return sums


def write_sum(name: str, digest: str, path: Path = C.SHA256SUMS) -> None:
    sums = read_sums(path)
    sums[name] = digest
    lines = ["# sha256 of raw files as downloaded. Check: shasum -a 256 -c SHA256SUMS"]
    lines += [f"{d}  {n}" for n, d in sorted(sums.items())]
    path.write_text("\n".join(lines) + "\n")


def download(force: bool = False, accept_new_checksum: bool = False) -> Path:
    """Download the raw CSV and check it against SHA256SUMS.

    The first person to download pins the hash (commit SHA256SUMS). After that,
    a different file is an error unless --accept-new-checksum is given, so the
    whole team provably trains on the same bytes.
    """
    C.RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = C.RAW_CSV
    rel = dest.relative_to(C.ROOT).as_posix()

    if dest.exists() and not force:
        print(f"{rel} already exists; checking hash (use --force to re-download)")
    else:
        part = dest.with_suffix(".csv.part")
        req = urllib.request.Request(C.DOWNLOAD_URL, headers={"User-Agent": "hospital-beds-06763/0.1"})
        print(f"downloading {C.DOWNLOAD_URL}\n  -> {rel}")
        t0, done = time.time(), 0
        with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as out:
            while block := resp.read(1 << 20):
                out.write(block)
                done += len(block)
                print(f"\r  {done / 1e6:,.0f} MB  ({time.time() - t0:.0f}s)", end="", file=sys.stderr)
        print(file=sys.stderr)
        shutil.move(part, dest)

    digest = sha256_of(dest)
    pinned = read_sums().get(rel)
    if pinned is None:
        write_sum(rel, digest)
        print(f"pinned new hash in SHA256SUMS: {digest[:16]}...  -> commit SHA256SUMS")
    elif pinned == digest:
        print(f"hash OK: {digest[:16]}... matches SHA256SUMS")
    elif accept_new_checksum:
        write_sum(rel, digest)
        print(f"hash CHANGED and accepted: {pinned[:16]}... -> {digest[:16]}...  -> commit SHA256SUMS and tell the team")
    else:
        raise SystemExit(
            f"hash MISMATCH for {rel}\n  pinned:     {pinned}\n  downloaded: {digest}\n"
            "The source file changed. Re-run with --accept-new-checksum only after the team agrees."
        )
    return dest


# ---------------------------------------------------------------- SQL pipeline
def connect(path: Path = C.DB_PATH) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def _sql(name: str) -> str:
    text = (C.SQL_DIR / name).read_text()
    return text.format(
        raw_csv=C.RAW_CSV.as_posix(),
        target=C.TARGET,
        capacity=C.CAPACITY,
        suppressed=C.SUPPRESSED,
        fill=C.SUPPRESSED_FILL,
        train_start=C.TRAIN_START.isoformat(),
        test_end=C.TEST_END.isoformat(),
    )


def ingest(con: duckdb.DuckDBPyConnection) -> int:
    if not C.RAW_CSV.exists():
        raise SystemExit(f"{C.RAW_CSV} not found. Run: uv run beds download")
    con.execute(_sql("01_raw.sql"))
    return con.execute("SELECT count(*) FROM raw").fetchone()[0]


def build(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Run staging, validation and clean; return the counts table."""
    for name in ("02_staging.sql", "03_validate.sql", "04_clean.sql"):
        con.execute(_sql(name))
    counts = counts_table(con)
    C.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY clean TO '{(C.CLEAN_DIR / 'clean.parquet').as_posix()}' (FORMAT parquet)")
    return counts


HARD_RULES = [
    ("r_missing_key", "no hospital key"),
    ("r_bad_week", "collection_week did not parse"),
    ("r_out_of_window", f"week outside {C.TRAIN_START}..{C.TEST_END}"),
    ("r_duplicate", "duplicate hospital-week (kept first / corrected)"),
    ("r_target_missing", f"{C.TARGET} missing"),
    ("r_target_negative", f"{C.TARGET} negative (not the sentinel)"),
]
FLAG_RULES = [
    ("r_target_suppressed", "target suppressed (-999999): kept, y_measured NULL"),
    ("r_used_gt_capacity", "beds used > inpatient beds: kept, flagged"),
    ("r_capacity_unknown", "capacity missing or suppressed: kept"),
]


def counts_table(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Waterfall: rows arrived -> each HARD rule removes rows in order -> survived.

    Rules are applied in order, so each row is counted under the FIRST rule it
    fails and the removed counts add up exactly to arrived - survived.
    FLAG rules are reported on the surviving rows and remove nothing.
    """
    rows = []
    arrived = con.execute("SELECT count(*) FROM raw").fetchone()[0]
    rows.append(("arrived", "rows in the raw CSV", arrived, arrived))
    excluded: list[str] = []
    remaining = arrived
    for col, desc in HARD_RULES:
        prior = " AND ".join(f"NOT {c}" for c in excluded) or "true"
        n = con.execute(f"SELECT count(*) FROM validation WHERE {prior} AND {col}").fetchone()[0]
        remaining -= n
        rows.append((f"removed: {col}", desc, -n, remaining))
        excluded.append(col)
    survived = con.execute("SELECT count(*) FROM clean").fetchone()[0]
    assert survived == remaining, (survived, remaining)
    rows.append(("survived", "rows in data/clean/clean.parquet", survived, survived))
    keep = " AND ".join(f"NOT {c}" for c, _ in HARD_RULES)
    for col, desc in FLAG_RULES:
        n = con.execute(f"SELECT count(*) FROM validation WHERE {keep} AND {col}").fetchone()[0]
        rows.append((f"flagged: {col}", desc, n, survived))
    n_measured = con.execute("SELECT count(*) FROM clean WHERE y_measured IS NOT NULL").fetchone()[0]
    rows.append(("measured target", "survived rows with a measured target", n_measured, survived))
    n_hosp = con.execute("SELECT count(DISTINCT hospital_pk) FROM clean").fetchone()[0]
    rows.append(("hospitals", "distinct hospitals in clean", n_hosp, n_hosp))
    return pd.DataFrame(rows, columns=["step", "description", "rows", "running_total"])
