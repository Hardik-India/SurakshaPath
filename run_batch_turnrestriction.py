from run_pipeline import run_full_scenario
import pandas as pd
import time

existing = pd.read_csv("batch_intervention_results.csv")
tested_junctions = existing["node_id"].unique().tolist()

print(f"Testing turn_restriction on {len(tested_junctions)} already-tested junctions...")

all_new_results = []
start_time = time.time()

for i, node_id in enumerate(tested_junctions):
    already_has_turn_restriction = ((existing["node_id"] == node_id) & (existing["intervention"] == "turn_restriction")).any()
    if already_has_turn_restriction:
        continue

    print(f"\n{'#'*70}")
    print(f"JUNCTION {i+1}/{len(tested_junctions)}: {node_id}  (elapsed {(time.time()-start_time)/60:.1f} min)")
    print(f"{'#'*70}")

    try:
        results = run_full_scenario(node_id, interventions=("turn_restriction",))
        all_new_results.extend(results)
    except Exception as e:
        print(f"  ERROR: {e}")
        continue

    combined = pd.concat([existing, pd.DataFrame(all_new_results)], ignore_index=True)
    combined = combined.drop_duplicates(subset=["node_id", "intervention", "seed"], keep="last")
    combined.to_csv("batch_intervention_results.csv", index=False)
    print(f"  Progress saved ({len(combined)} total rows).")

print(f"\nDone. Total time: {(time.time()-start_time)/60:.1f} min")