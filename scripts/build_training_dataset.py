import pandas as pd

print("Loading all source tables...")
batch_results = pd.read_csv("batch_intervention_results.csv")
node_features = pd.read_csv("node_features.csv")
node_baseline_behavior = pd.read_csv("node_baseline_from_existing_data.csv")

print(f"Batch results: {len(batch_results)} rows")
print(f"Node features: {len(node_features)} rows")
print(f"Node baseline behavior: {len(node_baseline_behavior)} rows")

# --- Step 1: Collapse replicate seeds into mean/stdev per (node_id, intervention) ---
print("\nAggregating replicate seeds...")
summary = batch_results.groupby(["node_id", "intervention"]).agg(
    mean_total_conflicts=("total_conflicts", "mean"),
    std_total_conflicts=("total_conflicts", "std"),
    mean_severe_conflicts=("severe_conflicts", "mean"),
    std_severe_conflicts=("severe_conflicts", "std"),
    num_replicates=("seed", "count")
).reset_index()

summary["std_total_conflicts"] = summary["std_total_conflicts"].fillna(0)
summary["std_severe_conflicts"] = summary["std_severe_conflicts"].fillna(0)

print(f"Summary table: {len(summary)} (junction, intervention) combinations")

# --- Step 2a: Get each junction's SUBNET baseline (for computing an accurate, paired delta) ---
subnet_baseline = summary[summary["intervention"] == "none"][["node_id", "mean_total_conflicts", "mean_severe_conflicts"]]
subnet_baseline = subnet_baseline.rename(columns={
    "mean_total_conflicts": "subnet_baseline_conflicts",
    "mean_severe_conflicts": "subnet_baseline_severe"
})
summary = summary.merge(subnet_baseline, on="node_id", how="left")

# --- Step 2b: Get each junction's CITYWIDE baseline (for the model's input feature — consistent at inference time) ---
citywide_baseline = pd.read_csv("baseline_conflicts_per_node.csv")[["node_id", "total_conflicts", "severe_conflicts"]]
citywide_baseline = citywide_baseline.rename(columns={
    "total_conflicts": "baseline_mean_conflicts",
    "severe_conflicts": "baseline_mean_severe"
})
summary = summary.merge(citywide_baseline, on="node_id", how="left")

# --- Step 3: Compute delta using the PAIRED subnet comparison (same methodology, correct) ---
summary["conflict_delta"] = summary["mean_total_conflicts"] - summary["subnet_baseline_conflicts"]
summary["conflict_pct_change"] = (summary["conflict_delta"] / summary["subnet_baseline_conflicts"].replace(0, 1)) * 100

summary["severe_delta"] = summary["mean_severe_conflicts"] - summary["subnet_baseline_severe"]
summary["severe_pct_change"] = (summary["severe_delta"] / summary["subnet_baseline_severe"].replace(0, 1)) * 100

# --- Step 4: Merge in static node features (signal presence, lane count, etc.) ---
print("\nMerging in node features and baseline behavior...")
final_df = summary.merge(node_features, on="node_id", how="left")
final_df = final_df.merge(node_baseline_behavior, on="node_id", how="left")

# --- Step 5: Flag whether the effect is likely real vs noise ---
# Simple heuristic: effect is "significant" if |delta| > combined stdev of this and baseline
def is_significant(row):
    if row["intervention"] == "none":
        return False
    combined_std = (row["std_total_conflicts"] + 
                     summary[(summary["node_id"] == row["node_id"]) & (summary["intervention"] == "none")]["std_total_conflicts"].values[0]
                     if len(summary[(summary["node_id"] == row["node_id"]) & (summary["intervention"] == "none")]) > 0 else row["std_total_conflicts"]) / 2
    return abs(row["conflict_delta"]) > combined_std if combined_std > 0 else False

final_df["likely_real_effect"] = final_df.apply(is_significant, axis=1)

final_df.to_csv("surrogate_training_data.csv", index=False)

print(f"\nFinal training dataset saved: surrogate_training_data.csv ({len(final_df)} rows)")
print("\n--- Summary by intervention type ---")
print(final_df.groupby("intervention")["conflict_pct_change"].describe())

print("\n--- Rows flagged as likely real effects ---")
real_effects = final_df[final_df["likely_real_effect"] == True][["node_id", "intervention", "conflict_pct_change", "likely_real_effect"]]
print(real_effects if len(real_effects) > 0 else "None flagged as clearly significant — mostly noise-level effects across this junction set.")