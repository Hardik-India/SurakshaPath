import pandas as pd
import folium
from folium.plugins import HeatMap

print("Loading all three tables...")
node_features = pd.read_csv("node_features.csv")
node_baseline = pd.read_csv("node_baseline_from_existing_data.csv")
node_conflicts = pd.read_csv("baseline_conflicts_per_node.csv")

print(f"node_features: {len(node_features)} rows")
print(f"node_baseline: {len(node_baseline)} rows")
print(f"node_conflicts: {len(node_conflicts)} rows")

# Merge: start from features (has every junction), left-join the others
merged = node_features.merge(node_baseline, on="node_id", how="left")
merged = merged.merge(node_conflicts, on="node_id", how="left")

# Junctions with no conflicts recorded = zero, not missing
merged["total_conflicts"] = merged["total_conflicts"].fillna(0)
merged["severe_conflicts"] = merged["severe_conflicts"].fillna(0)

merged.to_csv("node_master_table.csv", index=False)
print(f"\nSaved merged master table: node_master_table.csv ({len(merged)} rows)")

# --- Build the heatmap ---
map_data = merged.dropna(subset=["lat", "lon"])
map_data = map_data[map_data["total_conflicts"] > 0]  # only plot junctions with actual conflict data

print(f"Plotting {len(map_data)} junctions with conflict data on the heatmap...")

center_lat = map_data["lat"].mean()
center_lon = map_data["lon"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles="CartoDB positron")

heat_data = map_data[["lat", "lon", "total_conflicts"]].values.tolist()
HeatMap(heat_data, radius=20, blur=18, max_zoom=17).add_to(m)

top_risk = map_data.sort_values("total_conflicts", ascending=False).head(10)
for _, row in top_risk.iterrows():
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=7,
        color="red",
        fill=True,
        fill_opacity=0.8,
        popup=(f"Junction: {row['node_id']}<br>"
               f"Total conflicts: {int(row['total_conflicts'])}<br>"
               f"Severe conflicts: {int(row['severe_conflicts'])}<br>"
               f"Has signal: {row['has_signal']}")
    ).add_to(m)

m.save("kolkata_risk_heatmap.html")
print("\nHeatmap saved to kolkata_risk_heatmap.html")
print("\nTop 10 highest-risk junctions:")
print(top_risk[["node_id", "total_conflicts", "severe_conflicts", "has_signal"]])