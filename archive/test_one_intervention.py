from intervention_tools import run_scenario
import pandas as pd

NET_FILE = "central_kolkata.net.xml"
SUMOCFG = "central_kolkata.sumocfg"

# Pick your #1 highest-conflict junction from Phase 5's output
baseline = pd.read_csv("baseline_conflicts_per_node.csv")
top_node = baseline.sort_values("total_conflicts", ascending=False).iloc[0]
test_node_id = top_node["node_id"]

print(f"Testing intervention on junction: {test_node_id}")
print(f"Baseline conflicts: {top_node['total_conflicts']}")

ssm_result = run_scenario(NET_FILE, SUMOCFG, test_node_id, "speed_breaker", "test1")

if ssm_result:
    print(f"\nSuccess. Conflict output saved to: {ssm_result}")
    print("Next: we'll count conflicts specifically at this junction and compare to baseline.")
else:
    print("\nSomething went wrong — check the error above.")