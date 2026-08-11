from run_pipeline import run_full_scenario
import pandas as pd
import time
import shutil

# Preserve the old short-window dataset for comparison/reference
shutil.copy("batch_intervention_results.csv", "batch_intervention_results_shortwindow_v1.csv")

baseline = pd.read_csv("baseline_conflicts_per_node.csv")
node_features = pd.read_csv("node_features.csv")
old_results = pd.read_csv("batch_intervention_results_shortwindow_v1.csv")

# Re-test every junction that was previously tested
target_junctions = old_results["node_id"].unique().tolist()
print(f"Regenerating with 20-min window for {len(target_junctions)} junctions...")

all_results = []
start_time = time.time()

for i, node_id in enumerate(target_junctions):
    print(f"\n{'#'*70}")
    print(f"JUNCTION {i+1}/{len(target_junctions)}: {node_id}  (elapsed {(time.time()-start_time)/60:.1f} min)")
    print(f"{'#'*70}")

    try:
        results = run_full_scenario(node_id)
        all_results.extend(results)
    except Exception as e:
        print(f"  ERROR: {e}")
        continue

    pd.DataFrame(all_results).to_csv("batch_intervention_results.csv", index=False)
    print(f"  Progress saved ({len(all_results)} rows so far).")

print(f"\nDone. Total time: {(time.time()-start_time)/60:.1f} min")
print(f"Total rows: {len(all_results)}")