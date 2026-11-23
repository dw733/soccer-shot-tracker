"""Record training shots or chart the on-target rates from a CSV."""

import argparse
import csv
from collections import defaultdict
from datetime import date
from math import isfinite
from pathlib import Path

FIELDS = ("session", "distance_m", "foot", "on_target")
FEET = {"dominant": "Dominant foot", "weak": "Weak foot"}
DEMO_FILE = "example_shots.csv"


def parse_shot(row):
    session, distance, foot, result = (row[key].strip() for key in FIELDS)
    date.fromisoformat(session)
    distance_m = float(distance)
    if not isfinite(distance_m) or distance_m <= 0:
        raise ValueError("distance_m must be a positive number")
    if foot not in FEET:
        raise ValueError("foot must be dominant or weak")
    if result not in ("0", "1"):
        raise ValueError("on_target must be 1 (on target) or 0 (off target)")
    return distance_m, foot, int(result)


def read_shots(path):
    with path.open(newline="", encoding="utf-8-sig") as file:
        rows = csv.DictReader(file)
        if rows.fieldnames != list(FIELDS):
            raise ValueError("CSV columns must be " + ", ".join(FIELDS))
        for line, row in enumerate(rows, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV line {line} has the wrong number of values")
            try:
                yield parse_shot(row)
            except ValueError as error:
                raise ValueError(f"CSV line {line}: {error}") from error


def add_shot(path, session, distance, foot, result):
    row = dict(zip(FIELDS, (session, distance, foot, result)))
    parse_shot(row)
    if path.name == DEMO_FILE:
        raise ValueError("Choose a separate CSV for your own shots.")
    path.parent.mkdir(parents=True, exist_ok=True)
    empty = not path.exists() or path.stat().st_size == 0
    if not empty:
        # Check the existing file before adding another row.
        list(read_shots(path))
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if empty:
            writer.writeheader()
        writer.writerow(row)


def summarize(shots):
    counts = defaultdict(lambda: [0, 0])
    for distance, foot, on_target in shots:
        group = counts[distance, foot]
        group[0] += on_target
        group[1] += 1
    if not counts:
        raise ValueError("Add at least one shot before making a chart.")
    return counts


def draw_chart(counts, output, demo):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    distances = sorted({distance for distance, _ in counts})
    width = 0.34
    size = max(8, len(distances) * 1.35 + 3)
    fig, ax = plt.subplots(figsize=(size, 4.5), layout="constrained")
    fig.set_facecolor("#f5f8f7")
    ax.set_facecolor("#f5f8f7")
    for (foot, name), color, offset in zip(FEET.items(), ("#176853", "#397eb2"), (-width / 2, width / 2)):
        bars, labels = [], []
        for index, distance in enumerate(distances):
            if (distance, foot) not in counts:
                continue
            hits, attempts = counts[distance, foot]
            bars.append((index + offset, hits / attempts))
            labels.append(f"{hits}/{attempts}")
        if bars:
            positions, rates = zip(*bars)
            group = ax.bar(positions, rates, width, color=color, label=name, zorder=3)
            ax.bar_label(group, labels=labels, padding=5, fontsize=10, color="#172a32")

    title = "On-target shots by foot and distance"
    if demo:
        title += "\nExample data from a simulated practice"
    ax.set_title(title, loc="left", pad=17, color="#172a32", fontweight="bold")
    ax.set_xticks(range(len(distances)), [f"{value:g} m" for value in distances])
    ax.set_xlabel("Distance from goal")
    ax.set_ylabel("On-target rate")
    ax.set_ylim(0, 1.14)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.yaxis.grid(color="#cfdbd7")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="upper right", frameon=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Record one shot")
    add.add_argument("csv", type=Path)
    add.add_argument("--session", default=date.today().isoformat())
    add.add_argument("--distance", required=True)
    add.add_argument("--foot", choices=FEET, required=True)
    add.add_argument("--on-target", choices=("0", "1"), required=True)
    chart = commands.add_parser("chart", help="Print on-target counts and save a chart")
    chart.add_argument("csv", type=Path)
    chart.add_argument("--output", type=Path, default=Path("output/shots.png"))

    args = parser.parse_args()
    try:
        if args.command == "add":
            add_shot(args.csv, args.session, args.distance, args.foot, args.on_target)
            print(f"Added one shot to {args.csv}")
        else:
            counts = summarize(read_shots(args.csv))
            for (distance, foot), (hits, attempts) in sorted(counts.items()):
                print(f"{distance:g} m | {FEET[foot]} | {hits}/{attempts} ({hits / attempts:.0%})")
            draw_chart(counts, args.output, demo=args.csv.name == DEMO_FILE)
            print(f"Saved {args.output}")
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
