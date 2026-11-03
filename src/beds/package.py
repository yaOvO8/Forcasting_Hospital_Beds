"""Build the submission zip the course asks for.

Contents: every git-tracked file (so nothing untracked, e.g. a stray .env,
can sneak in), plus data/clean/ and results/. The raw CSV is included only if
the zip stays under the size limit; otherwise the grader uses
`uv run beds download`, checked against SHA256SUMS.
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

from beds import config as C

LIMIT_BYTES = 450 * 1024**2  # course limit is 500 MB; keep headroom
FORBIDDEN = (".env", ".key", "id_rsa")


def _tracked() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=C.ROOT, capture_output=True, text=True, check=True)
    return [C.ROOT / p for p in out.stdout.splitlines()]


def build_zip(name: str = "hospital-beds-submission.zip") -> Path:
    files = _tracked()
    files += [p for d in (C.CLEAN_DIR, C.RESULTS) for p in d.rglob("*") if p.is_file()]
    bad = [p for p in files if p.name.startswith(".env") or p.name.endswith(FORBIDDEN)]
    if bad:
        raise SystemExit(f"refusing to package secrets: {bad}")

    size = sum(p.stat().st_size for p in files)
    raw_included = C.RAW_CSV.exists() and size + C.RAW_CSV.stat().st_size < LIMIT_BYTES
    if raw_included:
        files.append(C.RAW_CSV)

    out_dir = C.ROOT / "submission"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / name
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(files)):
            z.write(p, Path("hospital-beds") / p.relative_to(C.ROOT))
    print(f"wrote {out.relative_to(C.ROOT)} ({out.stat().st_size / 1e6:.1f} MB); "
          f"raw CSV {'included' if raw_included else 'NOT included (download script + SHA256SUMS instead)'}")
    return out
