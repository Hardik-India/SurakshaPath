import sumolib
import subprocess
import math

def get_bounding_box_around_node(net, node_id, radius_m=300):
    """Returns (x1,y1,x2,y2) in SUMO's internal XY coords, a box of radius_m meters around the node."""
    node = net.getNode(node_id)
    x, y = node.getCoord()
    return (x - radius_m, y - radius_m, x + radius_m, y + radius_m)


def crop_network(full_net_file, node_id, output_net_file, radius_m=300):
    net = sumolib.net.readNet(full_net_file)
    x1, y1, x2, y2 = get_bounding_box_around_node(net, node_id, radius_m)
    boundary_str = f"{x1},{y1},{x2},{y2}"

    cmd = [
        "netconvert",
        "--sumo-net-file", full_net_file,
        "-o", output_net_file,
        "--keep-edges.in-boundary", boundary_str,
        "--no-warnings", "true"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  ERROR cropping network: {result.stderr[:500]}")
        return None

    print(f"  Cropped sub-network saved to {output_net_file} (radius {radius_m}m around {node_id})")
    return output_net_file


if __name__ == "__main__":
    import sys
    import pandas as pd
    baseline = pd.read_csv("baseline_conflicts_per_node.csv")
    top_node = baseline.sort_values("total_conflicts", ascending=False).iloc[0]
    test_node_id = top_node["node_id"]

    print(f"Cropping sub-network around: {test_node_id}")
    crop_network("central_kolkata.net.xml", test_node_id, "test_subnet.net.xml", radius_m=300)