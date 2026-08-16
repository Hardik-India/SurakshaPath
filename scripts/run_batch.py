from run_pipeline import run_full_scenario
import pandas as pd
import time

NUM_JUNCTIONS = 15   # top N by baseline conflict count

baseline = pd.read_csv("baseline_conflicts_per_node.csv")
target_junctions = baseline.sort_values("total_conflicts", ascending=False).head(NUM_JUNCTIONS)["node_id"].tolist()

print(f"Running full pipeline on {len(target_junctions)} junctions...")
print(target_junctions)

all_results = []
start_time = time.time()

for i, node_id in enumerate(target_junctions):
    print(f"\n{'#'*70}")
    print(f"JUNCTION {i+1}/{len(target_junctions)}: {node_id}")
    print(f"Elapsed so far: {(time.time()-start_time)/60:.1f} min")
    print(f"{'#'*70}")

    try:
        results = run_full_scenario(node_id)
        all_results.extend(results)
    except Exception as e:
        print(f"  ERROR on junction {node_id}: {e}")
        continue

    # Save progress after every junction, in case of interruption
    pd.DataFrame(all_results).to_csv("batch_intervention_results.csv", index=False)
    print(f"  Progress saved ({len(all_results)} total result rows so far).")

total_time = (time.time() - start_time) / 60
print(f"\n\nBATCH COMPLETE. Total time: {total_time:.1f} minutes.")
print(f"Total result rows: {len(all_results)}")
print("Saved to batch_intervention_results.csv")