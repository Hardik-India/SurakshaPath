from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import os
from predict_intervention import predict_intervention_effect

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

node_features = pd.read_csv(os.path.join(DATA_DIR, "node_features.csv"))
baseline_conflicts = pd.read_csv(os.path.join(DATA_DIR, "baseline_conflicts_per_node.csv"))

merged = node_features.merge(baseline_conflicts, on="node_id", how="left")
merged["total_conflicts"] = merged["total_conflicts"].fillna(0)
merged["severe_conflicts"] = merged["severe_conflicts"].fillna(0)
merged["is_conflict_zone"] = merged["total_conflicts"] > 0

MEDIAN_LANES = node_features["num_lanes_total"].median()

# --- Time-of-day support ---
VALID_SLOTS = ["office", "noon", "evening", "midnight"]
TIMESERIES_FILE = os.path.join(DATA_DIR, "baseline_conflicts_timeseries.csv")
HAS_TIMESERIES = os.path.exists(TIMESERIES_FILE)

if HAS_TIMESERIES:
    timeseries_df = pd.read_csv(TIMESERIES_FILE)
    SLOTS_WITH_DATA = [
        slot for slot in VALID_SLOTS
        if f"total_conflicts_{slot}" in timeseries_df.columns
        and timeseries_df[f"total_conflicts_{slot}"].sum() > 0
    ]
else:
    timeseries_df = None
    SLOTS_WITH_DATA = []


def get_conflicts_for_slot(slot):
    if slot == "all" or not HAS_TIMESERIES or slot not in SLOTS_WITH_DATA:
        return merged[["node_id", "lat", "lon", "total_conflicts", "severe_conflicts"]].copy()

    df = timeseries_df[[
        "node_id", "lat", "lon",
        f"total_conflicts_{slot}", f"severe_conflicts_{slot}"
    ]].copy()
    df = df.rename(columns={
        f"total_conflicts_{slot}": "total_conflicts",
        f"severe_conflicts_{slot}": "severe_conflicts",
    })
    return df


def build_reason(row):
    reasons = []
    if row["num_lanes_total"] <= MEDIAN_LANES:
        reasons.append(f"only {int(row['num_lanes_total'])} connected lane(s), at or below the area's median of {int(MEDIAN_LANES)}")
    if row["has_signal"]:
        reasons.append("movements here are signal-regulated, which separates conflicting traffic in time")
    else:
        reasons.append("this junction did not register any close-proximity vehicle interactions during simulation")

    if not reasons:
        reasons.append("simulated traffic volume here was too low to generate measurable conflicts")

    return "No vehicle conflicts were detected here during simulation. Likely reasons: " + "; ".join(reasons) + "."


def severity_tier(total_conflicts):
    if total_conflicts <= 0:
        return "none"
    elif total_conflicts < 60:
        return "low"
    elif total_conflicts <= 150:
        return "moderate"
    else:
        return "high"


@app.route("/")
def index():
    return jsonify({"status": "SurakshaPath API running"})


@app.route("/api/heatmap")
def api_heatmap():
    slot = request.args.get("time", "all")
    slot_df = get_conflicts_for_slot(slot)
    heat_rows = slot_df[slot_df["total_conflicts"] > 0][["lat", "lon", "total_conflicts"]]
    return jsonify(heat_rows.values.tolist())


@app.route("/api/nodes")
def api_nodes():
    slot = request.args.get("time", "all")
    slot_df = get_conflicts_for_slot(slot)

    full = slot_df.merge(
        node_features[["node_id", "has_signal", "num_lanes_total"]],
        on="node_id", how="left"
    )
    full["is_conflict_zone"] = full["total_conflicts"] > 0
    valid = full.dropna(subset=["lat", "lon"])

    nodes = []
    for _, row in valid.iterrows():
        is_zone = bool(row["is_conflict_zone"])
        entry = {
            "node_id": row["node_id"],
            "lat": row["lat"],
            "lon": row["lon"],
            "total_conflicts": int(row["total_conflicts"]),
            "severe_conflicts": int(row["severe_conflicts"]),
            "has_signal": bool(row["has_signal"]),
            "num_lanes_total": int(row["num_lanes_total"]),
            "is_conflict_zone": is_zone,
            "severity_tier": severity_tier(row["total_conflicts"]),
            "time_slot": slot,
        }
        if not is_zone:
            entry["reason"] = build_reason(row)
        nodes.append(entry)
    return jsonify(nodes)


@app.route("/api/time-slots")
def api_time_slots():
    return jsonify({
        "available": len(SLOTS_WITH_DATA) > 0,
        "slots": SLOTS_WITH_DATA,
    })


@app.route("/api/predict", methods=["POST"])
def api_predict():
    data = request.get_json()
    node_id = data.get("node_id")
    intervention = data.get("intervention")

    if not node_id or not intervention:
        return jsonify({"error": "Missing node_id or intervention"}), 400

    result = predict_intervention_effect(node_id, intervention)
    return jsonify(result)


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    data = request.get_json()
    node_id = data.get("node_id")

    if not node_id:
        return jsonify({"error": "Missing node_id"}), 400

    from predict_intervention import recommend_best_intervention
    result = recommend_best_intervention(node_id)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)