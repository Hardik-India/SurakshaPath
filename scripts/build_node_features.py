import sumolib
import pandas as pd

print("Loading network...")
net = sumolib.net.readNet("central_kolkata.net.xml")

rows = []
nodes = net.getNodes()
print(f"Found {len(nodes)} nodes/junctions. Extracting features...")

for node in nodes:
    node_id = node.getID()
    node_type = node.getType()          # traffic_light, priority, right_before_left, etc.
    has_signal = (node_type == "traffic_light")

    incoming = node.getIncoming()
    outgoing = node.getOutgoing()
    connected_edges = incoming + outgoing

    all_lanes = []
    for edge in connected_edges:
        all_lanes.extend(edge.getLanes())

    num_lanes_total = len(all_lanes)
    num_connected_edges = len(connected_edges)

    if all_lanes:
        avg_speed_limit_ms = sum(l.getSpeed() for l in all_lanes) / len(all_lanes)
    else:
        avg_speed_limit_ms = 0.0

    x, y = node.getCoord()
    try:
        lon, lat = net.convertXY2LonLat(x, y)
    except Exception:
        lon, lat = None, None

    rows.append({
        "node_id": node_id,
        "node_type": node_type,
        "has_signal": has_signal,
        "num_lanes_total": num_lanes_total,
        "num_connected_edges": num_connected_edges,
        "avg_speed_limit_ms": round(avg_speed_limit_ms, 2),
        "lat": lat,
        "lon": lon
    })

df = pd.DataFrame(rows)
df.to_csv("node_features.csv", index=False)

print(f"Saved {len(df)} node rows to node_features.csv")
print(f"Junctions with signals: {df['has_signal'].sum()}")
print(df.head())