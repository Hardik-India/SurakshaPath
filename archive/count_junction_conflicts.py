import pandas as pd
import xml.etree.ElementTree as ET
from scipy.spatial import cKDTree
import sys

def count_conflicts_near_node(ssm_file, target_node_id, node_features_csv="node_features.csv", radius_deg=0.0015):
    """Count total and severe conflicts within a radius of a specific junction's coordinates."""
    node_df = pd.read_csv(node_features_csv)
    target_row = node_df[node_df["node_id"] == target_node_id]

    if len(target_row) == 0:
        print(f"ERROR: node_id '{target_node_id}' not found in {node_features_csv}")
        return None

    target_lat = target_row.iloc[0]["lat"]
    target_lon = target_row.iloc[0]["lon"]

    tree = ET.parse(ssm_file)
    root = tree.getroot()

    total = 0
    severe = 0

    for conflict in root.findall("conflict"):
        min_ttc_elem = conflict.find("minTTC")
        max_drac_elem = conflict.find("maxDRAC")

        position = None
        for elem in [min_ttc_elem, max_drac_elem]:
            if elem is not None and elem.get("position") not in (None, "NA"):
                position = elem.get("position")
                break
        if position is None:
            continue

        try:
            lon_str, lat_str = position.split(",")
            lon, lat = float(lon_str), float(lat_str)
        except Exception:
            continue

        dist = ((lat - target_lat)**2 + (lon - target_lon)**2) ** 0.5
        if dist <= radius_deg:
            total += 1
            min_ttc = float(min_ttc_elem.get("value")) if (min_ttc_elem is not None and min_ttc_elem.get("value") != "NA") else None
            max_drac = float(max_drac_elem.get("value")) if (max_drac_elem is not None and max_drac_elem.get("value") != "NA") else None
            if (min_ttc is not None and min_ttc < 1.5) or (max_drac is not None and max_drac > 4.0):
                severe += 1

    return {"node_id": target_node_id, "total_conflicts": total, "severe_conflicts": severe}


if __name__ == "__main__":
    baseline = pd.read_csv("baseline_conflicts_per_node.csv")
    top_node = baseline.sort_values("total_conflicts", ascending=False).iloc[0]
    test_node_id = top_node["node_id"]

    print(f"Junction: {test_node_id}")
    print(f"Baseline (no intervention): {int(top_node['total_conflicts'])} total, {int(top_node['severe_conflicts'])} severe")

    result = count_conflicts_near_node("ssm_test1.xml", test_node_id)
    if result:
        print(f"After speed_breaker: {result['total_conflicts']} total, {result['severe_conflicts']} severe")

        delta = result['total_conflicts'] - top_node['total_conflicts']
        pct = (delta / top_node['total_conflicts'] * 100) if top_node['total_conflicts'] > 0 else 0
        print(f"\nChange: {delta:+.0f} conflicts ({pct:+.1f}%)")