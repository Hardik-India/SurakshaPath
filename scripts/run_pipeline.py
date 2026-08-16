import subprocess
import xml.etree.ElementTree as ET
import statistics
import os
from crop_subnetwork import crop_network
from intervention_tools import apply_speed_reduction, apply_signal_retiming, apply_add_signal, apply_turn_restriction

FULL_NET = "central_kolkata.net.xml"
SEEDS = [42, 123, 777]
DEMAND_END = 1200  # seconds of sim-time for each subnet run


def count_conflicts(ssm_file):
    try:
        tree = ET.parse(ssm_file)
    except Exception:
        return {"total_conflicts": 0, "severe_conflicts": 0}

    root = tree.getroot()
    total = 0
    severe = 0
    for conflict in root.findall("conflict"):
        total += 1
        min_ttc_elem = conflict.find("minTTC")
        max_drac_elem = conflict.find("maxDRAC")
        min_ttc = float(min_ttc_elem.get("value")) if (min_ttc_elem is not None and min_ttc_elem.get("value") != "NA") else None
        max_drac = float(max_drac_elem.get("value")) if (max_drac_elem is not None and max_drac_elem.get("value") != "NA") else None
        if (min_ttc is not None and min_ttc < 1.5) or (max_drac is not None and max_drac > 4.0):
            severe += 1
    return {"total_conflicts": total, "severe_conflicts": severe}


def run_sumo(net_file, sumocfg, ssm_out, seed):
    cmd = [
        "sumo", "-c", sumocfg,
        "--net-file", net_file,
        "--device.ssm.probability", "1.0",
        "--device.ssm.file", ssm_out,
        "--device.ssm.measures", "TTC PET DRAC",
        "--device.ssm.geo", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "90",
        "--seed", str(seed)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"    ERROR (seed {seed}): {result.stderr[-400:]}")
        return False
    return True


def run_full_scenario(node_id, interventions=None, radius_m=300, seeds=SEEDS):
    """Crop subnet around node_id, run applicable interventions across all seeds, return raw result rows."""
    tag = node_id.replace("/", "_")[:40]
    subnet_file = f"subnet_{tag}.net.xml"
    trips_file = f"subnet_{tag}_trips.trips.xml"
    sumocfg_file = f"subnet_{tag}.sumocfg"

    import pandas as pd
    node_features_df = pd.read_csv("node_features.csv")
    node_row = node_features_df[node_features_df["node_id"] == node_id]
    has_signal = bool(node_row.iloc[0]["has_signal"]) if len(node_row) > 0 else False

    if interventions is None:
        if has_signal:
            interventions = ("none", "speed_breaker", "signal_retiming")
        else:
            interventions = ("none", "speed_breaker", "add_signal")
    else:
        if not has_signal and "signal_retiming" in interventions:
            interventions = tuple(i for i in interventions if i != "signal_retiming")
            print(f"  Note: '{node_id}' has no signal — skipping signal_retiming.")
        if has_signal and "add_signal" in interventions:
            interventions = tuple(i for i in interventions if i != "add_signal")
            print(f"  Note: '{node_id}' already has a signal — skipping add_signal.")

    print(f"\n=== Junction: {node_id} ===")
    print("  Cropping sub-network...")
    result = crop_network(FULL_NET, node_id, subnet_file, radius_m=radius_m)
    if result is None:
        print("  SKIPPING — crop failed.")
        return []

    print("  Generating local demand...")
    trip_cmd = [
        "python", f"{os.environ['SUMO_HOME']}\\tools\\randomTrips.py",
        "-n", subnet_file, "-o", trips_file,
        "--begin", "0", "--end", str(DEMAND_END), "--period", "1.5", "--validate"
    ]
    r = subprocess.run(trip_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  SKIPPING — demand generation failed: {r.stderr[-400:]}")
        return []

    with open(sumocfg_file, "w") as f:
        f.write(f"""<configuration>
  <input>
    <net-file value="{subnet_file}"/>
    <route-files value="{trips_file}"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="{DEMAND_END}"/>
    <step-length value="0.5"/>
  </time>
</configuration>""")

    rows = []
    for intervention in interventions:
        print(f"  Intervention: {intervention}")

        if intervention == "none":
            net_for_run = subnet_file
        elif intervention == "speed_breaker":
            net_for_run = f"subnet_{tag}_speedbreaker.net.xml"
            apply_speed_reduction(subnet_file, node_id, net_for_run, reduction_factor=0.8)
        elif intervention == "signal_retiming":
            net_for_run = f"subnet_{tag}_signalretime.net.xml"
            apply_signal_retiming(subnet_file, node_id, net_for_run, green_multiplier=1.3)
        elif intervention == "turn_restriction":
            net_for_run = f"subnet_{tag}_turnrestrict.net.xml"
            apply_turn_restriction(subnet_file, node_id, net_for_run, banned_dir="l")
        elif intervention == "add_signal":
            net_for_run = f"subnet_{tag}_addsignal.net.xml"
            result = apply_add_signal(subnet_file, node_id, net_for_run)
            if result is None:
                print(f"    Skipping add_signal for {node_id} — conversion failed.")
                continue
        else:
            print(f"    Unknown intervention '{intervention}', skipping.")
            continue

        for seed in seeds:
            ssm_out = f"ssm_{tag}_{intervention}_seed{seed}.xml"
            ok = run_sumo(net_for_run, sumocfg_file, ssm_out, seed)
            if ok:
                counts = count_conflicts(ssm_out)
                print(f"    seed {seed}: total={counts['total_conflicts']}, severe={counts['severe_conflicts']}")
                rows.append({
                    "node_id": node_id,
                    "intervention": intervention,
                    "seed": seed,
                    "total_conflicts": counts["total_conflicts"],
                    "severe_conflicts": counts["severe_conflicts"]
                })

    return rows


if __name__ == "__main__":
    # Quick standalone test on one junction, all 3 interventions, before batching
    import pandas as pd
    baseline = pd.read_csv("baseline_conflicts_per_node.csv")
    top_node = baseline.sort_values("total_conflicts", ascending=False).iloc[0]
    test_node_id = top_node["node_id"]

    results = run_full_scenario(test_node_id)

    df = pd.DataFrame(results)