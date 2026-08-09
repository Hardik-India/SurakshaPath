import pandas as pd
import joblib

classifier = joblib.load("surrogate_model_classifier.pkl")
ridge_model = joblib.load("surrogate_model_ridge.pkl")
feature_cols = joblib.load("surrogate_model_features.pkl")

node_features = pd.read_csv("node_features.csv")
node_baseline_behavior = pd.read_csv("node_baseline_from_existing_data.csv")
baseline_conflicts = pd.read_csv("baseline_conflicts_per_node.csv")


def predict_intervention_effect(node_id, intervention_type):
    node_row = node_features[node_features["node_id"] == node_id]
    conflict_row = baseline_conflicts[baseline_conflicts["node_id"] == node_id]

    if len(node_row) == 0:
        return {"error": f"Junction '{node_id}' not found."}
    if len(conflict_row) == 0:
        return {"error": f"Junction '{node_id}' has no recorded baseline data (never simulated)."}

    baseline_mean_conflicts = float(conflict_row.iloc[0]["total_conflicts"])
    baseline_mean_severe = float(conflict_row.iloc[0]["severe_conflicts"])
    num_lanes_total = node_row.iloc[0]["num_lanes_total"]
    avg_speed_limit_ms = node_row.iloc[0]["avg_speed_limit_ms"]
    has_signal = bool(node_row.iloc[0]["has_signal"])

    if intervention_type == "signal_retiming" and not has_signal:
        return {"error": f"This junction has no traffic signal — signal retiming isn't applicable here."}

    if intervention_type == "other":
        return {
            "error": None,
            "not_modeled": True,
            "message": "Custom/other interventions aren't included in the trained model yet. "
                       "This would need a new SUMO simulation batch to generate training data for it. "
                       "Try Speed Breaker or Traffic Signal Retiming for a data-backed prediction."
        }

    input_row = {
        "baseline_mean_conflicts": baseline_mean_conflicts,
        "baseline_mean_severe": baseline_mean_severe,
        "num_lanes_total": num_lanes_total,
        "avg_speed_limit_ms": avg_speed_limit_ms,
        "int_none": 1 if intervention_type == "none" else 0,
        "int_signal_retiming": 1 if intervention_type == "signal_retiming" else 0,
        "int_speed_breaker": 1 if intervention_type == "speed_breaker" else 0,
    }

    X_input = pd.DataFrame([input_row])[feature_cols]

    predicted_class = classifier.predict(X_input)[0]
    probabilities = dict(zip(classifier.classes_, classifier.predict_proba(X_input)[0]))
    confidence = float(probabilities[predicted_class])

    estimated_delta = float(ridge_model.predict(X_input)[0])
    predicted_absolute = round(baseline_mean_conflicts + estimated_delta)

    return {
        "node_id": node_id,
        "intervention": intervention_type,
        "baseline_conflicts": int(baseline_mean_conflicts),
        "baseline_severe_conflicts": int(baseline_mean_severe),
        "predicted_effect": predicted_class,
        "confidence": round(confidence, 2),
        "estimated_change": round(estimated_delta, 1),
        "predicted_conflicts_after": predicted_absolute,
        "all_probabilities": {k: round(float(v), 2) for k, v in probabilities.items()},
        "has_signal": has_signal
    }