import sumolib
import xml.etree.ElementTree as ET
import subprocess
import os

def get_connected_edges(net, node_id):
    """Return all edge IDs (incoming + outgoing) connected to a junction."""
    node = net.getNode(node_id)
    incoming = node.getIncoming()
    outgoing = node.getOutgoing()
    return {e.getID() for e in incoming + outgoing}


def apply_speed_reduction(net_file, node_id, output_file, reduction_factor=0.8):
    """Speed breaker simulation: reduce speed limit only on INCOMING (approach) edges to this junction."""
    net = sumolib.net.readNet(net_file)
    node = net.getNode(node_id)
    connected_edge_ids = {e.getID() for e in node.getIncoming()}  # incoming only, not outgoing

    tree = ET.parse(net_file)
    root = tree.getroot()
    changed = 0

    for edge_elem in root.findall("edge"):
        if edge_elem.get("id") in connected_edge_ids:
            for lane_elem in edge_elem.findall("lane"):
                current_speed = float(lane_elem.get("speed"))
                lane_elem.set("speed", str(round(current_speed * reduction_factor, 2)))
                changed += 1

    tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"  Applied speed reduction to {changed} lanes across {len(connected_edge_ids)} edges.")
    return output_file


def apply_signal_retiming(net_file, node_id, output_file, green_multiplier=1.3):
    """Signal retiming simulation: extend green phase duration at this junction's traffic light."""
    net = sumolib.net.readNet(net_file)

    # Find the tlLogic ID that actually controls this node
    tls_id_for_node = None
    for tls in net.getTrafficLights():
        controlled_nodes = {conn[0].getEdge().getToNode().getID() for conn in tls.getConnections()}
        if node_id in controlled_nodes or tls.getID() == node_id:
            tls_id_for_node = tls.getID()
            break

    if tls_id_for_node is None:
        print(f"  WARNING: No traffic light found controlling node {node_id}. Copying network unchanged.")
        import shutil
        shutil.copy(net_file, output_file)
        return output_file

    tree = ET.parse(net_file)
    root = tree.getroot()
    changed = 0

    for tl_elem in root.findall("tlLogic"):
        if tl_elem.get("id") == tls_id_for_node:
            for phase in tl_elem.findall("phase"):
                state = phase.get("state")
                if "G" in state or "g" in state:
                    dur = float(phase.get("duration"))
                    phase.set("duration", str(round(dur * green_multiplier, 1)))
                    changed += 1

    tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"  Applied signal retiming to tlLogic '{tls_id_for_node}', {changed} green phases extended.")
    return output_file


def run_scenario(net_file, sumocfg, node_id, intervention_type, scenario_tag):
    """Apply intervention (if any), run simulation, return path to conflict output."""
    if intervention_type == "speed_breaker":
        modified_net = f"temp_net_{scenario_tag}.net.xml"
        apply_speed_reduction(net_file, node_id, modified_net)
    elif intervention_type == "signal_retiming":
        modified_net = f"temp_net_{scenario_tag}.net.xml"
        apply_signal_retiming(net_file, node_id, modified_net)
    elif intervention_type == "none":
        modified_net = net_file
    else:
        raise ValueError(f"Unknown intervention type: {intervention_type}")

    ssm_output = f"ssm_{scenario_tag}.xml"

    cmd = [
        "sumo", "-c", sumocfg,
        "--net-file", modified_net,
        "--device.ssm.probability", "1.0",
        "--device.ssm.file", ssm_output,
        "--device.ssm.measures", "TTC PET DRAC",
        "--device.ssm.thresholds", "3.0 2.0 3.0",
        "--device.ssm.geo", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "90",
        "--max-num-vehicles", "2000"
    ]

    print(f"  Running SUMO for scenario '{scenario_tag}'...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)  # 15 min hard cap
    except subprocess.TimeoutExpired:
        print("  TIMEOUT: scenario exceeded 15 minutes, something is likely gridlocked.")
        return None

    if result.returncode != 0:
        print(f"  ERROR running scenario (return code {result.returncode}):")
        print(f"  STDOUT (last 1000 chars): {result.stdout[-1000:]}")
        print(f"  STDERR (last 1000 chars): {result.stderr[-1000:]}")
        return None

    if result.returncode != 0:
        print(f"  ERROR running scenario: {result.stderr[:500]}")
        return None

    return ssm_output