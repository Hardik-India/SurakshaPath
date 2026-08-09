import sumolib
import pandas as pd

print("Loading network...")
net = sumolib.net.readNet("central_kolkata.net.xml")

print("Loading lane_dataset.csv...")
lane_df = pd.read_csv("lane_dataset.csv")
print(f"Loaded {len(lane_df)} rows.")

# Build a lane_id -> junction_id lookup once (much faster than calling sumolib per-row)
print("Building lane-to-junction lookup...")
lane_to_junction = {}
for edge in net.getEdges():
    to_node_id = edge.getToNode().getID()
    for lane in edge.getLanes():
        lane_to_junction[lane.getID()] = to_node_id

lane_df["junction_id"] = lane_df["lane_id"].map(lane_to_junction)

unmapped = lane_df["junction_id"].isna().sum()
if unmapped > 0:
    print(f"Warning: {unmapped} rows could not be mapped to a junction (dropping these).")
lane_df = lane_df.dropna(subset=["junction_id"])

# Convert numeric columns that may contain blanks/empty strings
numeric_cols = [
    "vehicle_count", "mean_speed_ms", "max_speed_observed_ms", "halting_count",
    "occupancy_pct", "speed_limit_ms", "mean_gap_m", "min_gap_m",
    "mean_rel_velocity_ms", "mean_time_gap_s", "min_time_gap_s",
    "mean_acceleration_ms2", "min_acceleration_ms2", "hard_brake_count"
]
for col in numeric_cols:
    lane_df[col] = pd.to_numeric(lane_df[col], errors="coerce")

print("Aggregating by junction...")
node_baseline = lane_df.groupby("junction_id").agg(
    total_vehicle_count=("vehicle_count", "sum"),
    mean_speed_ms=("mean_speed_ms", "mean"),
    max_speed_observed_ms=("max_speed_observed_ms", "max"),
    total_halting_count=("halting_count", "sum"),
    mean_occupancy_pct=("occupancy_pct", "mean"),
    mean_gap_m=("mean_gap_m", "mean"),
    min_gap_m=("min_gap_m", "min"),
    mean_rel_velocity_ms=("mean_rel_velocity_ms", "mean"),
    mean_time_gap_s=("mean_time_gap_s", "mean"),
    min_time_gap_s=("min_time_gap_s", "min"),
    mean_acceleration_ms2=("mean_acceleration_ms2", "mean"),
    min_acceleration_ms2=("min_acceleration_ms2", "min"),
    total_hard_brakes=("hard_brake_count", "sum"),
    num_lane_rows=("lane_id", "count")
).reset_index()

node_baseline = node_baseline.rename(columns={"junction_id": "node_id"})
node_baseline.to_csv("node_baseline_from_existing_data.csv", index=False)

print(f"Saved {len(node_baseline)} junction rows to node_baseline_from_existing_data.csv")
print(node_baseline.head())