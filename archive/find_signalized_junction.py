import pandas as pd

node_features = pd.read_csv("node_features.csv")
baseline = pd.read_csv("baseline_conflicts_per_node.csv")

merged = baseline.merge(node_features[["node_id", "has_signal"]], on="node_id", how="left")
signalized = merged[merged["has_signal"] == True].sort_values("total_conflicts", ascending=False)

print("Top signalized junctions by conflict count:")
print(signalized[["node_id", "total_conflicts", "severe_conflicts"]].head(10))