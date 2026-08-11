from run_pipeline import run_full_scenario
import pandas as pd

node_id = "cluster_664446535_8507351665_8507351666"
results = run_full_scenario(node_id)

df = pd.DataFrame(results)
print("\n" + "=" * 60)
print(df)
df.to_csv("signalized_junction_test.csv", index=False)