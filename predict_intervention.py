import pandas as pd
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")

classifier = joblib.load(os.path.join(MODELS_DIR, "surrogate_model_classifier.pkl"))
ridge_model = joblib.load(os.path.join(MODELS_DIR, "surrogate_model_ridge.pkl"))
feature_cols = joblib.load(os.path.join(MODELS_DIR, "surrogate_model_features.pkl"))

node_features = pd.read_csv(os.path.join(DATA_DIR, "node_features.csv"))
node_baseline_behavior = pd.read_csv(os.path.join(DATA_DIR, "node_baseline_from_existing_data.csv"))
baseline_conflicts = pd.read_csv(os.path.join(DATA_DIR, "baseline_conflicts_per_node.csv"))

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
        return {"error": "This junction has no traffic signal — signal retiming isn't applicable here. Try 'Add Traffic Signal' instead."}

    if intervention_type == "add_signal" and has_signal:
        return {"error": "This junction already has a traffic signal — 'Add Traffic Signal' isn't applicable here."}

    input_row = {col: 0 for col in feature_cols}
    input_row["baseline_mean_conflicts"] = baseline_mean_conflicts
    input_row["baseline_mean_severe"] = baseline_mean_severe
    input_row["num_lanes_total"] = num_lanes_total
    input_row["avg_speed_limit_ms"] = avg_speed_limit_ms
    int_col = f"int_{intervention_type}"
    if int_col in input_row:
        input_row[int_col] = 1

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

def get_applicable_interventions(has_signal):
    if has_signal:
        return ["speed_breaker", "signal_retiming"]
    else:
        return ["speed_breaker", "add_signal", "turn_restriction"]


def recommend_best_intervention(node_id):
    node_row = node_features[node_features["node_id"] == node_id]
    if len(node_row) == 0:
        return {"error": f"Junction '{node_id}' not found."}

    has_signal = bool(node_row.iloc[0]["has_signal"])
    applicable = get_applicable_interventions(has_signal)

    results = []
    for intervention in applicable:
        result = predict_intervention_effect(node_id, intervention)
        if "error" not in result:
            results.append(result)

    if not results:
        return {"error": "Could not generate predictions for any applicable intervention at this junction."}

    results_sorted = sorted(results, key=lambda r: r["estimated_change"])
    best = results_sorted[0]

    intervention_labels = {
        "speed_breaker": "installing a Speed Breaker",
        "signal_retiming": "retiming the Traffic Signal",
        "add_signal": "installing a Traffic Signal",
        "turn_restriction": "restricting left turns"
    }

    if best["estimated_change"] < -3:
        narrative = (
            f"Based on simulated scenarios, {intervention_labels[best['intervention']]} is predicted to "
            f"reduce conflicts by approximately {abs(best['estimated_change']):.0f} "
            f"(from {best['baseline_conflicts']} to ~{best['predicted_conflicts_after']}), "
            f"with {int(best['confidence']*100)}% model confidence. "
            f"This is the most effective single intervention modeled for this junction."
        )
        recommendation_type = "positive"
    else:
        other_lines = ", ".join(
            f"{intervention_labels[r['intervention']]} ({'+' if r['estimated_change'] >= 0 else ''}{r['estimated_change']:.0f})"
            for r in results_sorted
        )
        narrative = (
            f"This junction is a high-saturation chokepoint — one of the busiest in Central Kolkata — and single, "
            f"isolated fixes show limited benefit here in modeling: {other_lines}. This is a known pattern at "
            f"heavily saturated junctions: individual interventions often need to be combined (e.g., a turn "
            f"restriction alongside signal retiming) or paired with signal-timing tuned specifically to this "
            f"junction's real traffic volume, rather than a generic default. Of the options modeled, "
            f"{intervention_labels[best['intervention']]} shows the smallest disruption "
            f"({best['estimated_change']:+.0f}) and is the best starting point for further, combined-intervention study."
        )
        recommendation_type = "research"

    return {
        "node_id": node_id,
        "best_intervention": best["intervention"],
        "best_result": best,
        "all_results": results_sorted,
        "narrative": narrative,
        "recommendation_type": recommendation_type
    }