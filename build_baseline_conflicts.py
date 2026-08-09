import pandas as pd
import xml.etree.ElementTree as ET
from scipy.spatial import cKDTree
import numpy as np

SEVERE_TTC_THRESHOLD = 1.5
SEVERE_DRAC_THRESHOLD = 4.0   # higher DRAC = harder braking needed = more severe

print("Loading node_features.csv for junction coordinates...")
node_df = pd.read_csv("node_features.csv")
node_df = node_df.dropna(subset=["lat", "lon"])

node_coords = node_df[["lat", "lon"]].values
node_ids = node_df["node_id"].values
tree = cKDTree(node_coords)

print("Parsing central_kolkata_ssm.xml...")
xml_tree = ET.parse("central_kolkata_ssm.xml")
root = xml_tree.getroot()

conflict_rows = []
skipped = 0

for conflict in root.findall("conflict"):
    min_ttc_elem = conflict.find("minTTC")
    max_drac_elem = conflict.find("maxDRAC")
    pet_elem = conflict.find("PET")

    # Prefer minTTC's position; fall back to maxDRAC's position
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

    # Find nearest junction to this conflict's real-world location
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
    print("WARNING: Still no usable conflicts. Something else is wrong — stop and investigate further.")
else:
    df_conflicts.to_csv("all_conflicts_mapped.csv", index=False)

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

    baseline_summary.to_csv("baseline_conflicts_per_node.csv", index=False)

    print(f"Saved {len(baseline_summary)} junction conflict summaries to baseline_conflicts_per_node.csv")
    print(baseline_summary.sort_values("total_conflicts", ascending=False).head(10))