import pandas as pd
import folium
from folium.plugins import HeatMap
from predict_intervention import predict_intervention_effect

node_features = pd.read_csv("node_features.csv")
baseline_conflicts = pd.read_csv("baseline_conflicts_per_node.csv")

merged = node_features.merge(baseline_conflicts, on="node_id", how="left")
merged["total_conflicts"] = merged["total_conflicts"].fillna(0)
map_data = merged.dropna(subset=["lat", "lon"])
map_data = map_data[map_data["total_conflicts"] > 0]

center_lat = map_data["lat"].mean()
center_lon = map_data["lon"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles="CartoDB positron")

heat_data = map_data[["lat", "lon", "total_conflicts"]].values.tolist()
HeatMap(heat_data, radius=20, blur=18, max_zoom=17).add_to(m)

# Get the junctions we actually have batch results for (the ones with trained predictions)
batch_results = pd.read_csv("batch_intervention_results.csv")
tested_junction_ids = batch_results["node_id"].unique().tolist()

print(f"Building prediction popups for {len(tested_junction_ids)} tested junctions...")

for node_id in tested_junction_ids:
    row = map_data[map_data["node_id"] == node_id]
    if len(row) == 0:
        continue
    row = row.iloc[0]

    popup_lines = [
        f"<b>Junction:</b> {node_id[:40]}...",
        f"<b>Baseline conflicts:</b> {int(row['total_conflicts'])}",
        f"<b>Severe conflicts:</b> {int(row['severe_conflicts'])}",
        f"<b>Has signal:</b> {row['has_signal']}",
        "<hr>"
    ]

    for intervention in ["speed_breaker", "signal_retiming"]:
        result = predict_intervention_effect(node_id, intervention)
        if "error" in result:
            popup_lines.append(f"<i>{intervention}: not applicable</i>")
        else:
            effect = result["predicted_effect"]
            conf = result["confidence"]
            color_word = {"increase": "🔴 worse", "decrease": "🟢 better", "no_change": "⚪ no change"}[effect]
            popup_lines.append(f"<b>{intervention}:</b> {color_word} (confidence {conf})")

    popup_html = "<br>".join(popup_lines)

    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=8,
        color="red" if row["total_conflicts"] > map_data["total_conflicts"].median() else "orange",
        fill=True,
        fill_opacity=0.8,
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m)

m.save("kolkata_prediction_heatmap.html")
print("\nSaved: kolkata_prediction_heatmap.html")
print("Open it and click any marker to see baseline risk + predicted intervention effects.")