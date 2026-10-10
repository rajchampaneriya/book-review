"""make summary: results/exp3/summary.csv exactly as docs/exp3-spec.md defines.

One row per (stack, variant, fault_rate): median and min-max over runs of
duplicate_bookings, duplicate_charges and lost; duplicates_per_10k per run
(duplicate_bookings / logical_requests x 10000) with its median and min-max;
at fault 0, p99 overhead = median p99 (v2) - median p99 (naive) per stack.
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "results" / "exp3" / "runs.csv"
OUT = REPO / "results" / "exp3" / "summary.csv"

COLUMNS = [
    "stack", "variant", "fault_rate", "runs",
    "median_duplicate_bookings", "min_max_duplicate_bookings",
    "median_duplicate_charges", "min_max_duplicate_charges",
    "median_lost", "min_max_lost",
    "median_duplicates_per_10k", "min_max_duplicates_per_10k",
    "p99_overhead_ms",
]


def median_and_min_max(values: list[float]) -> tuple[float, float, float]:
    return statistics.median(values), min(values), max(values)


def main() -> int:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    with RUNS.open() as f:
        for row in csv.DictReader(f):
            groups[(row["stack"], row["variant"], row["fault_rate"])].append(row)

    p99_overhead: dict[str, int] = {}
    for stack in {key[0] for key in groups}:
        naive = groups.get((stack, "naive", "0"))
        v2 = groups.get((stack, "v2", "0"))
        if naive and v2:
            p99_overhead[stack] = round(
                statistics.median(int(r["p99_ms"]) for r in v2)
                - statistics.median(int(r["p99_ms"]) for r in naive)
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for (stack, variant, fault_rate), rows in sorted(groups.items()):
            per_10k = [int(r["duplicate_bookings"]) / int(r["logical_requests"]) * 10000 for r in rows]
            d_med, d_min, d_max = median_and_min_max([int(r["duplicate_bookings"]) for r in rows])
            c_med, c_min, c_max = median_and_min_max([int(r["duplicate_charges"]) for r in rows])
            l_med, l_min, l_max = median_and_min_max([int(r["lost"]) for r in rows])
            k_med, k_min, k_max = median_and_min_max(per_10k)
            writer.writerow({
                "stack": stack,
                "variant": variant,
                "fault_rate": fault_rate,
                "runs": len(rows),
                "median_duplicate_bookings": round(d_med, 1),
                "min_max_duplicate_bookings": f"{d_min}-{d_max}",
                "median_duplicate_charges": round(c_med, 1),
                "min_max_duplicate_charges": f"{c_min}-{c_max}",
                "median_lost": round(l_med, 1),
                "min_max_lost": f"{l_min}-{l_max}",
                "median_duplicates_per_10k": round(k_med, 1),
                "min_max_duplicates_per_10k": f"{round(k_min, 1)}-{round(k_max, 1)}",
                "p99_overhead_ms": p99_overhead.get(stack, "") if fault_rate == "0" else "",
            })
    print(f"summary: wrote {OUT.relative_to(REPO)} ({len(groups)} groups)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
