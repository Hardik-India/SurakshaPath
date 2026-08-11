import pandas as pd

df = pd.read_csv("surrogate_training_data.csv")
df_no_baseline = df[df["intervention"] != "none"]

print("Conflict delta by intervention type:")
print(df_no_baseline.groupby("intervention")["conflict_delta"].describe())

print("\nHow many rows show decrease vs increase vs ~no change:")
print(df_no_baseline.groupby("intervention")["conflict_delta"].apply(
    lambda x: pd.Series({"decrease": (x < -5).sum(), "increase": (x > 5).sum(), "no_change": ((x >= -5) & (x <= 5)).sum()})
))

print("\nBaseline conflict range of junctions actually tested:")
print(df["baseline_mean_conflicts"].describe())