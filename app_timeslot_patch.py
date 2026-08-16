"""
This is not a standalone script — it's the new/changed pieces to drop into
app.py. See the accompanying message for exactly where each piece goes.
"""

# --- 1. Add near the top, after the existing CSV loads ---

import os

VALID_SLOTS = ["office", "noon", "evening", "midnight"]
TIMESERIES_FILE = "baseline_conflicts_timeseries.csv"
HAS_TIMESERIES = os.path.exists(TIMESERIES_FILE)

if HAS_TIMESERIES:
    timeseries_df = pd.read_csv(TIMESERIES_FILE)
else:
    timeseries_df = None


def get_conflicts_for_slot(slot):
    """
    Returns a dataframe with node_id, lat, lon, total_conflicts, severe_conflicts
    for the requested time slot. Falls back to the original all-day 'merged'
    dataframe if the time-series file hasn't been generated yet, or if the
    slot isn't recognized.
    """
    if not HAS_TIMESERIES or slot not in VALID_SLOTS:
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


# --- 2. Replace the existing /api/heatmap route with this ---

@app.route("/api/heatmap")
def api_heatmap():
    slot = request.args.get("time", "all")  # "all" = original combined behavior
    slot_df = get_conflicts_for_slot(slot)
    heat_rows = slot_df[slot_df["total_conflicts"] > 0][["lat", "lon", "total_conflicts"]]
    return jsonify(heat_rows.values.tolist())


# --- 3. Replace the existing /api/nodes route with this ---

@app.route("/api/nodes")
def api_nodes():
    slot = request.args.get("time", "all")
    slot_df = get_conflicts_for_slot(slot)

    # Bring in the static node attributes (signal, lanes) that don't vary by time
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


# --- 4. New route: tells the frontend which slots are actually available ---

@app.route("/api/time-slots")
def api_time_slots():
    return jsonify({
        "available": HAS_TIMESERIES,
        "slots": VALID_SLOTS if HAS_TIMESERIES else [],
    })
