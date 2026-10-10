"""make chart: grouped bars of duplicate bookings per 10,000 logical requests.

Reads results/exp3/summary.csv only (or --input) and writes
figures/exp3_duplicates.svg (or --output). One group per stack; within each
group four bars: 1% naive, 1% keyed, 5% naive, 5% keyed. The y value is the
median duplicate bookings per 10,000 logical requests with a thin whisker for
the min-max of the runs. The title is a placeholder; the author writes it.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
STACKS = ["dotnet", "java", "python"]
BARS = [("naive", "0.01"), ("v2", "0.01"), ("naive", "0.05"), ("v2", "0.05")]
LABELS = ["1% naive", "1% keyed", "5% naive", "5% keyed"]
NAIVE_COLOUR = "#1F4E79"
KEYED_COLOUR = "#9DB9D5"
TEXT_COLOUR = "#555555"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", default=str(REPO / "results" / "exp3" / "summary.csv"))
    parser.add_argument("--output", default=str(REPO / "figures" / "exp3_duplicates.svg"))
    args = parser.parse_args()

    rows: dict[tuple[str, str, str], dict[str, str]] = {}
    with open(args.input, newline="") as f:
        for row in csv.DictReader(f):
            rows[(row["stack"], row["variant"], row["fault_rate"])] = row

    stacks = [s for s in STACKS if any((s, v, fl) in rows for v, fl in BARS)]
    if not stacks:
        raise SystemExit(f"no usable rows in {args.input}")

    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["text.color"] = TEXT_COLOUR
    plt.rcParams["axes.labelcolor"] = TEXT_COLOUR
    plt.rcParams["xtick.color"] = TEXT_COLOUR
    plt.rcParams["ytick.color"] = TEXT_COLOUR

    figure, axis = plt.subplots(figsize=(8, 4.5))
    width = 0.19
    positions = range(len(stacks))

    for i, (variant, fault) in enumerate(BARS):
        offsets = [p + (i - 1.5) * width for p in positions]
        medians, lows, highs, values = [], [], [], []
        for stack in stacks:
            row = rows.get((stack, variant, fault))
            medians.append(float(row["median_duplicates_per_10k"]) if row else 0.0)
            if row:
                low, high = row["min_max_duplicates_per_10k"].split("-")
                lows.append(float(row["median_duplicates_per_10k"]) - float(low))
                highs.append(float(high) - float(row["median_duplicates_per_10k"]))
            else:
                lows.append(0.0)
                highs.append(0.0)
            values.append(row["median_duplicates_per_10k"] if row else "0")

        colour = NAIVE_COLOUR if variant == "naive" else KEYED_COLOUR
        bars = axis.bar(
            offsets, medians, width=width, color=colour,
            yerr=[lows, highs], error_kw={"elinewidth": 0.6, "ecolor": TEXT_COLOUR},
        )
        for bar, value in zip(bars, values):
            axis.annotate(
                value,
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                ha="center", va="bottom", fontsize=8,
            )

    axis.set_xticks(list(positions), stacks)
    axis.set_ylabel("duplicate bookings per 10,000 logical requests")
    axis.set_title("TITLE: author to write")
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(False, axis="both")
    figure.tight_layout()
    figure.savefig(args.output, transparent=True)
    print(f"chart: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
