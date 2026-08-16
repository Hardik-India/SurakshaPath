"""
merge_timeslots.py

Combines the 4 per-time-slot baseline_conflicts_per_node_<slot>.csv files
(produced by build_baseline_conflicts_timeslot.py) into one wide file,
baseline_conflicts_timeseries.csv, with one row per node_id and separate
conflict columns per slot. app.py reads this to serve time-of-day-aware
heatmap data.

Run this AFTER you've generated all 4 baseline_conflicts_per_node_<slot>.csv files.

Usage:
    python merge_timeslots.py
"""

import pandas as pd

SLOTS = ["office", "noon", "evening", "midnight"]

node_features = pd.read_csv("node_features.csv")
merged = node_features[["node_id", "lat", "lon"]].copy()

for slot in SLOTS:
    path = f"baseline_conflicts_per_node_{slot}.csv"
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        print(f"WARNING: {path} not found — skipping '{slot}'. Run build_baseline_conflicts_timeslot.py for it first.")
        merged[f"total_conflicts_{slot}"] = 0
        merged[f"severe_conflicts_{slot}"] = 0
        continue

    df = df[["node_id", "total_conflicts", "severe_conflicts"]].rename(columns={
        "total_conflicts": f"total_conflicts_{slot}",
        "severe_conflicts": f"severe_conflicts_{slot}",
    })
    merged = merged.merge(df, on="node_id", how="left")
    merged[f"total_conflicts_{slot}"] = merged[f"total_conflicts_{slot}"].fillna(0)
    merged[f"severe_conflicts_{slot}"] = merged[f"severe_conflicts_{slot}"].fillna(0)

merged.to_csv("baseline_conflicts_timeseries.csv", index=False)
print(f"Saved {len(merged)} rows to baseline_conflicts_timeseries.csv")
print("\nConflict totals per slot (sanity check — office/evening should usually beat midnight):")
for slot in SLOTS:
    col = f"total_conflicts_{slot}"
    if col in merged.columns:
        print(f"  {slot:10s}: {int(merged[col].sum())} total conflicts across all junctions")
