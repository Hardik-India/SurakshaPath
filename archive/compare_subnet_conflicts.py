import xml.etree.ElementTree as ET

def count_conflicts(ssm_file):
    tree = ET.parse(ssm_file)
    root = tree.getroot()

    total = 0
    severe = 0
    ttc_values = []
    drac_values = []

    for conflict in root.findall("conflict"):
        min_ttc_elem = conflict.find("minTTC")
        max_drac_elem = conflict.find("maxDRAC")

        total += 1

        min_ttc = None
        if min_ttc_elem is not None and min_ttc_elem.get("value") != "NA":
            min_ttc = float(min_ttc_elem.get("value"))
            ttc_values.append(min_ttc)

        max_drac = None
        if max_drac_elem is not None and max_drac_elem.get("value") != "NA":
            max_drac = float(max_drac_elem.get("value"))
            drac_values.append(max_drac)

        if (min_ttc is not None and min_ttc < 1.5) or (max_drac is not None and max_drac > 4.0):
            severe += 1

    return {
        "total_conflicts": total,
        "severe_conflicts": severe,
        "mean_min_ttc": sum(ttc_values) / len(ttc_values) if ttc_values else None,
        "mean_max_drac": sum(drac_values) / len(drac_values) if drac_values else None
    }


baseline = count_conflicts("subnet_ssm_baseline.xml")
intervention = count_conflicts("subnet_ssm_intervention.xml")

print("=" * 50)
print("BASELINE (no intervention)")
print(f"  Total conflicts:  {baseline['total_conflicts']}")
print(f"  Severe conflicts: {baseline['severe_conflicts']}")
print(f"  Mean min TTC:     {baseline['mean_min_ttc']}")
print(f"  Mean max DRAC:    {baseline['mean_max_drac']}")

print()
print("AFTER speed_breaker INTERVENTION")
print(f"  Total conflicts:  {intervention['total_conflicts']}")
print(f"  Severe conflicts: {intervention['severe_conflicts']}")
print(f"  Mean min TTC:     {intervention['mean_min_ttc']}")
print(f"  Mean max DRAC:    {intervention['mean_max_drac']}")

print()
print("=" * 50)
delta = intervention['total_conflicts'] - baseline['total_conflicts']
pct = (delta / baseline['total_conflicts'] * 100) if baseline['total_conflicts'] > 0 else 0
severe_delta = intervention['severe_conflicts'] - baseline['severe_conflicts']

print(f"CHANGE: {delta:+d} total conflicts ({pct:+.1f}%)")
print(f"CHANGE: {severe_delta:+d} severe conflicts")
print("=" * 50)