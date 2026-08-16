"""
build_baseline_conflicts_timeslot.py

Same logic as the original build_baseline_conflicts.py, but takes the SSM
input file and output CSV name as command-line arguments so it can be run
once per time-of-day slot without overwriting results each time.

Usage:
    python build_baseline_conflicts_timeslot.py central_kolkata_ssm_office.xml baseline_conflicts_per_node_office.csv
    python build_baseline_conflicts_timeslot.py central_kolkata_ssm_noon.xml baseline_conflicts_per_node_noon.csv
    python build_baseline_conflicts_timeslot.py central_kolkata_ssm_evening.xml baseline_conflicts_per_node_evening.csv
    python build_baseline_conflicts_timeslot.py central_kolkata_ssm_midnight.xml baseline_conflicts_per_node_midnight.csv
"""

import sys
import pandas as pd
import xml.etree.ElementTree as ET
from scipy.spatial import cKDTree
import numpy as np

SEVERE_TTC_THRESHOLD = 1.5
SEVERE_DRAC_THRESHOLD = 4.0

if len(sys.argv) != 3:
    print("Usage: python build_baseline_conflicts_timeslot.py <ssm_input.xml> <output_baseline.csv>")
    sys.exit(1)

SSM_INPUT_FILE = sys.argv[1]
OUTPUT_FILE = sys.argv[2]

print(f"Loading node_features.csv for junction coordinates...")
node_df = pd.read_csv("node_features.csv")
node_df = node_df.dropna(subset=["lat", "lon"])

node_coords = node_df[["lat", "lon"]].values
node_ids = node_df["node_id"].values
tree = cKDTree(node_coords)

print(f"Parsing {SSM_INPUT_FILE}...")
xml_tree = ET.parse(SSM_INPUT_FILE)
root = xml_tree.getroot()

conflict_rows = []
skipped = 0

for conflict in root.findall("conflict"):
    min_ttc_elem = conflict.find("minTTC")
    max_drac_elem = conflict.find("maxDRAC")
    pet_elem = conflict.find("PET")

    position = None
    for elem in [min_ttc_elem, max_drac_elem]:
        if elem is not None and elem.get("position") not in (None, "NA"):
            position = elem.get("position")
            break

    if position is None:
        skipped += 1
        continue

    try:
        lon_str, lat_str = position.split(",")
        lon, lat = float(lon_str), float(lat_str)
    except Exception:
        skipped += 1
        continue

    dist, idx = tree.query([lat, lon])
    nearest_node_id = node_ids[idx]

    def safe_float(elem):
        if elem is None or elem.get("value") in (None, "NA"):
            return None
        return float(elem.get("value"))

    conflict_rows.append({
        "node_id": nearest_node_id,
        "distance_to_node": dist,
        "time": float(conflict.get("begin")),
        "ego_id": conflict.get("ego"),
        "foe_id": conflict.get("foe"),
        "min_ttc": safe_float(min_ttc_elem),
        "max_drac": safe_float(max_drac_elem),
        "pet": safe_float(pet_elem)
    })

print(f"Parsed {len(conflict_rows)} conflicts with valid position. Skipped {skipped}.")

df_conflicts = pd.DataFrame(conflict_rows)

if len(df_conflicts) == 0:
    print(f"WARNING: No usable conflicts found in {SSM_INPUT_FILE}.")
    # Still write an empty-but-valid file so downstream merge doesn't break
    pd.DataFrame(columns=[
        "node_id", "total_conflicts", "severe_conflicts", "mean_min_ttc",
        "mean_max_drac", "mean_pet", "mean_distance_to_node"
    ]).to_csv(OUTPUT_FILE, index=False)
else:
    def is_severe(row):
        ttc_severe = (row["min_ttc"] is not None) and (row["min_ttc"] < SEVERE_TTC_THRESHOLD)
        drac_severe = (row["max_drac"] is not None) and (row["max_drac"] > SEVERE_DRAC_THRESHOLD)
        return ttc_severe or drac_severe

    df_conflicts["is_severe"] = df_conflicts.apply(is_severe, axis=1)

    baseline_summary = df_conflicts.groupby("node_id").agg(
        total_conflicts=("time", "count"),
        severe_conflicts=("is_severe", "sum"),
        mean_min_ttc=("min_ttc", "mean"),
        mean_max_drac=("max_drac", "mean"),
        mean_pet=("pet", "mean"),
        mean_distance_to_node=("distance_to_node", "mean")
    ).reset_index()

    baseline_summary.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved {len(baseline_summary)} junction conflict summaries to {OUTPUT_FILE}")
    print(baseline_summary.sort_values("total_conflicts", ascending=False).head(10))
