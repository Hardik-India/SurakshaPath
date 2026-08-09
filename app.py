from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import pandas as pd
from predict_intervention import predict_intervention_effect

app = Flask(__name__)
CORS(app)

node_features = pd.read_csv("node_features.csv")
baseline_conflicts = pd.read_csv("baseline_conflicts_per_node.csv")
batch_results = pd.read_csv("batch_intervention_results.csv")

merged = node_features.merge(baseline_conflicts, on="node_id", how="left")
merged["total_conflicts"] = merged["total_conflicts"].fillna(0)
merged["severe_conflicts"] = merged["severe_conflicts"].fillna(0)

tested_junction_ids = set(batch_results["node_id"].unique())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/heatmap")
def api_heatmap():
    heat_rows = merged[merged["total_conflicts"] > 0][["lat", "lon", "total_conflicts"]]
    return jsonify(heat_rows.values.tolist())


@app.route("/api/nodes")
def api_nodes():
    tested = merged[merged["node_id"].isin(tested_junction_ids)]
    nodes = []
    for _, row in tested.iterrows():
        nodes.append({
            "node_id": row["node_id"],
            "lat": row["lat"],
            "lon": row["lon"],
            "total_conflicts": int(row["total_conflicts"]),
            "severe_conflicts": int(row["severe_conflicts"]),
            "has_signal": bool(row["has_signal"])
        })
    return jsonify(nodes)


@app.route("/api/predict", methods=["POST"])
def api_predict():
    data = request.get_json()
    node_id = data.get("node_id")
    intervention = data.get("intervention")

    if not node_id or not intervention:
        return jsonify({"error": "Missing node_id or intervention"}), 400

    result = predict_intervention_effect(node_id, intervention)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)