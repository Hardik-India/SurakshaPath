import subprocess
import xml.etree.ElementTree as ET
import statistics

SEEDS = [42, 123, 777]   # 3 independent replicates

def run_sumo_scenario(net_file, output_ssm_file, seed):
    cmd = [
        "sumo", "-c", "subnet.sumocfg",
        "--net-file", net_file,
        "--device.ssm.probability", "1.0",
        "--device.ssm.file", output_ssm_file,
        "--device.ssm.measures", "TTC PET DRAC",
        "--device.ssm.geo", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "90",
        "--seed", str(seed)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  ERROR (seed {seed}): {result.stderr[-500:]}")
        return False
    return True


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

        min_ttc = None
        if min_ttc_elem is not None and min_ttc_elem.get("value") != "NA":
            min_ttc = float(min_ttc_elem.get("value"))
        max_drac = None
        if max_drac_elem is not None and max_drac_elem.get("value") != "NA":
            max_drac = float(max_drac_elem.get("value"))

        if (min_ttc is not None and min_ttc < 1.5) or (max_drac is not None and max_drac > 4.0):
            severe += 1

    return {"total_conflicts": total, "severe_conflicts": severe}


print("=" * 60)
print("RUNNING BASELINE REPLICATES (no intervention)")
print("=" * 60)
baseline_results = []
for seed in SEEDS:
    print(f"\nSeed {seed}...")
    ssm_out = f"subnet_ssm_baseline_seed{seed}.xml"
    ok = run_sumo_scenario("test_subnet.net.xml", ssm_out, seed)
    if ok:
        counts = count_conflicts(ssm_out)
        baseline_results.append(counts["total_conflicts"])
        print(f"  Total conflicts: {counts['total_conflicts']}, Severe: {counts['severe_conflicts']}")

print("\n" + "=" * 60)
print("RUNNING INTERVENTION REPLICATES (speed_breaker)")
print("=" * 60)
intervention_results = []
for seed in SEEDS:
    print(f"\nSeed {seed}...")
    ssm_out = f"subnet_ssm_intervention_seed{seed}.xml"
    ok = run_sumo_scenario("subnet_intervention.net.xml", ssm_out, seed)
    if ok:
        counts = count_conflicts(ssm_out)
        intervention_results.append(counts["total_conflicts"])
        print(f"  Total conflicts: {counts['total_conflicts']}, Severe: {counts['severe_conflicts']}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if len(baseline_results) >= 2 and len(intervention_results) >= 2:
    b_mean = statistics.mean(baseline_results)
    b_stdev = statistics.stdev(baseline_results)
    i_mean = statistics.mean(intervention_results)
    i_stdev = statistics.stdev(intervention_results)

    print(f"Baseline:     mean={b_mean:.1f}, stdev={b_stdev:.1f}, values={baseline_results}")
    print(f"Intervention: mean={i_mean:.1f}, stdev={i_stdev:.1f}, values={intervention_results}")

    delta = i_mean - b_mean
    pct = (delta / b_mean * 100) if b_mean > 0 else 0
    print(f"\nMean change: {delta:+.1f} conflicts ({pct:+.1f}%)")

    # Rough signal-vs-noise check: is the mean difference bigger than the combined natural variance?
    combined_stdev = (b_stdev + i_stdev) / 2
    if combined_stdev > 0 and abs(delta) < combined_stdev:
        print(f"\n⚠ WARNING: The change ({abs(delta):.1f}) is SMALLER than the natural run-to-run")
        print(f"  variance (~{combined_stdev:.1f}). This result is likely NOISE, not a real effect.")
    else:
        print(f"\n✓ The change appears LARGER than natural run-to-run variance (~{combined_stdev:.1f}).")
        print(f"  This suggests a real effect, though 3 replicates is still a small sample.")
else:
    print("Not enough successful runs to compute statistics.")