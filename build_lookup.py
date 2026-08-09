import sumolib
import pandas as pd

net = sumolib.net.readNet("central_kolkata.net.xml")

tls_rows = []
for tls in net.getTrafficLights():
    tls_id = tls.getID()
    for connection in tls.getConnections():
        in_lane = connection[0]
        tls_rows.append({"lane_id": in_lane.getID(), "edge_id": in_lane.getEdge().getID(), "tls_id": tls_id})
pd.DataFrame(tls_rows).to_csv("lane_signal_lookup.csv", index=False)

geo_rows = []
for edge in net.getEdges():
    for lane in edge.getLanes():
        shape = lane.getShape()
        mid_x, mid_y = shape[len(shape)//2]
        lon, lat = net.convertXY2LonLat(mid_x, mid_y)
        geo_rows.append({
            "lane_id": lane.getID(), "edge_id": edge.getID(),
            "speed_limit_ms": lane.getSpeed(), "lat": lat, "lon": lon
        })
pd.DataFrame(geo_rows).to_csv("lane_geo_lookup.csv", index=False)

print("Lookup tables built.")