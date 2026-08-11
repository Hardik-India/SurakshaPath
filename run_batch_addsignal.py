from run_pipeline import run_full_scenario
import pandas as pd

baseline = pd.read_csv("baseline_conflicts_per_node.csv")
node_features = pd.read_csv("node_features.csv")

merged = baseline.merge(node_features[["node_id", "has_signal"]], on="node_id", how="left")
top15 = merged.sort_values("total_conflicts", ascending=False).head(15)
unsignalized = top15[top15["has_signal"] == False]["node_id"].tolist()

print(f"Running add_signal batch on {len(unsignalized)} unsignalized junctions from the top 15...")

all_results = []
for node_id in unsignalized:
    results = run_full_scenario(node_id)
    all_results.extend(results)

new_df = pd.DataFrame(all_results)
existing = pd.read_csv("batch_intervention_results.csv")

combined = pd.concat([existing, new_df], ignore_index=True)
combined = combined.drop_duplicates(subset=["node_id", "intervention", "seed"], keep="last")
combined.to_csv("batch_intervention_results.csv", index=False)

print(f"\nDone. batch_intervention_results.csv now has {len(combined)} total rows.")