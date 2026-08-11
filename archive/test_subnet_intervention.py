import subprocess
import pandas as pd
from intervention_tools import apply_speed_reduction

SUBNET_FILE = "test_subnet.net.xml"

# Step 1: Generate short local demand (5 minutes sim-time, dense enough for conflicts)
print("Generating local demand for sub-network...")
result = subprocess.run([
    "python", f"{__import__('os').environ['SUMO_HOME']}\\tools\\randomTrips.py",
    "-n", SUBNET_FILE,
    "-o", "subnet_trips.trips.xml",
    "--begin", "0", "--end", "300", "--period", "1.5",
    "--validate"
], capture_output=True, text=True)

if result.returncode != 0:
    print("ERROR generating trips:", result.stderr[-800:])
    exit()
print("  Demand generated.")

# Step 2: Build a minimal sumocfg for the sub-network
sumocfg_content = f"""<configuration>
  <input>
    <net-file value="{SUBNET_FILE}"/>
    <route-files value="subnet_trips.trips.xml"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="300"/>
    <step-length value="0.5"/>
  </time>
</configuration>
"""
with open("subnet.sumocfg", "w") as f:
    f.write(sumocfg_content)
print("  subnet.sumocfg created.")

# Step 3: Run BASELINE (no intervention) on the sub-network
print("\nRunning baseline scenario...")
baseline_cmd = [
    "sumo", "-c", "subnet.sumocfg",
    "--device.ssm.probability", "1.0",
    "--device.ssm.file", "subnet_ssm_baseline.xml",
    "--device.ssm.measures", "TTC PET DRAC",
    "--device.ssm.geo", "true",
    "--no-warnings", "true",
    "--time-to-teleport", "90"
]
r1 = subprocess.run(baseline_cmd, capture_output=True, text=True, timeout=300)
if r1.returncode != 0:
    print("ERROR in baseline run:", r1.stderr[-800:])
    exit()
print("  Baseline complete: subnet_ssm_baseline.xml")

# Step 4: Apply intervention and run again
print("\nApplying speed_breaker intervention...")
baseline = pd.read_csv("baseline_conflicts_per_node.csv")
top_node = baseline.sort_values("total_conflicts", ascending=False).iloc[0]
test_node_id = top_node["node_id"]

apply_speed_reduction(SUBNET_FILE, test_node_id, "subnet_intervention.net.xml", reduction_factor=0.8)

intervention_cmd = [
    "sumo", "-c", "subnet.sumocfg",
    "--net-file", "subnet_intervention.net.xml",
    "--device.ssm.probability", "1.0",
    "--device.ssm.file", "subnet_ssm_intervention.xml",
    "--device.ssm.measures", "TTC PET DRAC",
    "--device.ssm.geo", "true",
    "--no-warnings", "true",
    "--time-to-teleport", "90"
]
r2 = subprocess.run(intervention_cmd, capture_output=True, text=True, timeout=300)
if r2.returncode != 0:
    print("ERROR in intervention run:", r2.stderr[-800:])
    exit()
print("  Intervention run complete: subnet_ssm_intervention.xml")

print("\nBoth scenarios finished successfully. Ready to count and compare conflicts.")