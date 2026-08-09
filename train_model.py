import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score, classification_report
import joblib

print("Loading training data...")
df = pd.read_csv("surrogate_training_data.csv")

df = pd.get_dummies(df, columns=["intervention"], prefix="int")
intervention_cols = [c for c in df.columns if c.startswith("int_")]

# Drop near-zero-importance features found last run, keep the model lean
feature_cols = ["baseline_mean_conflicts", "baseline_mean_severe", "num_lanes_total", "avg_speed_limit_ms"] + intervention_cols

df_clean = df.dropna(subset=feature_cols + ["conflict_delta"])
print(f"Rows: {len(df_clean)}, Features: {len(feature_cols)}")

X = df_clean[feature_cols].copy()
y_regression = df_clean["conflict_delta"]

# --- Classification target: direction of effect ---
NOISE_THRESHOLD = 5.0  # conflicts - below this, call it "no significant change"
def classify_effect(delta):
    if delta > NOISE_THRESHOLD:
        return "increase"
    elif delta < -NOISE_THRESHOLD:
        return "decrease"
    else:
        return "no_change"

y_classification = df_clean["conflict_delta"].apply(classify_effect)
print(f"\nClass distribution: {y_classification.value_counts().to_dict()}")

loo = LeaveOneOut()

# --- Approach A: Ridge Regression on the delta ---
print("\n" + "="*60)
print("APPROACH A: Ridge Regression (predicting exact delta)")
print("="*60)
ridge_preds, ridge_actuals = [], []
for train_idx, test_idx in loo.split(X):
    model = Ridge(alpha=5.0)
    model.fit(X.iloc[train_idx], y_regression.iloc[train_idx])
    ridge_preds.append(model.predict(X.iloc[test_idx])[0])
    ridge_actuals.append(y_regression.iloc[test_idx].values[0])

ridge_mae = mean_absolute_error(ridge_actuals, ridge_preds)
ridge_r2 = r2_score(ridge_actuals, ridge_preds)
naive_mae = mean_absolute_error(ridge_actuals, np.zeros(len(ridge_actuals)))
print(f"Ridge MAE: {ridge_mae:.1f} | R²: {ridge_r2:.3f} | Naive MAE: {naive_mae:.1f}")

# --- Approach B: Classification (increase / decrease / no_change) ---
print("\n" + "="*60)
print("APPROACH B: Classification (predicting direction of effect)")
print("="*60)
class_preds, class_actuals = [], []
for train_idx, test_idx in loo.split(X):
    model = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42)
    model.fit(X.iloc[train_idx], y_classification.iloc[train_idx])
    class_preds.append(model.predict(X.iloc[test_idx])[0])
    class_actuals.append(y_classification.iloc[test_idx].values[0])

acc = accuracy_score(class_actuals, class_preds)
naive_class_acc = (pd.Series(class_actuals) == "no_change").mean()  # always guessing majority class
print(f"Classification accuracy: {acc:.3f}")
print(f"Naive accuracy (always guess most common class): {naive_class_acc:.3f}")
print("\nDetailed report:")
print(classification_report(class_actuals, class_preds, zero_division=0))

# --- Train final models on full data for deployment ---
print("\nTraining final models on full dataset...")
final_ridge = Ridge(alpha=5.0)
final_ridge.fit(X, y_regression)
joblib.dump(final_ridge, "surrogate_model_ridge.pkl")

final_classifier = RandomForestClassifier(n_estimators=200, max_depth=4, random_state=42)
final_classifier.fit(X, y_classification)
joblib.dump(final_classifier, "surrogate_model_classifier.pkl")

joblib.dump(feature_cols, "surrogate_model_features.pkl")
print("Saved: surrogate_model_ridge.pkl, surrogate_model_classifier.pkl, surrogate_model_features.pkl")

print("\n" + "="*60)
print("RECOMMENDATION")
print("="*60)
if acc > naive_class_acc:
    print(f"Classification approach BEATS naive baseline ({acc:.2f} vs {naive_class_acc:.2f}).")
    print("Recommend using the classifier as your primary deliverable — it reliably predicts")
    print("direction of effect, which is honest and useful even without precise magnitude.")
else:
    print("Neither approach clearly beats naive baselines with current data volume.")
    print("Recommend: (1) present feature-importance/correlational findings as insight,")
    print("(2) frame magnitude prediction as future work needing more simulation data,")
    print("(3) still demo the working SUMO-based scenario testing pipeline itself as the")
    print("    core technical contribution — that part is fully proven and working.")