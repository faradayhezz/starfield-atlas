"""Reproduce telescope-image import and blind-solve boundary tests, offline.

Run from the repository root after setup:
    python scripts/benchmark_telescope_images.py

JSON goes to stdout; progress goes to stderr. Jobs use a temporary directory.
No source-page coordinates, object IDs or field hints are sent to the pipeline.
An unexpected solution is NOT accepted as valid without independent validation.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.image_io import load_native
from backend.pipeline import analyze_image

FIXTURES = ROOT / "tests" / "network-fixtures"


def main() -> int:
    manifest = json.loads((FIXTURES / "TELESCOPE_SOURCES.json").read_text(encoding="utf-8"))
    report = {
        "testedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "applicationCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": platform.python_version(),
        "platform": platform.system(),
        "pipeline": "backend.pipeline.analyze_image; defaults; no external hints",
        "results": [],
    }
    passed = True
    with tempfile.TemporaryDirectory(prefix="starfield-telescope-") as temporary:
        for item in manifest["images"]:
            source = FIXTURES / item["file"]
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != item["sha256"]:
                raise ValueError(f"Fixture integrity mismatch: {item['file']}")
            record = {"id": item["id"], "inputSha256": digest, "bytes": source.stat().st_size}
            native = load_native(source)
            try:
                record["decoded"] = native.export_info()
                if native.size != (item["width"], item["height"]):
                    raise ValueError("Decoded dimensions differ from source manifest")
            finally:
                native.close()
            print(f"Testing {item['id']} ...", file=sys.stderr, flush=True)
            started = perf_counter()
            progress = []
            def on_progress(stage: str, percent: int, message: str) -> None:
                progress.append({"stage": stage, "percent": percent})
            try:
                result = analyze_image(
                    source, Path(temporary) / item["id"],
                    filename="test-input" + source.suffix,
                    progress_callback=on_progress,
                )
            except RuntimeError as exc:
                record["message"] = str(exc)
                if str(exc).startswith("未能从星点几何中得到可靠天球解"):
                    record["outcome"] = "rejected_no_reliable_solution"
                else:
                    record["outcome"] = "runtime_error"
            except Exception as exc:
                record["outcome"] = "unexpected_error"
                record["message"] = f"{type(exc).__name__}: {exc}"
            else:
                record["outcome"] = "unexpected_solution_requires_independent_validation"
                record["wcs"] = result["wcs"]
            record["elapsedSeconds"] = round(perf_counter() - started, 3)
            record["progress"] = progress
            record["matchesExpectation"] = record["outcome"] == item["expectedCurrentSolverOutcome"]
            passed = passed and record["matchesExpectation"]
            report["results"].append(record)
            print(f"{record['outcome']}: {record['elapsedSeconds']} s", file=sys.stderr, flush=True)
    # Escapes keep redirected JSON portable across legacy Windows code pages.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
